# ubuntuone.syncdaemon.tools - tools for SyncDaemon
#
# Authors: Guillermo Gonzalez <guillermo.gonzalez@canonical.com>
#          Manuel de la Pena <manuel@canonical.com>
#          Alejandro J. Cura <alecu@canonical.com>
#
# Copyright 2011 Canonical Ltd.
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

"""SyncDaemon Tools."""

import logging
import time
import subprocess
import sys

from twisted.internet import defer, reactor
from _winreg import OpenKey, HKEY_LOCAL_MACHINE, QueryValueEx

from ubuntuone.syncdaemon.config import get_user_config
from ubuntuone.platform.windows.ipc_client import UbuntuOneClient

U1_REG_PATH = r'Software\\Ubuntu One'
SD_INSTALL_PATH = 'SyncDaemonInstallPath'

def is_running(bus=None):
    """Check if there is a syncdaemon instance running."""
    #TODO: Do not start two instances of this process
    #      https://launchpad.net/bugs/803672
    #NOTE: Changed to True so SD can be restarted while this bug is fixed
    return True


class SyncDaemonTool(object):
    """Various utility methods to test/play with the SyncDaemon."""

    # WARNING: most of the methods of this class are "pre-processed" by
    # __getattribute__, to call _call_after_connection before the method
    # is called, so they should either be decorated with inlineCallbacks
    # or return a deferred.
    #
    # All methods and instance variables that should not be handled that way
    # should be put in the list below (or start with _):

    _DONT_VERIFY_CONNECTED = [
        "wait_connected",
        "client", "last_event", "delayed_call", "log", "connected",
    ]

    def _should_wrap(self, attr_name):
        """Check if this attribute should be wrapped."""
        return not (attr_name in SyncDaemonTool._DONT_VERIFY_CONNECTED
                    or attr_name.startswith("_"))

    def __getattribute__(self, attr_name):
        """If the attribute is not special, verify the ipc connection."""
        attr = super(SyncDaemonTool, self).__getattribute__(attr_name)
        if SyncDaemonTool._should_wrap(self, attr_name):
            return self._call_after_connection(attr)
        else:
            return attr

    def __init__(self):
        """Initialize this instance."""
        self.client = UbuntuOneClient()
        self.last_event = 0
        self.delayed_call = None
        self.log = logging.getLogger('ubuntuone.SyncDaemon.SDTool')
        self.connected = self.client.connect()

    def _call_after_connection(self, method):
        """Make sure Perspective Broker is connected before calling."""

        @defer.inlineCallbacks
        def call_after_connection_inner(*args, **kwargs):
            """Call the given method after the connection to pb is made."""
            yield self.connected
            retval = yield method(*args, **kwargs)
            defer.returnValue(retval)

        return call_after_connection_inner

    def _get_dict(self, a_dict):
        """Converts a dict returned by the IPC to a dict of strings."""
        str_dict = {}
        for key in a_dict:
            str_dict[key] = unicode(a_dict[key])
        return str_dict

    def wait_connected(self):
        """Wait until syncdaemon is connected to the server."""
        self.log.debug('wait_connected')
        d = defer.Deferred()

        def check_connection_status():
            """Check if the daemon is up and running."""
            # check if the syncdaemon is running
            # catch all errors, pylint: disable-msg=W0703
            try:
                self.client.connect()
                d.callback(True)
            except Exception, e:
                self.log.debug('Not connected: %s', e)
                d.errback()

        reactor.callLater(.5, check_connection_status)
        return d

    @defer.inlineCallbacks
    def get_current_downloads(self):
        """Return a deferred that will be fired with the current downloads."""
        downloads = yield self.client.status.current_downloads()
        downloads_str = []
        for download in downloads:
            downloads_str.append(self._get_dict(download))
        defer.returnValue(downloads_str)

    def wait_all_downloads(self, verbose=False):
        """Wait until there is no more pending downloads."""
        self.log.debug('wait_all_downloads')
        d = self.get_current_downloads()

        def reply_handler(downloads):
            """Check if the are downloads in progress.

            If so, reschelude a new check if there is at least one.

            """
            if verbose:
                sys.stdout.write(', %s' % str(len(downloads)))
                sys.stdout.flush()
            if len(downloads) > 0:
                self.log.debug('wait_all_downloads: %d', len(downloads))
                return self.get_current_downloads()
            else:
                self.log.debug('wait_all_downloads: No more downloads')
                return True

        if verbose:
            sys.stdout.write('\nchecking current downloads')
            sys.stdout.flush()
        d.addCallback(reply_handler)
        return d

    @defer.inlineCallbacks
    def get_current_uploads(self):
        """Return a deferred that will be called with the current uploads."""
        uploads = yield self.client.status.current_uploads()
        uploads_str = []
        for upload in uploads:
             uploads_str.append(self._get_dict(upload))
        defer.returnValue(uploads_str)

    def wait_all_uploads(self, verbose=False):
        """Wait until there is no more pending uploads."""
        self.log.debug('wait_all_uploads')
        d = self.get_current_uploads()

        def reply_handler(uploads):
            """Check if the are downloads in progress.

            If so, reschelude a new check if there is at least one.

            """
            if verbose:
                sys.stdout.write(', %s' % str(len(uploads)))
                sys.stdout.flush()
            if len(uploads) > 0:
                self.log.debug('wait_all_uploads: %d', len(uploads))
                return self.get_current_uploads()
            else:
                self.log.debug('wait_all_uploads: No more uploads')
                return True

        if verbose:
            sys.stdout.write('\nchecking current uploads')
            sys.stdout.flush()

        d.addCallback(reply_handler)
        return d

    def wait_no_more_events(self, last_event_interval, verbose=False):
        """Wait until no more events are fired by the syncdaemon."""
        self.log.debug('wait_no_more_events')
        d = defer.Deferred()

        def check_last_event():
            """Check time!

            Check if the daemon is connected and didn't received event
            in the last_event_interval.
            """
            current_time = time.time()
            if self.last_event and \
               current_time - self.last_event < last_event_interval:
                # keep it running in case this is the last event
                self.log.debug('rescheduling wait_no_more_events')
                if not self.delayed_call.active():
                    self.delayed_call = reactor.callLater(last_event_interval,
                                                          check_last_event)
                else:
                    self.delayed_call.reset(last_event_interval)
            else:
                self.log.debug('wait_no_more_events: No more events!')
                d.callback(True)

        if verbose:
            sys.stdout.write("Listening events")
            sys.stdout.flush()

        def event_handler(event_dict):
            """Update last_event and run checks."""
            self.last_event = time.time()
            self.log.debug('wait_no_more_events - new event: %s - %s',
                           event_dict['event_name'], str(self.last_event))
            if verbose:
                sys.stdout.write('.')
                sys.stdout.flush()
            if self.delayed_call.active():
                self.delayed_call.reset(last_event_interval)

        self.client.events.on_event_cb = event_handler

        def cleanup(result):
            """Remove the signal handler."""
            self.client.events.on_event_cb = None
            return result
        d.addBoth(cleanup)

        # in case the daemon already reached nirvana
        self.delayed_call = reactor.callLater(last_event_interval,
                                              check_last_event)
        return d

    def wait_for_nirvana(self, last_event_interval=5, verbose=False):
        """Wait until the syncdaemon reachs nirvana.

        This is when there are:
            - the syncdaemon is connected
            - 0 transfers inprogress
            - no more events are fired in the event queue
        @param last_event_interval: the seconds to wait to determine that there
        is no more events in the queue and the daemon reached nirvana
        """
        self.log.debug('wait_for_nirvana')
        return self.client.sync_daemon.wait_for_nirvana(last_event_interval)

    def accept_share(self, share_id):
        """Accept the share with id: share_id."""
        self.log.debug('accept_share(%s)', share_id)
        self.client.shares.on_share_answer_response = lambda info:\
                                                info['volume_id']==share_id
        return self.client.shares.accept_share(share_id)

    def reject_share(self, share_id):
        """Reject the share with id: share_id."""
        self.log.debug('reject_share(%s)', share_id)
        self.client.shares.on_share_answer_response = lambda info:\
                                                info['volume_id']==share_id
        return self.client.shares.reject_share(share_id)

    def subscribe_share(self, share_id):
        """Subscribe to a share given its id."""
        self.log.debug('subscribe_share: %r', share_id)
        return self.client.shares.subscribe(share_id)

    def unsubscribe_share(self, share_id):
        """Unsubscribe from a share given its id."""
        self.log.debug('unsubscribe_share: %r', share_id)
        return self.client.shares.unsubscribe(share_id)

    @defer.inlineCallbacks
    def get_shares(self):
        """Get the list of shares (accepted or not)."""
        self.log.debug('get_shares')
        shares = yield self.client.shares.get_shares()
        shares_str = []
        for share in shares:
            shares_str.append(self._get_dict(share))
        defer.returnValue(shares_str)

    def refresh_shares(self):
        """Call refresh_shares method via DBus.

        Request a refresh of share list to the server.

        """
        self.log.debug('refresh_shares')
        return self.client.shares.refresh_shares()

    def offer_share(self, path, username, name, access_level):
        """Offer a share at the specified path to user with id: username."""
        self.log.debug('offer_share(%s, %s, %s, %s)',
                   path, username, name, access_level)
        return self.client.shares.create_share(path, username, name,
                                               access_level)

    @defer.inlineCallbacks
    def list_shared(self):
        """Get the list of the shares "shared"/created/offered."""
        self.log.debug('list_shared')
        shared = yield self.client.shares.get_shared()
        shares_str = []
        for share in shared:
            shares_str.append(self._get_dict(share))
        defer.returnValue(shares_str)

    def wait_for_signals(self, signal_ok, signal_error,
                         dbus_iface=None):
        """Wait for one of the specified signals, return a deferred.

        @param signal_ok: this will fire the deferred's callback
        @param signal_error: the will fire the deferred's errback
        @param dbus_iface: the interface the signal belongs to
        """
        raise NotImplementedError('Not implemented yet!')

    def create_folder(self, path):
        """Create a user defined folder in the specified path."""
        self.log.debug('create_folder')
        return self.client.folders.create(path)

    def delete_folder(self, folder_id):
        """Delete a user defined folder given its id."""
        self.log.debug('delete_folder')
        return self.client.folders.delete(folder_id)

    def subscribe_folder(self, folder_id):
        """Subscribe to a user defined folder given its id."""
        self.log.debug('subscribe_folder')
        return self.client.folders.subscribe(folder_id)

    def unsubscribe_folder(self, folder_id):
        """Unsubscribe from a user defined folder given its id."""
        self.log.debug('unsubscribe_folder')
        return self.client.folders.unsubscribe(folder_id)

    @defer.inlineCallbacks
    def get_folders(self):
        """Return the list of folders (a list of dicts)."""
        self.log.debug('get_folders')
        folders = yield self.client.folders.get_folders()
        folders_str = []
        for folder in folders:
            folders_str.append(self._get_dict(folder))
        defer.returnValue(folders_str)

    def get_folder_info(self, path):
        """Call the get_info method for a UDF path."""
        self.log.debug('get_info')
        return self.client.folders.get_info(path)

    def get_metadata(self, path):
        """Call the exposed mtehod FileSystem.get_metadata using DBus."""
        self.log.debug('get_metadata(%s)', path)
        return self.client.file_system.get_metadata(path)

    @defer.inlineCallbacks
    def change_public_access(self, path, is_public):
        """Change the public access for a given path."""
        self.log.debug('change_public_access(%s)', path)
        metadata = yield self.client.file_system.get_metadata(path)
        file_info = yield self.client.public_files.change_public_access(
                                                          metadata['share_id'],
                                                          metadata['node_id'],
                                                          is_public)
        defer.returnValue(file_info)

    def quit(self):
        """Quit the syncdaemon."""
        self.log.debug('quit')
        # avoid triggering dbus activation while calling quit
        if not is_running():
            return defer.succeed(None)

        def check(r):
            """Wait 0.5 sec to return, to allow syncdaemon to shutdown."""
            d1 = defer.Deferred()
            reactor.callLater(0.5, d1.callback, r)
            return d1
        
        d = self.client.sync_daemon.quit()
        d.addCallback(check)
        return d

    def wait_for_signal(self, signal_name, filter):
        """Wait for the specified DBus signal (the first received).

        @param signal_name: the signal name
        @param filter: a callable to filter signal, must return True, and is
        used to fire the deferred callback.

        """
        raise NotImplementedError('Not implemented.')

    def connect(self):
        """Connect syncdaemon."""
        return self.client.sync_daemon.connect()

    def disconnect(self):
        """Disconnect syncdaemon."""
        return self.client.sync_daemon.disconnect()

    @defer.inlineCallbacks
    def get_status(self):
        """Get the current_status dict."""
        status = yield self.client.status.current_status()
        state_dict = self._get_dict(status)
        state_dict['is_connected'] = bool(state_dict['is_connected'])
        state_dict['is_online'] = bool(state_dict['is_online'])
        state_dict['is_error'] = bool(state_dict['is_error'])
        defer.returnValue(state_dict)

    def waiting(self):
        """Return a description of the waiting queue elements."""
        return self.client.status.waiting()

    def waiting_metadata(self):
        """Return a description of the waiting metadata queue elements."""
        return self.client.status.waiting_metadata()

    def waiting_content(self):
        """Return the waiting content queue elements."""
        return self.client.status.waiting_content()

    def start(self):
        """Start syncdaemon if it's not running."""
        if not is_running():
            # look in the reg to find the path of the .exe to be executed
            # to launch the sd on windows
            key = OpenKey(HKEY_LOCAL_MACHINE, U1_REG_PATH)
            path = QueryValueEx(key, SD_INSTALL_PATH)[0]
            p = subprocess.Popen([path,])
            return defer.succeed(p)
        else:
            return defer.succeed(None)

    def get_throttling_limits(self):
        """Return a dict with the read and write limits."""
        return self.client.config.get_throttling_limits()

    def set_throttling_limits(self, read_limit, write_limit):
        """Set the read and write limits."""
        return self.client.config.set_throttling_limits(read_limit,
                                                        write_limit)

    def is_throttling_enabled(self):
        """Check if throttling is enabled."""
        return self.client.config.bandwidth_throttling_enabled()

    def enable_throttling(self, enabled):
        """Enable/disable throttling."""
        if enabled:
            return self.client.config.enable_bandwidth_throttling()
        else:
            return self.client.config.disable_bandwidth_throttling()

    def is_files_sync_enabled(self):
        """Check if files sync is enabled."""
        self.log.debug('is_files_sync_enabled')
        return get_user_config().get_files_sync_enabled()

    @defer.inlineCallbacks
    def enable_files_sync(self, enabled):
        """Enable/disable files sync."""
        config = get_user_config()
        was_enabled = config.get_files_sync_enabled()
        self.log.debug('enable_files_sync: enable? %r was enabled? %r',
                       enabled, was_enabled)
        if was_enabled:
            yield self.client.config.set_files_sync_enabled(enabled)
            config.set_files_sync_enabled(enabled)
            if not enabled:
                # User requested the service to be disabled
                self.quit()
        else:
            if enabled:
                config.set_files_sync_enabled(True)
                config.save()
                self.start()

    def is_autoconnect_enabled(self):
        """Check if autoconnect is enabled."""
        return self.client.config.autoconnect_enabled()

    def enable_autoconnect(self, enabled):
        """Enable/disable autoconnect."""
        return self.client.config.set_autoconnect_enabled(enabled)

    def is_show_all_notifications_enabled(self):
        """Check if show_all_notifications is enabled."""
        return self.client.config.show_all_notifications_enabled()

    def enable_show_all_notifications(self, enabled):
        """Enable/disable show_all_notifications."""
        if enabled:
            return self.client.config.enable_show_all_notifications()
        else:
            return self.client.config.disable_show_all_notifications()

    def is_share_autosubscribe_enabled(self):
        """Check if share_autosubscribe is enabled."""
        return self.client.config.share_autosubscribe_enabled()

    def enable_share_autosubscribe(self, enabled):
        """Enable/disable share_autosubscribe."""
        if enabled:
            return self.client.config.enable_share_autosubscribe()
        else:
            return self.client.config.disable_share_autosubscribe()

    def is_udf_autosubscribe_enabled(self):
        """Check if udf_autosubscribe is enabled."""
        return self.client.config.udf_autosubscribe_enabled()

    def enable_udf_autosubscribe(self, enabled):
        """Enable/disable udf_autosubscribe."""
        if enabled:
            return self.client.config.enable_udf_autosubscribe()
        else:
            return self.client.config.disable_udf_autosubscribe()

    def refresh_volumes(self):
        """Call refresh_volumes method via DBus.

        Request the volumes list to the server.
        """
        self.log.debug('refresh_volumes')
        return self.client.folders.refresh_volumes()

    def rescan_from_scratch(self, volume_id):
        """Call rescan_from_scratch via DBus.

        Request a rescan from scratch for volume_id.
        """
        self.log.debug('rescan_from_scratch %r', volume_id)
        return self.client.sync_daemon.rescan_from_scratch(volume_id)

    def get_dirty_nodes(self):
        """Call get_dirty_nodes via DBus.

        Return the list of dirty nodes.
        """
        self.log.debug('get_dirty_nodes')
        return self.client.file_system.get_dirty_nodes()

    def get_root_dir(self):
        """Return the root directory."""
        return self.client.sync_daemon.get_rootdir()

    def get_shares_dir(self):
        """Return the shares directory."""
        return self.client.sync_daemon.get_sharesdir()

    def get_shares_dir_link(self):
        """Return the shares link directory."""
        return self.client.sync_daemon.get_sharesdir_link()

    def set_status_changed_handler(self, handler):
        """Set the status changed handler."""
        self.client.status.on_status_changed_cb = handler
        return defer.succeed(None)
