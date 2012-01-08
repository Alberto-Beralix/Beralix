# ubuntuone.platform.linux.dbus_interface - DBus Interface
#
# Author: Guillermo Gonzalez <guillermo.gonzalez@canonical.com>
#
# Copyright 2009 Canonical Ltd.
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
"""DBUS interface module."""

import logging
import warnings

import dbus.service

from dbus import DBusException
from xml.etree import ElementTree

from twisted.internet import defer
from twisted.python.failure import Failure
from ubuntuone.syncdaemon.interfaces import IMarker
from ubuntuone.platform.credentials.linux import (
    DBUS_BUS_NAME, DBUS_CREDENTIALS_PATH,
    DBUS_CREDENTIALS_IFACE)
from ubuntuone.platform.linux.launcher import UbuntuOneLauncher

from ubuntuone.syncdaemon.interaction_interfaces import (
    bool_str,
    get_share_dict,
    get_udf_dict,
    SyncdaemonConfig,
    SyncdaemonEventListener,
    SyncdaemonEvents,
    SyncdaemonFileSystem,
    SyncdaemonFolders,
    SyncdaemonPublicFiles,
    SyncdaemonService,
    SyncdaemonShares,
    SyncdaemonStatus)

# Disable the "Invalid Name" check here, as we have lots of DBus style names
# pylint: disable-msg=C0103

DBUS_IFACE_NAME = 'com.ubuntuone.SyncDaemon'
DBUS_IFACE_SYNC_NAME = DBUS_IFACE_NAME + '.SyncDaemon'
DBUS_IFACE_STATUS_NAME = DBUS_IFACE_NAME + '.Status'
DBUS_IFACE_EVENTS_NAME = DBUS_IFACE_NAME + '.Events'
DBUS_IFACE_FS_NAME = DBUS_IFACE_NAME + '.FileSystem'
DBUS_IFACE_SHARES_NAME = DBUS_IFACE_NAME + '.Shares'
DBUS_IFACE_CONFIG_NAME = DBUS_IFACE_NAME + '.Config'
DBUS_IFACE_FOLDERS_NAME = DBUS_IFACE_NAME + '.Folders'
DBUS_IFACE_PUBLIC_FILES_NAME = DBUS_IFACE_NAME + '.PublicFiles'
DBUS_IFACE_LAUNCHER_NAME = DBUS_IFACE_NAME + '.Launcher'

# NetworkManager State constants
NM_STATE_UNKNOWN = 0
NM_STATE_ASLEEP_OLD = 1
NM_STATE_ASLEEP = 10
NM_STATE_CONNECTING_OLD = 2
NM_STATE_CONNECTING = 40
NM_STATE_CONNECTED_OLD = 3
NM_STATE_CONNECTED_LOCAL = 50
NM_STATE_CONNECTED_SITE = 60
NM_STATE_CONNECTED_GLOBAL = 70
NM_STATE_DISCONNECTED_OLD = 4
NM_STATE_DISCONNECTED = 20
# NM state -> events mapping
# Note that the LOCAL and SITE mappings are *not* a typo.  Local and site links
# are not enough to connect to one.ubuntu.com, so we treat them as if we were
# not connected.
NM_STATE_EVENTS = {NM_STATE_CONNECTED_OLD: 'SYS_NET_CONNECTED',
                   NM_STATE_CONNECTED_LOCAL: 'SYS_NET_DISCONNECTED',
                   NM_STATE_CONNECTED_SITE: 'SYS_NET_DISCONNECTED',
                   NM_STATE_CONNECTED_GLOBAL: 'SYS_NET_CONNECTED',
                   NM_STATE_DISCONNECTED_OLD: 'SYS_NET_DISCONNECTED',
                   NM_STATE_DISCONNECTED: 'SYS_NET_DISCONNECTED'}

logger = logging.getLogger("ubuntuone.SyncDaemon.DBus")


class NoAccessToken(Exception):
    """The access token could not be retrieved."""


def get_classname(thing):
    """Get the clasname of the thing.

    If we could forget 2.5, we could do attrgetter('__class__.__name__')
    Alas, we can't forget it yet.
    """
    return thing.__class__.__name__


def sanitize_dict(data):
    """Sanitize *IN PLACE* a dict values to go through DBus."""
    for k, v in data.items():
        if IMarker.providedBy(v):
            # this goes first, as it also is instance of basestring
            data[k] = repr(v)
        elif isinstance(v, basestring):
            pass  # to avoid str() to already strings
        elif isinstance(v, bool):
            data[k] = bool_str(v)
        elif v is None:
            data[k] = 'None'
        else:
            data[k] = str(v)


class DBusExposedObject(dbus.service.Object):
    """Base class that provides some helper methods to DBus exposed objects."""
    #__metaclass__ = InterfaceType

    def __init__(self, bus_name, path):
        """Create the instance."""
        dbus.service.Object.__init__(self, bus_name=bus_name,
                                     object_path=self.path)

    @dbus.service.signal(DBUS_IFACE_SYNC_NAME, signature='sa{ss}')
    def SignalError(self, signal, extra_args):
        """An error ocurred while trying to emit a signal."""

    def emit_signal_error(self, signal, extra_args):
        """Emit an Error signal."""
        self.SignalError(signal, extra_args)

    @classmethod
    def _add_docstring(cls, func, reflection_data):
        """Add <docstring> tag to reflection_data if func.__doc__ isn't None."""
        # add docstring element
        if getattr(func, '__doc__', None) is not None:

            element = ElementTree.fromstring(reflection_data)
            doc = element.makeelement('docstring', dict())
            data = '<![CDATA[' + func.__doc__ + ']]>'
            doc.text = '%s'
            element.insert(0, doc)
            return ElementTree.tostring(element) % data
        else:
            return reflection_data

    @classmethod
    def _reflect_on_method(cls, func):
        """override _reflect_on_method to provide an extra <docstring> element
        in the xml.
        """
        reflection_data = dbus.service.Object._reflect_on_method(func)
        reflection_data = cls._add_docstring(func, reflection_data)
        return reflection_data

    @classmethod
    def _reflect_on_signal(cls, func):
        reflection_data = dbus.service.Object._reflect_on_signal(func)
        reflection_data = cls._add_docstring(func, reflection_data)
        return reflection_data


