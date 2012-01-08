# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import datetime
import gzip
import logging
import operator
import os
import random
import json
import struct
import shutil
import subprocess
import time
import threading

from bsddb import db as bdb

from gi.repository import GObject
from gi.repository import Gio

# py3 compat
try:
    import cPickle as pickle
    pickle # pyflakes
except ImportError:
    import pickle

# py3 compat
try:
    from io import StringIO
    StringIO # pyflakes
    from urllib.parse import quote_plus
    quote_plus # pyflakes
except ImportError:
    from StringIO import StringIO
    from urllib import quote_plus

from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.backend.piston.rnrclient_pristine import ReviewDetails
from softwarecenter.db.categories import CategoriesParser
from softwarecenter.db.database import Application, StoreDatabase
import softwarecenter.distro
from softwarecenter.utils import (upstream_version_compare,
                                  uri_to_filename,
                                  get_language,
                                  save_person_to_config,
                                  get_person_from_config,
                                  calc_dr,
                                  wilson_score,
                                  utf8,
                                  )
from softwarecenter.paths import (SOFTWARE_CENTER_CACHE_DIR,
                                  APP_INSTALL_PATH,
                                  XAPIAN_BASE_PATH,
                                  RNRApps,
                                  PistonHelpers,
                                  )
#from softwarecenter.enums import *

from softwarecenter.netstatus import network_state_is_connected

from spawn_helper import SpawnHelper

LOG = logging.getLogger(__name__)

class ReviewStats(object):
    def __init__(self, app):
        self.app = app
        self.ratings_average = None
        self.ratings_total = 0
        self.rating_spread = [0,0,0,0,0]
        self.dampened_rating = 3.00
    def __repr__(self):
        return ("<ReviewStats '%s' ratings_average='%s' ratings_total='%s'" 
                " rating_spread='%s' dampened_rating='%s'>" % 
                (self.app, self.ratings_average, self.ratings_total, 
                self.rating_spread, self.dampened_rating))
    

class UsefulnessCache(object):

    USEFULNESS_CACHE = {}
    
    def __init__(self, try_server=False):
        self.rnrclient = RatingsAndReviewsAPI()
        fname = "usefulness.p"
        self.USEFULNESS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                    fname)
        
        self._retrieve_votes_from_cache()
        #Only try to get votes from the server if required, otherwise just use cache
        if try_server:
            self._retrieve_votes_from_server()
    
    def _retrieve_votes_from_cache(self):
        if os.path.exists(self.USEFULNESS_CACHE_FILE):
            try:
                self.USEFULNESS_CACHE = pickle.load(open(self.USEFULNESS_CACHE_FILE))
            except:
                LOG.exception("usefulness cache load fallback failure")
                os.rename(self.USEFULNESS_CACHE_FILE, self.USEFULNESS_CACHE_FILE+".fail")
        return
    
    def _retrieve_votes_from_server(self):
        LOG.debug("_retrieve_votes_from_server started")
        user = get_person_from_config()
        
        if not user:
            LOG.warn("Could not get usefulness from server, no username in config file")
            return False
        
        # run the command and add watcher
        cmd = [os.path.join(
                softwarecenter.paths.datadir, PistonHelpers.GET_USEFUL_VOTES),
               "--username", user, 
              ]
        spawn_helper = SpawnHelper()
        spawn_helper.connect("data-available", self._on_usefulness_data)
        spawn_helper.run(cmd)

    def _on_usefulness_data(self, spawn_helper, results):
        '''called if usefulness retrieved from server'''
        LOG.debug("_usefulness_loaded started")
        self.USEFULNESS_CACHE.clear()
        for result in results:
            self.USEFULNESS_CACHE[str(result['review_id'])] = result['useful']
        if not self.save_usefulness_cache_file():
            LOG.warn("Read usefulness results from server but failed to write to cache")
    
    def save_usefulness_cache_file(self):
        """write the dict out to cache file"""
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        try:
            if not os.path.exists(cachedir):
                os.makedirs(cachedir)
            pickle.dump(self.USEFULNESS_CACHE,
                      open(self.USEFULNESS_CACHE_FILE, "w"))
            return True
        except:
            return False
    
    def add_usefulness_vote(self, review_id, useful):
        """pass a review id and useful boolean vote and save it into the dict, then try to save to cache file"""
        self.USEFULNESS_CACHE[str(review_id)] = useful
        if self.save_usefulness_cache_file():
            return True
        return False
    
    def check_for_usefulness(self, review_id):
        """pass a review id and get a True/False useful back or None if the review_id is not in the dict"""
        return self.USEFULNESS_CACHE.get(str(review_id))
    
    

