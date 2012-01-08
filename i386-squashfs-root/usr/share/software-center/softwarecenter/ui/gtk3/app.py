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

# order is import here, otherwise test/gtk3/test_purchase.py is unhappy
from gi.repository import GObject
from gi.repository import Gtk

import atexit
import collections
import locale
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import gettext
import logging
import os
import subprocess
import sys
import xapian
import glob

import webbrowser

from gettext import gettext as _

# purely to initialize the netstatus
import softwarecenter.netstatus
# make pyflakes shut up
softwarecenter.netstatus.NETWORK_STATE

# db imports
from softwarecenter.db.application import Application
from softwarecenter.db import DebFileApplication

# misc imports
from softwarecenter.plugin import PluginManager
from softwarecenter.paths import SOFTWARE_CENTER_PLUGIN_DIRS
from softwarecenter.enums import (Icons,
                                  PkgStates,
                                  ViewPages,
                                  AppActions,
                                  DB_SCHEMA_VERSION,
                                  MOUSE_EVENT_FORWARD_BUTTON,
                                  MOUSE_EVENT_BACK_BUTTON)
from softwarecenter.utils import (clear_token_from_ubuntu_sso,
                                  get_http_proxy_string_from_gsettings,
                                  wait_for_apt_cache_ready)
from softwarecenter.ui.gtk3.utils import (get_sc_icon_theme,
                                          init_sc_css_provider)
from softwarecenter.version import VERSION
from softwarecenter.db.database import StoreDatabase
from softwarecenter.backend.transactionswatcher import TransactionFinishedResult
try:
    from aptd_gtk3 import InstallBackendUI
    InstallBackendUI # pyflakes
except:
    from softwarecenter.backend.installbackend import InstallBackendUI

# ui imports
import softwarecenter.ui.gtk3.dialogs.dependency_dialogs as dependency_dialogs
import softwarecenter.ui.gtk3.dialogs.deauthorize_dialog as deauthorize_dialog
import softwarecenter.ui.gtk3.dialogs as dialogs

from softwarecenter.ui.gtk3.SimpleGtkbuilderApp import SimpleGtkbuilderApp
from softwarecenter.ui.gtk3.panes.installedpane import InstalledPane
from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
from softwarecenter.ui.gtk3.panes.historypane import HistoryPane
from softwarecenter.ui.gtk3.panes.globalpane import GlobalPane
from softwarecenter.ui.gtk3.panes.pendingpane import PendingPane
from softwarecenter.ui.gtk3.session.viewmanager import ViewManager, get_viewmanager

from softwarecenter.config import get_config
from softwarecenter.backend import get_install_backend

from softwarecenter.backend.channel import AllInstalledChannel
from softwarecenter.backend.reviews import get_review_loader, UsefulnessCache
from softwarecenter.backend.oneconfhandler import get_oneconf_handler
from softwarecenter.distro import get_distro
from softwarecenter.db.pkginfo import get_pkg_info


from gi.repository import Gdk

LOG = logging.getLogger(__name__)

# py3 compat
def callable(func):
    return isinstance(func, collections.Callable)

class SoftwarecenterDbusController(dbus.service.Object):
    """ 
    This is a helper to provide the SoftwarecenterIFace
    
    It provides only a bringToFront method that takes 
    additional arguments about what packages to show
    """
    def __init__(self, parent, bus_name,
                 object_path='/com/ubuntu/Softwarecenter'):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.parent = parent

    @dbus.service.method('com.ubuntu.SoftwarecenterIFace')
    def bringToFront(self, args):
        if args != 'nothing-to-show':
            self.parent.show_available_packages(args)
        self.parent.window_main.present()
        return True

    @dbus.service.method('com.ubuntu.SoftwarecenterIFace')
    def triggerDatabaseReopen(self):
        self.parent.db.emit("reopen")

    @dbus.service.method('com.ubuntu.SoftwarecenterIFace')
    def triggerCacheReload(self):
        self.parent.cache.emit("cache-ready")

# XXX Haven't really thought this through....
#~ class SoftwareCenterInitOndemand(object):
#~ 
    #~ """ Init objects/data that are low priority, i.e, use case is
        #~ niche and/or load times are low and will not impact user
        #~ experience.  All data and objects are loaded on request.
    #~ """
#~ 
    #~ def init(self):
        #~ pass


#~ class SoftwareCenterInitDelayed(object):
#~ 
    #~ """ Init objects/data that are medium priority, not needed instantly
        #~ but rather _potentially_ required within the first few seconds
        #~ of USC usage.
    #~ """
#~ 
    #~ def init(self):
        #~ # reviews
        #~ self.review_loader = get_review_loader(self.cache, self.db)
        #~ # FIXME: add some kind of throttle, I-M-S here
        #~ self.review_loader.refresh_review_stats(self.on_review_stats_loaded)
        #~ #load usefulness votes from server when app starts
        #~ self.useful_cache = UsefulnessCache(True)
        #~ self.setup_database_rebuilding_listener()
        #~ # open plugin manager and load plugins
        #~ self.plugin_manager = PluginManager(self, SOFTWARE_CENTER_PLUGIN_DIRS)
        #~ self.plugin_manager.load_plugins()



