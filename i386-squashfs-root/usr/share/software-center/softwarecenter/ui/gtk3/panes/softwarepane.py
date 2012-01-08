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

from gi.repository import Atk
import dbus
import gettext
from gi.repository import GObject
from gi.repository import Gtk, Gdk
#~ from gi.repository import Cairo
import logging
import os
import xapian

from gettext import gettext as _

import softwarecenter.utils
from softwarecenter.backend import get_install_backend
from softwarecenter.db.database import Application
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.enums import (ActionButtons,
                                  SortMethods,
                                  TransactionTypes,
                                  DEFAULT_SEARCH_LIMIT,
                                  NonAppVisibility)

from softwarecenter.utils import (ExecutionTime,
                                  convert_desktop_file_to_installed_location,
                                  get_file_path_from_iconname,
                                  wait_for_apt_cache_ready,
                                  utf8
                                  )

from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerView
from softwarecenter.ui.gtk3.widgets.searchaid import SearchAid

from softwarecenter.ui.gtk3.views.appview import AppView
from softwarecenter.ui.gtk3.views.appdetailsview_gtk import (
                                                AppDetailsViewGtk as
                                                AppDetailsView)

from softwarecenter.utils import is_no_display_desktop_file

from basepane import BasePane

LOG = logging.getLogger(__name__)


class UnityLauncherInfo(object):
    """ Simple class to keep track of application details needed for
        Unity launcher integration
    """
    def __init__(self,
                 name,
                 icon_name,
                 icon_file_path,
                 icon_x,
                 icon_y,
                 icon_size,
                 app_install_desktop_file_path,
                 installed_desktop_file_path,
                 trans_id):
        self.name = name
        self.icon_name = icon_name
        self.icon_file_path = icon_file_path
        self.icon_x = icon_x
        self.icon_y = icon_y
        self.icon_size = icon_size
        self.app_install_desktop_file_path = app_install_desktop_file_path
        self.installed_desktop_file_path = installed_desktop_file_path
        self.trans_id = trans_id
        self.add_to_launcher_requested = False


# for DisplayState attribute type-checking
from softwarecenter.db.categories import Category
from softwarecenter.backend.channel import SoftwareChannel
from softwarecenter.db.appfilter import AppFilter


class DisplayState(object):

    _attrs = {'category': (type(None), Category),
              'channel': (type(None), SoftwareChannel),
              'subcategory': (type(None), Category),
              'search_term': (str,),
              'application': (type(None), Application),
              'limit': (int,),
              'filter': (type(None), AppFilter),
              'previous_purchases_query': (type(None), xapian.Query)
            }

    def __init__(self):
        self.category = None
        self.channel = None
        self.subcategory = None
        self.search_term = ""
        self.application = None
        self.limit = 0
        self.filter = None
        self.previous_purchases_query = None
        return

    def __setattr__(self, name, val):
        attrs = self._attrs
        if name not in attrs:
            raise AttributeError("The attr name \"%s\" is not permitted" % name)
            Gtk.main_quit()
        if not isinstance(val, attrs[name]):
            msg = "Attribute %s expects %s, got %s" % (name, attrs[name], type(val))
            raise TypeError(msg)
            Gtk.main_quit()
        return object.__setattr__(self, name, val)

    def __str__(self):
        s = unicode('%s %s "%s" %s %s', 'utf8').encode('utf8') % \
                                 (self.category,
                                  self.subcategory,
                                  self.search_term,
                                  self.application,
                                  self.channel,)
        return s

    def copy(self):
        state = DisplayState()
        state.channel = self.channel
        state.category = self.category
        state.subcategory = self.subcategory
        state.search_term = self.search_term
        state.application = self.application
        state.limit = self.limit
        if self.filter:
            state.filter = self.filter.copy()
        else:
            state.filter = None
        return state

    def reset(self):
        self.channel = None
        self.category = None
        self.subcategory = None
        self.search_term = ""
        self.application = None
        self.limit = 0
        #~ self.filter = None
        return

