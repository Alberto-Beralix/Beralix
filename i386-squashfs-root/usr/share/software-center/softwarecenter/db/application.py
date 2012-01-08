# Copyright (C) 2010 Canonical
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

import locale
import logging
import os
import re

from gettext import gettext as _
from softwarecenter.backend.channel import is_channel_available
from softwarecenter.distro import get_distro
from softwarecenter.enums import PkgStates, XapianValues, Icons

from softwarecenter.paths import (APP_INSTALL_CHANNELS_PATH,
                                  SOFTWARE_CENTER_ICON_CACHE_DIR,
                                  )
from softwarecenter.utils import utf8

LOG = logging.getLogger(__name__)

# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """ The central software item abstraction. it contains a 
        pkgname that is always available and a optional appname
        for packages with multiple applications
        
        There is also a __cmp__ method and a name property
    """
    def __init__(self, appname="", pkgname="", request="", popcon=0):
        if not (appname or pkgname):
            raise ValueError("Need either appname or pkgname or request")
        # defaults
        self.pkgname = pkgname.replace("$kernel", os.uname()[2])
        if appname:
            self.appname = utf8(appname)
        else:
            self.appname = ''
        # the request can take additional "request" data like apturl
        # strings or the path of a local deb package
        self.request = request
        self._popcon = popcon
        # a "?" in the name means its a apturl request
        if "?" in pkgname:
            # the bit before the "?" is the pkgname, everything else the req
            (self.pkgname, sep, self.request) = pkgname.partition("?")

    @property
    def name(self):
        """Show user visible name"""
        if self.appname:
            return self.appname
        return self.pkgname
    @property
    def popcon(self):
        return self._popcon
    # get a AppDetails object for this Applications
    def get_details(self, db):
        """ return a new AppDetails object for this application """
        return AppDetails(db, application=self)

    def get_untranslated_app(self, db):
        """ return a Application object with the untranslated application
            name 
        """
        try:
            doc = db.get_xapian_document(self.appname, self.pkgname)
        except IndexError:
            return self
        untranslated_application = doc.get_value(XapianValues.APPNAME_UNTRANSLATED)
        uapp = Application(untranslated_application, self.pkgname)
        return uapp

    @staticmethod
    def get_display_name(db, doc):
        """ Return the application name as it should be displayed in the UI
            If the appname is defined, just return it, else return
            the summary (per the spec)
        """
        if doc:
            appname = db.get_appname(doc)
            if appname:
                return appname
            else:
                return db.get_summary(doc)
    @staticmethod
    def get_display_summary(db, doc):
        """ Return the application summary as it should be displayed in the UI
            If the appname is defined, return the application summary, else return
            the application's pkgname (per the spec)
        """
        if doc:
            if db.get_appname(doc):
                return db.get_summary(doc)
            else:
                return db.get_pkgname(doc)
        
    # special methods
    def __hash__(self):
        return ("%s:%s" % (self.appname, self.pkgname)).__hash__()
    def __cmp__(self, other):
        return self.apps_cmp(self, other)
    def __str__(self):
        return unicode("%s,%s", 'utf8').encode('utf8') % (self.appname, self.pkgname)
    def __repr__(self):
        return "[Application: appname=%s pkgname=%s]" % (self.appname, self.pkgname)
    @staticmethod
    def apps_cmp(x, y):
        """ sort method for the applications """
        # sort(key=locale.strxfrm) would be more efficient, but its
        # currently broken, see http://bugs.python.org/issue2481
        if x.appname and y.appname:
            return locale.strcoll(x.appname, y.appname)
        elif x.appname:
            return locale.strcoll(x.appname, y.pkgname)
        elif y.appname:
            return locale.strcoll(x.pkgname, y.appname)
        else:
            return cmp(x.pkgname, y.pkgname)

# the details
class AppDetails(object):
    """ The details for a Application. This contains all the information
        we have available like website etc
    """

    def __init__(self, db, doc=None, application=None):
        """ Create a new AppDetails object. It can be created from
            a xapian.Document or from a db.application.Application object
        """
        if not doc and not application:
            raise ValueError("Need either document or application")
        self._db = db
        self._db.connect("reopen", self._on_db_reopen)
        self._cache = self._db._aptcache
        self._distro = get_distro()
        self._history = None
        # import here (intead of global) to avoid dbus dependency
        # in update-software-center (that imports application, but
        # never uses AppDetails) LP: #620011
        from softwarecenter.backend import get_install_backend
        self._backend = get_install_backend()
        # FIXME: why two error states ?
        self._error = None
        self._error_not_found = None

        # load application
        self._app = application
        if doc:
            self._app = Application(self._db.get_appname(doc), 
                                    self._db.get_pkgname(doc), 
                                    "")

        # sustitute for apturl
        if self._app.request:
            self._app.request = self._app.request.replace(
                "$distro", self._distro.get_codename())

        # load pkg cache
        self._pkg = None
        if (self._app.pkgname in self._cache and 
            self._cache[self._app.pkgname].candidate):
            self._pkg = self._cache[self._app.pkgname]

        # load xapian document
        self._doc = doc
        if not self._doc:
            try:
                self._doc = self._db.get_xapian_document(
                    self._app.appname, self._app.pkgname)
            except IndexError:
                # if there is no document and no apturl request,
                # set error state
                debfile_matches = re.findall(r'/', self._app.request)
                channel_matches = re.findall(r'channel=[a-z,-]*', 
                                             self._app.request)
                section_matches = re.findall(r'section=[a-z]*', 
                                             self._app.request)
                if (not self._pkg and 
                    not debfile_matches and 
                    not channel_matches and 
                    not section_matches):
                    self._error = _("Not found")
                    self._error_not_found = utf8(_(u"There isn\u2019t a software package called \u201c%s\u201D in your current software sources.")) % utf8(self.pkgname)

    def same_app(self, other):
        return self.pkgname == other.pkgname

    def _on_db_reopen(self, db):
        if self._doc:
            try:
                LOG.debug("db-reopen, refreshing docid for %s" % self._app)
                self._doc = self._db.get_xapian_document(
                    self._app.appname, self._app.pkgname)
            except IndexError:
                LOG.warn("document no longer valid after db reopen")
                self._doc = None

    @property
    def channelname(self):
        if self._doc:
            channel = self._doc.get_value(XapianValues.ARCHIVE_CHANNEL)
            path = APP_INSTALL_CHANNELS_PATH + channel + ".list"
            if os.path.exists(path):
                return channel
        else:
            # check if we have an apturl request to enable a channel
            channel_matches = re.findall(r'channel=([0-9a-z,-]*)', self._app.request)
            if channel_matches:
                channel = channel_matches[0]
                channelfile = APP_INSTALL_CHANNELS_PATH + channel + ".list"
                if os.path.exists(channelfile):
                    return channel

    @property
    def channelfile(self):
        channel = self.channelname
        if channel:
            return APP_INSTALL_CHANNELS_PATH + channel + ".list"

    @property
    def eulafile(self):
        channel = self.channelname
        if channel:
            eulafile =  APP_INSTALL_CHANNELS_PATH + channel + ".eula"
            if os.path.exists(eulafile):
                return eulafile

    @property
    def component(self):
        """ 
        get the component (main, universe, ..)
        
        this uses the data from apt, if there is none it uses the 
        data from the app-install-data files
        """
        # try apt first
        if self._pkg:
            for origin in self._pkg.candidate.origins:
                if (origin.origin == "Ubuntu" and origin.trusted and origin.component):
                    return origin.component
        # then xapian
        elif self._doc:
            comp = self._doc.get_value(XapianValues.ARCHIVE_SECTION)
            return comp
        # then apturl requests
        else:
            section_matches = re.findall(r'section=([a-z]+)', self._app.request)
            if section_matches:
                valid_section_matches = []
                for section_match in section_matches:
                    if self._unavailable_component(component_to_check=section_match) and valid_section_matches.count(section_match) == 0:
                        valid_section_matches.append(section_match)
                if valid_section_matches:
                    return ('&').join(valid_section_matches)

    @property
    def desktop_file(self):
        if self._doc:
            return self._doc.get_value(XapianValues.DESKTOP_FILE)

    @property
    def description(self):
        if self._pkg:
            return self._pkg.candidate.description
        elif self._doc:
            if self._doc.get_value(XapianValues.SC_DESCRIPTION):
                return self._doc.get_value(XapianValues.SC_DESCRIPTION)
        # if its in need-source state and we have a eula, display it
        # as the description
        if self.pkg_state == PkgStates.NEEDS_SOURCE and self.eulafile:
            return open(self.eulafile).read()
        return ""

    @property
    def error(self):
        if self._error_not_found:
            return self._error_not_found
        elif self._error:
            return self._error
        # this may have changed since we inited the appdetails
        elif self.pkg_state == PkgStates.NOT_FOUND:
            self._error =  _("Not found")
            self._error_not_found = utf8(_(u"There isn\u2019t a software package called \u201c%s\u201D in your current software sources.")) % utf8(self.pkgname)
            return self._error_not_found

    @property
    def icon(self):
        if self.pkg_state == PkgStates.NOT_FOUND:
            return Icons.MISSING_PKG
        if self._doc:
            return os.path.splitext(self._db.get_iconname(self._doc))[0]
        if not self.summary:
            return Icons.MISSING_PKG
            
    @property
    def icon_file_name(self):
        if self._doc:
            return self._db.get_iconname(self._doc)
    
    @property
    def icon_url(self):
        if self._doc:
            return self._db.get_icon_download_url(self._doc)

    @property
    def cached_icon_file_path(self):
        if self._doc:
            return os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR, self._db.get_iconname(self._doc))

    @property
    def installation_date(self):
        from softwarecenter.db.history import get_pkg_history
        self._history = get_pkg_history()
        return self._history.get_installed_date(self.pkgname)
        
    @property
    def purchase_date(self):
        if self._doc:
            return self._doc.get_value(XapianValues.PURCHASED_DATE)

    @property
    def license(self):
        xapian_license = None
        if self._doc:
            xapian_license = self._doc.get_value(XapianValues.LICENSE)
        if xapian_license:
            # try to i18n this, the server side does not yet support
            # translations, but fortunately for the most common ones
            # like "Properitary" we have translations in s-c
            return _(xapian_license)
        else:
            return self._distro.get_license_text(self.component)

    @property
    def maintenance_status(self):
        return self._distro.get_maintenance_status(
            self._cache, self.display_name, self.pkgname, self.component, 
            self.channelname)

    @property
    def name(self):
        """ Return the name of the application, this will always
            return Application.name. Most UI will want to use
            the property display_name instead
        """
        return self._app.name
    
    @property
    def display_name(self):
        """ Return the application name as it should be displayed in the UI
            If the appname is defined, just return it, else return
            the summary (per the spec)
        """
        if self._error_not_found:
            return self._error
        if self._doc:
            return Application.get_display_name(self._db, self._doc)
        return self.name

    @property
    def display_summary(self):
        """ Return the application summary as it should be displayed in the UI
            If the appname is defined, return the application summary, else return
            the application's pkgname (per the spec)
        """
        if self._doc:
            return Application.get_display_summary(self._db, self._doc)
        return ""

    @property
    def pkg(self):
        if self._pkg:
            return self._pkg

    @property
    def pkgname(self):
        return self._app.pkgname

    @property
    def pkg_state(self):
        # puchase state
        if self.pkgname in self._backend.pending_purchases:
            return PkgStates.INSTALLING_PURCHASED

        # via the pending transactions dict
        if self.pkgname in self._backend.pending_transactions:
            # FIXME: we don't handle upgrades yet
            # if there is no self._pkg yet, that means this is a INSTALL
            # from a previously not-enabled source (like a purchase)
            if self._pkg and self._pkg.installed:
                return PkgStates.REMOVING
            else:
                return PkgStates.INSTALLING

        # if we have _pkg that means its either:
        # - available for download (via sources.list)
        # - locally installed
        # - intalled and available for download
        if self._pkg:
            # Don't handle upgrades yet
            #if self._pkg.installed and self._pkg._isUpgradable:
            #    return PkgStates.UPGRADABLE
            if self._pkg.is_installed:
                return PkgStates.INSTALLED
            else:
                return PkgStates.UNINSTALLED
        # if we don't have a _pkg, then its either:
        #  - its in a unavailable repo
        #  - the repository information is outdated
        #  - the repository information is missing (/var/lib/apt/lists empty)
        #  - its a failure in our meta-data (e.g. typo in the pkgname in
        #    the metadata)
        if not self._pkg:
            if self.channelname:
                if self._unavailable_channel():
                    return PkgStates.NEEDS_SOURCE
                else:
                    self._error =  _("Not found")
                    self._error_not_found = utf8(_(u"There isn\u2019t a software package called \u201c%s\u201D in your current software sources.")) % utf8(self.pkgname)
                    return PkgStates.NOT_FOUND
            else:
                if self.price:
                    return PkgStates.NEEDS_PURCHASE
                if (self.purchase_date and
                    self._doc.get_value(XapianValues.ARCHIVE_DEB_LINE)):
                    return PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED
                if self.component:
                    components = self.component.split('&')
                    for component in components:
                        if component and self._unavailable_component(component_to_check=component):
                            return PkgStates.NEEDS_SOURCE
                self._error =  _("Not found")
                self._error_not_found = utf8(_(u"There isn\u2019t a software package called \u201c%s\u201D in your current software sources.")) % utf8(self.pkgname)
                return PkgStates.NOT_FOUND
        return PkgStates.UNKNOWN

    @property
    def price(self):
        if self._doc:
            return self._doc.get_value(XapianValues.PRICE)

    @property
    def ppaname(self):
        if self._doc:
            return self._doc.get_value(XapianValues.ARCHIVE_PPA)

    @property
    def deb_line(self):
        if self._doc:
            return self._doc.get_value(XapianValues.ARCHIVE_DEB_LINE)

    @property
    def signing_key_id(self):
        if self._doc:
            return self._doc.get_value(XapianValues.ARCHIVE_SIGNING_KEY_ID)

    @property
    def screenshot(self):
        # if there is a custom screenshot url provided, use that
        if self._doc:
            if self._doc.get_value(XapianValues.SCREENSHOT_URL):
                return self._doc.get_value(XapianValues.SCREENSHOT_URL)
        # else use the default
        return self._distro.SCREENSHOT_LARGE_URL % { 'pkgname' : self.pkgname, 
                                                     'version' : self.version or 0 }

    @property
    def summary(self):
        if self._doc:
            return self._db.get_summary(self._doc)
        elif self._pkg:
            return self._pkg.candidate.summary

    @property
    def thumbnail(self):
        # if there is a custom thumbnail url provided, use that
        if self._doc:
            if self._doc.get_value(XapianValues.THUMBNAIL_URL):
                return self._doc.get_value(XapianValues.THUMBNAIL_URL)
        # else use the default
        return self._distro.SCREENSHOT_THUMB_URL % { 'pkgname' : self.pkgname, 
                                                     'version' : self.version or 0}

    @property
    def version(self):
        if self._pkg:
            if self._pkg.installed:
                return self._pkg.installed.version
            else:
                return self._pkg.candidate.version

    @property
    def warning(self):
        # apturl minver matches
        if not self.pkg_state == PkgStates.INSTALLED:
            if self._app.request:
                minver_matches = re.findall(r'minver=[a-z,0-9,-,+,.,~]*', self._app.request)
                if minver_matches and self.version:
                    minver = minver_matches[0][7:]
                    from softwarecenter.utils import version_compare
                    if version_compare(minver, self.version) > 0:
                        return _("Version %s or later not available.") % minver
        # can we enable a source
        if not self._pkg:
            source_to_enable = None
            if self.channelname and self._unavailable_channel():
                source_to_enable = self.channelname
            elif (self.component and 
                  self.component not in ("independent", "commercial")):
                source_to_enable = self.component
            if source_to_enable:
                sources = source_to_enable.split('&')
                sources_length = len(sources)
                if sources_length == 1:
                    warning = _("Available from the \"%s\" source.") % sources[0]
                elif sources_length > 1:
                    # Translators: the visible string is constructed concatenating 
                    # the following 3 strings like this: 
                    # Available from the following sources: %s, ... %s, %s.                
                    warning = _("Available from the following sources: ")
                    # Cycle through all, but the last
                    for source in sources[:-1]:
                        warning += _("\"%s\", ") % source
                    warning += _("\"%s\".") % sources[sources_length - 1]
                return warning

    @property
    def website(self):
        if self._pkg:
            return self._pkg.website
    
    @property
    def license_key(self):
        if self._doc:
            return self._doc.get_value(XapianValues.LICENSE_KEY)

    @property
    def license_key_path(self):
        if self._doc:
            return self._doc.get_value(XapianValues.LICENSE_KEY_PATH)

    def _unavailable_channel(self):
        """ Check if the given doc refers to a channel that is currently not enabled """
        return not is_channel_available(self.channelname)

    def _unavailable_component(self, component_to_check=None):
        """ Check if the given doc refers to a component that is currently not enabled """
        if component_to_check:
            component = component_to_check
        elif self.component:
            component = self.component
        else:
            component =  self._doc.get_value(XapianValues.ARCHIVE_SECTION)
        if not component:
            return False
        distro_codename = self._distro.get_codename()
        available = self._cache.component_available(distro_codename, component)
        return (not available)

    def __str__(self):
        details = []
        details.append("* AppDetails")
        details.append("                name: %s" % self.name)
        details.append("        display_name: %s" % self.display_name)
        details.append("                 pkg: %s" % self.pkg)
        details.append("             pkgname: %s" % self.pkgname)
        details.append("         channelname: %s" % self.channelname)
        details.append("                 ppa: %s" % self.ppaname)
        details.append("         channelfile: %s" % self.channelfile)
        details.append("           component: %s" % self.component)
        details.append("        desktop_file: %s" % self.desktop_file)
        details.append("         description: %s" % self.description)
        details.append("               error: %s" % self.error)
        details.append("                icon: %s" % self.icon)
        details.append("      icon_file_name: %s" % self.icon_file_name)
        details.append("            icon_url: %s" % self.icon_url)
        details.append("   installation_date: %s" % self.installation_date)
        details.append("       purchase_date: %s" % self.purchase_date)
        details.append("             license: %s" % self.license)
        details.append("  maintenance_status: %s" % self.maintenance_status)
        details.append("           pkg_state: %s" % self.pkg_state)
        details.append("               price: %s" % self.price)
        details.append("          screenshot: %s" % self.screenshot)
        details.append("             summary: %s" % self.summary)
        details.append("     display_summary: %s" % self.display_summary)
        details.append("           thumbnail: %s" % self.thumbnail)
        details.append("             version: %s" % self.version)
        details.append("             website: %s" % self.website)
        return '\n'.join(details)