class Review(object):
    """A individual review object """
    def __init__(self, app):
        # a softwarecenter.db.database.Application object
        self.app = app
        self.app_name = app.appname
        self.package_name = app.pkgname
        # the review items that the object fills in
        self.id = None
        self.language = None
        self.summary = ""
        self.review_text = ""
        self.package_version = None
        self.date_created = None
        self.rating = None
        self.reviewer_username = None
        self.reviewer_displayname = None
        self.version = ""
        self.usefulness_total = 0
        self.usefulness_favorable = 0
        # this will be set if tryint to submit usefulness for this review failed
        self.usefulness_submit_error = False
        self.delete_error = False
        self.modify_error = False
    def __repr__(self):
        return "[Review id=%s review_text='%s' reviewer_username='%s']" % (
            self.id, self.review_text, self.reviewer_username)
    def __cmp__(self, other):
        # first compare version, high version number first
        vc = upstream_version_compare(self.version, other.version)
        if vc != 0:
            return vc
        # then wilson score
        uc = cmp(wilson_score(self.usefulness_favorable, 
                              self.usefulness_total),
                 wilson_score(other.usefulness_favorable,
                              other.usefulness_total))
        if uc != 0:
            return uc
        # last is date
        t1 = datetime.datetime.strptime(self.date_created, '%Y-%m-%d %H:%M:%S')
        t2 = datetime.datetime.strptime(other.date_created, '%Y-%m-%d %H:%M:%S')
        return cmp(t1, t2)
        
    @classmethod
    def from_piston_mini_client(cls, other):
        """ converts the rnrclieent reviews we get into
            "our" Review object (we need this as we have more
            attributes then the rnrclient review object)
        """
        app = Application("", other.package_name)
        review = cls(app)
        for (attr, value) in other.__dict__.items():
            if not attr.startswith("_"):
                setattr(review, attr, value)
        return review

    @classmethod
    def from_json(cls, other):
        """ convert json reviews into "out" review objects """
        app = Application("", other["package_name"])
        review = cls(app)
        for k, v in other.items():
            setattr(review, k, v)
        return review

