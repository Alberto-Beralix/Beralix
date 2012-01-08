# -*- coding: utf-8 -*-

# Authors: Alejandro J. Cura <alecu@canonical.com>
# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""Export the control backend thru DBus."""

from functools import wraps
import sys

import dbus.service
# pylint: disable=E0611
# pylint: disable=W0404
if 'gobject' in sys.modules:
    import gobject as GObject
else:
    from gi.repository import GObject
# pylint: enable=W0404
# pylint: enable=E0611

from dbus.mainloop.glib import DBusGMainLoop
from dbus.service import method, signal

from twisted.python.failure import Failure
from ubuntuone.syncdaemon.interaction_interfaces import bool_str

from ubuntuone.controlpanel import (DBUS_BUS_NAME, DBUS_PREFERENCES_PATH,
    DBUS_PREFERENCES_IFACE)
from ubuntuone.controlpanel.backend import (
    ControlBackend, filter_field, UnauthorizedError,
    FILE_SYNC_DISABLED, FILE_SYNC_DISCONNECTED,
    FILE_SYNC_ERROR, FILE_SYNC_IDLE, FILE_SYNC_STARTING, FILE_SYNC_STOPPED,
    FILE_SYNC_SYNCING,
    MSG_KEY, STATUS_KEY,
)
from ubuntuone.controlpanel.logger import setup_logging, log_call
from ubuntuone.controlpanel.utils import (ERROR_TYPE, ERROR_MESSAGE,
    failure_to_error_dict, exception_to_error_dict)


logger = setup_logging('dbus_service')


def make_unicode(anything):
    """Transform 'anything' on an unicode."""
    if isinstance(anything, bool):
        anything = bool_str(anything)
    elif not isinstance(anything, unicode):
        anything = str(anything).decode('utf8', 'replace')

    return anything


def transform_info(f):
    """Decorator to apply to DBus success signals.

    With this call, a list of dicts with string keys and any values is
    transformed into a list with string-string dicts.

    """
    def inner(info):
        """Do the info transformation."""
        logger.debug('processing info: %r', info)

        def process_dict(data):
            """Stringify dict's values."""
            result = {}
            for key, val in data.iteritems():
                result[key] = make_unicode(val)
            return result

        if isinstance(info, dict):
            result = process_dict(info)
        else:
            result = []
            for data in info:
                result.append(process_dict(data))

        result = f(result)
        return result

    return inner


def error_handler(error):
    """Handle 'error' properly to be able to call a dbus error signal.
     If 'error' is a Failure, then transform the exception in it to a error
    dict. If 'error' is a regular Exception, transform it.

    If 'error' is already a string-string dict, just pass it along. Build a
    generic error dict in any other case.

    """
    result = {}
    if isinstance(error, Failure):
        result = failure_to_error_dict(error)
    elif isinstance(error, Exception):
        result = exception_to_error_dict(error)
    elif isinstance(error, dict):
        # ensure that both keys and values are unicodes
        result = dict(map(make_unicode, i) for i in error.iteritems())
    else:
        msg = 'Got unexpected error argument %r' % error
        result = {ERROR_TYPE: 'UnknownError', ERROR_MESSAGE: msg}

    return result


def transform_failure(f, auth_error=None):
    """Decorator to apply to DBus error signals.

    With this call, a Failure is transformed into a string-string dict.

    """
    def inner(error, _=None):
        """Do the Failure transformation."""
        logger.error('processing failure: %r', error.printTraceback())
        error_dict = error_handler(error)
        if auth_error is not None and error.check(UnauthorizedError):
            result = auth_error(error_dict)
        elif _ is not None:
            result = f(_, error_dict)
        else:
            result = f(error_dict)
        return result

    return inner


def debug(f):
    """Debug the call to 'f'."""

    @wraps(f)
    def inner(self, *args, **kwargs):
        """Fake the call to 'f'."""
        print '\n===', self, f, args, kwargs
        return f(self, *args, **kwargs)

    return inner


