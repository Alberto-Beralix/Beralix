# -*- coding: utf-8 -*-
# Copyright (C) 2009,2010 Canonical
#
# Authors:
#  Michael Vogt, Matthew McGowan
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

from gi.repository import GObject
from gi.repository import Gtk, GdkPixbuf
import logging
import os

from gettext import gettext as _

from softwarecenter.enums import (Icons, 
                                  XapianValues)


from softwarecenter.utils import ExecutionTime, SimpleFileDownloader
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.database import Application
from softwarecenter.distro import get_distro
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR

import softwarecenter.paths
from softwarecenter.db.categories import (
    category_subcat, category_cat, CategoriesParser)

# global cache icons to speed up rendering
_app_icon_cache = {}


LOG = logging.getLogger(__name__)

class CategoryRowReference:
    """ A simple container for Category properties to be 
        displayed in a AppListStore or AppTreeStore
    """

    def __init__(self, untranslated_name, display_name, subcats, pkg_count):
        self.untranslated_name = untranslated_name
        self.display_name = GObject.markup_escape_text(display_name)
        #self.subcategories = subcats
        self.pkg_count = pkg_count
        self.vis_count = pkg_count
        return


class UncategorisedRowRef(CategoryRowReference):

    def __init__(self, untranslated_name=None, display_name=None, pkg_count=0):
        if untranslated_name is None:
            untranslated_name = 'Uncategorised'
        if display_name is None:
            display_name = _("Uncategorized")

        CategoryRowReference.__init__(self,
                                      untranslated_name,
                                      display_name,
                                      None, pkg_count)
        return


class _AppPropertiesHelper(object):
    """ Baseclass that contains common functions for our
        liststore/treestore, only useful for subclassing
    """

    def _download_icon_and_show_when_ready(self, cache, pkgname, icon_file_name):
        LOG.debug("did not find the icon locally, must download %s" % icon_file_name)

        def on_image_download_complete(downloader, image_file_path):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_file_path,
                                                      self.icon_size,
                                                      self.icon_size)
            # replace the icon in the icon_cache now that we've got the real one
            icon_file = os.path.splitext(os.path.basename(image_file_path))[0]
            self.icon_cache[icon_file] = pb
        
        url = get_distro().get_downloadable_icon_url(cache, pkgname, icon_file_name)
        if url is not None:
            icon_file_path = os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR, icon_file_name)
            image_downloader = SimpleFileDownloader()
            image_downloader.connect('file-download-complete', on_image_download_complete)
            image_downloader.download_file(url, icon_file_path)

    def update_availability(self, doc):
        doc.available = None
        doc.installed = None
        self.is_installed(doc)
        return

    def is_available(self, doc):
        if doc.available is None:
            pkgname = self.get_pkgname(doc)
            doc.available = pkgname in self.cache
        return doc.available

    def is_installed(self, doc):
        if doc.installed is None:
            pkgname = self.get_pkgname(doc)
            if doc.available is None:
                doc.available = pkgname in self.cache
            doc.installed = doc.available and self.cache[pkgname].is_installed
        return doc.installed

    def get_pkgname(self, doc):
        return self.db.get_pkgname(doc)

    def get_application(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)
        pkgname = self.db.get_pkgname(doc)
        # TODO: requests
        return Application(appname, pkgname, "")

    def get_appname(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)
        if not appname:
            appname = self.db.get_summary(doc)
        else:
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, self.get_pkgname(doc))
        return appname

    def get_markup(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)

        if not appname:
            appname = self.db.get_summary(doc)
            summary = self.get_pkgname(doc)
        else:
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, self.get_pkgname(doc))

            summary = self.db.get_summary(doc)

        return "%s\n<small>%s</small>" % (
                 GObject.markup_escape_text(appname),
                 GObject.markup_escape_text(summary))

    def get_icon(self, doc):
        try:
            icon_file_name = self.db.get_iconname(doc)
            if icon_file_name:
                icon_name = os.path.splitext(icon_file_name)[0]
                if icon_name in self.icon_cache:
                    return self.icon_cache[icon_name]
                # icons.load_icon takes between 0.001 to 0.01s on my
                # machine, this is a significant burden because get_value
                # is called *a lot*. caching is the only option
                
                # look for the icon on the iconpath
                if self.icons.has_icon(icon_name):
                    icon = self.icons.load_icon(icon_name, self.icon_size, 0)
                    if icon:
                        self.icon_cache[icon_name] = icon
                        return icon
                #~ elif self.db.get_icon_needs_download(doc):
                    #~ self._download_icon_and_show_when_ready(
                        #~ self.cache, 
                        #~ self.get_pkgname(doc),
                        #~ icon_file_name)
                    #~ # display the missing icon while the real one downloads
                    #~ self.icon_cache[icon_name] = self._missing_icon
        except GObject.GError as e:
            LOG.debug("get_icon returned '%s'" % e)
        return self._missing_icon

    def get_review_stats(self, doc):
        return self.review_loader.get_review_stats(self.get_application(doc))

    def get_transaction_progress(self, doc):
        pkgname = self.get_pkgname(doc)
        if pkgname in self.backend.pending_transactions:
            return self.backend.pending_transactions[pkgname].progress
        return -1

    def _category_translate(self, catname):
        """ helper that will look into the categories we got from the 
            parser and returns the translated name if it find it,
            otherwise it resorts to plain gettext
        """
        # look into parsed categories that use .directory translation 
        for cat in self.all_categories:
            if cat.untranslated_name == catname:
                return cat.name
        # else just use plain gettext
        return _(catname)

    def get_categories(self, doc):
        categories = doc.get_value(XapianValues.CATEGORIES).split(';') or []
        if categories and categories[0] == 'SC_CATEGORY':
            return _(categories[-1])
        for key in category_subcat:
            if key in categories:
                visible_category = category_subcat[key].split(';')[1]
                return self._category_translate(visible_category)
        for key in category_cat:
            if key in categories:
                visible_category = category_cat[key]
                return self._category_translate(visible_category)
        if categories:
            return _('System')
        else:
            return ''