class Status(DBusExposedObject):
    """Represent the status of the syncdaemon."""

    def __init__(self, bus_name, dbus_iface, syncdaemon_status=None):
        """Create the instance.

        @param bus: the BusName of this DBusExposedObject.
        """
        if not syncdaemon_status:
            syncdaemon_status = SyncdaemonStatus(dbus_iface.main,
                                                 dbus_iface.action_queue,
                                                 dbus_iface.fs_manager)
        self.syncdaemon_status = syncdaemon_status
        self.path = '/status'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_STATUS_NAME,
                         in_signature='', out_signature='a{ss}')
    def current_status(self):
        """Return the current status of the system, one of: local_rescan,
        offline, trying_to_connect, server_rescan or online.
        """
        logger.debug('called current_status')
        return self.syncdaemon_status.current_status()

    @dbus.service.method(DBUS_IFACE_STATUS_NAME, out_signature='aa{ss}')
    def current_downloads(self):
        """Return a list of files with a download in progress."""
        logger.debug('called current_downloads')
        return self.syncdaemon_status.current_downloads()

    @dbus.service.method(DBUS_IFACE_STATUS_NAME,
                         in_signature='s', out_signature='t')
    def free_space(self, vol_id):
        """Return the free space for the given volume."""
        logger.debug('free_space for volume %r', vol_id)
        return self.syncdaemon_status.free_space(vol_id)

    @dbus.service.method(DBUS_IFACE_STATUS_NAME, out_signature='a(ssa{ss})')
    def waiting(self):
        """Return a list of the operations in action queue."""
        logger.debug('called waiting')
        commands = self.syncdaemon_status.waiting()
        for op, op_id, data in commands:
            sanitize_dict(data)
        return commands

    @dbus.service.method(DBUS_IFACE_STATUS_NAME, out_signature='a(sa{ss})')
    def waiting_metadata(self):
        """Return a list of the operations in the meta-queue.

        As we don't have meta-queue anymore, this is faked. This method
        is deprecated, and will go away in a near future.

        """
        warnings.warn('Use "waiting" method instead.', DeprecationWarning)
        logger.debug('called waiting_metadata')
        commands = self.syncdaemon_status.waiting_metadata()
        for op, data  in commands:
            sanitize_dict(data)
        return commands

    @dbus.service.method(DBUS_IFACE_STATUS_NAME, out_signature='aa{ss}')
    def waiting_content(self):
        """Return a list of files that are waiting to be up- or downloaded.

        As we don't have content-queue anymore, this is faked.  This method
        is deprecated, and will go away in a near future.

        """
        warnings.warn('Use "waiting" method instead.', DeprecationWarning)
        logger.debug('called waiting_content')
        commands = self.syncdaemon_status.waiting_content()
        for data in commands:
            sanitize_dict(data)
        return commands

    @dbus.service.method(DBUS_IFACE_STATUS_NAME, out_signature='aa{ss}')
    def current_uploads(self):
        """Return a list of files with a upload in progress."""
        logger.debug('called current_uploads')
        return self.syncdaemon_status.current_uploads()

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME)
    def DownloadStarted(self, path):
        """Fire a signal to notify that a download has started."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='sa{ss}')
    def DownloadFileProgress(self, path, info):
        """Fire a signal to notify about a download progress."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='sa{ss}')
    def DownloadFinished(self, path, info):
        """Fire a signal to notify that a download has finished."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME)
    def UploadStarted(self, path):
        """Fire a signal to notify that an upload has started."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='sa{ss}')
    def UploadFileProgress(self, path, info):
        """Fire a signal to notify about an upload progress."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='sa{ss}')
    def UploadFinished(self, path, info):
        """Fire a signal to notify that an upload has finished."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='say')
    def InvalidName(self, dirname, filename):
        """Fire a signal to notify an invalid file or dir name."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='ssss')
    def BrokenNode(self, volume_id, node_id, mdid, path):
        """Fire a signal to notify a broken node."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME)
    def StatusChanged(self, status):
        """Fire a signal to notify that the status of the system changed."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='a{ss}')
    def AccountChanged(self, account_info):
        """Fire a signal to notify that account information has changed."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME)
    def ContentQueueChanged(self):
        """Fire a signal to notify that the content queue has changed.

        This signal is deprecated, and will go away in a near future.

        """
        msg = 'Connect to RequestQueueAdded/RequestQueueRemoved instead.'
        warnings.warn(msg, DeprecationWarning)

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME)
    def MetaQueueChanged(self):
        """Fire a signal to notify that the meta queue has changed.

        This signal is deprecated, and will go away in a near future.

        """
        msg = 'Connect to RequestQueueAdded/RequestQueueRemoved instead.'
        warnings.warn(msg, DeprecationWarning)

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='ssa{ss}')
    def RequestQueueAdded(self, op_name, op_id, data):
        """Fire a signal to notify that this command was added."""

    @dbus.service.signal(DBUS_IFACE_STATUS_NAME, signature='ssa{ss}')
    def RequestQueueRemoved(self, op_name, op_id, data):
        """Fire a signal to notify that this command was removed."""

    def emit_content_queue_changed(self):
        """Emit ContentQueueChanged.

        This signal is deprecated, and will go away in a near future.
        """
        self.ContentQueueChanged()

    def emit_invalid_name(self, dirname, filename):
        """Emit InvalidName."""
        self.InvalidName(unicode(dirname), str(filename))

    def emit_broken_node(self, volume_id, node_id, mdid, path):
        """Emit BrokenNode."""
        if mdid is None:
            mdid = ''
        if path is None:
            path = ''
        self.BrokenNode(volume_id, node_id, mdid, path.decode('utf8'))

    def emit_status_changed(self, state):
        """Emit StatusChanged."""
        self.StatusChanged(self.syncdaemon_status.current_status())

    def emit_download_started(self, download):
        """Emit DownloadStarted."""
        self.DownloadStarted(download)

    def emit_download_file_progress(self, download, **info):
        """Emit DownloadFileProgress."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.DownloadFileProgress(download, info)

    def emit_download_finished(self, download, **info):
        """Emit DownloadFinished."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.DownloadFinished(download, info)

    def emit_upload_started(self, upload):
        """Emit UploadStarted."""
        self.UploadStarted(upload)

    def emit_upload_file_progress(self, upload, **info):
        """Emit UploadFileProgress."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.UploadFileProgress(upload, info)

    def emit_upload_finished(self, upload, **info):
        """Emit UploadFinished."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.UploadFinished(upload, info)

    def emit_account_changed(self, account_info):
        """Emit AccountChanged."""
        info_dict = {'purchased_bytes': unicode(account_info.purchased_bytes)}
        self.AccountChanged(info_dict)

    def emit_metaqueue_changed(self):
        """Emit MetaQueueChanged.

        This signal is deprecated, and will go away in a near future.
        """
        self.MetaQueueChanged()

    def emit_requestqueue_added(self, op_name, op_id, data):
        """Emit RequestQueueAdded."""
        sanitize_dict(data)
        self.RequestQueueAdded(op_name, str(op_id), data)

    def emit_requestqueue_removed(self, op_name, op_id, data):
        """Emit RequestQueueRemoved."""
        sanitize_dict(data)
        self.RequestQueueRemoved(op_name, str(op_id), data)