class SoftwareCenterAppGtk3(SimpleGtkbuilderApp):

    WEBLINK_URL = "http://apt.ubuntu.com/p/%s"

    # the size of the icon for dialogs
    APP_ICON_SIZE = Gtk.IconSize.DIALOG

    def __init__(self, datadir, xapian_base_path, options, args=None):
        # setup dbus and exit if there is another instance already
        # running
        self.setup_dbus_or_bring_other_instance_to_front(args)

        self.datadir = datadir
        SimpleGtkbuilderApp.__init__(self, 
                                     datadir+"/ui/gtk3/SoftwareCenter.ui", 
                                     "software-center")
        gettext.bindtextdomain("software-center", "/usr/share/locale")
        gettext.textdomain("software-center")

        try:
            locale.setlocale(locale.LC_ALL, "")
            # we need this for bug #846038, with en_NG setlocale() is fine
            # but the next getlocale() will crash (fun!)
            locale.getlocale()
        except:
            LOG.exception("setlocale failed, resetting to C")
            locale.setlocale(locale.LC_ALL, "C")


        if "SOFTWARE_CENTER_DEBUG_TABS" in os.environ:
            self.notebook_view.set_show_tabs(True)

        # distro specific stuff
        self.distro = get_distro()

        # setup proxy
        self._setup_proxy_initially()

        # Disable software-properties if it does not exist
        if not os.path.exists("/usr/bin/software-properties-gtk"):
            sources = self.builder.get_object("menuitem_software_sources")
            sources.set_sensitive(False)

        # a main iteration friendly apt cache
        self.cache = get_pkg_info()
        self.cache.open()
        self.cache.connect("cache-broken", self._on_apt_cache_broken)

        # xapian
        pathname = os.path.join(xapian_base_path, "xapian")
        self._use_axi = not options.disable_apt_xapian_index
        try:
            self.db = StoreDatabase(pathname, self.cache)
            self.db.open(use_axi = self._use_axi)
            if self.db.schema_version() != DB_SCHEMA_VERSION:
                LOG.warn("database format '%s' expected, but got '%s'" % (
                         DB_SCHEMA_VERSION, self.db.schema_version()))
                if os.access(pathname, os.W_OK):
                    self._rebuild_and_reopen_local_db(pathname)
        except xapian.DatabaseOpeningError:
            # Couldn't use that folder as a database
            # This may be because we are in a bzr checkout and that
            #   folder is empty. If the folder is empty, and we can find the
            # script that does population, populate a database in it.
            if os.path.isdir(pathname) and not os.listdir(pathname):
                self._rebuild_and_reopen_local_db(pathname)
        except xapian.DatabaseCorruptError:
            LOG.exception("xapian open failed")
            dialogs.error(None, 
                          _("Sorry, can not open the software database"),
                          _("Please re-install the 'software-center' "
                            "package."))
            # FIXME: force rebuild by providing a dbus service for this
            sys.exit(1)

        # backend
        self.backend = get_install_backend()
        self.backend.ui = InstallBackendUI()
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("channels-changed", self.on_channels_changed)

        # misc state
        self._block_menuitem_view = False
        
        # for use when viewing previous purchases
        self.scagent = None
        self.sso = None

        # additional icons come from app-install-data
        self.icons = get_sc_icon_theme(self.datadir)
        Gtk.Window.set_default_icon_name("softwarecenter")

        # inhibit the error-bell, Bug #846138...
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-error-bell", False)

        # wire up the css provider to reconfigure on theme-changes
        self.window_main.connect("style-updated",
                                 self._on_style_updated,
                                 init_sc_css_provider,
                                 settings,
                                 Gdk.Screen.get_default(),
                                 datadir)

        # register view manager and create view panes/widgets
        self.view_manager = ViewManager(self.notebook_view, options)

        self.global_pane = GlobalPane(self.view_manager, self.datadir, self.db, self.cache, self.icons)
        self.vbox1.pack_start(self.global_pane, False, False, 0)
        self.vbox1.reorder_child(self.global_pane, 1)

        # available pane
        self.available_pane = AvailablePane(self.cache,
                                            self.db,
                                            self.distro,
                                            self.icons,
                                            self.datadir,
                                            self.navhistory_back_action,
                                            self.navhistory_forward_action)
        self.available_pane.connect("available-pane-created", self.on_available_pane_created)
        self.view_manager.register(self.available_pane, ViewPages.AVAILABLE)

        # installed pane (view not fully initialized at this point)
        self.installed_pane = InstalledPane(self.cache,
                                            self.db, 
                                            self.distro,
                                            self.icons,
                                            self.datadir)
        self.installed_pane.connect("installed-pane-created", self.on_installed_pane_created)
        self.view_manager.register(self.installed_pane, ViewPages.INSTALLED)

        # history pane (not fully loaded at this point)
        self.history_pane = HistoryPane(self.cache,
                                        self.db,
                                        self.distro,
                                        self.icons,
                                        self.datadir)
        self.view_manager.register(self.history_pane, ViewPages.HISTORY)

        # pending pane
        self.pending_pane = PendingPane(self.icons)
        self.view_manager.register(self.pending_pane, ViewPages.PENDING)

        # TRANSLATORS: this is the help menuitem label, e.g. Ubuntu Software Center _Help
        self.menuitem_help.set_label(_("%s _Help")%self.distro.get_app_name())

        # specify the smallest allowable window size
        self.window_main.set_size_request(730, 470)

        # reviews
        self.review_loader = get_review_loader(self.cache, self.db)
        # FIXME: add some kind of throttle, I-M-S here
        self.review_loader.refresh_review_stats(self.on_review_stats_loaded)
        #load usefulness votes from server when app starts
        self.useful_cache = UsefulnessCache(True)
        self.setup_database_rebuilding_listener()

        # open plugin manager and load plugins
        self.plugin_manager = PluginManager(self, SOFTWARE_CENTER_PLUGIN_DIRS)
        self.plugin_manager.load_plugins()

        # setup window name and about information (needs branding)
        name = self.distro.get_app_name()
        self.window_main.set_title(name)
        self.aboutdialog.set_program_name(name)
        about_description = self.distro.get_app_description()
        self.aboutdialog.set_comments(about_description)

        # about dialog
        self.aboutdialog.connect("response", lambda dialog, rid: dialog.hide())
        self.aboutdialog.connect("delete_event", lambda w,e: self.aboutdialog.hide_on_delete())

        # restore state
        self.config = get_config()
        self.restore_state()

        # run s-c-agent update
        if options.disable_buy:
            file_menu = self.builder.get_object("menu1")
            file_menu.remove(self.builder.get_object("menuitem_reinstall_purchases"))
        else:
            sc_agent_update = os.path.join(
                self.datadir, "update-software-center-agent")
            (pid, stdin, stdout, stderr) = GObject.spawn_async(
                [sc_agent_update, "--datadir", datadir], 
                flags=GObject.SPAWN_DO_NOT_REAP_CHILD)
            GObject.child_watch_add(
                pid, self._on_update_software_center_agent_finished)

        if options.disable_buy and not options.enable_lp:
            file_menu.remove(self.builder.get_object("separator_login"))
            
        # TODO: Remove the following two lines once we have remove repository
        #       support in aptdaemon (see LP: #723911)
        file_menu = self.builder.get_object("menu1")
        file_menu.remove(self.builder.get_object("menuitem_deauthorize_computer"))

        # keep track of the current active pane
        self.active_pane = self.available_pane
        self.window_main.connect("realize", self.on_realize)

        # launchpad integration help, its ok if that fails
        try:
            from gi.repository import LaunchpadIntegration
            LaunchpadIntegration.set_sourcepackagename("software-center")
            LaunchpadIntegration.add_items(self.menu_help, 3, True, False)
        except Exception, e:
            LOG.debug("launchpad integration error: '%s'" % e)



    # helper
    def _rebuild_and_reopen_local_db(self, pathname):
        """ helper that rebuilds a db and reopens it """
        from softwarecenter.db.update import rebuild_database
        LOG.info("building local database")
        rebuild_database(pathname)
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open(use_axi=self._use_axi)

    def _setup_proxy_initially(self):
        from gi.repository import Gio
        self._setup_proxy()
        self._gsettings = Gio.Settings.new("org.gnome.system.proxy.http")
        self._gsettings.connect("changed", self._setup_proxy)

    def _setup_proxy(self, setting=None, key=None):
        proxy = get_http_proxy_string_from_gsettings()
        if proxy:
            os.environ["http_proxy"] = proxy
        elif "http_proxy" in os.environ:
            del os.environ["http_proxy"]


    # callbacks
    def on_realize(self, widget):
        return

    def on_available_pane_created(self, widget):
        # connect signals
        self.available_pane.app_details_view.connect("application-request-action", 
                                                     self.on_application_request_action)
        self.available_pane.app_view.connect("application-request-action", 
                                             self.on_application_request_action)
        # FIXME
        #~ self.available_pane.app_view.connect("mouse-nav-requested", 
                                             #~ self.on_window_main_button_press_event)
        self.available_pane.searchentry.grab_focus()
    
    def on_channel_pane_created(self, widget):
        #~ channel_section = SoftwareSection()
        # note that the view_id for each channel's section is set later
        # depending on whether the channel view will display available or
        # installed items
        #~ self.channel_pane.set_section(channel_section)

        # connect signals
        self.channel_pane.app_details_view.connect("application-request-action", 
                                                   self.on_application_request_action)
        self.channel_pane.app_view.connect("application-request-action", 
                                           self.on_application_request_action)
                                           
    def on_installed_pane_created(self, widget):
        #~ installed_section = SoftwareSection()
        #~ installed_section.set_view_id(ViewPages.INSTALLED)
        #~ self.installed_pane.set_section(installed_section)
        
        # connect signals
        self.installed_pane.app_details_view.connect("application-request-action", 
                                                     self.on_application_request_action)
        self.installed_pane.app_view.connect("application-request-action", 
                                             self.on_application_request_action)
    
    def _on_update_software_center_agent_finished(self, pid, condition):
        LOG.info("software-center-agent finished with status %i" % os.WEXITSTATUS(condition))
        if os.WEXITSTATUS(condition) == 0:
            self.db.reopen()

    def on_review_stats_loaded(self, reviews):
        LOG.debug("on_review_stats_loaded: '%s'" % len(reviews))

    def on_window_main_delete_event(self, widget, event):
        if hasattr(self, "glaunchpad"):
            self.glaunchpad.shutdown()
        self.save_state()
        try:
            Gtk.main_quit()
        except Exception as e:
            LOG.warning(e)
        
    def on_window_main_key_press_event(self, widget, event):
        """ Define all the accelerator keys here - slightly messy, but the ones
            defined in the menu don't seem to work.. """

        # close
        if ((event.keyval == Gdk.keyval_from_name("w") or
             event.keyval == Gdk.keyval_from_name("q")) and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_close.activate()

        # undo/redo
        if (event.keyval == Gdk.keyval_from_name("z") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_undo.get_sensitive():
                self.menuitem_undo.activate()

        if (event.keyval == Gdk.keyval_from_name("Z") and
            event.state == (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK)):
            self.menuitem_edit.activate()
            if self.menuitem_redo.get_sensitive():
                self.menuitem_redo.activate()

        # cut/copy/paste
        if (event.keyval == Gdk.keyval_from_name("x") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_cut.get_sensitive():
                self.menuitem_cut.activate()

        if (event.keyval == Gdk.keyval_from_name("c") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_copy.get_sensitive():
                self.menuitem_copy.activate()

        if (event.keyval == Gdk.keyval_from_name("v") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_paste.get_sensitive():
                self.menuitem_paste.activate()

        # copy web link
        if (event.keyval == Gdk.keyval_from_name("C") and
            event.state == (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK)):
            self.menuitem_edit.activate()
            if self.menuitem_copy_web_link.get_sensitive():
                self.menuitem_copy_web_link.activate()

        # select all
        if (event.keyval == Gdk.keyval_from_name("a") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_select_all.get_sensitive():
                self.menuitem_select_all.activate()

        # search
        if (event.keyval == Gdk.keyval_from_name("f") and
            event.state == Gdk.ModifierType.CONTROL_MASK):
            self.menuitem_edit.activate()
            if self.menuitem_search.get_sensitive():
                self.menuitem_search.activate()

        # back
        if ((event.keyval == Gdk.keyval_from_name("bracketleft") and
             event.state == Gdk.ModifierType.CONTROL_MASK) or
            ((event.keyval == Gdk.keyval_from_name("Left") or
              event.keyval == Gdk.keyval_from_name("KP_Left")) and
             event.state == Gdk.ModifierType.MOD1_MASK) or
            event.keyval == Gdk.keyval_from_name("BackSpace")):
            self.menuitem_view.activate()
            if self.menuitem_go_back.get_sensitive():
                self.menuitem_go_back.activate()

        # forward
        if ((event.keyval == Gdk.keyval_from_name("bracketright") and
             event.state == Gdk.ModifierType.CONTROL_MASK) or
            ((event.keyval == Gdk.keyval_from_name("Right") or
              event.keyval == Gdk.keyval_from_name("KP_Right")) and
             event.state == Gdk.ModifierType.MOD1_MASK)):
            self.menuitem_view.activate()
            if self.menuitem_go_forward.get_sensitive():
                self.menuitem_go_forward.activate()
            
    def on_window_main_button_press_event(self, widget, event):
        """
        Implement back/forward navigation via mouse navigation keys using
        the same button codes as used in Nautilus.
        """
        if event.button == MOUSE_EVENT_BACK_BUTTON:
            self.menuitem_view.activate()
            if self.menuitem_go_back.get_sensitive():
                self.menuitem_go_back.activate()
        elif event.button == MOUSE_EVENT_FORWARD_BUTTON:
            self.menuitem_view.activate()
            if self.menuitem_go_forward.get_sensitive():
                self.menuitem_go_forward.activate()
        
    def _on_lp_login(self, lp, token):
        self._lp_login_successful = True
        private_archives = self.glaunchpad.get_subscribed_archives()
        self.view_switcher.get_model().channel_manager.feed_in_private_sources_list_entries(
            private_archives)

    def _on_sso_login(self, sso, oauth_result):
        self._sso_login_successful = True
        # consumer key is the openid identifier
        self.scagent.query_available_for_me(oauth_result["token"],
                                            oauth_result["consumer_key"])

    def _on_style_updated(self, widget, init_css_callback, *args):
        init_css_callback(widget, *args)
        return

    def _available_for_me_result(self, scagent, result_list):
        #print "available_for_me_result", result_list
        from softwarecenter.db.update import (
            add_from_purchased_but_needs_reinstall_data)
        available_for_me_query = add_from_purchased_but_needs_reinstall_data(
            result_list, self.db, self.cache)
        self.available_pane.on_previous_purchases_activated(available_for_me_query) 
        
    def on_application_request_action(self, widget, app, addons_install, addons_remove, action):
        """callback when an app action is requested from the appview,
           if action is "remove", must check if other dependencies have to be
           removed as well and show a dialog in that case
        """
        LOG.debug("on_application_action_requested: '%s' %s" % (app, action))
        appdetails = app.get_details(self.db)
        if action == "remove":
            if not dependency_dialogs.confirm_remove(None, self.datadir, app,
                                                     self.db, self.icons):
                    # craft an instance of TransactionFinishedResult to send with the
                    # transaction-stopped signal
                    result = TransactionFinishedResult(None, False)
                    result.pkgname = app.pkgname
                    self.backend.emit("transaction-stopped", result)
                    return
        elif action == "install":
            # If we are installing a package, check for dependencies that will 
            # also be removed and show a dialog for confirmation
            # generic removal text (fixing LP bug #554319)
            if not dependency_dialogs.confirm_install(None, self.datadir, app, 
                                                      self.db, self.icons):
                    # craft an instance of TransactionFinishedResult to send with the
                    # transaction-stopped signal
                    result = TransactionFinishedResult(None, False)
                    result.pkgname = app.pkgname
                    self.backend.emit("transaction-stopped", result)
                    return

        # this allows us to 'upgrade' deb files
        if action == 'upgrade' and app.request and type(app) == DebFileApplication:
            action = 'install'
 
        # action_func is one of:  "install", "remove", "upgrade", "apply_changes"
        action_func = getattr(self.backend, action)
        if action == 'install':
            # the package.deb path name is in the request
            if app.request and type(app) == DebFileApplication:
                debfile_name = app.request
            else:
                debfile_name = None
            action_func(app.pkgname, app.appname, appdetails.icon, debfile_name, addons_install, addons_remove)
        elif callable(action_func):
            action_func(app.pkgname, app.appname, appdetails.icon, addons_install=addons_install, addons_remove=addons_remove)
        else:
            LOG.error("Not a valid action in AptdaemonBackend: '%s'" % action)
            
    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(Icons.MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    # File Menu
    def on_menu_file_activate(self, menuitem):
        """Enable/disable install/remove"""
        LOG.debug("on_menu_file_activate")

        # reset it all
        self.menuitem_install.set_sensitive(False)
        self.menuitem_remove.set_sensitive(False)

        # get our active pane
        vm = get_viewmanager()
        if vm is None:
            return False
        self.active_pane = vm.get_view_widget(vm.get_active_view())
        if self.active_pane is None:
            return False

        # determine the current app
        app = self.active_pane.get_current_app()
        if not app:
            return False

        # wait for the cache to become ready (if needed)
        if not self.cache.ready:
            GObject.timeout_add(
                100, lambda: self.on_menu_file_activate(menuitem))
            return False

        # update menu items
        pkg_state = None
        error = None
        # FIXME:  Use a Gtk.Action for the Install/Remove/Buy/Add Source/Update Now action
        #         so that all UI controls (menu item, applist view button and appdetails
        #         view button) are managed centrally:  button text, button sensitivity,
        #         and callback method
        # FIXME:  Add buy support here by implementing the above
        appdetails = app.get_details(self.db)
        if appdetails:
            pkg_state = appdetails.pkg_state
            error = appdetails.error
        if app.pkgname in self.active_pane.app_view.tree_view._action_block_list:
            return False
        elif pkg_state == PkgStates.UPGRADABLE or pkg_state == PkgStates.REINSTALLABLE and not error:
            self.menuitem_install.set_sensitive(True)
            self.menuitem_remove.set_sensitive(True)
        elif pkg_state == PkgStates.INSTALLED:
            self.menuitem_remove.set_sensitive(True)
        elif pkg_state == PkgStates.UNINSTALLED and not error:
            self.menuitem_install.set_sensitive(True)
        elif (not pkg_state and 
              not self.active_pane.is_category_view_showing() and 
              app.pkgname in self.cache and 
              not app.pkgname in self.active_pane.app_view.tree_view._action_block_list and
              not error):
            # when does this happen?
            pkg = self.cache[app.pkgname]
            installed = bool(pkg.installed)
            self.menuitem_install.set_sensitive(not installed)
            self.menuitem_remove.set_sensitive(installed)
        # return False to ensure that a possible GObject.timeout_add ends
        return False

    def on_menuitem_launchpad_private_ppas_activate(self, menuitem):
        from backend.launchpad import GLaunchpad
        self.glaunchpad = GLaunchpad()
        self.glaunchpad.connect("login-successful", self._on_lp_login)
        from view.logindialog import LoginDialog
        d = LoginDialog(self.glaunchpad, self.datadir, parent=self.window_main)
        d.login()

    def _create_dbus_sso_if_needed(self):
        if not self.sso:
            from softwarecenter.backend.login_sso import get_sso_backend
            # see bug #773214 for the rational
            #appname = _("Ubuntu Software Center Store")
            appname = "Ubuntu Software Center Store"
            help_text = _("To reinstall previous purchases, sign in to the "
                          "Ubuntu Single Sign-On account you used to pay for them.")
            #window = self.window_main.get_window()
            #xid = self.get_window().xid
            xid = 0
            self.sso = get_sso_backend(xid,
                                       appname,
                                       help_text)
            self.sso.connect("login-successful", self._on_sso_login)

    def _login_via_dbus_sso(self):
        self._create_dbus_sso_if_needed()
        self.sso.login()

    def _create_scagent_if_needed(self):
        if not self.scagent:
            from softwarecenter.backend.scagent import SoftwareCenterAgent
            self.scagent = SoftwareCenterAgent()
            self.scagent.connect("available-for-me", self._available_for_me_result)
            
    def on_menuitem_reinstall_purchases_activate(self, menuitem):
        self.view_manager.set_active_view(ViewPages.AVAILABLE)
        self.available_pane.show_appview_spinner()
        self._create_scagent_if_needed()
        self._login_via_dbus_sso()
            
    def on_menuitem_deauthorize_computer_activate(self, menuitem):
    
        # FIXME: need Ubuntu SSO username here
        # account_name = get_person_from_config()
        account_name = None
        
        # get a list of installed purchased packages
        installed_purchased_packages = self.db.get_installed_purchased_packages()

        # display the deauthorize computer dialog
        deauthorize = deauthorize_dialog.deauthorize_computer(None,
                                                              self.datadir,
                                                              self.db,
                                                              self.icons,
                                                              account_name,
                                                              installed_purchased_packages)
        if deauthorize:
            # clear the ubuntu SSO token for this account
            # FIXME: this needs to be consolidated - one token is 
            #        aquired for purchase in utils/submit_review.py
            #        the other one in softwarecenter/app.py
            clear_token_from_ubuntu_sso(_("Ubuntu Software Center"))
            clear_token_from_ubuntu_sso(_("Ubuntu Software Center Store"))
            
            # uninstall the list of purchased packages
            # TODO: do we need to check for dependencies and show a removal
            # dialog for that case?  seems not since these are purchased apps
            for pkgname in installed_purchased_packages:
                app = Application(pkgname=pkgname)
                appdetails = app.get_details(self.db)
                self.backend.remove(app.pkgname, app.appname, appdetails.icon)
            
            # TODO: remove the corresponding private PPA sources
            # FIXME: this should really be done using aptdaemon, update this if/when
            #        remove repository support is added to aptdaemon
            # (private-ppa.launchpad.net_commercial-ppa-uploaders*)
            purchased_sources = glob.glob("/etc/apt/sources.list.d/private-ppa.launchpad.net_commercial-ppa-uploaders*")
            for source in purchased_sources:
                print("source: %s" % source)

    def on_menuitem_sync_between_computers_activate(self, menuitem):
        if self.view_manager.get_active_view() != ViewPages.INSTALLED:
            pane = self.view_manager.set_active_view(ViewPages.INSTALLED)
            state = pane.state.copy()
            state.channel = AllInstalledChannel()
            page = None
            self.view_manager.display_page(pane, page, state)
            self.installed_pane.refresh_apps()
        get_oneconf_handler().sync_between_computers(True)
        
    def on_menuitem_install_activate(self, menuitem):
        app = self.active_pane.get_current_app()
        self.on_application_request_action(self, app, [], [], AppActions.INSTALL)

    def on_menuitem_remove_activate(self, menuitem):
        app = self.active_pane.get_current_app()
        self.on_application_request_action(self, app, [], [], AppActions.REMOVE)
        
    def on_menuitem_close_activate(self, widget):
        Gtk.main_quit()

# Edit Menu
    def on_menu_edit_activate(self, menuitem):
        """
        Check whether the search field is focused and if so, focus some items
        """
        edit_menu_items = [self.menuitem_undo,
                           self.menuitem_redo,
                           self.menuitem_cut, 
                           self.menuitem_copy,
                           self.menuitem_copy_web_link,
                           self.menuitem_paste,
                           self.menuitem_delete,
                           self.menuitem_select_all,
                           self.menuitem_search]
        for item in edit_menu_items:
            item.set_sensitive(False)

        # get our active pane
        vm = get_viewmanager()
        if vm is None:
            return False
        self.active_pane = vm.get_view_widget(vm.get_active_view())

        if (self.active_pane and 
            self.active_pane.searchentry and
            self.active_pane.searchentry.get_visible()):
            # undo, redo, cut, copy, paste, delete, select_all sensitive 
            # if searchentry is focused (and other more specific conditions)
            if self.active_pane.searchentry.is_focus():
                if len(self.active_pane.searchentry._undo_stack) > 1:
                    self.menuitem_undo.set_sensitive(True)
                if len(self.active_pane.searchentry._redo_stack) > 0:
                    self.menuitem_redo.set_sensitive(True)
                bounds = self.active_pane.searchentry.get_selection_bounds()
                if bounds:
                    self.menuitem_cut.set_sensitive(True)
                    self.menuitem_copy.set_sensitive(True)
                self.menuitem_paste.set_sensitive(True)
                if self.active_pane.searchentry.get_text():
                    self.menuitem_delete.set_sensitive(True)
                    self.menuitem_select_all.set_sensitive(True)
            # search sensitive if searchentry is not focused
            else:
                self.menuitem_search.set_sensitive(True)

        # weblink
        if self.active_pane:
            app = self.active_pane.get_current_app()
            if app and app.pkgname:
                self.menuitem_copy_web_link.set_sensitive(True)

        # details view
        if (self.active_pane and 
            self.active_pane.is_app_details_view_showing()):

            self.menuitem_select_all.set_sensitive(True)
            sel_text = self.active_pane.app_details_view.desc.get_selected_text()

            if sel_text:
                self.menuitem_copy.set_sensitive(True)

    def on_menuitem_undo_activate(self, menuitem):
        self.active_pane.searchentry.undo()
        
    def on_menuitem_redo_activate(self, menuitem):
        self.active_pane.searchentry.redo()

    def on_menuitem_cut_activate(self, menuitem):
        self.active_pane.searchentry.cut_clipboard()

    def on_menuitem_copy_activate(self, menuitem):
        if (self.active_pane and
            self.active_pane.is_app_details_view_showing()):

            self.active_pane.app_details_view.desc.copy_clipboard()

        elif self.active_pane:
            self.active_pane.searchentry.copy_clipboard()

    def on_menuitem_paste_activate(self, menuitem):
        self.active_pane.searchentry.paste_clipboard()

    def on_menuitem_delete_activate(self, menuitem):
        self.active_pane.searchentry.set_text("")

    def on_menuitem_select_all_activate(self, menuitem):
        if (self.active_pane and
            self.active_pane.is_app_details_view_showing()):

            self.active_pane.app_details_view.desc.select_all()
            self.active_pane.app_details_view.desc.grab_focus()

        elif self.active_pane:
            self.active_pane.searchentry.select_region(0, -1)

    def on_menuitem_copy_web_link_activate(self, menuitem):
        app = self.active_pane.get_current_app()
        if app:
            display = Gdk.Display.get_default()
            selection = Gdk.Atom.intern ("CLIPBOARD", False)
            clipboard = Gtk.Clipboard.get_for_display(display, selection)
            clipboard.set_text(self.WEBLINK_URL % app.pkgname, -1)

    def on_menuitem_search_activate(self, widget):
        if self.active_pane:
            self.active_pane.searchentry.grab_focus()
            self.active_pane.searchentry.select_region(0, -1)

    def on_menuitem_software_sources_activate(self, widget):
        self.window_main.set_sensitive(False)
        # run software-properties-gtk
        window = self.window_main.get_window()
        if hasattr(window, 'xid'):
            xid = window.xid
        else:
            xid = 0

        p = subprocess.Popen(
            ["/usr/bin/software-properties-gtk", 
             "-n", 
             "-t", str(xid)])
        # Monitor the subprocess regularly
        GObject.timeout_add(100, self._poll_software_sources_subprocess, p)

    def _poll_software_sources_subprocess(self, popen):
        ret = popen.poll()
        if ret is None:
            # Keep monitoring
            return True
        # A return code of 1 means that the sources have changed
        if ret == 1:
            self.run_update_cache()
        self.window_main.set_sensitive(True)
        # Stop monitoring
        return False

# View Menu
    def on_menu_view_activate(self, menuitem):
        vm = get_viewmanager()
        if vm is None:
            self.menuitem_view_all.set_sensitive(False)
            self.menuitem_view_supported_only.set_sensitive(False)
            self.menuitem_go_back.set_sensitive(False)
            self.menuitem_go_forward.set_sensitive(False)
            return False
            
        left_sensitive = vm.back_forward.left.get_sensitive()
        self.menuitem_go_back.set_sensitive(left_sensitive)
        right_sensitive = vm.back_forward.right.get_sensitive()
        self.menuitem_go_forward.set_sensitive(right_sensitive)

        self.menuitem_view.blocked = True

        # get our active pane
        self.active_pane = vm.get_view_widget(vm.get_active_view())
        if (self.active_pane and
            self.active_pane == self.available_pane or
            self.active_pane == self.installed_pane):
            self.menuitem_view_all.set_sensitive(True)
            self.menuitem_view_supported_only.set_sensitive(True)

            from softwarecenter.db.appfilter import get_global_filter
            supported_only = get_global_filter().supported_only
            self.menuitem_view_all.set_active(not supported_only)
            self.menuitem_view_supported_only.set_active(supported_only)
        else:
            self.menuitem_view_all.set_sensitive(False)
            self.menuitem_view_supported_only.set_sensitive(False)

        self.menuitem_view.blocked = False

    def on_menuitem_view_all_activate(self, widget):
        if self.menuitem_view.blocked:
            return
        from softwarecenter.db.appfilter import get_global_filter
        if get_global_filter().supported_only == True:
            get_global_filter().supported_only = False

            self.available_pane.refresh_apps()
            try:
                self.installed_pane.refresh_apps()
            except: # may not be initialised
                pass

    def on_menuitem_view_supported_only_activate(self, widget):
        if self.menuitem_view.blocked:
            return
        from softwarecenter.db.appfilter import get_global_filter
        if get_global_filter().supported_only == False:
            get_global_filter().supported_only = True

            self.available_pane.refresh_apps()
            try:
                self.installed_pane.refresh_apps()
            except: # may not be initialised
                pass

            # navigate up if the details page is no longer available
            #~ ap = self.active_pane
            #~ if (ap and ap.is_app_details_view_showing and ap.app_details_view.app and
                #~ not self.distro.is_supported(self.cache, None, ap.app_details_view.app.pkgname)):
                #~ if len(ap.app_view.get_model()) == 0:
                    #~ ap.navigation_bar.navigate_up_twice()
                #~ else:
                    #~ ap.navigation_bar.navigate_up()
                #~ ap.on_application_selected(None, None)    

            #~ # navigate up if the list page is empty
            #~ elif (ap and ap.is_applist_view_showing() and 
                #~ len(ap.app_view.get_model()) == 0):
                #~ ap.navigation_bar.navigate_up()
                #~ ap.on_application_selected(None, None)    

    def on_navhistory_back_action_activate(self, navhistory_back_action=None):
        vm = get_viewmanager()
        vm.nav_back()

    def on_navhistory_forward_action_activate(self, navhistory_forward_action=None):
        vm = get_viewmanager()
        vm.nav_forward()

# Help Menu
    def on_menuitem_about_activate(self, widget):
        self.aboutdialog.set_version(VERSION)
        self.aboutdialog.set_transient_for(self.window_main)
        self.aboutdialog.show()

    def on_menuitem_help_activate(self, menuitem):
        # run yelp
        p = subprocess.Popen(["yelp","ghelp:software-center"])
        # collect the exit status (otherwise we leave zombies)
        GObject.timeout_add_seconds(1, lambda p: p.poll() == None, p)

    def on_menuitem_developer_activate(self, menuitem):
        webbrowser.open("http://developer.ubuntu.com/")
            
    def _ask_and_repair_broken_cache(self):
        # wait until the window window is available
        if self.window_main.props.visible == False:
            GObject.timeout_add_seconds(1, self._ask_and_repair_broken_cache)
            return
        if dialogs.confirm_repair_broken_cache(self.window_main,
                                                      self.datadir):
            self.backend.fix_broken_depends()

    def _on_apt_cache_broken(self, aptcache):
        self._ask_and_repair_broken_cache()

    def _on_transaction_finished(self, backend, result):
        """ callback when an application install/remove transaction 
            (or a cache reload) has finished 
        """
        self.cache.open()

    def on_channels_changed(self, backend, res):
        """ callback when the set of software channels has changed """
        LOG.debug("on_channels_changed %s" % res)
        if res:
            # reopen the database, this will ensure that the right signals
            # are send and triggers "refresh_apps"
            # and refresh the displayed app in the details as well
            self.db.reopen()

    # helper

    def run_update_cache(self):
        """update the apt cache (e.g. after new sources where added """
        self.backend.reload()

    def update_app_list_view(self, channel=None):
        """Helper that updates the app view list """
        if self.active_pane is None:
            return
        if channel is None and self.active_pane.is_category_view_showing():
            return
        if channel:
            self.channel_pane.set_channel(channel)
            self.active_pane.refresh_apps()

    def _on_database_rebuilding_handler(self, is_rebuilding):
        LOG.debug("_on_database_rebuilding_handler %s" % is_rebuilding)
        self._database_is_rebuilding = is_rebuilding

        if is_rebuilding:
            pass
        else:
            # we need to reopen when the database finished updating
            self.db.reopen()

    def setup_database_rebuilding_listener(self):
        """
        Setup system bus listener for database rebuilding
        """
        self._database_is_rebuilding = False
        # get dbus
        try:
            bus = dbus.SystemBus()
        except:
            LOG.exception("could not get system bus")
            return
        # check if its currently rebuilding (most likely not, so we
        # just ignore errors from dbus because the interface
        try:
            proxy_obj = bus.get_object("com.ubuntu.Softwarecenter",
                                       "/com/ubuntu/Softwarecenter")
            iface = dbus.Interface(proxy_obj, "com.ubuntu.Softwarecenter")
            res = iface.IsRebuilding()
            self._on_database_rebuilding_handler(res)
        except Exception as e:
            LOG.debug("query for the update-database exception '%s' (probably ok)" % e)

        # add signal handler
        bus.add_signal_receiver(self._on_database_rebuilding_handler,
                                "DatabaseRebuilding",
                                "com.ubuntu.Softwarecenter")

    def setup_dbus_or_bring_other_instance_to_front(self, args):
        """ 
        This sets up a dbus listener
        """
        try:
            bus = dbus.SessionBus()
        except:
            LOG.exception("could not initiate dbus")
            return
        # if there is another Softwarecenter running bring it to front
        # and exit, otherwise install the dbus controller
        try:
            proxy_obj = bus.get_object('com.ubuntu.Softwarecenter', 
                                       '/com/ubuntu/Softwarecenter')
            iface = dbus.Interface(proxy_obj, 'com.ubuntu.SoftwarecenterIFace')
            if args:
                iface.bringToFront(args)
            else:
                # None can not be transported over dbus
                iface.bringToFront('nothing-to-show')
            sys.exit()
        except dbus.DBusException:
            bus_name = dbus.service.BusName('com.ubuntu.Softwarecenter',bus)
            self.dbusControler = SoftwarecenterDbusController(self, bus_name)

    def show_available_packages(self, packages):
        """ Show packages given as arguments in the available_pane
            If the list of packages is only one element long show that,
            otherwise turn it into a comma seperated search
        """
        # strip away the apt: prefix
        if packages and packages[0].startswith("apt:///"):
            # this is for 'apt:pkgname' in alt+F2 in gnome
            packages[0] = packages[0].partition("apt:///")[2]
        elif packages and packages[0].startswith("apt://"):
            packages[0] = packages[0].partition("apt://")[2]
        elif packages and packages[0].startswith("apt:"):
            packages[0] = packages[0].partition("apt:")[2]

        # allow s-c to be called with a search term
        if packages and packages[0].startswith("search:"):
            packages[0] = packages[0].partition("search:")[2]
            self.available_pane.init_view()
            self.available_pane.searchentry.set_text(" ".join(packages))
            return

        if len(packages) == 1:
            request = packages[0]

            # are we dealing with a path?
            if os.path.exists(request) and not os.path.isdir(request):
                if not request.startswith('/'):
                # we may have been given a relative path
                    request = os.path.join(os.getcwd(), request)
                app = DebFileApplication(request)
            else:
                # package from archive
                # if there is a "/" in the string consider it as tuple
                # of (pkgname, appname) for exact matching (used by
                # e.g. unity
                (pkgname, sep, appname) = packages[0].partition("/")
                app = Application(appname, pkgname)

            @wait_for_apt_cache_ready
            def show_app(self, app):
                # if the pkg is installed, show it in the installed pane
                if (app.pkgname in self.cache and 
                    self.cache[app.pkgname].installed):
                    self.installed_pane.init_view()
                    self.installed_pane.show_app(app)
                else:
                    self.available_pane.init_view()
                    self.available_pane.show_app(app)
            show_app(self, app)
            return    
        elif len(packages) > 1:
            # turn multiple packages into a search with ","
            self.available_pane.init_view()
            self.available_pane.searchentry.set_text(",".join(packages))
            return
        # normal startup, queue showing the lobby when we are ready
        def show_lobby():
            self.view_manager.set_active_view(ViewPages.AVAILABLE)
        GObject.idle_add(show_lobby)

    def restore_state(self):
        if self.config.has_option("general", "size"):
            (x, y) = self.config.get("general", "size").split(",")
            self.window_main.set_default_size(int(x), int(y))
        else:
            # on first launch, specify the default window size to take advantage
            # of the available screen real estate (but set a reasonable limit
            # in case of a crazy-huge monitor)
            screen_height = Gdk.Screen.height()
            screen_width = Gdk.Screen.width()
            self.window_main.set_default_size(min(int(.85 * screen_width), 1200),
                                              min(int(.85 * screen_height), 800))
        if (self.config.has_option("general", "maximized") and
            self.config.getboolean("general", "maximized")):
            self.window_main.maximize()

    def save_state(self):
        LOG.debug("save_state")
        # this happens on a delete event, we explicitely save_state() there
        window = self.window_main.get_window()
        if window is None:
            return
        if not self.config.has_section("general"):
            self.config.add_section("general")
        maximized = window.get_state() & Gdk.WindowState.MAXIMIZED
        if maximized:
            self.config.set("general", "maximized", "True")
        else:
            self.config.set("general", "maximized", "False")
            # size only matters when non-maximized
            size = self.window_main.get_size() 
            self.config.set("general","size", "%s, %s" % (size[0], size[1]))
        self.config.write()

    def run(self, args):
        self.window_main.show_all()
        # support both "pkg1 pkg" and "pkg1,pkg2" (and pkg1,pkg2 pkg3)
        if args:
            for (i, arg) in enumerate(args[:]):
                if "," in arg:
                    args.extend(arg.split(","))
                    del args[i]

        # FIXME: make this more predictable and less random
        # show args when the app is ready
        self.show_available_packages(args)

        atexit.register(self.save_state)
        SimpleGtkbuilderApp.run(self)