class ReviewLoader(object):
    """A loader that returns a review object list"""

    # cache the ReviewStats
    REVIEW_STATS_CACHE = {}
    _cache_version_old = False

    def __init__(self, cache, db, distro=None):
        self.cache = cache
        self.db = db
        self.distro = distro
        if not self.distro:
            self.distro = softwarecenter.distro.get_distro()
        fname = "%s_%s" % (uri_to_filename(self.distro.REVIEWS_SERVER),
                           "review-stats-pkgnames.p")
        self.REVIEW_STATS_CACHE_FILE = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                                    fname)
        self.REVIEW_STATS_BSDDB_FILE = "%s__%s.%s.db" % (
            self.REVIEW_STATS_CACHE_FILE, 
            bdb.DB_VERSION_MAJOR, 
            bdb.DB_VERSION_MINOR)

        self.language = get_language()
        if os.path.exists(self.REVIEW_STATS_CACHE_FILE):
            try:
                self.REVIEW_STATS_CACHE = pickle.load(open(self.REVIEW_STATS_CACHE_FILE))
                self._cache_version_old = self._missing_histogram_in_cache()
            except:
                LOG.exception("review stats cache load failure")
                os.rename(self.REVIEW_STATS_CACHE_FILE, self.REVIEW_STATS_CACHE_FILE+".fail")
    
    def _missing_histogram_in_cache(self):
        '''iterate through review stats to see if it has been fully reloaded
           with new histogram data from server update'''
        for app in self.REVIEW_STATS_CACHE.values():
            result = getattr(app, 'rating_spread', False)
            if not result:
                return True
        return False

    def get_reviews(self, application, callback, page=1, language=None):
        """run callback f(app, review_list) 
           with list of review objects for the given
           db.database.Application object
        """
        return []

    def update_review_stats(self, translated_application, stats):
        application = Application("", translated_application.pkgname)
        self.REVIEW_STATS_CACHE[application] = stats

    def get_review_stats(self, translated_application):
        """return a ReviewStats (number of reviews, rating)
           for a given application. this *must* be super-fast
           as it is called a lot during tree view display
        """
        # check cache
        try:
            application = Application("", translated_application.pkgname)
            if application in self.REVIEW_STATS_CACHE:
                return self.REVIEW_STATS_CACHE[application]
        except ValueError:
            pass
        return None

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        pass

    def save_review_stats_cache_file(self, nonblocking=True):
        """ save review stats cache file in xdg cache dir """
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        # write out the stats
        if nonblocking:
            t = threading.Thread(target=self._save_review_stats_cache_blocking)
            t.run()
        else:
            self._save_review_stats_cache_blocking()

    def _save_review_stats_cache_blocking(self):
        # dump out for software-center in simple pickle
        self._dump_pickle_for_sc()
        # dump out in c-friendly dbm format for unity
        try:
            outfile = self.REVIEW_STATS_BSDDB_FILE
            outdir = self.REVIEW_STATS_BSDDB_FILE + ".dbenv/"
            self._dump_bsddbm_for_unity(outfile, outdir)
        except bdb.DBError as e:
            # see bug #858437, db corruption seems to be rather common
            # on ecryptfs
            LOG.warn("error creating bsddb: '%s' (corrupted?)" % e)
            try:
                shutil.rmtree(outdir)
                self._dump_bsddbm_for_unity(outfile, outdir)
            except:
                LOG.exception("trying to repair DB failed")

    def _dump_pickle_for_sc(self):
        """ write out the full REVIEWS_STATS_CACHE as a pickle """
        pickle.dump(self.REVIEW_STATS_CACHE,
                      open(self.REVIEW_STATS_CACHE_FILE, "w"))
                                       
    def _dump_bsddbm_for_unity(self, outfile, outdir):
        """ write out the subset that unity needs of the REVIEW_STATS_CACHE
            as a C friendly (using struct) bsddb
        """
        env = bdb.DBEnv()
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        env.open (outdir,
                  bdb.DB_CREATE | bdb.DB_INIT_CDB | bdb.DB_INIT_MPOOL |
                  bdb.DB_NOMMAP, # be gentle on e.g. nfs mounts
                  0600)
        db = bdb.DB (env)
        db.open (outfile,
                 dbtype=bdb.DB_HASH,
                 mode=0600,
                 flags=bdb.DB_CREATE)
        for (app, stats) in self.REVIEW_STATS_CACHE.iteritems():
            # pkgname is ascii by policy, so its fine to use str() here
            db[str(app.pkgname)] = struct.pack('iii', 
                                               stats.ratings_average or 0,
                                               stats.ratings_total,
                                               stats.dampened_rating)
        db.close ()
        env.close ()
    
    def get_top_rated_apps(self, quantity=12, category=None):
        """Returns a list of the packages with the highest 'rating' based on
           the dampened rating calculated from the ReviewStats rating spread.
           Also optionally takes a category (string) to filter by"""

        cache = self.REVIEW_STATS_CACHE
        
        if category:
            applist = self._get_apps_for_category(category)
            cache = self._filter_cache_with_applist(cache, applist)
        
        #create a list of tuples with (Application,dampened_rating)
        dr_list = []
        for item in cache.items():
            if hasattr(item[1],'dampened_rating'):
                dr_list.append((item[0], item[1].dampened_rating))
            else:
                dr_list.append((item[0], 3.00))
        
        #sorted the list descending by dampened rating
        sorted_dr_list = sorted(dr_list, key=operator.itemgetter(1),
                                reverse=True)
        
        #return the quantity requested or as much as we can
        if quantity < len(sorted_dr_list):
            return_qty = quantity
        else:
            return_qty = len(sorted_dr_list)
        
        top_rated = []
        for i in range (0,return_qty):
            top_rated.append(sorted_dr_list[i][0])
        
        return top_rated
    
    def _filter_cache_with_applist(self, cache, applist):
        """Take the review cache and filter it to only include the apps that
           also appear in the applist passed in"""
        filtered_cache = {}
        for key in cache.keys():
            if key.pkgname in applist:
                filtered_cache[key] = cache[key]
        
        return filtered_cache
        
    def _get_query_for_category(self, category):
        cat_parser = CategoriesParser(self.db)
        categories = cat_parser.parse_applications_menu(APP_INSTALL_PATH)
        for c in categories:
            if category == c.untranslated_name:
                query = c.query
                return query
        return False
    
    def _get_apps_for_category(self, category):
        query = self._get_query_for_category(category)
        if not query:
            LOG.warn("_get_apps_for_category: received invalid category")
            return []
        
        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        db = StoreDatabase(pathname, self.cache)
        db.open()
        docs = db.get_docs_from_query(query)
        
        #from the db docs, return a list of pkgnames
        applist = []
        for doc in docs:
            applist.append(db.get_pkgname(doc))
        return applist

    # writing new reviews spawns external helper
    # FIXME: instead of the callback we should add proper gobject signals
    def spawn_write_new_review_ui(self, translated_app, version, iconname, 
                                  origin, parent_xid, datadir, callback):
        """ this spawns the UI for writing a new review and
            adds it automatically to the reviews DB """
        app = translated_app.get_untranslated_app(self.db)
        cmd = [os.path.join(datadir, RNRApps.SUBMIT_REVIEW), 
               "--pkgname", app.pkgname,
               "--iconname", iconname,
               "--parent-xid", "%s" % parent_xid,
               "--version", version,
               "--origin", origin,
               "--datadir", datadir,
               ]
        if app.appname:
            # needs to be (utf8 encoded) str, otherwise call fails
            cmd += ["--appname", utf8(app.appname)]
        spawn_helper = SpawnHelper(format="json")
        spawn_helper.connect(
            "data-available", self._on_submit_review_data, app, callback)
        spawn_helper.run(cmd)

    def _on_submit_review_data(self, spawn_helper, review_json, app, callback):
        """ called when submit_review finished, when the review was send
            successfully the callback is triggered with the new reviews
        """
        LOG.debug("_on_submit_review_data")
        # read stdout from submit_review
        review = ReviewDetails.from_dict(review_json)
        # FIXME: ideally this would be stored in ubuntu-sso-client
        #        but it dosn't so we store it here
        save_person_to_config(review.reviewer_username)
        if not app in self._reviews: 
            self._reviews[app] = []
        self._reviews[app].insert(0, Review.from_piston_mini_client(review))
        callback(app, self._reviews[app])

    def spawn_report_abuse_ui(self, review_id, parent_xid, datadir, callback):
        """ this spawns the UI for reporting a review as inappropriate
            and adds the review-id to the internal hide list. once the
            operation is complete it will call callback with the updated
            review list
        """
        cmd = [os.path.join(datadir, RNRApps.REPORT_REVIEW), 
               "--review-id", review_id,
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper("json")
        spawn_helper.connect("exited", 
                             self._on_report_abuse_finished, 
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_report_abuse_finished(self, spawn_helper, exitcode, review_id, callback):
        """ called when report_absuse finished """
        LOG.debug("hide id %s " % review_id)
        if exitcode == 0:
            for (app, reviews) in self._reviews.items():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        # remove the one we don't want to see anymore
                        self._reviews[app].remove(review)
                        callback(app, self._reviews[app], None, 'remove', review)
                        break


    def spawn_submit_usefulness_ui(self, review_id, is_useful, parent_xid, datadir, callback):
        cmd = [os.path.join(datadir, RNRApps.SUBMIT_USEFULNESS), 
               "--review-id", "%s" % review_id,
               "--is-useful", "%s" % int(is_useful),
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper(format="none")
        spawn_helper.connect("exited", 
                             self._on_submit_usefulness_finished, 
                             review_id, is_useful, callback)
        spawn_helper.connect("error",
                             self._on_submit_usefulness_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_submit_usefulness_finished(self, spawn_helper, res, review_id, is_useful, callback):
        """ called when report_usefulness finished """
        # "Created", "Updated", "Not modified" - 
        # once lp:~mvo/rnr-server/submit-usefulness-result-strings makes it
        response = spawn_helper._stdout
        if response == '"Not modified"':
            self._on_submit_usefulness_error(spawn_helper, response, review_id, callback)
            return

        LOG.debug("usefulness id %s " % review_id)
        useful_votes = UsefulnessCache()
        useful_votes.add_usefulness_vote(review_id, is_useful)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # update usefulness, older servers do not send
                    # usefulness_{total,favorable} so we use getattr
                    review.usefulness_total = getattr(review, "usefulness_total", 0) + 1
                    if is_useful:
                        review.usefulness_favorable = getattr(review, "usefulness_favorable", 0) + 1
                        callback(app, self._reviews[app], useful_votes, 'replace', review)
                        break

    def _on_submit_usefulness_error(self, spawn_helper, error_str, review_id, callback):
            LOG.warn("submit usefulness id=%s failed with error: %s" %
                     (review_id, error_str))
            for (app, reviews) in self._reviews.items():
                for review in reviews:
                    if str(review.id) == str(review_id):
                        review.usefulness_submit_error = True
                        callback(app, self._reviews[app], None, 'replace', review)
                        break

    def spawn_delete_review_ui(self, review_id, parent_xid, datadir, callback):
        cmd = [os.path.join(datadir, RNRApps.DELETE_REVIEW), 
               "--review-id", "%s" % review_id,
               "--parent-xid", "%s" % parent_xid,
               "--datadir", datadir,
              ]
        spawn_helper = SpawnHelper(format="none")
        spawn_helper.connect("exited", 
                             self._on_delete_review_finished, 
                             review_id, callback)
        spawn_helper.connect("error", self._on_delete_review_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_delete_review_finished(self, spawn_helper, res, review_id, callback):
        """ called when delete_review finished"""
        LOG.debug("delete id %s " % review_id)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # remove the one we don't want to see anymore
                    self._reviews[app].remove(review)
                    callback(app, self._reviews[app], None, 'remove', review)
                    break                    

    def _on_delete_review_error(self, spawn_helper, error_str, review_id, callback):
        """called if delete review errors"""
        LOG.warn("delete review id=%s failed with error: %s" % (review_id, error_str))
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    review.delete_error = True
                    callback(app, self._reviews[app], action='replace', 
                             single_review=review)
                    break

    
    def spawn_modify_review_ui(self, parent_xid, iconname, datadir, review_id, callback):
        """ this spawns the UI for writing a new review and
            adds it automatically to the reviews DB """
        cmd = [os.path.join(datadir, RNRApps.MODIFY_REVIEW), 
               "--parent-xid", "%s" % parent_xid,
               "--iconname", iconname,
               "--datadir", "%s" % datadir,
               "--review-id", "%s" % review_id,
               ]
        spawn_helper = SpawnHelper(format="json")
        spawn_helper.connect("data-available", 
                             self._on_modify_review_finished, 
                             review_id, callback)
        spawn_helper.connect("error", self._on_modify_review_error,
                             review_id, callback)
        spawn_helper.run(cmd)

    def _on_modify_review_finished(self, spawn_helper, review_json, review_id, callback):
        """called when modify_review finished"""
        LOG.debug("_on_modify_review_finished")
        #review_json = spawn_helper._stdout
        mod_review = ReviewDetails.from_dict(review_json)
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    # remove the one we don't want to see anymore
                    self._reviews[app].remove(review)
                    new_review = Review.from_piston_mini_client(mod_review)
                    self._reviews[app].insert(0, new_review)
                    callback(app, self._reviews[app], action='replace', 
                             single_review=new_review)
                    break
                    
    def _on_modify_review_error(self, spawn_helper, error_str, review_id, callback):
        """called if modify review errors"""
        LOG.debug("modify review id=%s failed with error: %s" % (review_id, error_str))
        for (app, reviews) in self._reviews.items():
            for review in reviews:
                if str(review.id) == str(review_id):
                    review.modify_error = True
                    callback(app, self._reviews[app], action='replace', 
                             single_review=review)
                    break


# this code had several incernations: 
# - python threads, slow and full of latency (GIL)
# - python multiprocesing, crashed when accessibility was turned on, 
#                          does not work in the quest session (#743020)
# - GObject.spawn_async() looks good so far (using the SpawnHelper code)
class ReviewLoaderSpawningRNRClient(ReviewLoader):
    """ loader that uses multiprocessing to call rnrclient and
        a glib timeout watcher that polls periodically for the
        data 
    """

    def __init__(self, cache, db, distro=None):
        super(ReviewLoaderSpawningRNRClient, self).__init__(cache, db, distro)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        self._reviews = {}

    def _update_rnrclient_offline_state(self):
        # this needs the lp:~mvo/piston-mini-client/offline-mode branch
        self.rnrclient._offline_mode = not network_state_is_connected()

    # reviews
    def get_reviews(self, translated_app, callback, page=1, language=None):
        """ public api, triggers fetching a review and calls callback
            when its ready
        """
        # its fine to use the translated appname here, we only submit the
        # pkgname to the server
        app = translated_app
        self._update_rnrclient_offline_state()
        if language is None:
            language = self.language
        # gather args for the helper
        try:
            origin = self.cache.get_origin(app.pkgname)
        except:
            # this can happen if e.g. the app has multiple origins, this
            # will be handled later
            origin = None
        # special case for not-enabled PPAs
        if not origin and self.db:
            details = app.get_details(self.db)
            ppa = details.ppaname
            if ppa:
                origin = "lp-ppa-%s" % ppa.replace("/", "-")
        # if there is no origin, there is nothing to do
        if not origin:
            callback(app, [])
            return
        distroseries = self.distro.get_codename()
        # run the command and add watcher
        cmd = [os.path.join(softwarecenter.paths.datadir, PistonHelpers.GET_REVIEWS),
               "--language", language, 
               "--origin", origin, 
               "--distroseries", distroseries, 
               "--pkgname", str(app.pkgname), # ensure its str, not unicode
               "--page", str(page),
              ]
        spawn_helper = SpawnHelper()
        spawn_helper.connect(
            "data-available", self._on_reviews_helper_data, app, callback)
        spawn_helper.run(cmd)

    def _on_reviews_helper_data(self, spawn_helper, piston_reviews, app, callback):
        # convert into our review objects
        reviews = []
        for r in piston_reviews:
            reviews.append(Review.from_piston_mini_client(r))
        # add to our dicts and run callback
        self._reviews[app] = reviews
        callback(app, self._reviews[app])
        return False

    # stats
    def refresh_review_stats(self, callback):
        """ public api, refresh the available statistics """
        try:
            mtime = os.path.getmtime(self.REVIEW_STATS_CACHE_FILE)
            days_delta = int((time.time() - mtime) // (24*60*60))
            days_delta += 1
        except OSError:
            days_delta = 0
        LOG.debug("refresh with days_delta: %s" % days_delta)
        #origin = "any"
        #distroseries = self.distro.get_codename()
        cmd = [os.path.join(
                softwarecenter.paths.datadir, PistonHelpers.GET_REVIEW_STATS),
               # FIXME: the server currently has bug (#757695) so we
               #        can not turn this on just yet and need to use
               #        the old "catch-all" review-stats for now
               #"--origin", origin, 
               #"--distroseries", distroseries, 
              ]
        if days_delta:
            cmd += ["--days-delta", str(days_delta)]
        spawn_helper = SpawnHelper()
        spawn_helper.connect("data-available", self._on_review_stats_data, callback)
        spawn_helper.run(cmd)

    def _on_review_stats_data(self, spawn_helper, piston_review_stats, callback):
        """ process stdout from the helper """
        review_stats = self.REVIEW_STATS_CACHE

        if self._cache_version_old and self._server_has_histogram(piston_review_stats):
            self.REVIEW_STATS_CACHE = {}
            self.save_review_stats_cache_file()
            self.refresh_review_stats(callback)
            return
        
        # convert to the format that s-c uses
        for r in piston_review_stats:
            s = ReviewStats(Application("", r.package_name))
            s.ratings_average = float(r.ratings_average)
            s.ratings_total = float(r.ratings_total)
            if r.histogram:
                s.rating_spread = json.loads(r.histogram)
            else:
                s.rating_spread = [0,0,0,0,0]
            s.dampened_rating = calc_dr(s.rating_spread)
            review_stats[s.app] = s
        self.REVIEW_STATS_CACHE = review_stats
        callback(review_stats)
        self.save_review_stats_cache_file()
    
    def _server_has_histogram(self, piston_review_stats):
        '''check response from server to see if histogram is supported'''
        supported = getattr(piston_review_stats[0], "histogram", False)
        if not supported:
            return False
        return True

class ReviewLoaderJsonAsync(ReviewLoader):
    """ get json (or gzip compressed json) """

    def _gio_review_download_complete_callback(self, source, result):
        app = source.get_data("app")
        callback = source.get_data("callback")
        try:
            (success, json_str, etag) = source.load_contents_finish(result)
        except GObject.GError:
            # ignore read errors, most likely transient
            return callback(app, [])
        # check for gzip header
        if json_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO(json_str))
            json_str = gz.read()
        reviews_json = json.loads(json_str)
        reviews = []
        for review_json in reviews_json:
            review = Review.from_json(review_json)
            reviews.append(review)
        # run callback
        callback(app, reviews)

    def get_reviews(self, app, callback, page=1, language=None):
        """ get a specific review and call callback when its available"""
        # FIXME: get this from the app details
        origin = self.cache.get_origin(app.pkgname)
        distroseries = self.distro.get_codename()
        if app.appname:
            appname = ";"+app.appname
        else:
            appname = ""
        url = self.distro.REVIEWS_URL % { 'pkgname' : app.pkgname,
                                          'appname' : quote_plus(appname.encode("utf-8")),
                                          'language' : self.language,
                                          'origin' : origin,
                                          'distroseries' : distroseries,
                                          'version' : 'any',
                                         }
        LOG.debug("looking for review at '%s'" % url)
        f=Gio.File.new_for_uri(url)
        f.set_data("app", app)
        f.set_data("callback", callback)
        f.load_contents_async(self._gio_review_download_complete_callback)

    # review stats code
    def _gio_review_stats_download_finished_callback(self, source, result):
        callback = source.get_data("callback")
        try:
            (json_str, length, etag) = source.load_contents_finish(result)
        except GObject.GError:
            # ignore read errors, most likely transient
            return
        # check for gzip header
        if json_str.startswith("\37\213"):
            gz=gzip.GzipFile(fileobj=StringIO(json_str))
            json_str = gz.read()
        review_stats_json = json.loads(json_str)
        review_stats = {}
        for review_stat_json in review_stats_json:
            #appname = review_stat_json["app_name"]
            pkgname = review_stat_json["package_name"]
            app = Application('', pkgname)
            stats = ReviewStats(app)
            stats.ratings_total = int(review_stat_json["ratings_total"])
            stats.ratings_average = float(review_stat_json["ratings_average"])
            review_stats[app] = stats
        # update review_stats dict
        self.REVIEW_STATS_CACHE = review_stats
        self.save_review_stats_cache_file()
        # run callback
        callback(review_stats)

    def refresh_review_stats(self, callback):
        """ get the review statists and call callback when its there """
        f=Gio.File(self.distro.REVIEW_STATS_URL)
        f.set_data("callback", callback)
        f.load_contents_async(self._gio_review_stats_download_finished_callback)

class ReviewLoaderFake(ReviewLoader):

    USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", "Bar Tender", "Baz Lightyear"]
    SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
    IPSUM = "no ipsum\n\nstill no ipsum"

    def __init__(self, cache, db):
        self._review_stats_cache = {}
        self._reviews_cache = {}
    def _random_person(self):
        return random.choice(self.USERS)
    def _random_text(self):
        return random.choice(self.LOREM.split("\n\n"))
    def _random_summary(self):
        return random.choice(self.SUMMARIES)
    def get_reviews(self, application, callback, page=1, language=None):
        if not application in self._review_stats_cache:
            self.get_review_stats(application)
        stats = self._review_stats_cache[application]
        if not application in self._reviews_cache:
            reviews = []
            for i in range(0, stats.ratings_total):
                review = Review(application)
                review.id = random.randint(1,50000)
                # FIXME: instead of random, try to match the avg_rating
                review.rating = random.randint(1,5)
                review.summary = self._random_summary()
                review.date_created = time.strftime("%Y-%m-%d %H:%M:%S")
                review.reviewer_username = self._random_person()
                review.review_text = self._random_text().replace("\n","")
                review.usefulness_total = random.randint(1, 20)
                review.usefulness_favorable = random.randint(1, 20)
                reviews.append(review)
            self._reviews_cache[application] = reviews
        reviews = self._reviews_cache[application]
        callback(application, reviews)
    def get_review_stats(self, application):
        if not application in self._review_stats_cache:
            stat = ReviewStats(application)
            stat.ratings_average = random.randint(1,5)
            stat.ratings_total = random.randint(1,20)
            self._review_stats_cache[application] = stat
        return self._review_stats_cache[application]
    def refresh_review_stats(self, callback):
        review_stats = []
        callback(review_stats)

class ReviewLoaderFortune(ReviewLoaderFake):
    def __init__(self, cache, db):
        ReviewLoaderFake.__init__(self, cache, db)
        self.LOREM = ""
        for i in range(10):
            out = subprocess.Popen(["fortune"], stdout=subprocess.PIPE).communicate()[0]
            self.LOREM += "\n\n%s" % out

class ReviewLoaderTechspeak(ReviewLoaderFake):
    """ a test review loader that does not do any network io
        and returns random review texts
    """
    LOREM=u"""This package is using cloud based technology that will
make it suitable in a distributed environment where soup and xml-rpc
are used. The backend is written in C++ but the frontend code will
utilize dynamic languages lika LUA to provide a execution environment
based on JIT technology.

The software in this packages has a wonderful GUI, its based on OpenGL
but can alternative use DirectX (on plattforms were it is
available). Dynamic shading utilizes all GPU cores and out-of-order
thread scheduling is used to visualize the data optimally on multi
core systems.

The database support in tthis application is bleding edge. Not only
classical SQL techniques are supported but also object-relational
models and advanced ORM technology that will do auto-lookups based on
dynamic join/select optimizations to leverage sharded or multihosted
databases to their peak performance.

The Enterprise computer system is controlled by three primary main
processing cores cross linked with a redundant melacortz ramistat and
fourteen kiloquad interface modules. The core elements are based on
FTL nanoprocessor units arranged into twenty-five bilateral
kelilactirals with twenty of those units being slaved to the central
heisenfram terminal. . . . Now this is the isopalavial interface which
controls the main firomactal drive unit. . . .  The ramistat kiloquad
capacity is a function of the square root of the intermix ratio times
the sum of the plasma injector quotient.

The iApp is using the new touch UI that feels more natural then
tranditional window based offerings. It supports a Job button that
will yell at you when pressed and a iAmCool mode where the logo of
your new device blinks so that you attract maximum attention.

This app is a lifestyle choice.
It sets you apart from those who are content with bland UI designed
around 1990's paradigms.  This app represents you as a dynamic trend
setter with taste.  The carefully controlled user interface is
perfectly tailored to the needs of a new age individual, and extreme
care has been taken to ensure that all buttons are large enough for even the
most robust digits.

Designed with the web 2.0 and touch screen portable technologies in
mind this app is the ultimate in media experience.  With this
lifestyle application you extend your social media and search reach.
Exciting innovations in display and video reinvigorates the user
experience, offering beautifully rendered advertisements straight to
your finger tips. This has limitless possibilities and will permeate
every facet of your life.  Believe the hype."""

class ReviewLoaderIpsum(ReviewLoaderFake):
    """ a test review loader that does not do any network io
        and returns random lorem ipsum review texts
    """
    #This text is under public domain
    #Lorem ipsum
    #Cicero
    LOREM=u"""lorem ipsum "dolor" äöü sit amet consetetur sadipscing elitr sed diam nonumy
eirmod tempor invidunt ut labore et dolore magna aliquyam erat sed diam
voluptua at vero eos et accusam et justo duo dolores et ea rebum stet clita
kasd gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem
ipsum dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod
tempor invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at
vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis at vero eros
et accumsan et iusto odio dignissim qui blandit praesent luptatum zzril
delenit augue duis dolore te feugait nulla facilisi lorem ipsum dolor sit
amet consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat

ut wisi enim ad minim veniam quis nostrud exerci tation ullamcorper suscipit
lobortis nisl ut aliquip ex ea commodo consequat duis autem vel eum iriure
dolor in hendrerit in vulputate velit esse molestie consequat vel illum
dolore eu feugiat nulla facilisis at vero eros et accumsan et iusto odio
dignissim qui blandit praesent luptatum zzril delenit augue duis dolore te
feugait nulla facilisi

nam liber tempor cum soluta nobis eleifend option congue nihil imperdiet
doming id quod mazim placerat facer possim assum lorem ipsum dolor sit amet
consectetuer adipiscing elit sed diam nonummy nibh euismod tincidunt ut
laoreet dolore magna aliquam erat volutpat ut wisi enim ad minim veniam quis
nostrud exerci tation ullamcorper suscipit lobortis nisl ut aliquip ex ea
commodo consequat

duis autem vel eum iriure dolor in hendrerit in vulputate velit esse
molestie consequat vel illum dolore eu feugiat nulla facilisis

at vero eos et accusam et justo duo dolores et ea rebum stet clita kasd
gubergren no sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum
dolor sit amet consetetur sadipscing elitr sed diam nonumy eirmod tempor
invidunt ut labore et dolore magna aliquyam erat sed diam voluptua at vero
eos et accusam et justo duo dolores et ea rebum stet clita kasd gubergren no
sea takimata sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit
amet consetetur sadipscing elitr at accusam aliquyam diam diam dolore
dolores duo eirmod eos erat et nonumy sed tempor et et invidunt justo labore
stet clita ea et gubergren kasd magna no rebum sanctus sea sed takimata ut
vero voluptua est lorem ipsum dolor sit amet lorem ipsum dolor sit amet
consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat

consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore
et dolore magna aliquyam erat sed diam voluptua at vero eos et accusam et
justo duo dolores et ea rebum stet clita kasd gubergren no sea takimata
sanctus est lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur
sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore
magna aliquyam erat sed diam voluptua at vero eos et accusam et justo duo
dolores et ea rebum stet clita kasd gubergren no sea takimata sanctus est
lorem ipsum dolor sit amet lorem ipsum dolor sit amet consetetur sadipscing
elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore magna
aliquyam erat sed diam voluptua at vero eos et accusam et justo duo dolores
et ea rebum stet clita kasd gubergren no sea takimata sanctus est lorem
ipsum dolor sit amet"""

review_loader = None
def get_review_loader(cache, db=None):
    """ 
    factory that returns a reviews loader singelton
    """
    global review_loader
    if not review_loader:
        if "SOFTWARE_CENTER_IPSUM_REVIEWS" in os.environ:
            review_loader = ReviewLoaderIpsum(cache, db)
        elif "SOFTWARE_CENTER_FORTUNE_REVIEWS" in os.environ:
            review_loader = ReviewLoaderFortune(cache, db)
        elif "SOFTWARE_CENTER_TECHSPEAK_REVIEWS" in os.environ:
            review_loader = ReviewLoaderTechspeak(cache, db)
        elif "SOFTWARE_CENTER_GIO_REVIEWS" in os.environ:
            review_loader = ReviewLoaderJsonAsync(cache, db)
        else:
            review_loader = ReviewLoaderSpawningRNRClient(cache, db)
    return review_loader

if __name__ == "__main__":
    def callback(app, reviews):
        print "app callback:"
        print app, reviews
    def stats_callback(stats):
        print "stats callback:"
        print stats

    # cache
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    db = StoreDatabase(XAPIAN_BASE_PATH+"/xapian", cache)
    db.open()

    # rnrclient loader
    app = Application("ACE", "unace")
    #app = Application("", "2vcard")

    loader = ReviewLoaderSpawningRNRClient(cache, db)
    print loader.refresh_review_stats(stats_callback)
    print loader.get_reviews(app, callback)

    print "\n\n"
    print "default loader, press ctrl-c for next loader"
    context = GObject.main_context_default()
    main = GObject.MainLoop(context)
    main.run()

    # default loader
    app = Application("","2vcard")
    loader = get_review_loader(cache, db)
    loader.refresh_review_stats(stats_callback)
    loader.get_reviews(app, callback)
    main.run()
