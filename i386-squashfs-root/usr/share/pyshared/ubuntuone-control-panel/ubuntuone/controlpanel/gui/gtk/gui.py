# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
#          Eric Casteleijn <eric.casteleijn@canonical.com>
#
# Copyright 2010 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The user interface for the control panel for Ubuntu One."""

from __future__ import division

import os

from functools import wraps

import dbus
import gtk
import gobject

from dbus.mainloop.glib import DBusGMainLoop
from ubuntu_sso import networkstate
# pylint: disable=E0611,F0401
from ubuntuone.platform.credentials import (
    APP_NAME as U1_APP_NAME,
    CredentialsManagementTool,
)
# pylint: enable=E0611,F0401

# Wildcard import ubuntuone.controlpanel.gui
# pylint: disable=W0401, W0614
from ubuntuone.controlpanel.gui import *
# pylint: enable=W0401, W0614
from ubuntuone.controlpanel.gui.gtk import (
    DBUS_IFACE_GUI, DBUS_BUS_NAME as DBUS_BUS_NAME_GUI,
    DBUS_PATH as DBUS_PATH_GUI, package_manager)
from ubuntuone.controlpanel.gui.gtk.widgets import LabelLoading, PanelTitle
# Use ubiquity package when ready (LP: #673665)
from ubuntuone.controlpanel.gui.gtk.widgets import GreyableBin

from ubuntuone.controlpanel import (DBUS_BUS_NAME, DBUS_PREFERENCES_PATH,
    DBUS_PREFERENCES_IFACE, TRANSLATION_DOMAIN, backend)
from ubuntuone.controlpanel.backend import (DEVICE_TYPE_PHONE,
    DEVICE_TYPE_COMPUTER)
from ubuntuone.controlpanel.dbus_service import bool_str
from ubuntuone.controlpanel.logger import setup_logging, log_call
from ubuntuone.controlpanel.utils import (get_data_file,
    ERROR_TYPE, ERROR_MESSAGE)


try:
    from gi.repository import Unity     # pylint: disable=E0611
    USE_LIBUNITY = True
    U1_DOTDESKTOP = "ubuntuone-installer.desktop"
except ImportError:
    USE_LIBUNITY = False

logger = setup_logging('gtk.gui')


WARNING_MARKUP = '<span foreground="%s"><b>%%s</b></span>' % ERROR_COLOR

CP_WMCLASS_NAME = 'ubuntuone-control-panel-gtk'
CP_WMCLASS_CLASS = 'ubuntuone-installer'


def error_handler(*args, **kwargs):
    """Log errors when calling D-Bus methods in a async way."""
    logger.error('Error handler received: %r, %r', args, kwargs)