class Events(DBusExposedObject):
    """The events of the system translated to D-BUS signals.

    @param bus_name: the BusName of this DBusExposedObject.
    @param event_queue: the Event Queue
    """
    def __init__(self, bus_name, event_queue):
        self.events = SyncdaemonEvents(event_queue)
        self.path = '/events'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.signal(DBUS_IFACE_EVENTS_NAME,
                         signature='a{ss}')
    def Event(self, event_dict):
        """Fire a D-BUS signal, notifying an event."""

    def emit_event(self, event):
        """Emit the signal."""
        event_dict = {}
        for key, value in event.iteritems():
            event_dict[str(key)] = str(value)
        self.Event(event_dict)

    @dbus.service.method(DBUS_IFACE_EVENTS_NAME, in_signature='sa{ss}')
    def push_event(self, event_name, args):
        """Push an event to the event queue."""
        logger.debug('push_event: %r with %r', event_name, args)
        self.events.push_event(event_name, args)


class AllEventsSender(object):
    """Event listener that sends all of them through DBus."""

    def __init__(self, dbus_iface):
        self.dbus_iface = dbus_iface

    def handle_default(self, event_name, **kwargs):
        """Handle all events."""
        event_dict = {'event_name': event_name}
        event_dict.update(kwargs)
        self.dbus_iface.events.emit_event(event_dict)


class SyncDaemon(DBusExposedObject):
    """The Daemon dbus interface."""

    def __init__(self, bus_name, dbus_iface):
        """Create the instance.

        @param bus: the BusName of this DBusExposedObject.
        """
        self.dbus_iface = dbus_iface
        self.service = SyncdaemonService(dbus_iface, dbus_iface.main,
                                         dbus_iface.volume_manager,
                                         dbus_iface.action_queue)
        self.path = '/'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='')
    def connect(self):
        """Connect to the server."""
        logger.debug('connect requested')
        self.service.connect()

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='')
    def disconnect(self):
        """Disconnect from the server."""
        logger.debug('disconnect requested')
        self.service.disconnect()

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='s')
    def get_rootdir(self):
        """Return the root dir/mount point."""
        logger.debug('called get_rootdir')
        return self.service.get_rootdir()

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='s')
    def get_sharesdir(self):
        """Return the shares dir/mount point."""
        logger.debug('called get_sharesdir')
        return self.service.get_sharesdir()

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='s')
    def get_sharesdir_link(self):
        """Return the shares dir/mount point."""
        logger.debug('called get_sharesdir_link')
        return self.service.get_sharesdir_link()

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='d', out_signature='b',
                         async_callbacks=('reply_handler', 'error_handler'))
    def wait_for_nirvana(self, last_event_interval,
                         reply_handler=None, error_handler=None):
        """Call the reply handler when there are no more
        events or transfers.
        """
        logger.debug('called wait_for_nirvana')
        return self.service.wait_for_nirvana(last_event_interval,
                                             reply_handler, error_handler)

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def quit(self, reply_handler=None, error_handler=None):
        """Shutdown the syncdaemon."""
        logger.debug('Quit requested')
        self.service.quit(reply_handler, error_handler)

    @dbus.service.method(DBUS_IFACE_SYNC_NAME,
                         in_signature='s', out_signature='')
    def rescan_from_scratch(self, volume_id):
        """Request a rescan from scratch of the volume with volume_id."""
        self.service.rescan_from_scratch(volume_id)

    @dbus.service.signal(DBUS_IFACE_SYNC_NAME,
                         signature='ss')
    def RootMismatch(self, root_id, new_root_id):
        """RootMismatch signal, the user connected with a different account."""

    def emit_root_mismatch(self, root_id, new_root_id):
        """Emit RootMismatch signal."""
        self.RootMismatch(root_id, new_root_id)

    @dbus.service.signal(DBUS_IFACE_SYNC_NAME,
                         signature='a{ss}')
    def QuotaExceeded(self, volume_dict):
        """QuotaExceeded signal, the user ran out of space."""

    def emit_quota_exceeded(self, volume_dict):
        """Emit QuotaExceeded signal."""
        self.QuotaExceeded(volume_dict)


class FileSystem(DBusExposedObject):
    """A dbus interface to the FileSystem Manager."""

    def __init__(self, bus_name, fs_manager, action_queue):
        """Create the instance."""
        self.syncdaemon_filesystem = SyncdaemonFileSystem(fs_manager,
                                                          action_queue)
        self.path = '/filesystem'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_FS_NAME,
                         in_signature='s', out_signature='a{ss}')
    def get_metadata(self, path):
        """Return the metadata (as a dict) for the specified path."""
        logger.debug('get_metadata by path: %r', path)
        return self.syncdaemon_filesystem.get_metadata(path)

    @dbus.service.method(DBUS_IFACE_FS_NAME,
                         in_signature='ss', out_signature='a{ss}')
    def get_metadata_by_node(self, share_id, node_id):
        """Return the metadata (as a dict) for the specified share/node."""
        logger.debug('get_metadata by share: %r  node: %r', share_id, node_id)
        return self.syncdaemon_filesystem.get_metadata_by_node(share_id,
                                                               node_id)

    @dbus.service.method(DBUS_IFACE_FS_NAME,
                         in_signature='s', out_signature='a{ss}')
    def get_metadata_and_quick_tree_synced(self, path):
        """Return the dict with the attributes of the metadata for
        the specified path, including the quick subtree status.
        """
        logger.debug('get_metadata_and_quick_tree_synced: %r', path)
        return self.syncdaemon_filesystem.get_metadata_and_quick_tree_synced(
                                                                        path)

    @dbus.service.method(DBUS_IFACE_FS_NAME,
                         in_signature='', out_signature='aa{ss}')
    def get_dirty_nodes(self):
        """Rerturn a list of dirty nodes."""
        return self.syncdaemon_filesystem.get_dirty_nodes()