class AppPropertiesHelper(_AppPropertiesHelper):

    def __init__(self, db, cache, icons, icon_size=48, global_icon_cache=False):
        self.db = db
        self.cache = cache

        cat_parser = CategoriesParser(db)
        self.all_categories = cat_parser.parse_applications_menu(
            softwarecenter.paths.APP_INSTALL_PATH)

        # reviews stats loader
        self.review_loader = get_review_loader(cache, db)

        # icon jazz
        self.icons = icons
        self.icon_size = icon_size
        # cache the 'missing icon' used in the treeview for apps without an icon
        self._missing_icon = icons.load_icon(Icons.MISSING_APP,
                                             icon_size, 0)

        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}
        return

    def get_icon_at_size(self, doc, width, height):
        pixbuf = self.get_icon(doc)
        pixbuf = pixbuf.scale_simple(width, height,
                                     GdkPixbuf.InterpType.BILINEAR)
        return pixbuf

    def get_transaction_progress(self, doc):
        raise NotImplemented


class AppGenericStore(_AppPropertiesHelper):

    # column types
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    # column id
    COL_ROW_DATA = 0

    # default icon size displayed in the treeview
    ICON_SIZE = 32

    # the amount of items to initially lo
    LOAD_INITIAL   = 75

    def __init__(self, db, cache, icons, icon_size, global_icon_cache):
        # the usual suspects
        self.db = db
        self.cache = cache

        # reviews stats loader
        self.review_loader = get_review_loader(cache, db)

        # backend stuff
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)

        # keep track of paths for transactions in progress
        self.transaction_path_map = {}

        # icon jazz
        self.icons = icons
        self.icon_size = icon_size

        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}

        # active row path
        self.active_row = None

        # cache the 'missing icon' used in the treeview for apps without an icon
        self._missing_icon = icons.load_icon(Icons.MISSING_APP, icon_size, 0)

        self._in_progress = False
        self._break = False

        # other stuff
        self.active = False
        return

    # FIXME: port from 
    @property
    def installable_apps(self):
        return []
    @property
    def existing_apps(self):
        return []

    def notify_action_request(self, doc, path):
        pkgname = str(self.get_pkgname(doc))
        self.transaction_path_map[pkgname] = (path, self.get_iter(path))
        return

    def set_from_matches(self, matches):
        # stub
        raise NotImplementedError

    # the following methods ensure that the contents data is refreshed
    # whenever a transaction potentially changes it: 
    def _on_transaction_started(self, backend, pkgname, appname, trans_id, trans_type):
        #~ self._refresh_transaction_map()
        pass

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if pkgname in self.transaction_path_map:
            path, it = self.transaction_path_map[pkgname]
            self.row_changed(path, it)
        return

    def _on_transaction_finished(self, backend, result):
        pkgname = str(result.pkgname)
        if pkgname in self.transaction_path_map:
            path, it = self.transaction_path_map[pkgname]
            doc = self.get_value(it, self.COL_ROW_DATA)
            self.update_availability(doc)
            self.row_changed(path, it)
            del self.transaction_path_map[pkgname]

    def buffer_icons(self):

        def buffer_icons():
            #~ print "Buffering icons ..."
            #t0 = GObject.get_current_time()
            if self.current_matches is None:
                return False
            db = self.db.xapiandb
            for m in self.current_matches:
                doc = db.get_document(m.docid)

                # calling get_icon is enough to cache the icon
                self.get_icon(doc)

                while Gtk.events_pending():
                    Gtk.main_iteration()

            #~ import sys
            #~ t_lapsed = round(GObject.get_current_time() - t0, 3)
            #~ print "Appstore buffered icons in %s seconds" % t_lapsed
            #from softwarecenter.utils import get_nice_size
            #~ cache_size = get_nice_size(sys.getsizeof(_app_icon_cache))
            #~ print "Number of icons in cache: %s consuming: %sb" % (len(_app_icon_cache), cache_size)
            return False    # remove from sources on completion

        if self.current_matches is not None:
            GObject.idle_add(buffer_icons)
        return