def register_service(bus):
    """Try to register DBus service for making sure we run only one instance.

    Return True if succesfully registered, False if already running.
    """
    name = bus.request_name(DBUS_BUS_NAME_GUI,
                                    dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
    return name != dbus.bus.REQUEST_NAME_REPLY_EXISTS


def publish_service(window=None, switch_to='', alert=False):
    """Publish the service on DBus."""
    if window is None:
        window = ControlPanelWindow(switch_to=switch_to, alert=alert)
    return ControlPanelService(window)


def main(switch_to='', alert=False):
    """Hook the DBus listeners and start the main loop."""
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    if register_service(bus):
        publish_service(switch_to=switch_to, alert=alert)
    else:
        obj = bus.get_object(DBUS_BUS_NAME_GUI, DBUS_PATH_GUI)
        service = dbus.Interface(obj, dbus_interface=DBUS_IFACE_GUI)

        def gui_error_handler(*args, **kwargs):
            """Log errors when calling D-Bus methods in a async way."""
            logger.error('Error handler received: %r, %r', args, kwargs)
            gtk.main_quit()

        def gui_reply_handler(*args, **kwargs):
            """Exit when done."""
            gtk.main_quit()

        service.switch_to_alert(
            switch_to, alert, reply_handler=gui_reply_handler,
            error_handler=gui_error_handler)

    gtk.main()


def on_size_allocate(widget, allocation, label):
    """Resize labels according to who 'widget' is being resized."""
    label.set_size_request(allocation.width - 2, -1)


@log_call(logger.debug)
def uri_hook(button, uri, *args, **kwargs):
    """Open an URI or do nothing if URI is not an URL."""
    if uri.startswith('http') or uri.startswith(FILE_URI_PREFIX):
        gtk.show_uri(None, uri, gtk.gdk.CURRENT_TIME)


class ControlPanelMixin(object):
    """A basic mixin class to provide common functionality to widgets."""

    def __init__(self, filename=None, backend_instance=None):
        if backend_instance is not None:
            self.backend = backend_instance
        else:
            bus = dbus.SessionBus()
            try:
                obj = bus.get_object(DBUS_BUS_NAME,
                                     DBUS_PREFERENCES_PATH,
                                     follow_name_owner_changes=True)
                iface = DBUS_PREFERENCES_IFACE
                self.backend = dbus.Interface(obj, dbus_interface=iface)
            except dbus.exceptions.DBusException:
                logger.exception('Can not connect to DBus at %r',
                                 (DBUS_BUS_NAME, DBUS_PREFERENCES_PATH))
                raise

        if filename is not None:
            builder = gtk.Builder()
            builder.set_translation_domain(TRANSLATION_DOMAIN)
            builder.add_from_file(get_data_file(os.path.join('gtk', filename)))
            builder.connect_signals(self)

            # untested directly
            for obj in builder.get_objects():
                name = getattr(obj, 'name', None)
                if name is None and isinstance(obj, gtk.Buildable):
                    # work around bug lp:507739
                    name = gtk.Buildable.get_name(obj)
                if name is None:
                    logger.warning("%s has no name (??)", obj)
                else:
                    setattr(self, name, obj)

        logger.debug('%s: started.', self.__class__.__name__)

    def _set_warning(self, message, label):
        """Set 'message' as warning in 'label'."""
        label.set_markup(WARNING_MARKUP % message)
        label.show()


class UbuntuOneBin(gtk.VBox):
    """A Ubuntu One bin."""

    TITLE = ''

    def __init__(self, title=None):
        gtk.VBox.__init__(self)
        self._is_processing = False

        if title is None:
            title = self.TITLE

        title = '<span font_size="large">%s</span>' % title
        self.title = PanelTitle(markup=title)
        self.pack_start(self.title, expand=False)

        self.message = LabelLoading(LOADING)
        self.pack_start(self.message, expand=False)

        self.connect('size-allocate', on_size_allocate, self.title)
        self.show_all()

    def _get_is_processing(self):
        """Is this panel processing a request?"""
        return self._is_processing

    def _set_is_processing(self, new_value):
        """Set if this panel is processing a request."""
        if new_value:
            self.message.start()
            self.set_sensitive(False)
        else:
            self.message.stop()
            self.set_sensitive(True)

        self._is_processing = new_value

    is_processing = property(fget=_get_is_processing, fset=_set_is_processing)

    @log_call(logger.debug)
    def on_success(self, message=''):
        """Use this callback to stop the Loading and show 'message'."""
        self.message.stop()
        self.message.set_markup(message)

    @log_call(logger.error)
    def on_error(self, message=None, error_dict=None):
        """Use this callback to stop the Loading and set a warning message."""
        if message is None and error_dict is None:
            message = VALUE_ERROR
        elif message is None and error_dict is not None:
            error_type = error_dict.get(ERROR_TYPE, UNKNOWN_ERROR)
            error_msg = error_dict.get(ERROR_MESSAGE)
            if error_msg:
                message = "%s (%s: %s)" % (VALUE_ERROR, error_type, error_msg)
            else:
                message = "%s (%s)" % (VALUE_ERROR, error_type)

        assert message is not None

        self.message.stop()
        self.message.set_markup(WARNING_MARKUP % message)


class OverviewPanel(GreyableBin, ControlPanelMixin):
    """The overview panel. Introduces Ubuntu One to the not logged user."""

    __gsignals__ = {
        'credentials-found': (gobject.SIGNAL_RUN_FIRST,  gobject.TYPE_NONE,
                              (gobject.TYPE_BOOLEAN, gobject.TYPE_PYOBJECT)),
    }

    def __init__(self, main_window):
        GreyableBin.__init__(self)
        creds_backend = CredentialsManagementTool()
        ControlPanelMixin.__init__(self, filename='overview.ui',
                                   backend_instance=creds_backend)
        self.add(self.itself)
        self.banner.set_from_file(get_data_file(OVERVIEW_BANNER))
        self.files_icon.set_from_file(get_data_file(FILES_ICON))
        self.music_stream_icon.set_from_file(get_data_file(MUSIC_STREAM_ICON))
        self.contacts_icon.set_from_file(get_data_file(CONTACTS_ICON))
        self.notes_icon.set_from_file(get_data_file(NOTES_ICON))

        self.warning_label.set_text('')
        self.warning_label.set_property('xalign', 0.5)

        self.connect_button.set_uri(CONNECT_BUTTON_LABEL)

        self.main_window = main_window
        self._credentials_are_new = False
        self.show()

        kw = dict(result_cb=self.on_network_state_changed)
        self.network_manager_state = networkstate.NetworkManagerState(**kw)
        self.network_manager_state.find_online_state()

    def _set_warning(self, message, label=None):
        """Set 'message' as global warning."""
        ControlPanelMixin._set_warning(self, message,
                                       label=self.warning_label)

    def _window_xid(self):
        """Return settings for credentials backend."""
        if self.main_window.window is not None:
            settings = {'window_id': str(self.main_window.window.xid)}
        else:
            settings = {}
        return settings

    def set_property(self, prop_name, new_value):
        """Override 'set_property' to disable buttons if prop is 'greyed'."""
        if prop_name == 'greyed':
            self.set_sensitive(not new_value)
        GreyableBin.set_property(self, prop_name, new_value)

    def set_sensitive(self, value):
        """Set the sensitiveness as per 'value'."""
        self.join_now_button.set_sensitive(value)
        self.connect_button.set_sensitive(value)

    def get_sensitive(self):
        """Return the sensitiveness."""
        result = self.join_now_button.get_sensitive() and \
                 self.connect_button.get_sensitive()
        return result

    def on_join_now_button_clicked(self, *a, **kw):
        """User wants to join now."""
        d = self.backend.register(**self._window_xid())
        d.addCallback(self.on_credentials_result)
        d.addErrback(self.on_credentials_error)
        self.set_property('greyed', True)
        self.warning_label.set_text('')

    def on_connect_button_clicked(self, *a, **kw):
        """User wants to connect now."""
        d = self.backend.login(**self._window_xid())
        d.addCallback(self.on_credentials_result)
        d.addErrback(self.on_credentials_error)
        self.set_property('greyed', True)
        self.warning_label.set_text('')

    def on_learn_more_button_clicked(self, *a, **kw):
        """User wants to learn more."""
        uri_hook(self.learn_more_button, LEARN_MORE_LINK)

    def on_credentials_result(self, result):
        """Process the credentials response.

        If 'result' is a non empty dict, they were found.
        If 'result' is an empty dict, they were not found.
        If 'result' is None, the user cancelled the process.

        """
        if result is None:
            self.on_authorization_denied()
        elif result == {}:
            self.on_credentials_not_found()
        else:
            self.on_credentials_found(result)

    @log_call(logger.info, with_args=False)
    def on_credentials_found(self, credentials):
        """Credentials backend notifies of credentials found."""
        self.set_property('greyed', False)
        self.emit('credentials-found', self._credentials_are_new, credentials)

    @log_call(logger.info)
    def on_credentials_not_found(self):
        """Creds backend notifies of credentials not found."""
        self._credentials_are_new = True
        self.set_property('greyed', False)

    @log_call(logger.error)
    def on_credentials_error(self, error_dict):
        """Creds backend notifies of an error when fetching credentials."""
        self.set_property('greyed', False)
        self._set_warning(CREDENTIALS_ERROR)

    @log_call(logger.info)
    def on_authorization_denied(self):
        """Creds backend notifies that user refused auth for 'app_name'."""
        self.set_property('greyed', False)

    @log_call(logger.info)
    def on_network_state_changed(self, state):
        """Network state is reported."""
        msg = ''
        if state is networkstate.OFFLINE:
            msg = NETWORK_OFFLINE % {'app_name': U1_APP_NAME}
            self.set_sensitive(False)
            self._set_warning(msg)
        else:
            self.set_sensitive(True)
            self.warning_label.set_text(msg)
            d = self.backend.find_credentials()
            d.addCallback(self.on_credentials_result)
            d.addErrback(self.on_credentials_error)


class DashboardPanel(UbuntuOneBin, ControlPanelMixin):
    """The dashboard panel. The user can manage the subscription."""

    TITLE = DASHBOARD_TITLE
    VALUE_ERROR = DASHBOARD_VALUE_ERROR

    def __init__(self, main_window=None):
        UbuntuOneBin.__init__(self)
        ControlPanelMixin.__init__(self, filename='dashboard.ui')
        self.add(self.itself)
        self.show()

        self.is_processing = True

        self.backend.connect_to_signal('AccountInfoReady',
                                       self.on_account_info_ready)
        self.backend.connect_to_signal('AccountInfoError',
                                       self.on_account_info_error)
        self.account.hide()

    @log_call(logger.debug)
    def on_account_info_ready(self, info):
        """Backend notifies of account info."""
        self.on_success()

        for i in (u'name', u'type', u'email'):
            label = getattr(self, '%s_label' % i)
            label.set_markup('%s' % (info[i]))
        self.account.show()

        self.is_processing = False

    @log_call(logger.error)
    def on_account_info_error(self, error_dict=None):
        """Backend notifies of an error when fetching account info."""
        self.on_error(message=self.VALUE_ERROR)
        self.is_processing = False


class VolumesPanel(UbuntuOneBin, ControlPanelMixin):
    """The volumes panel."""

    TITLE = FOLDERS_TITLE
    MAX_COLS = 8
    FREE_SPACE = '<span foreground="grey">%s</span>' % FREE_SPACE_TEXT
    NO_FREE_SPACE = '<span foreground="red"><b>%s</b></span>' % FREE_SPACE_TEXT
    ROW_HEADER = '<span font_size="large"><b>%s</b></span> %s'
    ROOT = '%s - <span foreground="%s" font_size="small">%s</span>'

    def __init__(self, main_window=None):
        UbuntuOneBin.__init__(self)
        ControlPanelMixin.__init__(self, filename='volumes.ui')
        self.add(self.itself)
        self.show_all()

        kw = dict(parent=main_window,
                  flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                  type=gtk.MESSAGE_WARNING,
                  buttons=gtk.BUTTONS_YES_NO)
        self.confirm_dialog = gtk.MessageDialog(**kw)

        # name, subscribed, icon name, show toggle, sensitive, icon size,
        # id, path
        self._empty_row = ('', False, '', False, False, gtk.ICON_SIZE_MENU,
                           None, None)

        self.backend.connect_to_signal('VolumesInfoReady',
                                       self.on_volumes_info_ready)
        self.backend.connect_to_signal('VolumesInfoError',
                                       self.on_volumes_info_error)
        self.backend.connect_to_signal('VolumeSettingsChanged',
                                       self.on_volume_settings_changed)
        self.backend.connect_to_signal('VolumeSettingsChangeError',
                                       self.on_volume_settings_change_error)

    def _process_name(self, name):
        """Tweak 'name' with a translatable music folder name."""
        if name == MUSIC_REAL_PATH:
            result = MUSIC_DISPLAY_NAME
        else:
            result = name
        return result

    def on_volumes_info_ready(self, info):
        """Backend notifies of volumes info."""

        self.volumes_store.clear()
        if not info:
            self.on_success(NO_FOLDERS)
            return
        else:
            self.on_success()

        for name, free_bytes, volumes in info:
            if backend.ControlBackend.NAME_NOT_SET in name:
                name = NAME_NOT_SET

            if name:
                name = name + "'s"
                # we already added user folders, let's add an empty row
                treeiter = self.volumes_store.append(None, self._empty_row)
            else:
                name = MY_FOLDERS

            scroll_to_cell = False
            if free_bytes == backend.ControlBackend.FREE_BYTES_NOT_AVAILABLE:
                free_bytes = ''
            else:
                free_bytes = int(free_bytes)
                if free_bytes < SHARES_MIN_SIZE_FULL:
                    free_bytes_str = self.NO_FREE_SPACE
                    scroll_to_cell = True
                else:
                    free_bytes_str = self.FREE_SPACE
                free_bytes_args = {'free_space': humanize(free_bytes)}
                free_bytes = free_bytes_str % free_bytes_args

            row = (self.ROW_HEADER % (name, free_bytes),
                   True, CONTACT_ICON_NAME, False, False,
                   gtk.ICON_SIZE_LARGE_TOOLBAR, None, None)
            treeiter = self.volumes_store.append(None, row)

            if scroll_to_cell:
                path = self.volumes_store.get_string_from_iter(treeiter)
                self.volumes_view.scroll_to_cell(path)

            for volume in volumes:
                sensitive = True
                name = self._process_name(volume[u'display_name'])
                icon_name = FOLDER_ICON_NAME

                is_root = volume[u'type'] == backend.ControlBackend.ROOT_TYPE
                is_share = volume[u'type'] == backend.ControlBackend.SHARE_TYPE

                if is_root:
                    sensitive = False
                    name = self.ROOT % (name, ORANGE, ALWAYS_SUBSCRIBED)
                elif is_share:
                    icon_name = SHARE_ICON_NAME
                elif name == MUSIC_DISPLAY_NAME:
                    icon_name = MUSIC_ICON_NAME

                if volume[u'path'] is None:
                    logger.warning('on_volumes_info_ready: about to store a '
                                   'volume with None path: %r', volume)

                row = (name, bool(volume[u'subscribed']), icon_name, True,
                       sensitive, gtk.ICON_SIZE_MENU, volume['volume_id'],
                       volume[u'path'])

                if is_root:  # root should go first!
                    self.volumes_store.prepend(treeiter, row)
                else:
                    self.volumes_store.append(treeiter, row)

        self.volumes_view.expand_all()
        self.volumes_view.show_all()

        self.is_processing = False

    @log_call(logger.error)
    def on_volumes_info_error(self, error_dict=None):
        """Backend notifies of an error when fetching volumes info."""
        self.on_error(error_dict=error_dict)

    @log_call(logger.info)
    def on_volume_settings_changed(self, volume_id):
        """The settings for 'volume_id' were changed."""
        self.is_processing = False

    @log_call(logger.error)
    def on_volume_settings_change_error(self, volume_id, error_dict=None):
        """The settings for 'volume_id' were not changed."""
        self.load()

    def on_subscribed_toggled(self, widget, path, *args, **kwargs):
        """The user toggled 'widget'."""
        treeiter = self.volumes_store.get_iter(path)
        volume_id = self.volumes_store.get_value(treeiter, 6)
        volume_path = self.volumes_store.get_value(treeiter, 7)
        subscribed = self.volumes_store.get_value(treeiter, 1)

        response = gtk.RESPONSE_YES
        if not subscribed and os.path.exists(volume_path):
            self.confirm_dialog.set_markup(FOLDERS_CONFIRM_MERGE %
                                           {'folder_path': volume_path})
            response = self.confirm_dialog.run()
            self.confirm_dialog.hide()

        if response == gtk.RESPONSE_YES:
            subscribed = not subscribed
            self.volumes_store.set_value(treeiter, 1, subscribed)
            self.backend.change_volume_settings(volume_id,
                {'subscribed': bool_str(subscribed)},
                reply_handler=NO_OP, error_handler=error_handler)

            self.is_processing = True

    def on_volumes_view_row_activated(self, widget, path, *args, **kwargs):
        """The user double clicked on a row."""
        treeiter = self.volumes_store.get_iter(path)
        volume_path = self.volumes_store.get_value(treeiter, 7)
        if volume_path is None:
            logger.warning('on_volumes_view_row_activated: volume_path for '
                           'tree_path %r is None', path)
        elif not os.path.exists(volume_path):
            logger.warning('on_volumes_view_row_activated: path %r '
                           'does not exist', volume_path)
        else:
            uri_hook(None, FILE_URI_PREFIX + volume_path)

    def load(self):
        """Load the volume list."""
        self.backend.volumes_info(reply_handler=NO_OP,
                                  error_handler=error_handler)
        self.is_processing = True


class SharesPanel(UbuntuOneBin, ControlPanelMixin):
    """The shares panel - NOT IMPLEMENTED YET."""

    TITLE = SHARES_TITLE

    def __init__(self, main_window=None):
        UbuntuOneBin.__init__(self)
        ControlPanelMixin.__init__(self)
        self.show_all()
        self.on_success('Not implemented yet.')


class Device(gtk.EventBox, ControlPanelMixin):
    """The device widget."""

    def __init__(self, confirm_remove_dialog=None):
        gtk.EventBox.__init__(self)
        ControlPanelMixin.__init__(self, filename='device.ui')

        self.confirm_dialog = confirm_remove_dialog
        self._updating = False
        self._last_settings = {}
        self.id = None
        self.is_local = False
        self.configurable = False

        self.update(device_id=None, device_name='',
                    is_local=False, configurable=False, limit_bandwidth=False,
                    max_upload_speed=0, max_download_speed=0,
                    show_all_notifications=True)

        self.add(self.itself)
        self.show()

        self.backend.connect_to_signal('DeviceSettingsChanged',
                                       self.on_device_settings_changed)
        self.backend.connect_to_signal('DeviceSettingsChangeError',
                                       self.on_device_settings_change_error)
        self.backend.connect_to_signal('DeviceRemoved',
                                       self.on_device_removed)
        self.backend.connect_to_signal('DeviceRemovalError',
                                       self.on_device_removal_error)

    def _change_device_settings(self, *args):
        """Update backend settings for this device."""
        if self._updating:
            return

        # Not disabling the GUI to avoid annyong twitchings
        #self.set_sensitive(False)
        self.warning_label.set_text('')
        self.backend.change_device_settings(self.id, self.__dict__,
            reply_handler=NO_OP, error_handler=error_handler)

    def _block_signals(f):
        """Execute 'f' while having the _updating flag set."""

        # pylint: disable=E0213,W0212,E1102

        @wraps(f)
        def inner(self, *args, **kwargs):
            """Execute 'f' while having the _updating flag set."""
            old = self._updating
            self._updating = True

            result = f(self, *args, **kwargs)

            self._updating = old
            return result

        return inner

    on_show_all_notifications_toggled = _change_device_settings
    on_max_upload_speed_value_changed = _change_device_settings
    on_max_download_speed_value_changed = _change_device_settings

    def on_limit_bandwidth_toggled(self, *args, **kwargs):
        """The limit bandwidth checkbox was toggled."""
        self.throttling_limits.set_sensitive(self.limit_bandwidth.get_active())
        self._change_device_settings()

    def on_remove_clicked(self, widget):
        """Remove button was clicked or activated."""
        response = gtk.RESPONSE_YES
        if self.confirm_dialog is not None:
            response = self.confirm_dialog.run()
            self.confirm_dialog.hide()

        if response == gtk.RESPONSE_YES:
            self.backend.remove_device(self.id,
                reply_handler=NO_OP, error_handler=error_handler)
            self.set_sensitive(False)

    @_block_signals
    def update(self, **kwargs):
        """Update according to named parameters.

        Possible settings are:
            * device_id (string, not shown to the user)
            * device_name (string)
            * type (either DEVICE_TYPE_PHONE or DEVICE_TYPE_COMPUTER)
            * is_local (True/False)
            * configurable (True/False)
            * if configurable, the following can be set:
                * show_all_notifications (True/False)
                * limit_bandwidth (True/False)
                * max_upload_speed (bytes)
                * max_download_speed (bytes)

        """
        if 'device_id' in kwargs:
            self.id = kwargs['device_id']

        if 'device_name' in kwargs:
            name = kwargs['device_name'].replace(DEVICE_REMOVABLE_PREFIX, '')
            name = '<span font_size="large"><b>%s</b></span>' % name
            self.device_name.set_markup(name)

        if 'device_type' in kwargs:
            dtype = kwargs['device_type']
            if dtype in (DEVICE_TYPE_COMPUTER, DEVICE_TYPE_PHONE):
                self.device_type.set_from_icon_name(dtype.lower(),
                    gtk.ICON_SIZE_LARGE_TOOLBAR)

        if 'is_local' in kwargs:
            self.is_local = bool(kwargs['is_local'])

        if 'configurable' in kwargs:
            self.configurable = bool(kwargs['configurable'])
            self.config_settings.set_visible(self.configurable)

        if 'show_all_notifications' in kwargs:
            value = bool(kwargs['show_all_notifications'])
            self.show_all_notifications.set_active(value)

        if 'limit_bandwidth' in kwargs:
            enabled = bool(kwargs['limit_bandwidth'])
            self.limit_bandwidth.set_active(enabled)
            self.throttling_limits.set_sensitive(enabled)

        for speed in ('max_upload_speed', 'max_download_speed'):
            if speed in kwargs:
                value = int(kwargs[speed]) // KILOBYTES
                getattr(self, speed).set_value(value)

        self._last_settings = self.__dict__

    @property
    def __dict__(self):
        result = {
            'device_id': self.id,
            'device_name': self.device_name.get_text(),
            'device_type': self.device_type.get_icon_name()[0].capitalize(),
            'is_local': bool_str(self.is_local),
            'configurable': bool_str(self.configurable),
            'show_all_notifications': \
                bool_str(self.show_all_notifications.get_active()),
            'limit_bandwidth': bool_str(self.limit_bandwidth.get_active()),
            'max_upload_speed': \
                str(self.max_upload_speed.get_value_as_int() * KILOBYTES),
            'max_download_speed': \
                str(self.max_download_speed.get_value_as_int() * KILOBYTES),
        }
        return result

    @log_call(logger.info, with_args=False)
    def on_device_settings_changed(self, device_id):
        """The change of this device settings succeded."""
        if device_id != self.id:
            return
        self.set_sensitive(True)
        self.warning_label.set_text('')
        self._last_settings = self.__dict__

    @log_call(logger.error)
    def on_device_settings_change_error(self, device_id, error_dict=None):
        """The change of this device settings failed."""
        if device_id != self.id:
            return
        self.update(**self._last_settings)
        self._set_warning(DEVICE_CHANGE_ERROR, self.warning_label)
        self.set_sensitive(True)

    # is safe to log the device_id since it was already removed
    @log_call(logger.warning)
    def on_device_removed(self, device_id):
        """The removal of this device succeded."""
        if device_id != self.id:
            return
        self.hide()

    @log_call(logger.error)
    def on_device_removal_error(self, device_id, error_dict=None):
        """The removal of this device failed."""
        if device_id != self.id:
            return
        self._set_warning(DEVICE_REMOVAL_ERROR, self.warning_label)
        self.set_sensitive(True)


class DevicesPanel(UbuntuOneBin, ControlPanelMixin):
    """The devices panel."""

    __gsignals__ = {
        'local-device-removed': (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ()),
    }

    TITLE = DEVICES_TITLE

    def __init__(self, main_window=None):
        UbuntuOneBin.__init__(self)
        ControlPanelMixin.__init__(self, filename='devices.ui')
        self.add(self.itself)
        self.show()

        self._devices = {}
        kw = dict(parent=main_window,
                  flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                  type=gtk.MESSAGE_WARNING,
                  buttons=gtk.BUTTONS_YES_NO,
                  message_format=DEVICE_CONFIRM_REMOVE)
        self.confirm_remove_dialog = gtk.MessageDialog(**kw)

        self.backend.connect_to_signal('DevicesInfoReady',
                                       self.on_devices_info_ready)
        self.backend.connect_to_signal('DevicesInfoError',
                                       self.on_devices_info_error)
        self.backend.connect_to_signal('DeviceRemoved',
                                       self.on_device_removed)

    @log_call(logger.info, with_args=False)
    def on_devices_info_ready(self, info):
        """Backend notifies of devices info."""
        for child in self.devices.get_children():
            self.devices.remove(child)

        if not info:
            self.on_success(NO_DEVICES)
        else:
            self.on_success()

        odd_row_color = self.message.style.bg[gtk.STATE_NORMAL]
        for i, device_info in enumerate(info):
            device = Device(confirm_remove_dialog=self.confirm_remove_dialog)
            device_info['device_name'] = device_info.pop('name', '')
            device_info['device_type'] = device_info.pop('type',
                                                         DEVICE_TYPE_COMPUTER)
            device.update(**device_info)

            if i % 2 == 1:
                device.modify_bg(gtk.STATE_NORMAL, odd_row_color)

            self.devices.pack_start(device)
            self._devices[device.id] = device

        self.is_processing = False

    @log_call(logger.error)
    def on_devices_info_error(self, error_dict=None):
        """Backend notifies of an error when fetching volumes info."""
        self.on_error(error_dict=error_dict)
        self.is_processing = False

    @log_call(logger.warning)
    def on_device_removed(self, device_id):
        """The removal of a device succeded."""
        if device_id in self._devices:
            child = self._devices.pop(device_id)
            self.devices.remove(child)

            if child.is_local:
                self.emit('local-device-removed')

    def load(self):
        """Load the device list."""
        self.backend.devices_info(reply_handler=NO_OP,
                                  error_handler=error_handler)
        self.is_processing = True


class InstallPackage(gtk.VBox, ControlPanelMixin):
    """A widget to process the install of a package."""

    __gsignals__ = {
        'finished': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    def __init__(self, package_name, message=None):
        gtk.VBox.__init__(self)
        ControlPanelMixin.__init__(self, filename='install.ui')
        self.add(self.itself)

        self.package_name = package_name
        self.package_manager = package_manager.PackageManager()
        self.args = {'package_name': self.package_name}
        self.transaction = None

        self.progress_bar = None

        self.message = message
        if self.message is None:
            self.message = INSTALL_PACKAGE % self.args
        self.reset()

        self.show()

    def reset(self):
        """Reset this interface."""
        children = self.itself.get_children()
        if self.progress_bar in children:
            self.itself.remove(self.progress_bar)
        if self.install_button_box not in children:
            self.itself.pack_start(self.install_button_box)
        self.install_label.set_markup(self.message)

    @package_manager.inline_callbacks
    def on_install_button_clicked(self, button):
        """The install button was clicked."""
        try:
            # create the install transaction
            self.transaction = yield self.package_manager.install(
                                    self.package_name)

            logger.debug('on_install_button_clicked: transaction is %r',
                         self.transaction)
            success = package_manager.aptdaemon.enums.EXIT_SUCCESS
            if self.transaction == success:
                self.on_install_finished(None, self.transaction)
                return

            # create the progress bar and pack it to the box
            self.progress_bar = package_manager.PackageManagerProgressBar(
                                    self.transaction)
            self.progress_bar.show()

            self.itself.remove(self.install_button_box)
            self.itself.pack_start(self.progress_bar)

            self.transaction.connect('finished', self.on_install_finished)
            self.install_label.set_markup(INSTALLING % self.args)
            yield self.transaction.run()
        except package_manager.aptdaemon.errors.NotAuthorizedError:
            self.reset()
        except:  # pylint: disable=W0702
            logger.exception('on_install_button_clicked')
            self._set_warning(FAILED_INSTALL % self.args,
                              self.install_label)
            if self.progress_bar is not None:
                self.progress_bar.hide()

    @log_call(logger.info)
    def on_install_finished(self, transaction, exit_code):
        """The installation finished."""
        if self.progress_bar is not None:
            self.progress_bar.set_sensitive(False)

        logger.info('on_install_finished: installation of %r was %r',
                    self.package_name, exit_code)
        if exit_code != package_manager.aptdaemon.enums.EXIT_SUCCESS:
            if hasattr(transaction, 'error'):
                logger.error('transaction failed: %r', transaction.error)
            self._set_warning(FAILED_INSTALL % self.args,
                              self.install_label)
        else:
            self.install_label.set_markup(SUCCESS_INSTALL % self.args)
            self.emit('finished')


class Service(gtk.VBox, ControlPanelMixin):
    """A service."""

    def __init__(self, service_id, name,
                 container=None, check_button=None, action_button=None,
                 *args, **kwargs):
        gtk.VBox.__init__(self)
        ControlPanelMixin.__init__(self)
        self.id = service_id
        self.container = container
        self.check_button = check_button
        self.action_button = action_button

        self.warning_label = gtk.Label()
        self.pack_start(self.warning_label, expand=False)

        self.button = gtk.CheckButton(label=name)
        self.pack_start(self.button, expand=False)

        self.show_all()


class FileSyncService(Service):
    """The file sync service."""

    def __init__(self, container, check_button, action_button):
        Service.__init__(self, service_id='file-sync',
                         name=FILE_SYNC_SERVICE_NAME,
                         container=container,
                         check_button=check_button,
                         action_button=action_button)

        self.container.set_sensitive(False)

        self.backend.connect_to_signal('FileSyncStatusChanged',
                                       self.on_file_sync_status_changed)
        self.backend.connect_to_signal('FilesEnabled', self.on_files_enabled)
        self.backend.connect_to_signal('FilesDisabled', self.on_files_disabled)

    @log_call(logger.debug)
    def on_file_sync_status_changed(self, status):
        """File Sync status changed."""
        enabled = status != backend.FILE_SYNC_DISABLED
        logger.info('FileSyncService: on_file_sync_status_changed: '
                    'status %r, enabled? %r', status, enabled)
        self.check_button.set_active(enabled)
        # if service is disabled, disable the action_button
        self.action_button.set_sensitive(enabled)

        if not self.container.is_sensitive():
            # first time we're getting this event
            self.check_button.connect('toggled', self.on_button_toggled)
            self.container.set_sensitive(True)

    def on_files_enabled(self):
        """Files service was enabled."""
        self.on_file_sync_status_changed('enabled!')

    def on_files_disabled(self):
        """Files service was disabled."""
        self.on_file_sync_status_changed(backend.FILE_SYNC_DISABLED)

    @log_call(logger.debug)
    def on_button_toggled(self, button):
        """Button was toggled, exclude/replicate the service properly."""
        logger.info('File Sync enabled? %r', self.check_button.get_active())
        if self.check_button.get_active():
            self.backend.enable_files(reply_handler=NO_OP,
                                      error_handler=error_handler)
        else:
            self.backend.disable_files(reply_handler=NO_OP,
                                       error_handler=error_handler)

    def load(self):
        """Load the information."""
        self.backend.file_sync_status(reply_handler=NO_OP,
                                      error_handler=error_handler)


class DesktopcouchService(Service):
    """A desktopcouch service."""

    def __init__(self, service_id, name, enabled,
                 container, check_button,
                 dependency=None, dependency_name=None):
        Service.__init__(self, service_id, name,
                         container, check_button, action_button=None)

        self.backend.connect_to_signal('ReplicationSettingsChanged',
            self.on_replication_settings_changed)
        self.backend.connect_to_signal('ReplicationSettingsChangeError',
            self.on_replication_settings_change_error)

        self.check_button.set_active(enabled)

        self.dependency = None
        if dependency is not None:
            if dependency_name is None:
                dependency_name = dependency
            args = {'plugin_name': dependency_name, 'service_name': service_id}
            message = INSTALL_PLUGIN % args
            self.dependency = InstallPackage(dependency, message)
            self.dependency.connect('finished', self.on_depedency_finished)

            self.container.pack_end(self.dependency, expand=False)
            self.check_button.set_sensitive(False)

        self.check_button.connect('toggled', self.on_button_toggled)

    def on_depedency_finished(self, widget):
        """The dependency was installed."""
        self.check_button.set_sensitive(True)
        self.container.remove(self.dependency)
        self.dependency = None

    @log_call(logger.debug)
    def on_button_toggled(self, button):
        """Button was toggled, exclude/replicate the service properly."""
        logger.info('Starting replication for %r? %r',
                    self.id, self.check_button.get_active())

        args = {'enabled': bool_str(self.check_button.get_active())}
        self.backend.change_replication_settings(self.id, args,
            reply_handler=NO_OP, error_handler=error_handler)

    @log_call(logger.info)
    def on_replication_settings_changed(self, replication_id):
        """The change of settings for this replication succeded."""
        if replication_id != self.id:
            return
        self.warning_label.set_text('')

    @log_call(logger.error)
    def on_replication_settings_change_error(self, replication_id,
                                             error_dict=None):
        """The change of settings for this replication failed."""
        if replication_id != self.id:
            return
        self.check_button.set_active(not self.check_button.get_active())
        self._set_warning(SETTINGS_CHANGE_ERROR, self.warning_label)


class ServicesPanel(UbuntuOneBin, ControlPanelMixin):
    """The services panel."""

    TITLE = SERVICES_TITLE

    def __init__(self, main_window=None):
        UbuntuOneBin.__init__(self)
        ControlPanelMixin.__init__(self, filename='services.ui')
        self.add(self.itself)
        self.files_icon.set_from_file(get_data_file(SERVICES_FILES_ICON))
        self.files_example.set_from_file(get_data_file(SERVICES_FILES_EXAMPLE))
        self.contacts_icon.set_from_file(get_data_file(SERVICES_CONTACTS_ICON))

        self.plugin_names = {'contacts': CONTACTS}

        self.package_manager = package_manager.PackageManager()
        self.install_box = None

        self._replications_ready = False  # hack to solve LP: #750309
        self.backend.connect_to_signal('ReplicationsInfoReady',
                                       self.on_replications_info_ready)
        self.backend.connect_to_signal('ReplicationsInfoError',
                                       self.on_replications_info_error)

        self.file_sync_service = FileSyncService(container=self.files,
            check_button=self.file_sync_check,
            action_button=self.file_sync_button)

        self.show()

    @property
    def has_desktopcouch(self):
        """Is desktopcouch installed?"""
        return self.package_manager.is_installed(DESKTOPCOUCH_PKG)

    def on_file_sync_button_clicked(self, *args, **kwargs):
        """The "Show me my U1 folder" button was clicked.

        XXX: this should be part of the FileSyncService widget.
        XXX: the Ubuntu One folder should be the user's root.

        """
        uri_hook(None, FILE_URI_PREFIX + os.path.expanduser('~/Ubuntu One'))

    def on_contacts_button_clicked(self, *args, **kwargs):
        """The "Take me to the Ubuntu One website" button was clicked.

        XXX: this should be part of the DesktopcouchService widget.

        """
        uri_hook(None, CONTACTS)

    @log_call(logger.debug)
    def load(self):
        """Load info."""
        self.file_sync_service.load()
        self.replications.hide()
        if self.install_box is not None:
            self.itself.remove(self.install_box)
            self.install_box = None

        logger.info('load: has_desktopcouch? %r', self.has_desktopcouch)
        if not self.has_desktopcouch:
            self.message.set_text('')

            self.install_box = InstallPackage(DESKTOPCOUCH_PKG)
            self.install_box.connect('finished', self.load_replications)
            self.itself.pack_end(self.install_box, expand=False)
            self.itself.reorder_child(self.install_box, 0)
        else:
            self.load_replications()

        self.message.stop()

    @log_call(logger.debug)
    def load_replications(self, *args):
        """Load replications info."""
        self._replications_ready = False  # hack to solve LP: #750309
        # ask replications to the backend
        self.message.start()
        self.backend.replications_info(reply_handler=NO_OP,
                                       error_handler=error_handler)

    @log_call(logger.debug)
    def on_replications_info_ready(self, info):
        """The replication info is ready."""
        self.on_success()

        self.replications.show()

        if self.install_box is not None:
            self.itself.remove(self.install_box)
            self.install_box = None

        for item in info:
            pkg = item['dependency']
            if not pkg or self.package_manager.is_installed(pkg):
                pkg = None

            sid = item['replication_id']
            container = getattr(self, sid, None)
            check_button = getattr(self, '%s_check' % sid, None)
            name = self.plugin_names.get(sid, None)
            child = DesktopcouchService(service_id=sid, name=item['name'],
                enabled=bool(item['enabled']), container=container,
                check_button=check_button,
                dependency=pkg, dependency_name=name)
            setattr(self, '%s_service' % sid, child)
            self._replications_ready = True  # hack to solve LP: #750309

    @log_call(logger.error)
    def on_replications_info_error(self, error_dict=None):
        """The replication info can not be retrieved."""
        if error_dict is not None and \
           error_dict.get('error_type', None) == 'NoPairingRecord':
            self.on_error(NO_PAIRING_RECORD)
        else:
            self.on_error(error_dict=error_dict)

    def refresh(self):
        """If replication list has been loaded, hide and show them."""
        if self._replications_ready:  # hack to solve LP: #750309
            self.replications.hide()
            self.replications.show()


class FileSyncStatus(gtk.HBox, ControlPanelMixin):
    """A file sync status widget."""

    def __init__(self):
        gtk.HBox.__init__(self)
        ControlPanelMixin.__init__(self)

        self.label = LabelLoading(LOADING)
        self.pack_start(self.label, expand=True)

        self.button = gtk.LinkButton(uri='')
        self.button.connect('clicked', self._on_button_clicked)
        self.pack_start(self.button, expand=False)

        self.show_all()

        self.backend.connect_to_signal('FileSyncStatusDisabled',
                                       self.on_file_sync_status_disabled)
        self.backend.connect_to_signal('FileSyncStatusStarting',
                                       self.on_file_sync_status_starting)
        self.backend.connect_to_signal('FileSyncStatusStopped',
                                       self.on_file_sync_status_stopped)
        self.backend.connect_to_signal('FileSyncStatusDisconnected',
                                       self.on_file_sync_status_disconnected)
        self.backend.connect_to_signal('FileSyncStatusSyncing',
                                       self.on_file_sync_status_syncing)
        self.backend.connect_to_signal('FileSyncStatusIdle',
                                       self.on_file_sync_status_idle)
        self.backend.connect_to_signal('FileSyncStatusError',
                                       self.on_file_sync_status_error)
        self.backend.connect_to_signal('FilesStartError',
                                       self.on_files_start_error)
        self.backend.connect_to_signal('FilesEnabled',
                                       self.on_file_sync_status_starting)
        self.backend.connect_to_signal('FilesDisabled',
                                       self.on_file_sync_status_disabled)

    def _update_status(self, msg, action, callback,
                       icon=None, color=None, tooltip=None):
        """Update the status info."""
        if icon is not None:
            foreground = '' if color is None else 'foreground="%s"' % color
            msg = '<span %s>%s</span> %s' % (foreground, icon, msg)
        self.label.set_markup(msg)
        self.label.stop()

        self.button.set_label(action)
        self.button.set_uri(action)
        self.button.set_sensitive(True)
        self.button.set_data('callback', callback)
        if tooltip is not None:
            self.button.set_tooltip_text(tooltip)

    def _on_button_clicked(self, button):
        """Button was clicked, act accordingly the label."""
        button.set_visited(False)
        button.set_sensitive(False)
        button.get_data('callback')(button)

    @log_call(logger.info)
    def on_file_sync_status_disabled(self, msg=None):
        """Backend notifies of file sync status being disabled."""
        self._update_status(FILE_SYNC_DISABLED,
                            FILE_SYNC_ENABLE, self.on_enable_clicked,
                            ERROR_ICON, ERROR_COLOR, FILE_SYNC_ENABLE_TOOLTIP)

    @log_call(logger.info)
    def on_file_sync_status_starting(self, msg=None):
        """Backend notifies of file sync status being starting."""
        self._update_status(FILE_SYNC_STARTING,
                            FILE_SYNC_STOP, self.on_stop_clicked,
                            SYNCING_ICON, ORANGE, FILE_SYNC_STOP_TOOLTIP)

    @log_call(logger.info)
    def on_file_sync_status_stopped(self, msg=None):
        """Backend notifies of file sync being stopped."""
        self._update_status(FILE_SYNC_STOPPED,
                            FILE_SYNC_START, self.on_start_clicked,
                            ERROR_ICON, ERROR_COLOR, FILE_SYNC_START_TOOLTIP)

    @log_call(logger.info)
    def on_file_sync_status_disconnected(self, msg=None):
        """Backend notifies of file sync status being ready."""
        self._update_status(FILE_SYNC_DISCONNECTED,
                            FILE_SYNC_CONNECT, self.on_connect_clicked,
                            ERROR_ICON, ERROR_COLOR,
                            FILE_SYNC_CONNECT_TOOLTIP,)

    @log_call(logger.info)
    def on_file_sync_status_syncing(self, msg=None):
        """Backend notifies of file sync status being syncing."""
        self._update_status(FILE_SYNC_SYNCING,
                            FILE_SYNC_DISCONNECT, self.on_disconnect_clicked,
                            SYNCING_ICON, ORANGE, FILE_SYNC_DISCONNECT_TOOLTIP)

    @log_call(logger.info)
    def on_file_sync_status_idle(self, msg=None):
        """Backend notifies of file sync status being idle."""
        self._update_status(FILE_SYNC_IDLE,
                            FILE_SYNC_DISCONNECT, self.on_disconnect_clicked,
                            IDLE_ICON, SUCCESS_COLOR,
                            FILE_SYNC_DISCONNECT_TOOLTIP)

    @log_call(logger.error)
    def on_file_sync_status_error(self, error_dict=None):
        """Backend notifies of an error when fetching file sync status."""
        msg = FILE_SYNC_ERROR
        reason = error_dict.get('error_msg', '') if error_dict else ''
        if reason:
            msg += ' (' + reason + ')'
        self._update_status(WARNING_MARKUP % msg,
                            FILE_SYNC_RESTART, self.on_restart_clicked,
                            tooltip=FILE_SYNC_RESTART_TOOLTIP)

    @log_call(logger.error)
    def on_files_start_error(self, error_dict=None):
        """Backend notifies of an error when starting the files service."""
        # service is probably disabled, ask for status to backend
        self.backend.file_sync_status(reply_handler=NO_OP,
                                      error_handler=error_handler)

    def on_connect_clicked(self, button=None):
        """User requested connection."""
        self.backend.connect_files(reply_handler=NO_OP,
                                   error_handler=error_handler)

    def on_disconnect_clicked(self, button=None):
        """User requested disconnection."""
        self.backend.disconnect_files(reply_handler=NO_OP,
                                      error_handler=error_handler)

    def on_enable_clicked(self, button=None):
        """User requested enable the service."""
        self.backend.enable_files(reply_handler=NO_OP,
                                  error_handler=error_handler)

    def on_restart_clicked(self, button=None):
        """User requested restart the service."""
        self.backend.restart_files(reply_handler=NO_OP,
                                   error_handler=error_handler)

    def on_start_clicked(self, button=None):
        """User requested start the service."""
        self.backend.start_files(reply_handler=NO_OP,
                                 error_handler=error_handler)

    def on_stop_clicked(self, button=None):
        """User requested stop the service."""
        self.backend.stop_files(reply_handler=NO_OP,
                                error_handler=error_handler)

    def load(self):
        """Load the information."""
        self.backend.file_sync_status(reply_handler=NO_OP,
                                      error_handler=error_handler)


class ManagementPanel(gtk.VBox, ControlPanelMixin):
    """The management panel.

    The user can manage dashboard, volumes, devices and services.

    """

    __gsignals__ = {
        'local-device-removed': (gobject.SIGNAL_RUN_FIRST,
                                 gobject.TYPE_NONE, ()),
        'unauthorized': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    DASHBOARD_BUTTON_NAME = 'ModeLeft'
    SERVICES_BUTTON_NAME = 'ModeRight'

    def __init__(self, main_window=None):
        gtk.VBox.__init__(self)
        ControlPanelMixin.__init__(self, filename='management.ui')
        self.add(self.itself)
        self.facebook_logo.set_from_file(get_data_file(FACEBOOK_LOGO))
        self.twitter_logo.set_from_file(get_data_file(TWITTER_LOGO))
        self.show()

        self.backend.connect_to_signal('AccountInfoReady',
                                       self.on_account_info_ready)
        self.backend.connect_to_signal('AccountInfoError',
                                       self.on_account_info_error)
        self.backend.connect_to_signal('UnauthorizedError',
                                       self.on_unauthorized_error)

        self.quota_progressbar.set_sensitive(False)

        self.quota_label = LabelLoading(LOADING)
        self.quota_box.pack_start(self.quota_label, expand=False)
        self.quota_box.reorder_child(self.quota_label, 0)

        self.status_label = FileSyncStatus()
        self.status_box.pack_end(self.status_label, expand=True)

        self.dashboard = DashboardPanel(main_window=main_window)
        self.volumes = VolumesPanel(main_window=main_window)
        self.shares = SharesPanel(main_window=main_window)
        self.devices = DevicesPanel(main_window=main_window)
        self.services = ServicesPanel(main_window=main_window)

        cb = lambda button, page_num: self.notebook.set_current_page(page_num)
        self.tabs = (u'dashboard', u'volumes', u'shares',
                     u'devices', u'services')
        for page_num, tab in enumerate(self.tabs):
            setattr(self, ('%s_page' % tab).upper(), page_num)
            button = getattr(self, '%s_button' % tab)
            button.connect('clicked', cb, page_num)
            self.notebook.insert_page(getattr(self, tab), position=page_num)

        self.dashboard_button.set_name(self.DASHBOARD_BUTTON_NAME)
        self.dashboard_button.set_tooltip_text(DASHBOARD_BUTTON_TOOLTIP)

        self.volumes_button.set_tooltip_text(FOLDERS_BUTTON_TOOLTIP)
        self.volumes_button.connect('clicked', lambda b: self.volumes.load())

        self.shares_button.set_tooltip_text(SHARES_BUTTON_TOOLTIP)

        self.devices_button.set_tooltip_text(DEVICES_BUTTON_TOOLTIP)
        self.devices_button.connect('clicked', lambda b: self.devices.load())
        self.devices.connect('local-device-removed',
                             lambda widget: self.emit('local-device-removed'))

        self.services_button.set_name(self.SERVICES_BUTTON_NAME)
        self.services_button.set_tooltip_text(SERVICES_BUTTON_TOOLTIP)
        self.services_button.connect('clicked',
                                     lambda b: self.services.refresh())

        self.enable_volumes = lambda: self.volumes_button.set_sensitive(True)
        self.disable_volumes = lambda: self.volumes_button.set_sensitive(False)
        self.backend.connect_to_signal('FilesEnabled', self.enable_volumes)
        self.backend.connect_to_signal('FilesDisabled', self.disable_volumes)

    def _update_quota(self, msg, data=None):
        """Update the quota info."""
        fraction = 0.0
        if data is not None:
            fraction = data.get('percentage', 0.0) / 100
            if fraction > 0 and fraction < 0.05:
                fraction = 0.05
            else:
                fraction = round(fraction, 2)

        logger.debug('ManagementPanel: updating quota to %r.', fraction)
        if fraction >= QUOTA_THRESHOLD:
            self.quota_label.set_markup(WARNING_MARKUP % msg)
        else:
            self.quota_label.set_markup(msg)
        self.quota_label.stop()

        if fraction == 0.0:
            self.quota_progressbar.set_sensitive(False)
        else:
            self.quota_progressbar.set_sensitive(True)

        self.quota_progressbar.set_fraction(min(fraction, 1))

    def load(self):
        """Load the account info and file sync status list."""
        self.backend.account_info(reply_handler=NO_OP,
                                  error_handler=error_handler)
        self.status_label.load()
        self.services.load()

    @log_call(logger.debug)
    def on_account_info_ready(self, info):
        """Backend notifies of account info."""
        used = int(info['quota_used'])
        total = int(info['quota_total'])
        data = {'used': humanize(used), 'total': humanize(total),
                'percentage': (used / total) * 100}
        self._update_quota(QUOTA_LABEL % data, data)

    @log_call(logger.error)
    def on_account_info_error(self, error_dict=None):
        """Backend notifies of an error when fetching account info."""
        self._update_quota(msg='')

    @log_call(logger.error)
    def on_unauthorized_error(self, error_dict=None):
        """Backend notifies that credentials are not valid."""
        self.emit('unauthorized')


class ControlPanel(gtk.Notebook, ControlPanelMixin):
    """The control panel per se, can be added into any other widget."""

    # should not be any larger than 736x525

    def __init__(self, main_window):
        gtk.Notebook.__init__(self)
        ControlPanelMixin.__init__(self)
        gtk.link_button_set_uri_hook(uri_hook)
        self.connect('destroy', self.shutdown)

        self.main_window = main_window

        self.set_show_tabs(False)
        self.set_show_border(False)

        self.overview = OverviewPanel(main_window=main_window)
        self.insert_page(self.overview, position=0)

        self.management = ManagementPanel(main_window=main_window)
        self.insert_page(self.management, position=1)

        self.overview.connect('credentials-found',
                              self.on_show_management_panel)
        self.management.connect('local-device-removed',
                                self.on_show_overview_panel)
        self.management.connect('unauthorized',
                                self.on_show_overview_panel)

        self.show()
        self.on_show_overview_panel()

        logger.debug('%s: started (window size %r).',
                     self.__class__.__name__, self.get_size_request())

    def shutdown(self, *args, **kwargs):
        """Shutdown backend."""
        logger.info('Shutting down...')
        self.backend.shutdown(reply_handler=NO_OP,
                              error_handler=error_handler)

    def on_show_overview_panel(self, widget=None):
        """Show the overview panel."""
        self.set_current_page(0)

    def on_show_management_panel(self, widget=None,
                                 credentials_are_new=False, token=None):
        """Show the notebook (main panel)."""
        if self.get_current_page() == 0:
            self.management.load()
            if credentials_are_new:
                # redirect user to services page to start using Ubuntu One
                self.management.services_button.clicked()
                # instruct syncdaemon to connect
                self.backend.connect_files(reply_handler=NO_OP,
                                           error_handler=error_handler)

            self.next_page()


class ControlPanelService(dbus.service.Object):
    """DBUS service that exposes some of the window's methods."""

    def __init__(self, window):
        self.window = window
        bus_name = dbus.service.BusName(
            DBUS_BUS_NAME_GUI, bus=dbus.SessionBus())
        dbus.service.Object.__init__(
            self, bus_name=bus_name, object_path=DBUS_PATH_GUI)

    @log_call(logger.debug)
    @dbus.service.method(dbus_interface=DBUS_IFACE_GUI, in_signature='sb')
    def switch_to_alert(self, panel='', alert=False):
        """Switch to named panel."""
        if panel:
            self.window.switch_to(panel)
        if alert:
            self.window.draw_attention()


class ControlPanelWindow(gtk.Window):
    """The main window for the Ubuntu One control panel."""

    def __init__(self, switch_to='', alert=False):
        super(ControlPanelWindow, self).__init__()

        # We need to set WMCLASS so Unity falls back and we only get one
        # launcher on the launcher panel
        self.set_wmclass(CP_WMCLASS_NAME, CP_WMCLASS_CLASS)

        self.connect('focus-in-event', self.remove_urgency)
        self.set_title(MAIN_WINDOW_TITLE % {'app_name': U1_APP_NAME})
        self.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        self.set_icon_name('ubuntuone')
        self.set_size_request(736, 525)  # bug #683164

        self.connect('delete-event', lambda w, e: gtk.main_quit())
        if alert:
            self.draw_attention()
        else:
            self.present()

        self.control_panel = ControlPanel(main_window=self)
        self.add(self.control_panel)

        logger.info('Starting %s pointing at panel: %r.',
                     self.__class__.__name__, switch_to)
        if switch_to:
            self.switch_to(switch_to)

        logger.debug('%s: started (window size %r).',
                     self.__class__.__name__, self.get_size_request())

    def remove_urgency(self, *args, **kwargs):
        """Remove urgency from the launcher entry."""
        if not USE_LIBUNITY:
            return
        entry = Unity.LauncherEntry.get_for_desktop_id(U1_DOTDESKTOP)
        if getattr(entry.props, 'urgent', False):
            self.switch_to('volumes')
            entry.props.urgent = False

    def draw_attention(self):
        """Draw attention to the control panel."""
        self.present_with_time(1)
        self.set_urgency_hint(True)

    def switch_to(self, panel):
        """Switch to named panel."""
        button = getattr(
            self.control_panel.management, '%s_button' % panel, None)
        if button is not None:
            button.clicked()
        else:
            logger.warning('Could not start at panel: %r.', panel)

    def main(self):
        """Run the main loop of the widget toolkit."""
        logger.debug('Starting GTK main loop.')
        gtk.main()