class Shares(DBusExposedObject):
    """A dbus interface to interact with shares."""

    def __init__(self, bus_name, fs_manager, volume_manager):
        """Create the instance."""
        self.syncdaemon_shares = SyncdaemonShares(fs_manager, volume_manager)
        self.path = '/shares'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='', out_signature='aa{ss}')
    def get_shares(self):
        """Return a list of dicts, each dict represents a share."""
        logger.debug('called get_shares')
        return self.syncdaemon_shares.get_shares()

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='s', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def accept_share(self, share_id, reply_handler=None, error_handler=None):
        """Accept a share.

        A ShareAnswerOk|Error signal will be fired in the future as a
        success/failure indicator.

        """
        logger.debug('accept_share: %r', share_id)
        self.syncdaemon_shares.accept_share(share_id, reply_handler,
                                            error_handler)


    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='s', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def reject_share(self, share_id, reply_handler=None, error_handler=None):
        """Reject a share."""
        logger.debug('reject_share: %r', share_id)
        self.syncdaemon_shares.reject_share(share_id, reply_handler,
                                            error_handler)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='s', out_signature='')
    def delete_share(self, share_id):
        """Delete a Share, both kinds: "to me" and "from me"."""
        logger.debug('delete_share: %r', share_id)
        try:
            self.syncdaemon_shares.delete_share(share_id)
        except Exception, e:
            logger.exception('Error while deleting share: %r', share_id)
            self.ShareDeleteError({'volume_id':share_id}, str(e))
            # propagate the error
            raise

    @dbus.service.method(DBUS_IFACE_SHARES_NAME, in_signature='s')
    def subscribe(self, share_id):
        """Subscribe to the specified share."""
        logger.debug('Shares.subscribe: %r', share_id)
        self.syncdaemon_shares.subscribe(share_id)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME, in_signature='s')
    def unsubscribe(self, share_id):
        """Unsubscribe from the specified share."""
        logger.debug('Shares.unsubscribe: %r', share_id)
        self.syncdaemon_shares.unsubscribe(share_id)

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}')
    def ShareChanged(self, share_dict):
        """A share changed, share_dict contains all the share attributes."""

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}')
    def ShareDeleted(self, share_dict):
        """A share was deleted, share_dict contains all available share
        attributes."""

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}s')
    def ShareDeleteError(self, share_dict, error):
        """A share was deleted, share_dict contains all available
        share attributes."""

    def emit_share_changed(self, message, share):
        """Emit ShareChanged or ShareDeleted signal for the share
        notification.
        """
        logger.debug('emit_share_changed: message %r, share %r.',
                    message, share)
        if message == 'deleted':
            self.ShareDeleted(get_share_dict(share))
        elif message == 'changed':
            self.ShareChanged(get_share_dict(share))

    def emit_share_delete_error(self, share, error):
        """Emit ShareDeleteError signal."""
        logger.info('emit_share_delete_error: share %r, error %r.',
                    share, error)
        self.ShareDeleteError(get_share_dict(share), error)

    def emit_free_space(self, share_id, free_bytes):
        """Emit ShareChanged when free space changes """
        if share_id in self.syncdaemon_shares.shares:
            share = self.syncdaemon_shares.shares[share_id]
            share_dict = get_share_dict(share)
            share_dict['free_bytes'] = unicode(free_bytes)
            self.ShareChanged(share_dict)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='ssss', out_signature='')
    def create_share(self, path, username, name, access_level):
        """Share a subtree to the user identified by username.

        @param path: that path to share (the root of the subtree)
        @param username: the username to offer the share to
        @param name: the name of the share
        @param access_level: 'View' or 'Modify'
        """
        logger.debug('create share: %r, %r, %r, %r',
                     path, username, name, access_level)
        self.syncdaemon_shares.create_share(path, username, name, access_level)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='sasss', out_signature='')
    def create_shares(self, path, usernames, name, access_level):
        """Share a subtree with several users at once.

        @param path: that path to share (the root of the subtree)
        @param usernames: the user names to offer the share to
        @param name: the name of the share
        @param access_level: 'View' or 'Modify'
        """
        logger.debug('create shares: %r, %r, %r, %r',
                     path, usernames, name, access_level)
        for user in usernames:
            self.syncdaemon_shares.create_share(path, user, name,
                                                access_level)

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}')
    def ShareCreated(self, share_info):
        """The requested share was succesfully created."""

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}s')
    def ShareCreateError(self, share_info, error):
        """An error ocurred while creating the share."""

    def emit_share_created(self, share_info):
        """Emit ShareCreated signal """
        logger.debug('emit_share_created: share_info %r.', share_info)
        self.ShareCreated(share_info)

    def emit_share_create_error(self, share_info, error):
        """Emit ShareCreateError signal."""
        info = self.syncdaemon_shares.get_create_error_share_info(share_info)
        logger.info('emit_share_create_error: share_info %r, error %r.',
                    info, error)
        self.ShareCreateError(info, error)

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='', out_signature='')
    def refresh_shares(self):
        """Refresh the share list, requesting it to the server."""
        self.syncdaemon_shares.refresh_shares()

    @dbus.service.method(DBUS_IFACE_SHARES_NAME,
                         in_signature='', out_signature='aa{ss}')
    def get_shared(self):
        """Return a list of dicts, each dict represents a shared share.
        A share might not have the path set, as we might be still fetching the
        nodes from the server. In this cases the path is ''
        """
        logger.debug('called get_shared')
        return self.syncdaemon_shares.get_shared()

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}')
    def ShareAnswerResponse(self, answer_info):
        """The answer to share was succesfull"""

    def emit_share_answer_response(self, share_id, answer, error=None):
        """Emits ShareAnswerResponse signal."""
        answer_info = dict(volume_id=share_id, answer=answer)
        if error:
            answer_info['error'] = error
        logger.debug('emit_share_answer_response: answer_info %r.', answer_info)
        self.ShareAnswerResponse(answer_info)

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME,
                         signature='a{ss}')
    def NewShare(self, share_info):
        """A new share notification."""

    def emit_new_share(self, share_id):
        """Emits NewShare signal."""
        share = self.syncdaemon_shares.get_volume(share_id)
        logger.debug('emit_new_share: share_id %r.', share_id)
        self.NewShare(get_share_dict(share))

    def emit_share_subscribed(self, share):
        """Emit the ShareSubscribed signal"""
        share_dict = get_share_dict(share)
        self.ShareSubscribed(share_dict)

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME, signature='a{ss}')
    def ShareSubscribed(self, share_info):
        """Notify the subscription to a share."""
        logger.info('Emitting ShareSubscribed %r.', share_info)

    def emit_share_subscribe_error(self, share_id, error):
        """Emit the ShareSubscribeError signal"""
        self.ShareSubscribeError({'id': share_id}, str(error))

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME, signature='a{ss}s')
    def ShareSubscribeError(self, share_info, error):
        """Notify an error while subscribing to a share."""
        logger.info('Emitting ShareSubscribeError %r %r.', share_info, error)

    def emit_share_unsubscribed(self, share):
        """Emit the ShareUnSubscribed signal"""
        share_dict = get_share_dict(share)
        self.ShareUnSubscribed(share_dict)

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME, signature='a{ss}')
    def ShareUnSubscribed(self, share_info):
        """Notify the unsubscription to a share."""
        logger.info('Emitting ShareUnSubscribed %r.', share_info)

    def emit_share_unsubscribe_error(self, share_id, error):
        """Emit the ShareUnSubscribeError signal"""
        self.ShareUnSubscribeError({'id': share_id}, str(error))

    @dbus.service.signal(DBUS_IFACE_SHARES_NAME, signature='a{ss}s')
    def ShareUnSubscribeError(self, share_info, error):
        """Notify an error while unsubscribing from a share."""
        logger.info('Emitting ShareUnSubscribeError %r %r.', share_info, error)