class SoftwarePane(Gtk.VBox, BasePane):
    """ Common base class for AvailablePane and InstalledPane"""

    class Pages:
        NAMES = ('appview', 'details', 'spinner')
        APPVIEW = 0
        DETAILS = 1
        SPINNER = 2

    __gsignals__ = {
        "app-list-changed" : (GObject.SignalFlags.RUN_LAST,
                              None, 
                              (int,),
                             ),
    }
    PADDING = 6

    def __init__(self, cache, db, distro, icons, datadir, show_ratings=True):

        Gtk.VBox.__init__(self)
        BasePane.__init__(self)

        # other classes we need        
        self.enquirer = AppEnquire(cache, db)
        self._query_complete_handler = self.enquirer.connect(
                            "query-complete", self.on_query_complete)

        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir
        self.show_ratings = show_ratings
        self.backend = get_install_backend()
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        # refreshes can happen out-of-bound so we need to be sure
        # that we only set the new model (when its available) if
        # the refresh_seq_nr of the ready model matches that of the
        # request (e.g. people click on ubuntu channel, get impatient, click
        # on partner channel)
        self.refresh_seq_nr = 0
        # keep track of applications that are candidates to be added
        # to the Unity launcher
        self.unity_launcher_items = {}
        # this should be initialized
        self.apps_search_term = ""
        # Create the basic frame for the common view
        self.state = DisplayState()
        vm = get_viewmanager()
        self.searchentry = vm.get_global_searchentry()
        self.back_forward = vm.get_global_backforward()
        # a notebook below
        self.notebook = Gtk.Notebook()
        if not "SOFTWARE_CENTER_DEBUG_TABS" in os.environ:
            self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        # an empty notebook, where the details view will eventually go
        self.details_notebook = Gtk.Notebook()
        self.details_notebook.set_show_border(False)
        # make a spinner view to display while the applist is loading
        self.spinner_view = SpinnerView()
        self.spinner_notebook = Gtk.Notebook()
        self.spinner_notebook.set_show_tabs(False)
        self.spinner_notebook.set_show_border(False)
        self.spinner_notebook.append_page(self.notebook, None)
        self.spinner_notebook.append_page(self.details_notebook, None)
        self.spinner_notebook.append_page(self.spinner_view, None)
        
        self.pack_start(self.spinner_notebook, True, True, 0)

        # add a bar at the bottom (hidden by default) for contextual actions
        self.action_bar = ActionBar()
        self.pack_start(self.action_bar, False, True, 0)

        # cursor
        self.busy_cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)
        
        # views to be created in init_view
        self.app_view = None
        self.app_details_view = None

    def init_view(self):
        """
        Initialize those UI components that are common to all subclasses of
        SoftwarePane.  Note that this method is intended to be called by
        the subclass itself at the start of its own init_view() implementation.
        """
        # common UI elements (applist and appdetails) 
        # its the job of the Child class to put it into a good location
        # list
        self.box_app_list = Gtk.VBox()

        # search aid
        self.search_aid = SearchAid(self)
        self.box_app_list.pack_start(self.search_aid, False, False, 0)

        self.app_view = AppView(self.db, self.cache,
                                self.icons, self.show_ratings)
        self.app_view.sort_methods_combobox.connect(
                    "changed",
                    self.on_app_view_sort_method_changed)

        self.init_atk_name(self.app_view, "app_view")
        self.box_app_list.pack_start(self.app_view, True, True, 0)
        self.app_view.connect("application-selected", 
                              self.on_application_selected)
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
                                             
        # details
        self.scroll_details = Gtk.ScrolledWindow()
        self.scroll_details.set_policy(Gtk.PolicyType.AUTOMATIC, 
                                        Gtk.PolicyType.AUTOMATIC)
        self.app_details_view = AppDetailsView(self.db, 
                                               self.distro,
                                               self.icons, 
                                               self.cache, 
                                               self.datadir,
                                               self)
        self.scroll_details.add(self.app_details_view)
        # when the cache changes, refresh the app list
        self.cache.connect("cache-ready", self.on_cache_ready)

        # aptdaemon
        self.backend.connect("transaction-started", self.on_transaction_started)
        self.backend.connect("transaction-finished", self.on_transaction_finished)
        self.backend.connect("transaction-stopped", self.on_transaction_stopped)
        
        # connect signals
        self.connect("app-list-changed", self.on_app_list_changed)
        
        # db reopen
        if self.db:
            self.db.connect("reopen", self.on_db_reopen)

    def init_atk_name(self, widget, name):
        """ init the atk name for a given gtk widget based on parent-pane
            and variable name (used for the mago tests)
        """
        name =  self.__class__.__name__ + "." + name
        Atk.Object.set_name(widget.get_accessible(), name)

    def on_cache_ready(self, cache):
        " refresh the application list when the cache is re-opened "
        LOG.debug("on_cache_ready")
        # it only makes sense to refresh if there is something to
        # refresh, otherwise we create a bunch of (not yet needed)
        # AppStore objects on startup when the cache sends its 
        # initial "cache-ready" signal
        model = self.app_view.tree_view.get_model()
        if model is None:
            return
        # FIXME: preserve selection too
        self.refresh_apps()

    @wait_for_apt_cache_ready
    def on_application_activated(self, appview, app):
        """callback when an app is clicked"""
        LOG.debug("on_application_activated: '%s'" % app)

        self.state.application = app

        vm = get_viewmanager()
        vm.display_page(self, SoftwarePane.Pages.DETAILS, self.state, self.display_details_page)

    def show_app(self, app):
        self.on_application_activated(None, app)

    def on_nav_back_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_back()

    def on_nav_forward_clicked(self, widget):
        vm = get_viewmanager()
        vm.nav_forward()

    def on_transaction_started(self, backend, pkgname, appname, trans_id, 
                               trans_type):
        self._register_unity_launcher_transaction_started(
            backend, pkgname, appname, trans_id, trans_type)

        
    def _get_onscreen_icon_details_for_launcher_service(self, app):
        if self.is_app_details_view_showing():
            return self.app_details_view.get_app_icon_details()
        else:
            # TODO: implement the app list view case once it has been specified
            return (0, 0, 0)
       
    def _register_unity_launcher_transaction_started(self, backend, pkgname, 
                                                     appname, trans_id, 
                                                     trans_type):
        # mvo: use use softwarecenter.utils explictely so that we can monkey
        #      patch it in the test
        if not softwarecenter.utils.is_unity_running():
            return
        # add to launcher only applies in the details view currently
        if not self.is_app_details_view_showing():
            return
        # we only care about getting the launcher information on an install
        if not trans_type == TransactionTypes.INSTALL:
            if pkgname in self.unity_launcher_items:
                self.unity_launcher_items.pop(pkgname)
                self.action_bar.clear()
            return
        # gather details for this transaction and create the launcher_info object
        app = Application(pkgname=pkgname, appname=appname)
        appdetails = app.get_details(self.db)
        (icon_size, icon_x, icon_y) = self._get_onscreen_icon_details_for_launcher_service(app)
        launcher_info = UnityLauncherInfo(app.name,
                                          appdetails.icon,
                                          "",        # we set the icon_file_path value *after* install
                                          icon_x,
                                          icon_y,
                                          icon_size,
                                          appdetails.desktop_file,
                                          "",        # we set the installed_desktop_file_path *after* install
                                          trans_id)
        self.unity_launcher_items[app.pkgname] = launcher_info
        self.show_add_to_launcher_panel(backend, pkgname, appname, app, appdetails, trans_id, trans_type)
                
    def show_add_to_launcher_panel(self, backend, pkgname, appname, app, appdetails, trans_id, trans_type):
        """
        if Unity is currently running, display a panel to allow the user
        the choose whether to add a newly-installed application to the
        launcher
        """
        # TODO: handle local deb install case
        # TODO: implement the list view case (once it is specified)
        # only show the panel if unity is running and this is a package install
        #
        # we only show the prompt for apps with a desktop file
        if not appdetails.desktop_file:
            return
        # do not add apps without a exec line (like wine, see #848437)
        if (os.path.exists(appdetails.desktop_file) and
            is_no_display_desktop_file(appdetails.desktop_file)):
                return
        self.action_bar.add_button(ActionButtons.CANCEL_ADD_TO_LAUNCHER,
                                    _("Not Now"), 
                                    self.on_cancel_add_to_launcher, 
                                    pkgname)
        self.action_bar.add_button(ActionButtons.ADD_TO_LAUNCHER,
                                   _("Add to Launcher"),
                                   self.on_add_to_launcher,
                                   pkgname,
                                   app,
                                   appdetails,
                                   trans_id)
        self.action_bar.set_label(utf8(_("Add %s to the launcher?")) % utf8(app.name))

    def on_query_complete(self, enquirer):
        self.emit("app-list-changed", len(enquirer.matches))
        sort_by_relevance = (self._is_in_search_mode() and
                             not self.app_view.user_defined_sort_method)
        
        self.app_view.display_matches(enquirer.matches,
                                      sort_by_relevance)
        self.hide_appview_spinner()
        return

    def on_app_view_sort_method_changed(self, combo):
        if self.app_view.get_sort_mode() == self.enquirer.sortmode:
            return

        self.show_appview_spinner()
        self.app_view.clear_model()
        query = self.get_query()
        self._refresh_apps_with_apt_cache(query)
        return

    def on_add_to_launcher(self, pkgname, app, appdetails, trans_id):
        """
        callback indicating the user has chosen to add the indicated application
        to the launcher
        """
        if pkgname in self.unity_launcher_items:
            launcher_info = self.unity_launcher_items[pkgname]
            if launcher_info.installed_desktop_file_path:
                # package install is complete, we can add to the launcher immediately
                self.unity_launcher_items.pop(pkgname)
                self.action_bar.clear()
                self._send_dbus_signal_to_unity_launcher(launcher_info)
            else:
                # package is not yet installed, it will be added to the launcher
                # once the installation is complete
                LOG.debug("the application '%s' will be added to the Unity launcher when installation is complete" % app.name)
                launcher_info.add_to_launcher_requested = True
                self.action_bar.set_label(_("%s will be added to the launcher when installation completes.") % app.name)
                self.action_bar.remove_button(ActionButtons.CANCEL_ADD_TO_LAUNCHER)
                self.action_bar.remove_button(ActionButtons.ADD_TO_LAUNCHER)

    def on_cancel_add_to_launcher(self, pkgname):
        if pkgname in self.unity_launcher_items:
            self.unity_launcher_items.pop(pkgname)
        self.action_bar.clear()
        
    def on_transaction_finished(self, backend, result):
        self._check_unity_launcher_transaction_finished(result)

    def _is_in_search_mode(self):
        return (self.state.search_term and
                len(self.state.search_term) >= 2)

    def _check_unity_launcher_transaction_finished(self, result):
        # add the completed transaction details to the corresponding
        # launcher_item
        if result.pkgname in self.unity_launcher_items:
            launcher_info = self.unity_launcher_items[result.pkgname]
            launcher_info.icon_file_path = get_file_path_from_iconname(
                self.icons, launcher_info.icon_name)
            installed_path = convert_desktop_file_to_installed_location(
                launcher_info.app_install_desktop_file_path, result.pkgname)
            launcher_info.installed_desktop_file_path = installed_path
            # if the request to add to launcher has already been made, do it now
            if launcher_info.add_to_launcher_requested:
                if result.success:
                    self._send_dbus_signal_to_unity_launcher(launcher_info)
                self.unity_launcher_items.pop(result.pkgname)
                self.action_bar.clear()
            
    def _send_dbus_signal_to_unity_launcher(self, launcher_info):
        LOG.debug("sending dbus signal to Unity launcher for application: ", launcher_info.name)
        LOG.debug("  launcher_info.icon_file_path: ", launcher_info.icon_file_path)
        LOG.debug("  launcher_info.installed_desktop_file_path: ", launcher_info.installed_desktop_file_path)
        LOG.debug("  launcher_info.trans_id: ", launcher_info.trans_id)
        try:
            bus = dbus.SessionBus()
            launcher_obj = bus.get_object('com.canonical.Unity.Launcher',
                                          '/com/canonical/Unity/Launcher')
            launcher_iface = dbus.Interface(launcher_obj, 'com.canonical.Unity.Launcher')
            launcher_iface.AddLauncherItemFromPosition(launcher_info.name,
                                                       launcher_info.icon_file_path,
                                                       launcher_info.icon_x,
                                                       launcher_info.icon_y,
                                                       launcher_info.icon_size,
                                                       launcher_info.installed_desktop_file_path,
                                                       launcher_info.trans_id)
        except Exception as e:
            LOG.warn("could not send dbus signal to the Unity launcher: (%s)", e)
            
    def on_transaction_stopped(self, backend, result):
        if result.pkgname in self.unity_launcher_items:
            self.unity_launcher_items.pop(result.pkgname)
        self.action_bar.clear()

    def show_appview_spinner(self):
        """ display the spinner in the appview panel """
        if not self.state.search_term:
            self.action_bar.clear()
        self.spinner_view.stop()
        self.spinner_notebook.set_current_page(SoftwarePane.Pages.SPINNER)
        # "mask" the spinner view momentarily to prevent it from flashing into
        # view in the case of short delays where it isn't actually needed
        GObject.timeout_add(100, self._unmask_appview_spinner)
        
    def _unmask_appview_spinner(self):
        self.spinner_view.start()
        return False
        
    def hide_appview_spinner(self):
        """ hide the spinner and display the appview in the panel """
        self.spinner_notebook.set_current_page(
                                        SoftwarePane.Pages.APPVIEW)
        self.spinner_view.stop()

    def set_section(self, section):
        self.section = section
        self.app_details_view.set_section(section)
        return

    def section_sync(self):
        self.app_details_view.set_section(self.section)
        return

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the the action bar up-to-date by
           keeping track of the app-list-changed signals
        """

        self.show_nonapps_if_required(len(self.enquirer.matches))
        self.search_aid.update_search_help(self.state)
        return

    def hide_nonapps(self):
        """ hide non-applications control in the action bar """
        self.action_bar.unset_label()
        return

    def show_nonapps_if_required(self, length):
        """
        update the state of the show/hide non-applications control
        in the action_bar
        """

        enquirer = self.enquirer
        n_apps = enquirer.nr_apps
        n_pkgs = enquirer.nr_pkgs

        # calculate the number of apps/pkgs
        if enquirer.limit > 0 and enquirer.limit < n_pkgs:
            n_apps = min(enquirer.limit, n_apps)
            n_pkgs = min(enquirer.limit - n_apps, n_pkgs)

        if not (n_apps and n_pkgs):
            self.hide_nonapps()
            return

        LOG.debug("nonapps_visible value=%s (always visible: %s)" % (
                self.nonapps_visible, 
                self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE))

        self.action_bar.unset_label()
        if self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE:
            LOG.debug('non-apps-ALWAYS-visible')
            # TRANSLATORS: the text inbetween the underscores acts as a link
            # In most/all languages you will want the whole string as a link
            label = gettext.ngettext("_Hide %(amount)i technical item_",
                                     "_Hide %(amount)i technical items_",
                                     n_pkgs) % { 'amount': n_pkgs, }
            self.action_bar.set_label(
                        label, link_result=self._hide_nonapp_pkgs) 
        else:
            label = gettext.ngettext("_Show %(amount)i technical item_",
                                     "_Show %(amount)i technical items_",
                                     n_pkgs) % { 'amount': n_pkgs, }
            self.action_bar.set_label(
                        label, link_result=self._show_nonapp_pkgs)

    def _on_label_app_list_header_activate_link(self, link, uri):
        #print "actiavte: ", link, uri
        if uri.startswith("search:"):
            self.searchentry.set_text(uri[len("search:"):])
        elif uri.startswith("search-all:"):
            self.unset_current_category()
            self.refresh_apps()
        elif uri.startswith("search-parent:"):
            self.apps_subcategory = None;
            self.refresh_apps()
        elif uri.startswith("search-unsupported:"):
            self.apps_filter.set_supported_only(False)
            self.refresh_apps()
        # FIXME: add ability to remove categories restriction here
        # True stops event propergation
        return True

    def _show_nonapp_pkgs(self):
        self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
        self.refresh_apps()

    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        self.refresh_apps()

    def get_query(self):
        channel_query = None
        #name = self.pane_name
        if self.channel:
            channel_query = self.channel.query
            #name = self.channel.display_name

        # search terms
        if self.apps_search_term:
            query = self.db.get_query_list_from_search_entry(
                self.apps_search_term, channel_query)

            return query
        # overview list
        # if we are in a channel, limit to that
        if channel_query:
            return channel_query
        # ... otherwise show all
        return xapian.Query("")
        
    def refresh_apps(self, query=None):
        """refresh the applist and update the navigation bar """
        LOG.debug("refresh_apps")

        # FIXME: make this available for all panes
        if query is None:
            query = self.get_query()

        self.app_view.clear_model()
        self.search_aid.reset()
        self.show_appview_spinner()
        self._refresh_apps_with_apt_cache(query)

    def quick_query(self, query):
        # a blocking query and does not emit "query-complete"
        with ExecutionTime("enquirer.set_query() quick query"):
            self.enquirer.set_query(
                                query,
                                limit=self.get_app_items_limit(),
                                nonapps_visible=self.nonapps_visible,
                                nonblocking_load=False,
                                filter=self.state.filter)
        return len(self.enquirer.matches)

    @wait_for_apt_cache_ready
    def _refresh_apps_with_apt_cache(self, query):
        LOG.debug("softwarepane query: %s" % query)
        # a nonblocking query calls on_query_complete once finished
        with ExecutionTime("enquirer.set_query()"):
            self.enquirer.set_query(
                                query,
                                limit=self.get_app_items_limit(),
                                sortmode=self.get_sort_mode(),
                                exact=self.is_custom_list(),
                                nonapps_visible=self.nonapps_visible,
                                filter=self.state.filter)
        return

    def display_details_page(self, page, view_state):
        self.app_details_view.show_app(view_state.application)
        self.action_bar.unset_label()
        return True

    def is_custom_list(self):
        return self.apps_search_term and ',' in self.apps_search_term

    def get_current_page(self):
        return self.notebook.get_current_page()

    def get_app_items_limit(self):
        if self.state.search_term:
            return DEFAULT_SEARCH_LIMIT
        elif self.state.subcategory and self.state.subcategory.item_limit > 0:
            return self.state.subcategory.item_limit
        elif self.state.category and self.state.category.item_limit > 0:
            return self.state.category.item_limit
        return 0

    def get_sort_mode(self):
        # if the category sets a custom sort order, that wins, this
        # is required for top-rated and whats-new
        if (self.state.category and 
            self.state.category.sortmode != SortMethods.BY_ALPHABET):
            return self.state.category.sortmode
        # searches are always by ranking unless the user decided differently
        if (self._is_in_search_mode() and 
            not self.app_view.user_defined_sort_method):
            return SortMethods.BY_SEARCH_RANKING
        # use the appview combo
        return self.app_view.get_sort_mode()

    def on_search_terms_changed(self, terms):
        " stub implementation "
        pass

    def on_db_reopen(self):
        " stub implementation "
        pass

    def is_category_view_showing(self):
        " stub implementation "
        pass
        
    def is_applist_view_showing(self):
        " stub implementation "
        pass
        
    def is_app_details_view_showing(self):
        " stub implementation "
        pass
        
    def get_current_app(self):
        " stub implementation "
        pass

    def on_application_selected(self, widget, app):
        " stub implementation "
        pass

    def get_current_category(self):
        " stub implementation "
        pass

    def unset_current_category(self):
        " stub implementation "
        pass