class AppListStore(Gtk.ListStore, AppGenericStore):
    """ use for flat applist views. for large lists this appends rows approx
        three times faster than the AppTreeStore equivalent
    """

    from gi.repository import GObject

    __gsignals__ = {
        "appcount-changed" : (GObject.SignalFlags.RUN_LAST,
                              None, 
                              (GObject.TYPE_PYOBJECT, ),
                             ),
        }

    def __init__(self, db, cache, icons, icon_size=AppGenericStore.ICON_SIZE, 
                 global_icon_cache=True):
        AppGenericStore.__init__(
            self, db, cache, icons, icon_size, global_icon_cache)
        Gtk.ListStore.__init__(self)
        self.set_column_types(self.COL_TYPES)

        self.current_matches = None
        return


    def set_from_matches(self, matches):
        """ set the content of the liststore based on a list of
            xapian.MSetItems
        """
        self.current_matches = matches
        n_matches = len(matches)
        if n_matches == 0: 
            return
    
        extent = min(self.LOAD_INITIAL, n_matches)

        with ExecutionTime("store.append_initial"):
            for doc in [m.document for m in matches][:extent]:
                doc.available = doc.installed = None
                self.append((doc,))

        if n_matches == extent: 
            return

        with ExecutionTime("store.append_placeholders"):
            for i in range(n_matches - extent):
                self.append()

        self.emit('appcount-changed', len(matches))
        self.buffer_icons()
        return

    def load_range(self, indices, step):
        db = self.db.xapiandb
        matches = self.current_matches

        n_matches = len(matches)

        start = indices[0]
        end = start + step

        if end >= n_matches:
            end = n_matches

        for i in range(start, end):
            if self[(i,)][0]: continue
            doc = db.get_document(matches[i].docid)
            doc.available = doc.installed = None
            self[(i,)][0] = doc
        return

    def clear(self):
        # reset the tranaction map because it will now be invalid
        self.transaction_path_map = {}
        self.current_matches = None
        Gtk.ListStore.clear(self)
        return


class AppTreeStore(Gtk.TreeStore, AppGenericStore):
    """ A treestore based application model
    """

    def __init__(self, db, cache, icons, icon_size=AppGenericStore.ICON_SIZE, 
                 global_icon_cache=True):
        AppGenericStore.__init__(
            self, db, cache, icons, icon_size, global_icon_cache)
        Gtk.TreeStore.__init__(self)
        self.set_column_types(self.COL_TYPES)
        return

    def set_documents(self, parent, documents):
        for doc in documents:
            doc.available = None; doc.installed = None
            self.append(parent, (doc,))

        self.transaction_path_map = {}
        return

    def set_category_documents(self, cat, documents):
        category = CategoryRowReference(cat.untranslated_name,
                                        cat.name,
                                        cat.subcategories,
                                        len(documents))

        it = self.append(None, (category,))
        self.set_documents(it, documents)
        return it

    def set_nocategory_documents(self, documents, untranslated_name=None, display_name=None):
        category = UncategorisedRowRef(untranslated_name,
                                       display_name,
                                       len(documents))
        it = self.append(None, (category,))
        self.set_documents(it, documents)
        return it

    def clear(self):
        # reset the tranaction map because it will now be invalid
        self.transaction_path_map = {}
        Gtk.TreeStore.clear(self)
        return