class Config(DBusExposedObject):
    """The Syncdaemon config/settings dbus interface."""

    def __init__(self, bus_name, dbus_iface):
        """Create the instance.

        @param bus: the BusName of this DBusExposedObject.
        """
        self.syncdaemon_config = SyncdaemonConfig(dbus_iface.main,
                                                  dbus_iface.action_queue)
        self.path = '/config'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='a{si}',
                         async_callbacks=('reply_handler', 'error_handler'))
    def get_throttling_limits(self, reply_handler=None, error_handler=None):
        """Get the read/write limit from AQ and return a dict.
        Returns a dict(download=int, upload=int), if int is -1 the value isn't
        configured.
        The values are bytes/second
        """
        logger.debug("called get_throttling_limits")
        return self.syncdaemon_config.get_throttling_limits(reply_handler,
                                                            error_handler)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='ii', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def set_throttling_limits(self, download, upload,
                         reply_handler=None, error_handler=None):
        """Set the read and write limits. The expected values are bytes/sec."""
        logger.debug("called set_throttling_limits")
        self.syncdaemon_config.set_throttling_limits(download, upload,
                                                     reply_handler,
                                                     error_handler)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def enable_bandwidth_throttling(self, reply_handler=None,
                                    error_handler=None):
        """Enable bandwidth throttling."""
        self.syncdaemon_config.enable_bandwidth_throttling(reply_handler,
                                                           error_handler)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='',
                         async_callbacks=('reply_handler', 'error_handler'))
    def disable_bandwidth_throttling(self, reply_handler=None,
                                     error_handler=None):
        """Disable bandwidth throttling."""
        self.syncdaemon_config.disable_bandwidth_throttling(reply_handler,
                                                            error_handler)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b',
                         async_callbacks=('reply_handler', 'error_handler'))
    def bandwidth_throttling_enabled(self, reply_handler=None,
                                     error_handler=None):
        """Returns True (actually 1) if bandwidth throttling is enabled and
        False (0) otherwise.
        """
        return self.syncdaemon_config.bandwidth_throttling_enabled(
                                                reply_handler, error_handler)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b')
    def udf_autosubscribe_enabled(self):
        """Return the udf_autosubscribe config value."""
        return self.syncdaemon_config.udf_autosubscribe_enabled()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def enable_udf_autosubscribe(self):
        """Enable UDF autosubscribe."""
        self.syncdaemon_config.enable_udf_autosubscribe()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def disable_udf_autosubscribe(self):
        """Disable UDF autosubscribe."""
        self.syncdaemon_config.disable_udf_autosubscribe()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b')
    def share_autosubscribe_enabled(self):
        """Return the share_autosubscribe config value."""
        return self.syncdaemon_config.share_autosubscribe_enabled()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def enable_share_autosubscribe(self):
        """Enable share autosubscribe."""
        self.syncdaemon_config.enable_share_autosubscribe()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def disable_share_autosubscribe(self):
        """Disable share autosubscribe."""
        self.syncdaemon_config.disable_share_autosubscribe()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='b', out_signature='')
    def set_files_sync_enabled(self, enabled):
        """Enable/disable file sync service."""
        logger.debug('called set_files_sync_enabled %d', enabled)
        self.syncdaemon_config.set_files_sync_enabled(enabled)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b')
    def files_sync_enabled(self):
        """Return the files_sync_enabled config value."""
        logger.debug('called files_sync_enabled')
        return self.syncdaemon_config.files_sync_enabled()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b')
    def autoconnect_enabled(self):
        """Return the autoconnect config value."""
        return self.syncdaemon_config.autoconnect_enabled()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME)
    def enable_autoconnect(self):
        """Enable syncdaemon autoconnect."""
        self.syncdaemon_config.set_autoconnect_enabled(True)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME)
    def disable_autoconnect(self):
        """Disable syncdaemon autoconnect."""
        self.syncdaemon_config.set_autoconnect_enabled(False)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='b', out_signature='')
    def set_autoconnect_enabled(self, enabled):
        """Enable syncdaemon autoconnect.

        This method is deprecated.

        """
        msg = 'Use enable_autoconnect/disable_autoconnect instead.'
        warnings.warn(msg, DeprecationWarning)
        self.syncdaemon_config.set_autoconnect_enabled(enabled)

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='b')
    def show_all_notifications_enabled(self):
        """Return the show_all_notifications config value."""
        return self.syncdaemon_config.show_all_notifications_enabled()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def enable_show_all_notifications(self):
        """Enable showing all notifications."""
        self.syncdaemon_config.enable_show_all_notifications()

    @dbus.service.method(DBUS_IFACE_CONFIG_NAME,
                         in_signature='', out_signature='')
    def disable_show_all_notifications(self):
        """Disable showing all notifications."""
        self.syncdaemon_config.disable_show_all_notifications()