class ControlPanelBackend(dbus.service.Object):
    """Export the Control Panel backend thru DBus."""

    def __init__(self, backend, *args, **kwargs):
        """Create this instance of the backend."""
        super(ControlPanelBackend, self).__init__(*args, **kwargs)
        self.backend = backend
        self.transform = lambda f: transform_failure(f, self.UnauthorizedError)
        logger.debug('ControlPanelBackend: created with %r, %r.',
                     args, kwargs)

    # pylint: disable=C0103

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def UnauthorizedError(self, error):
        """The credentials are not valid."""

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def account_info(self):
        """Find out the account info for the current logged in user."""
        d = self.backend.account_info()
        d.addCallback(transform_info(self.AccountInfoReady))
        d.addErrback(self.transform(self.AccountInfoError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def AccountInfoReady(self, info):
        """The info for the current user is available right now."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def AccountInfoError(self, error):
        """The info for the current user is currently unavailable."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def devices_info(self):
        """Find out the devices info for the logged in user."""
        d = self.backend.devices_info()
        d.addCallback(transform_info(self.DevicesInfoReady))
        d.addErrback(self.transform(self.DevicesInfoError))

    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="aa{ss}")
    def DevicesInfoReady(self, info):
        """The info for the devices is available right now."""
        logger.debug('DevicesInfoReady: args %r',
                     filter_field(info, field='device_id'))

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def DevicesInfoError(self, error):
        """The info for the devices is currently unavailable."""

    #---

    @log_call(logger.info, with_args=False)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="sa{ss}")
    def change_device_settings(self, device_id, settings):
        """Configure a given device."""
        d = self.backend.change_device_settings(device_id, settings)
        d.addCallback(self.DeviceSettingsChanged)
        d.addErrback(self.transform(self.DeviceSettingsChangeError),
                     device_id)

    @log_call(logger.info, with_args=False)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def DeviceSettingsChanged(self, device_id):
        """The settings for the device were changed."""

    @log_call(logger.error, with_args=False)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="sa{ss}")
    def DeviceSettingsChangeError(self, device_id, error):
        """Problem changing settings for the device."""

    #---

    @log_call(logger.warning, with_args=False)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="s")
    def remove_device(self, device_id):
        """Remove a given device."""
        d = self.backend.remove_device(device_id)
        d.addCallback(self.DeviceRemoved)
        d.addErrback(self.transform(self.DeviceRemovalError), device_id)

    @log_call(logger.warning, with_args=False)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def DeviceRemoved(self, device_id):
        """The removal for the device was completed."""

    @log_call(logger.error, with_args=False)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="sa{ss}")
    def DeviceRemovalError(self, device_id, error):
        """Problem removing the device."""

    #---

    def process_status(self, status_dict):
        """Match status with signals."""
        logger.info('process_status: new status received %r', status_dict)
        status = status_dict[STATUS_KEY]
        msg = status_dict[MSG_KEY]
        if status == FILE_SYNC_DISABLED:
            self.FileSyncStatusDisabled(msg)
        elif status == FILE_SYNC_STARTING:
            self.FileSyncStatusStarting(msg)
        elif status == FILE_SYNC_STOPPED:
            self.FileSyncStatusStopped(msg)
        elif status == FILE_SYNC_DISCONNECTED:
            self.FileSyncStatusDisconnected(msg)
        elif status == FILE_SYNC_SYNCING:
            self.FileSyncStatusSyncing(msg)
        elif status == FILE_SYNC_IDLE:
            self.FileSyncStatusIdle(msg)
        elif status == FILE_SYNC_ERROR:
            error_dict = {ERROR_TYPE: 'FileSyncStatusError',
                          ERROR_MESSAGE: msg}
            self.FileSyncStatusError(error_dict)
        else:
            self.FileSyncStatusError(error_handler(status_dict))

        self.FileSyncStatusChanged(status)

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def file_sync_status(self):
        """Get the status of the file sync service."""
        if self.backend.status_changed_handler is None:
            self.backend.status_changed_handler = self.process_status

        d = self.backend.file_sync_status()
        d.addCallback(self.process_status)
        d.addErrback(self.transform(self.FileSyncStatusError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusDisabled(self, msg):
        """The file sync status is disabled."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusStarting(self, msg):
        """The file sync service is starting."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusStopped(self, msg):
        """The file sync service is stopped."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusDisconnected(self, msg):
        """The file sync service is waiting for user to request connection."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusSyncing(self, msg):
        """The file sync service is currently syncing."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusIdle(self, msg):
        """The file sync service is idle."""

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def FileSyncStatusChanged(self, msg):
        """The file sync service status changed."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FileSyncStatusError(self, error):
        """Problem getting the file sync status."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def enable_files(self):
        """Enable the files service."""
        d = self.backend.enable_files()
        d.addCallback(lambda _: self.FilesEnabled())
        d.addErrback(self.transform(self.FilesEnableError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesEnabled(self):
        """The files service is enabled."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesEnableError(self, error):
        """Problem enabling the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def disable_files(self):
        """Disable the files service."""
        d = self.backend.disable_files()
        d.addCallback(lambda _: self.FilesDisabled())
        d.addErrback(self.transform(self.FilesDisableError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesDisabled(self):
        """The files service is disabled."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesDisableError(self, error):
        """Problem disabling the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def connect_files(self):
        """Connect the files service."""
        d = self.backend.connect_files()
        d.addCallback(lambda _: self.FilesConnected())
        d.addErrback(self.transform(self.FilesConnectError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesConnected(self):
        """The files service is connected."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesConnectError(self, error):
        """Problem connecting the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def disconnect_files(self):
        """Disconnect the files service."""
        d = self.backend.disconnect_files()
        d.addCallback(lambda _: self.FilesDisconnected())
        d.addErrback(self.transform(self.FilesDisconnectError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesDisconnected(self):
        """The files service is disconnected."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesDisconnectError(self, error):
        """Problem disconnecting the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def restart_files(self):
        """Restart the files service."""
        d = self.backend.restart_files()
        d.addCallback(lambda _: self.FilesRestarted())
        d.addErrback(self.transform(self.FilesRestartError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesRestarted(self):
        """The files service is restarted."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesRestartError(self, error):
        """Problem restarting the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def start_files(self):
        """Start the files service."""
        d = self.backend.start_files()
        d.addCallback(lambda _: self.FilesStarted())
        d.addErrback(self.transform(self.FilesStartError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesStarted(self):
        """The files service is started."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesStartError(self, error):
        """Problem starting the files service."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def stop_files(self):
        """Stop the files service."""
        d = self.backend.stop_files()
        d.addCallback(lambda _: self.FilesStopped())
        d.addErrback(self.transform(self.FilesStopError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE)
    def FilesStopped(self):
        """The files service is stopped."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def FilesStopError(self, error):
        """Problem stopping the files service."""

    #---

    def process_volumes(self, info):
        """Stringify the volumes info sent from the backend."""
        result = []
        f = lambda _: _
        for name, free_bytes, data in info:
            result.append((name, make_unicode(free_bytes),
                           transform_info(f)(data)))
        self.VolumesInfoReady(result)

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def volumes_info(self):
        """Find out the volumes info for the logged in user."""
        d = self.backend.volumes_info()
        d.addCallback(self.process_volumes)
        d.addErrback(self.transform(self.VolumesInfoError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a(ssaa{ss})")
    def VolumesInfoReady(self, info):
        """The info for the volumes is available right now."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def VolumesInfoError(self, error):
        """The info for the volumes is currently unavailable."""

    #---

    @log_call(logger.info)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="sa{ss}")
    def change_volume_settings(self, volume_id, settings):
        """Configure a given volume."""
        d = self.backend.change_volume_settings(volume_id, settings)
        d.addCallback(self.VolumeSettingsChanged)
        d.addErrback(self.transform(self.VolumeSettingsChangeError),
                     volume_id)

    @log_call(logger.info)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def VolumeSettingsChanged(self, volume_id):
        """The settings for the volume were changed."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="sa{ss}")
    def VolumeSettingsChangeError(self, volume_id, error):
        """Problem changing settings for the volume."""

    #---

    @log_call(logger.debug)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def replications_info(self):
        """Return the replications info."""
        d = self.backend.replications_info()
        d.addCallback(transform_info(self.ReplicationsInfoReady))
        d.addErrback(self.transform(self.ReplicationsInfoError))

    @log_call(logger.debug)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="aa{ss}")
    def ReplicationsInfoReady(self, info):
        """The replications info is ready."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="a{ss}")
    def ReplicationsInfoError(self, error):
        """Problem getting the replications info."""

    #---

    @log_call(logger.info)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="sa{ss}")
    def change_replication_settings(self, replication_id, settings):
        """Configure a given replication."""
        d = self.backend.change_replication_settings(replication_id, settings)
        d.addCallback(self.ReplicationSettingsChanged)
        d.addErrback(self.transform(self.ReplicationSettingsChangeError),
                     replication_id)

    @log_call(logger.info)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="s")
    def ReplicationSettingsChanged(self, replication_id):
        """The settings for the replication were changed."""

    @log_call(logger.error)
    @signal(dbus_interface=DBUS_PREFERENCES_IFACE, signature="sa{ss}")
    def ReplicationSettingsChangeError(self, replication_id, error):
        """Problem changing settings for the replication."""

    #---

    @log_call(logger.info)
    @method(dbus_interface=DBUS_PREFERENCES_IFACE, in_signature="")
    def shutdown(self):
        """Shutdown this service."""
        self.backend.shutdown()


def init_mainloop():
    """Start the DBus mainloop."""
    DBusGMainLoop(set_as_default=True)


def run_mainloop(loop=None):
    """Run the GObject main loop."""
    if loop is None:
        loop = GObject.MainLoop()
    loop.run()


def register_service():
    """Try to register DBus service for making sure we run only one instance.

    Return True if succesfully registered, False if already running.
    """
    session_bus = dbus.SessionBus()
    name = session_bus.request_name(DBUS_BUS_NAME,
                                    dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
    return name != dbus.bus.REQUEST_NAME_REPLY_EXISTS


def get_busname():
    """Build the DBus BusName."""
    return dbus.service.BusName(DBUS_BUS_NAME, bus=dbus.SessionBus())


def publish_backend(backend=None, shutdown_func=None):
    """Publish the backend on the DBus."""
    if backend is None:
        backend = ControlBackend(shutdown_func=shutdown_func)
    return ControlPanelBackend(backend=backend,
                               object_path=DBUS_PREFERENCES_PATH,
                               bus_name=get_busname())


def main():
    """Hook the DBus listeners and start the main loop."""
    init_mainloop()
    if register_service():
        loop = GObject.MainLoop()
        publish_backend(shutdown_func=loop.quit)
        run_mainloop(loop=loop)
    else:
        print "Control panel backend already running."