class Folders(DBusExposedObject):
    """A dbus interface to interact with User Defined Folders"""

    def __init__(self, bus_name, volume_manager, fs_manager):
        """Create the instance."""
        self.syncdaemon_folders = SyncdaemonFolders(volume_manager, fs_manager)
        self.path = '/folders'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME, in_signature='s')
    def create(self, path):
        """Create a user defined folder in the specified path."""
        logger.debug('Folders.create: %r', path)
        try:
            self.syncdaemon_folders.create(path)
        except Exception, e:
            logger.exception('Error while creating udf: %r', path)
            self.emit_folder_create_error(path, str(e))

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME, in_signature='s')
    def delete(self, folder_id):
        """Delete the folder specified by folder_id"""
        from ubuntuone.syncdaemon.volume_manager import VolumeDoesNotExist
        logger.debug('Folders.delete: %r', folder_id)
        try:
            self.syncdaemon_folders.delete(folder_id)
        except VolumeDoesNotExist, e:
            self.FolderDeleteError({'volume_id':folder_id}, str(e))
        except Exception, e:
            logger.exception('Error while deleting volume: %r', folder_id)
            self.FolderDeleteError({'volume_id':folder_id}, str(e))

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME, out_signature='aa{ss}')
    def get_folders(self):
        """Return the list of folders (a list of dicts)"""
        logger.debug('Folders.get_folders')
        return self.syncdaemon_folders.get_folders()

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME,
                         in_signature='s', out_signature='')
    def subscribe(self, folder_id):
        """Subscribe to the specified folder"""
        logger.debug('Folders.subscribe: %r', folder_id)
        self.syncdaemon_folders.subscribe(folder_id)

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME,
                         in_signature='s', out_signature='')
    def unsubscribe(self, folder_id):
        """Unsubscribe from the specified folder"""
        logger.debug('Folders.unsubscribe: %r', folder_id)
        self.syncdaemon_folders.unsubscribe(folder_id)

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME,
                         in_signature='s', out_signature='a{ss}')
    def get_info(self, path):
        """Return a dict containing the folder information."""
        logger.debug('Folders.get_info: %r', path)
        return self.syncdaemon_folders.get_info(path)

    @dbus.service.method(DBUS_IFACE_FOLDERS_NAME,
                         in_signature='', out_signature='')
    def refresh_volumes(self):
        """Refresh the volumes list, requesting it to the server."""
        self.syncdaemon_folders.refresh_volumes()

    def emit_folder_created(self, folder):
        """Emit the FolderCreated signal"""
        udf_dict = get_udf_dict(folder)
        self.FolderCreated(udf_dict)

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}')
    def FolderCreated(self, folder_info):
        """Notify the creation of a user defined folder."""

    def emit_folder_create_error(self, path, error):
        """Emit the FolderCreateError signal"""
        info = dict(path=path.decode('utf-8'))
        self.FolderCreateError(info, str(error))

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}s')
    def FolderCreateError(self, folder_info, error):
        """Notify an error during the creation of a user defined folder."""

    def emit_folder_deleted(self, folder):
        """Emit the FolderCreated signal"""
        udf_dict = get_udf_dict(folder)
        self.FolderDeleted(udf_dict)

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}')
    def FolderDeleted(self, folder_info):
        """Notify the deletion of a user defined folder."""

    def emit_folder_delete_error(self, folder, error):
        """Emit the FolderCreateError signal"""
        udf_dict = get_udf_dict(folder)
        self.FolderDeleteError(udf_dict, str(error))

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}s')
    def FolderDeleteError(self, folder_info, error):
        """Notify an error during the deletion of a user defined folder."""

    def emit_folder_subscribed(self, folder):
        """Emit the FolderSubscribed signal"""
        udf_dict = get_udf_dict(folder)
        self.FolderSubscribed(udf_dict)

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}')
    def FolderSubscribed(self, folder_info):
        """Notify the subscription to a user defined folder."""

    def emit_folder_subscribe_error(self, folder_id, error):
        """Emit the FolderSubscribeError signal"""
        self.FolderSubscribeError({'id':folder_id}, str(error))

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}s')
    def FolderSubscribeError(self, folder_info, error):
        """Notify an error while subscribing to a user defined folder."""

    def emit_folder_unsubscribed(self, folder):
        """Emit the FolderUnSubscribed signal"""
        udf_dict = get_udf_dict(folder)
        self.FolderUnSubscribed(udf_dict)

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}')
    def FolderUnSubscribed(self, folder_info):
        """Notify the unsubscription to a user defined folder."""

    def emit_folder_unsubscribe_error(self, folder_id, error):
        """Emit the FolderUnSubscribeError signal"""
        self.FolderUnSubscribeError({'id':folder_id}, str(error))

    @dbus.service.signal(DBUS_IFACE_FOLDERS_NAME,
                         signature='a{ss}s')
    def FolderUnSubscribeError(self, folder_info, error):
        """Notify an error while unsubscribing from a user defined folder."""


class Launcher(DBusExposedObject):
    """A DBus interface to interact with the launcher icon."""

    def __init__(self, bus_name):
        """Create the instance."""
        self.path = '/launcher'
        DBusExposedObject.__init__(self, bus_name=bus_name,
                                   path=self.path)

    @dbus.service.method(DBUS_IFACE_LAUNCHER_NAME)
    def unset_urgency(self):
        """Unset urgency on the launcher."""
        launcher = UbuntuOneLauncher()
        launcher.set_urgent(False)


class PublicFiles(DBusExposedObject):
    """A DBus interface for handling public files."""

    def __init__(self, bus_name, fs_manager, action_queue):
        self.syncdaemon_public_files = SyncdaemonPublicFiles(fs_manager,
                                                             action_queue)
        self.path = '/publicfiles'
        DBusExposedObject.__init__(self, bus_name=bus_name, path=self.path)

    @dbus.service.method(DBUS_IFACE_PUBLIC_FILES_NAME,
                         in_signature='ssb', out_signature='')
    def change_public_access(self, share_id, node_id, is_public):
        """Change the public access of a file."""
        logger.debug('PublicFiles.change_public_access: %r, %r, %r',
                     share_id, node_id, is_public)
        self.syncdaemon_public_files.change_public_access(share_id, node_id,
                                                          is_public)

    @dbus.service.method(DBUS_IFACE_PUBLIC_FILES_NAME)
    def get_public_files(self):
        """Request the list of public files to the server.

        The result will be send in a PublicFilesList signal.
        """
        self.syncdaemon_public_files.get_public_files()

    def emit_public_access_changed(self, share_id, node_id, is_public,
                                   public_url):
        """Emit the PublicAccessChanged signal."""
        share_id = str(share_id) if share_id else ''
        node_id = str(node_id)
        path = self.syncdaemon_public_files.get_path(share_id, node_id)
        self.PublicAccessChanged(dict(
                share_id=str(share_id) if share_id else '',
                node_id=str(node_id),
                is_public=bool_str(is_public),
                public_url=public_url if public_url else '',
                path=path))

    @dbus.service.signal(DBUS_IFACE_PUBLIC_FILES_NAME,
                         signature='a{ss}')
    def PublicAccessChanged(self, file_info):
        """Notify the new public access state of a file."""

    def emit_public_access_change_error(self, share_id, node_id, error):
        """Emit the PublicAccessChangeError signal."""
        path = self.syncdaemon_public_files.get_path(share_id, node_id)
        self.PublicAccessChangeError(dict(
                share_id=str(share_id) if share_id else '',
                node_id=str(node_id),
                path=path), str(error))

    @dbus.service.signal(DBUS_IFACE_PUBLIC_FILES_NAME,
                         signature='a{ss}s')
    def PublicAccessChangeError(self, file_info, error):
        """Report an error in changing the public access of a file."""

    @dbus.service.signal(DBUS_IFACE_PUBLIC_FILES_NAME,
                        signature='aa{ss}')
    def PublicFilesList(self, files):
        """Notify the list of public files."""

    @dbus.service.signal(DBUS_IFACE_PUBLIC_FILES_NAME,
                         signature='s')
    def PublicFilesListError(self, error):
        """Report an error in geting the public files list."""

    def emit_public_files_list(self, public_files):
        """Emit the PublicFilesList signal."""
        files = []
        for pf in public_files:
            volume_id = str(pf['volume_id'])
            node_id = str(pf['node_id'])
            public_url = str(pf['public_url'])
            path = self.syncdaemon_public_files.get_path(volume_id ,
                node_id).decode('utf-8')
            files.append(dict(volume_id=volume_id, node_id=node_id,
                public_url=public_url, path=path))
        self.PublicFilesList(files)

    def emit_public_files_list_error(self, error):
        """Emit the PublicFilesListError signal."""
        self.PublicFilesListError(error)


class DBusInterface(object):
    """Holder of all DBus exposed objects."""
    test = False

    def __init__(self, bus, main, system_bus=None, send_events=False):
        """Create the instance and add the exposed object to the
        specified bus.
        """
        self.bus = bus
        self.main = main
        self.event_queue = main.event_q
        self.action_queue = main.action_q
        self.fs_manager = main.fs
        self.volume_manager = main.vm
        self.send_events = send_events
        self.busName = dbus.service.BusName(DBUS_IFACE_NAME, bus=self.bus)
        self.status = Status(self.busName, self)

        # event listeners
        self.events = Events(self.busName, self.event_queue)
        self.event_listener = SyncdaemonEventListener(self)
        if self.send_events:
            self.all_events_sender = AllEventsSender(self)
            self.event_queue.subscribe(self.all_events_sender)

        self.sync = SyncDaemon(self.busName, self)
        self.fs = FileSystem(self.busName, self.fs_manager,
                             self.action_queue)
        self.shares = Shares(self.busName, self.fs_manager,
                             self.volume_manager)
        self.folders = Folders(self.busName, self.volume_manager,
                               self.fs_manager)
        self.launcher = Launcher(self.busName)
        self.public_files = PublicFiles(
            self.busName, self.fs_manager, self.action_queue)
        self.config = Config(self.busName, self)
        if system_bus is None and not DBusInterface.test:
            logger.debug('using the real system bus')
            self.system_bus = self.bus.get_system()
        elif system_bus is None and DBusInterface.test:
            # this is just for the case when test_sync instatiate Main for
            # running it's tests as pqm don't have a system bus running
            logger.debug('using the session bus as system bus')
            self.system_bus = self.bus
        else:
            self.system_bus = system_bus

        self.event_queue.subscribe(self.event_listener)
        # on initialization, fake a SYS_NET_CONNECTED if appropriate
        if DBusInterface.test:
            # testing under sync; just do it
            logger.debug('using the fake NetworkManager')
            self.connection_state_changed(NM_STATE_CONNECTED_GLOBAL)
        else:
            def error_handler(error):
                """Handle errors from NM."""
                logger.error(
                    "Error while getting the NetworkManager state %s",
                    error)
                # If we get an error back from NetworkManager, we should
                # just try to connect anyway; it probably means that
                # NetworkManager is down or broken or something.
                self.connection_state_changed(NM_STATE_CONNECTED_GLOBAL)
            try:
                nm = self.system_bus.get_object(
                    'org.freedesktop.NetworkManager',
                    '/org/freedesktop/NetworkManager',
                    follow_name_owner_changes=True)
                iface = dbus.Interface(nm, 'org.freedesktop.NetworkManager')
            except dbus.DBusException, e:
                if e.get_dbus_name() == \
                    'org.freedesktop.DBus.Error.ServiceUnknown':
                    # NetworkManager isn't running.
                    logger.warn("Unable to connect to NetworkManager. "
                                  "Assuming we have network.")
                    self.connection_state_changed(NM_STATE_CONNECTED_GLOBAL)
                else:
                    raise
            else:
                iface.state(reply_handler=self.connection_state_changed,
                            error_handler=error_handler)

        # register a handler to NM StateChanged signal
        self.system_bus.add_signal_receiver(self.connection_state_changed,
                               signal_name='StateChanged',
                               dbus_interface='org.freedesktop.NetworkManager',
                               path='/org/freedesktop/NetworkManager')

        self.oauth_credentials = None
        self._deferred = None # for firing login/registration

        logger.info('DBusInterface initialized.')

    def shutdown(self, with_restart=False):
        """Remove the registered object from the bus and unsubscribe from the
        event queue.
        """
        logger.info('Shuttingdown DBusInterface!')
        self.status.remove_from_connection()
        self.events.remove_from_connection()
        self.sync.remove_from_connection()
        self.fs.remove_from_connection()
        self.shares.remove_from_connection()
        self.config.remove_from_connection()
        self.event_queue.unsubscribe(self.event_listener)
        if self.send_events:
            self.event_queue.unsubscribe(self.all_events_sender)
        self.folders.remove_from_connection()
        self.launcher.remove_from_connection()
        # remove the NM's StateChanged signal receiver
        self.system_bus.remove_signal_receiver(self.connection_state_changed,
                               signal_name='StateChanged',
                               dbus_interface='org.freedesktop.NetworkManager',
                               path='/org/freedesktop/NetworkManager')
        self.bus.release_name(self.busName.get_name())
        if with_restart:
            # this is what activate_name_owner boils down to, except that
            # activate_name_owner blocks, which is a luxury we can't allow
            # ourselves.
            self.bus.call_async(dbus.bus.BUS_DAEMON_NAME,
                                dbus.bus.BUS_DAEMON_PATH,
                                dbus.bus.BUS_DAEMON_IFACE,
                                'StartServiceByName', 'su',
                                (DBUS_IFACE_NAME, 0),
                                self._restart_reply_handler,
                                self._restart_error_handler)

    def _restart_reply_handler(self, *args):
        """
        This is called by the restart async call.

        It's here to be stepped on from tests; in production we are
        going away and don't really care if the async call works or
        not: there is nothing we can do about it.
        """
    _restart_error_handler = _restart_reply_handler

    def connection_state_changed(self, state):
        """Push a connection state changed event to the Event Queue."""
        event = NM_STATE_EVENTS.get(state, None)
        if event is not None:
            self.event_queue.push(event)

    @defer.inlineCallbacks
    def connect(self, autoconnecting=False):
        """Push the SYS_USER_CONNECT event with the token.

        The token is requested via com.ubuntuone.credentials service. If
        'autoconnecting' is True, no UI window will be raised to promt the user
        for login/registration, only already existent credentials will be used.

        """
        logger.info('connect was requested. Are we autoconnecting? %r.',
                    autoconnecting)
        if self.oauth_credentials is not None:
            logger.debug('connect: oauth credentials were given by parameter.')
            ckey = csecret = key = secret = None
            if len(self.oauth_credentials) == 4:
                ckey, csecret, key, secret = self.oauth_credentials
            elif len(self.oauth_credentials) == 2:
                ckey, csecret = ('ubuntuone', 'hammertime')
                key, secret = self.oauth_credentials
            else:
                msg = 'connect: oauth_credentials (%s) was set but is useless!'
                logger.warning(msg, self.oauth_credentials)
                return
            token = {'consumer_key': ckey, 'consumer_secret': csecret,
                     'token': key, 'token_secret': secret}
        else:
            token = yield self._request_token(autoconnecting=autoconnecting)

        logger.info('connect: credential request was successful, '
                    'pushing SYS_USER_CONNECT.')
        self.event_queue.push('SYS_USER_CONNECT', access_token=token)

    def _signal_handler(self, *args, **kwargs):
        """Generic signal handler."""
        member = kwargs.get('member', None)
        d = self._deferred
        logger.debug('Handling DBus signal for member: %r.', member)

        if member in ('CredentialsError', 'AuthorizationDenied',
                      'CredentialsNotFound'):
            logger.warning('%r: %r %r', member, args, kwargs)
            if not args:
                d.errback(Failure(NoAccessToken(member)))
            else:
                d.errback(Failure(NoAccessToken("%s: %s %s" %
                                                (member, args, kwargs))))
        elif member == 'CredentialsFound' and not d.called:
            credentials = args[0]
            logger.info('%r: callbacking with credentials.', member)
            d.callback(credentials)
        else:
            logger.debug('_signal_handler: member %r not used or deferred '
                         'already called? %r.', member, d)

    def _request_token(self, autoconnecting):
        """Request to SSO auth service to fetch the token."""
        self._deferred = d = defer.Deferred()

        def error_handler(error):
            """Default dbus error handler."""
            logger.error('Handling DBus error on _request_token: %r.', error)
            if not d.called:
                d.errback(Failure(error))

        # register signal handlers for each kind of error
        match = self.bus.add_signal_receiver(self._signal_handler,
                    member_keyword='member',
                    dbus_interface=DBUS_CREDENTIALS_IFACE)
        # call ubuntu sso
        try:
            client = self.bus.get_object(DBUS_BUS_NAME, DBUS_CREDENTIALS_PATH,
                                         follow_name_owner_changes=True)
            iface = dbus.Interface(client, DBUS_CREDENTIALS_IFACE)
            # ignore the reply, we get the result via signals
            if autoconnecting:
                iface.find_credentials(reply_handler=lambda: None,
                                       error_handler=error_handler)
            else:
                iface.register({'window_id': '0'},  # no window ID
                               reply_handler=lambda: None,
                               error_handler=error_handler)
        except DBusException, e:
            error_handler(e)
        except:
            logger.exception('connect failed while getting the token')
            raise

        def remove_signal_receiver(r):
            """Cleanup the signal receivers."""
            self.bus.remove_signal_receiver(
                match, dbus_interface=DBUS_CREDENTIALS_IFACE)
            return r

        d.addBoth(remove_signal_receiver)
        return d

    def disconnect(self):
        """Push the SYS_USER_DISCONNECT event."""
        self.event_queue.push('SYS_USER_DISCONNECT')

    def quit(self):
        """Call Main.quit. """
        logger.debug('Calling Main.quit')
        self.main.quit()
