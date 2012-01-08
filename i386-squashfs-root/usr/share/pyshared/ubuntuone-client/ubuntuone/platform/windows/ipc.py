# -*- coding: utf-8 -*-
#
# Authors: Manuel de la Pena <manuel@canonical.com>
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
"""IPC implementation that replaces Dbus."""

import logging

from collections import defaultdict
from threading import Thread

from twisted.internet import defer, reactor
from twisted.spread.pb import (
    DeadReferenceError,
    NoSuchMethod,
    PBServerFactory,
    Referenceable,
    Root,
)
from ubuntu_sso.main.windows import get_activation_cmdline, get_sso_pb_port
from ubuntu_sso.utils.tcpactivation import (
    ActivationClient,
    ActivationConfig,
    ActivationInstance,
    AlreadyStartedError,
)
from ubuntuone.syncdaemon.interfaces import IMarker
from ubuntuone.platform.credentials import CredentialsManagementTool
from ubuntuone.platform.windows.network_manager import NetworkManager
from ubuntuone.syncdaemon.interaction_interfaces import (
    bool_str,
    get_share_dict,
    get_udf_dict,
    SyncdaemonConfig,
    SyncdaemonEvents,
    SyncdaemonEventListener,
    SyncdaemonFileSystem,
    SyncdaemonFolders,
    SyncdaemonPublicFiles,
    SyncdaemonService,
    SyncdaemonShares,
    SyncdaemonStatus
)

logger = logging.getLogger("ubuntuone.SyncDaemon.Pb")
LOCALHOST = "127.0.0.1"
SD_SSO_PORT_OFFSET = 1
SD_SERVICE_NAME = "ubuntuone-syncdaemon"
CLIENT_NOT_PROCESSED = -1


def get_sd_pb_port():
    """Returns the host and port for this user."""
    return get_sso_pb_port() + SD_SSO_PORT_OFFSET


def get_activation_config():
    """Get the configuration to activate the sso service."""
    port = get_sd_pb_port()
    service_name = SD_SERVICE_NAME
    cmdline = get_activation_cmdline(service_name)
    return ActivationConfig(service_name, cmdline, port)


def ipc_server_listen(server_factory):
    """Connect the IPC server factory."""
    port = get_sd_pb_port()
    # pylint: disable=E1101
    return reactor.listenTCP(port, server_factory, interface=LOCALHOST)


@defer.inlineCallbacks
def is_already_running():
    """Return if the sd is running by trying to get the port."""
    ai = ActivationInstance(get_activation_config())
    try:
        yield ai.get_port()
        defer.returnValue(False)
    except AlreadyStartedError:
        defer.returnValue(True)


@defer.inlineCallbacks
def ipc_client_connect(client_factory):
    """Connect the IPC client factory."""
    ac = ActivationClient(get_activation_config())
    port = yield ac.get_active_port()
    # pylint: disable=E1101
    connector = reactor.connectTCP(LOCALHOST, port, client_factory)
    defer.returnValue(connector)


class NoAccessToken(Exception):
    """The access token could not be retrieved."""


def remote_handler(handler):
    if handler:
        handler = lambda x: handler.callRemote('execute', x)
    return handler


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


class RemoteMeta(type):
    """Append remte_ to the remote methods.

    Remote has to be appended to the remote method to work over pb but this
    names cannot be used since the other platforms do not expect the remote
    prefix. This metaclass create those prefix so that the methods can be
    correctly called.
    """

    def __new__(cls, name, bases, attrs):
        remote_calls = attrs.get('remote_calls', [])
        signal_handlers = attrs.get('signal_handlers', [])
        for current in remote_calls + signal_handlers:
            attrs['remote_' + current] = attrs[current]
        return super(RemoteMeta, cls).__new__(cls, name, bases, attrs)


class SignalBroadcaster(object):
    """Object that allows to emit signals to clients over the IPC."""

    MSG_NO_SIGNAL_HANDLER = "No signal handler for %r in %r"
    MSG_COULD_NOT_EMIT_SIGNAL = "Could not emit signal %r to %r due to %r"

    def __init__(self):
        """Create a new instance."""
        self.clients_per_signal = defaultdict(set)

    def _ignore_no_such_method(self, failure, signal_name, current_client):
        """NoSuchMethod is not an error, ignore it."""
        failure.trap(NoSuchMethod)
        logger.debug(self.MSG_NO_SIGNAL_HANDLER, signal_name, current_client)

    def _other_failure(self, failure, signal_name, current_client):
        """Log the issue when emitting a signal."""
        logger.warning(self.MSG_COULD_NOT_EMIT_SIGNAL, signal_name,
                    current_client, failure.value)
        logger.warning('Traceback is:\n%s', failure.printDetailedTraceback())

    def remote_register_to_signals(self, client, signals):
        """Allow a client to register to some signals."""
        for signal in signals:
            self.clients_per_signal[signal].add(client)

    def remote_unregister_to_signals(self, client):
        """Allow a client to unregister from the signal."""
        for connected_clients in self.clients_per_signal.values():
            if client in connected_clients:
                connected_clients.remove(client)

    def emit_signal(self, signal_name, *args, **kwargs):
        """Emit the given signal to the clients."""
        logger.debug("emitting %r to all connected clients.", signal_name)
        dead_clients = set()
        for current_client in self.clients_per_signal[signal_name]:
            try:
                d = current_client.callRemote(signal_name, *args, **kwargs)
                d.addErrback(self._ignore_no_such_method, signal_name,
                                                          current_client)
                d.addErrback(self._other_failure, signal_name, current_client)
            except DeadReferenceError:
                dead_clients.add(current_client)
        for client in dead_clients:
            self.remote_unregister_to_signals(client)


class Status(Referenceable, SignalBroadcaster):
    """ Represent the status of the syncdaemon """

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'current_status',
        'current_downloads',
        'waiting',
        'waiting_metadata',
        'waiting_content',
        'current_uploads',
    ]

    def __init__(self, main, action_queue, fs_manager):
        """ Creates the instance."""
        super(Status, self).__init__()
        self.syncdaemon_status = SyncdaemonStatus(main, action_queue,
            fs_manager)

    def current_status(self):
        """ return the current status of the system, one of: local_rescan,
        offline, trying_to_connect, server_rescan or online.
        """
        logger.debug('called current_status')
        return self.syncdaemon_status.current_status()

    def current_downloads(self):
        """Return a list of files with a download in progress."""
        logger.debug('called current_downloads')
        return self.syncdaemon_status.current_downloads()

    def waiting(self):
        """Return a list of the operations in action queue."""
        logger.debug('called waiting')
        commands = self.syncdaemon_status.waiting()
        for op, op_id, data  in commands:
            sanitize_dict(data)
        return commands

    def waiting_metadata(self):
        """Return a list of the operations in the meta-queue.

        As we don't have meta-queue anymore, this is faked.
        """
        logger.debug('called waiting_metadata')
        return self.syncdaemon_status.waiting_metadata()

    def waiting_content(self):
        """Return a list of files that are waiting to be up- or downloaded.

        As we don't have content-queue anymore, this is faked.
        """
        logger.debug('called waiting_content')
        return self.syncdaemon_status.waiting_content()

    def current_uploads(self):
        """ return a list of files with a upload in progress """
        logger.debug('called current_uploads')
        return self.syncdaemon_status.current_uploads()

    def emit_content_queue_changed(self):
        """Emit ContentQueueChanged."""
        self.emit_signal('on_content_queue_changed')

    def emit_invalid_name(self, dirname, filename):
        """Emit InvalidName."""
        self.emit_signal('on_invalid_name', unicode(dirname), str(filename))

    def emit_broken_node(self, volume_id, node_id, mdid, path):
        """Emit BrokenNode."""
        if mdid is None:
            mdid = ''
        if path is None:
            path = ''
        self.emit_signal('on_broken_node', volume_id, node_id, mdid,
            path.decode('utf8'))

    def emit_status_changed(self, state):
        """Emit StatusChanged."""
        self.emit_signal('on_status_changed',
                         self.syncdaemon_status.current_status())

    def emit_download_started(self, download):
        """Emit DownloadStarted."""
        self.emit_signal('on_download_started', download)

    def emit_download_file_progress(self, download, **info):
        """Emit DownloadFileProgress."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.emit_signal('on_download_file_progress', download, info)

    def emit_download_finished(self, download, **info):
        """Emit DownloadFinished."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.emit_signal('on_download_finished', download, info)

    def emit_upload_started(self, upload):
        """Emit UploadStarted."""
        self.emit_signal('on_upload_started', upload)

    def emit_upload_file_progress(self, upload, **info):
        """Emit UploadFileProgress."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.emit_signal('on_upload_file_progress', upload, info)

    def emit_upload_finished(self, upload, **info):
        """Emit UploadFinished."""
        for k, v in info.copy().items():
            info[str(k)] = str(v)
        self.emit_signal('on_upload_finished', upload, info)

    def emit_account_changed(self, account_info):
        """Emit AccountChanged."""
        info_dict = {'purchased_bytes': unicode(account_info.purchased_bytes)}
        self.emit_signal('on_account_changed', info_dict)

    def emit_metaqueue_changed(self):
        """Emit MetaQueueChanged."""
        self.emit_signal('on_metaqueue_changed')

    def emit_requestqueue_added(self, op_name, op_id, data):
        """Emit RequestQueueAdded."""
        sanitize_dict(data)
        self.emit_signal('on_request_queue_added', op_name, str(op_id), data)

    def emit_requestqueue_removed(self, op_name, op_id, data):
        """Emit RequestQueueRemoved."""
        sanitize_dict(data)
        self.emit_signal('on_request_queue_removed', op_name, str(op_id), data)

class Events(Referenceable, SignalBroadcaster):
    """The events of the system translated to ipc signals."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'push_event',
    ]

    def __init__(self, event_queue):
        super(Events, self).__init__()
        self.events = SyncdaemonEvents(event_queue)

    def emit_event(self, event):
        """Emit the signal."""
        event_dict = {}
        for key, value in event.iteritems():
            event_dict[str(key)] = str(value)
        self.emit_signal('on_event', event_dict)

    def push_event(self, event_name, args):
        """Push an event to the event queue."""
        logger.debug('push_event: %r with %r', event_name, args)
        self.events.push_event(event_name, args)


class SyncDaemon(Referenceable, SignalBroadcaster):
    """ The Daemon ipc interface. """

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'connect',
        'disconnect',
        'get_rootdir',
        'get_sharesdir',
        'get_sharesdir_link',
        'wait_for_nirvana',
        'quit',
        'rescan_from_scratch',
    ]

    def __init__(self, root, main, volume_manager, action_queue):
        """ Creates the instance."""
        super(SyncDaemon, self).__init__()
        self.service = SyncdaemonService(root, main, volume_manager,
            action_queue)
        self.clients = []

    def connect(self):
        """ Connect to the server. """
        logger.debug('connect requested')
        self.service.connect()

    def disconnect(self):
        """ Disconnect from the server. """
        logger.debug('disconnect requested')
        self.service.disconnect()

    def get_rootdir(self):
        """ Returns the root dir/mount point. """
        logger.debug('called get_rootdir')
        return self.service.get_rootdir()

    def get_sharesdir(self):
        """ Returns the shares dir/mount point. """
        logger.debug('called get_sharesdir')
        return self.service.get_sharesdir()

    def get_sharesdir_link(self):
        """ Returns the shares dir/mount point. """
        logger.debug('called get_sharesdir_link')
        return self.service.get_sharesdir_link()

    def wait_for_nirvana(self, last_event_interval,
                         reply_handler=None, error_handler=None):
        """ call the reply handler when there are no more
        events or transfers.
        """
        logger.debug('called wait_for_nirvana')
        return self.service.wait_for_nirvana(last_event_interval,
            remote_handler(reply_handler), remote_handler(error_handler))

    def quit(self, reply_handler=None, error_handler=None):
        """ shutdown the syncdaemon. """
        logger.debug('Quit requested')
        self.service.quit(remote_handler(reply_handler),
            remote_handler(error_handler))

    def rescan_from_scratch(self, volume_id):
        """Request a rescan from scratch of the volume with volume_id."""
        self.service.rescan_from_scratch(volume_id)

    def emit_root_mismatch(self, root_id, new_root_id):
        """Emit RootMismatch signal."""
        self.emit_signal('on_root_mismatch', root_id, new_root_id)

    def emit_quota_exceeded(self, volume_dict):
        """Emit QuotaExceeded signal."""
        self.emit_signal('on_quota_exceeded', volume_dict)


class FileSystem(object, Referenceable):
    """ An ipc interface to the FileSystem Manager. """

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'get_metadata',
        'get_metadata_by_node',
        'get_metadata_and_quick_tree_synced',
        'get_dirty_nodes',
    ]

    def __init__(self, fs_manager, action_queue):
        """ Creates the instance. """
        super(FileSystem, self).__init__()
        self.syncdaemon_filesystem = SyncdaemonFileSystem(fs_manager,
            action_queue)

    def get_metadata(self, path):
        """Return the metadata (as a dict) for the specified path."""
        logger.debug('get_metadata by path: %r', path)
        return self.syncdaemon_filesystem.get_metadata(path)

    def get_metadata_by_node(self, share_id, node_id):
        """Return the metadata (as a dict) for the specified share/node."""
        logger.debug('get_metadata by share: %r  node: %r', share_id, node_id)
        return self.syncdaemon_filesystem.get_metadata_by_node(share_id,
                                                               node_id)

    def get_metadata_and_quick_tree_synced(self, path):
        """ returns the dict with the attributes of the metadata for
        the specified path, including the quick subtree status.
        """
        logger.debug('get_metadata_and_quick_tree_synced: %r', path)
        return self.syncdaemon_filesystem.get_metadata_and_quick_tree_synced(
            path)

    def get_dirty_nodes(self):
        """Return a list of dirty nodes."""
        return self.syncdaemon_filesystem.get_dirty_nodes()


class Shares(Referenceable, SignalBroadcaster):
    """A ipc interface to interact with shares."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
       'get_shares',
       'accept_share',
       'reject_share',
       'delete_share',
       'subscribe',
       'unsubscribe',
       'create_share',
       'create_shares',
       'refresh_shares',
       'get_shared',
    ]

    def __init__(self, fs_manager, volume_manager):
        """Create the instance."""
        super(Shares, self).__init__()
        self.syncdaemon_shares = SyncdaemonShares(fs_manager, volume_manager)

    def get_shares(self):
        """Return a list of dicts, each dict represents a share."""
        logger.debug('called get_shares')
        return self.syncdaemon_shares.get_shares()

    def accept_share(self, share_id, reply_handler=None, error_handler=None):
        """Accept a share.

        A ShareAnswerOk|Error signal will be fired in the future as a
        success/failure indicator.

        """
        logger.debug('accept_share: %r', share_id)
        self.syncdaemon_shares.accept_share(share_id,
            remote_handler(reply_handler), remote_handler(error_handler))

    def reject_share(self, share_id, reply_handler=None, error_handler=None):
        """Reject a share."""
        logger.debug('reject_share: %r', share_id)
        self.syncdaemon_shares.reject_share(share_id,
            remote_handler(reply_handler),
            remote_handler(error_handler))

    def delete_share(self, share_id):
        """Delete a Share, both kinds: "to me" and "from me"."""
        logger.debug('delete_share: %r', share_id)
        try:
            self.syncdaemon_shares.delete_share(share_id)
        except Exception, e:
            logger.exception('Error while deleting share: %r', share_id)
            self.emit_share_delete_error({'volume_id':share_id}, str(e))
            # propagate the error
            raise

    def subscribe(self, share_id):
        """Subscribe to the specified share."""
        logger.debug('Shares.subscribe: %r', share_id)
        self.syncdaemon_shares.subscribe(share_id)

    def unsubscribe(self, share_id):
        """Unsubscribe from the specified share."""
        logger.debug('Shares.unsubscribe: %r', share_id)
        self.syncdaemon_shares.unsubscribe(share_id)

    def emit_share_changed(self, message, share):
        """ emits ShareChanged or ShareDeleted signal for the share
        notification.
        """
        logger.debug('emit_share_changed: message %r, share %r.',
                    message, share)
        if message == 'deleted':
            self.emit_signal('on_share_deleted', get_share_dict(share))
        elif message == 'changed':
            self.emit_signal('on_share_changed', get_share_dict(share))

    def emit_share_delete_error(self, share, error):
        """Emits ShareDeleteError signal."""
        logger.info('emit_share_delete_error: share %r, error %r.',
                    share, error)
        self.emit_signal('on_share_delete_error',
            get_share_dict(share), error)

    def emit_free_space(self, share_id, free_bytes):
        """ emits ShareChanged when free space changes """
        if share_id in self.syncdaemon_shares.shares:
            share = self.syncdaemon_shares.shares[share_id]
            share_dict = get_share_dict(share)
            share_dict['free_bytes'] = unicode(free_bytes)
            self.emit_signal('on_share_changed',
                share_dict)

    def create_share(self, path, username, name, access_level):
        """ Share a subtree to the user identified by username.

        @param path: that path to share (the root of the subtree)
        @param username: the username to offer the share to
        @param name: the name of the share
        @param access_level: 'View' or 'Modify'
        """
        logger.debug('create share: %r, %r, %r, %r',
                     path, username, name, access_level)
        self.syncdaemon_shares.create_share(path, username, name, access_level)

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

    def emit_share_created(self, share_info):
        """ emits ShareCreated signal """
        logger.debug('emit_share_created: share_info %r.', share_info)
        self.emit_signal('on_share_created',
                share_info)

    def emit_share_create_error(self, share_info, error):
        """Emit ShareCreateError signal."""
        info = self.syncdaemon_shares.get_create_error_share_info(share_info)
        logger.info('emit_share_create_error: share_info %r, error %r.',
                    info, error)
        self.emit_signal('on_share_create_error', info, error)

    def refresh_shares(self):
        """ Refresh the share list, requesting it to the server. """
        self.syncdaemon_shares.refresh_shares()

    def get_shared(self):
        """ returns a list of dicts, each dict represents a shared share.
        A share might not have the path set, as we might be still fetching the
        nodes from the server. In this cases the path is ''
        """
        logger.debug('called get_shared')
        return self.syncdaemon_shares.get_shared()

    def emit_share_answer_response(self, share_id, answer, error=None):
        """Emits ShareAnswerResponse signal."""
        answer_info = dict(volume_id=share_id, answer=answer)
        if error:
            answer_info['error'] = error
        logger.debug('emit_share_answer_response: answer_info %r.', answer_info)
        self.emit_signal('on_share_answer_response', answer_info)

    def emit_new_share(self, share_id):
        """Emits NewShare signal."""
        share = self.syncdaemon_shares.get_volume(share_id)
        logger.debug('emit_new_share: share_id %r.', share_id)
        self.emit_signal('on_new_share', get_share_dict(share))

    def emit_share_subscribed(self, share):
        """Emit the ShareSubscribed signal"""
        self.emit_signal('on_share_subscribed', get_share_dict(share))

    def emit_share_subscribe_error(self, share_id, error):
        """Emit the ShareSubscribeError signal"""
        self.emit_signal('on_share_subscribe_error', {'id': share_id},
            str(error))

    def emit_share_unsubscribed(self, share):
        """Emit the ShareUnSubscribed signal"""
        self.emit_signal('on_share_unsubscribed', get_share_dict(share))

    def emit_share_unsubscribe_error(self, share_id, error):
        """Emit the ShareUnSubscribeError signal"""
        self.emit_signal('on_share_unsubscribe_error', {'id': share_id},
            str(error))

class Config(object, Referenceable):
    """ The Syncdaemon config/settings ipc interface. """

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'get_throttling_limits',
        'set_throttling_limits',
        'disable_udf_autosubscribe',
        'enable_udf_autosubscribe',
        'enable_bandwidth_throttling',
        'disable_bandwidth_throttling',
        'bandwidth_throttling_enabled',
        'udf_autosubscribe_enabled',
        'enable_udf_autosubscribe',
        'share_autosubscribe_enabled',
        'enable_share_autosubscribe',
        'disable_share_autosubscribe',
        'set_files_sync_enabled',
        'files_sync_enabled',
        'autoconnect_enabled',
        'set_autoconnect_enabled',
        'show_all_notifications_enabled',
        'enable_show_all_notifications',
        'disable_show_all_notifications'
    ]

    def __init__(self, main, action_queue):
        """ Creates the instance."""
        super(Config, self).__init__()
        self.syncdaemon_config = SyncdaemonConfig(main, action_queue)

    def get_throttling_limits(self, reply_handler=None, error_handler=None):
        """Get the read/write limit from AQ and return a dict.
        Returns a dict(download=int, upload=int), if int is -1 the value isn't
        configured.
        The values are bytes/second
        """
        logger.debug("called get_throttling_limits")
        return self.syncdaemon_config.get_throttling_limits(
            remote_handler(reply_handler), remote_handler(error_handler))

    def set_throttling_limits(self, download, upload,
                         reply_handler=None, error_handler=None):
        """Set the read and write limits. The expected values are bytes/sec."""
        logger.debug("called set_throttling_limits")
        self.syncdaemon_config.set_throttling_limits(download, upload,
            remote_handler(reply_handler), remote_handler(error_handler))

    def enable_bandwidth_throttling(self, reply_handler=None,
                                    error_handler=None):
        """Enable bandwidth throttling."""
        self.syncdaemon_config.enable_bandwidth_throttling(
            remote_handler(reply_handler), remote_handler(error_handler))

    def disable_bandwidth_throttling(self, reply_handler=None,
                                     error_handler=None):
        """Disable bandwidth throttling."""
        self.syncdaemon_config.disable_bandwidth_throttling(
            remote_handler(reply_handler), remote_handler(error_handler))

    def bandwidth_throttling_enabled(self, reply_handler=None,
                                     error_handler=None):
        """Returns True (actually 1) if bandwidth throttling is enabled and
        False (0) otherwise.
        """
        return self.syncdaemon_config.bandwidth_throttling_enabled(
            remote_handler(reply_handler), remote_handler(error_handler))

    def udf_autosubscribe_enabled(self):
        """Return the udf_autosubscribe config value."""
        return self.syncdaemon_config.udf_autosubscribe_enabled()

    def enable_udf_autosubscribe(self):
        """Enable UDF autosubscribe."""
        self.syncdaemon_config.enable_udf_autosubscribe()

    def disable_udf_autosubscribe(self):
        """Enable UDF autosubscribe."""
        self.syncdaemon_config.disable_udf_autosubscribe()

    def share_autosubscribe_enabled(self):
        """Return the share_autosubscribe config value."""
        return self.syncdaemon_config.share_autosubscribe_enabled()

    def enable_share_autosubscribe(self):
        """Enable UDF autosubscribe."""
        self.syncdaemon_config.enable_share_autosubscribe()

    def disable_share_autosubscribe(self):
        """Enable UDF autosubscribe."""
        self.syncdaemon_config.disable_share_autosubscribe()

    def set_files_sync_enabled(self, enabled):
        """Enable/disable file sync service."""
        logger.debug('called set_files_sync_enabled %d', enabled)
        self.syncdaemon_config.set_files_sync_enabled(enabled)

    def files_sync_enabled(self):
        """Return the files_sync_enabled config value."""
        logger.debug('called files_sync_enabled')
        return self.syncdaemon_config.files_sync_enabled()

    def autoconnect_enabled(self):
        """Return the autoconnect config value."""
        return self.syncdaemon_config.autoconnect_enabled()

    def set_autoconnect_enabled(self, enabled):
        """Enable syncdaemon autoconnect."""
        self.syncdaemon_config.set_autoconnect_enabled(enabled)

    def show_all_notifications_enabled(self):
        """Return the show_all_notifications config value."""
        return self.syncdaemon_config.show_all_notifications_enabled()

    def enable_show_all_notifications(self):
        """Enable showing all notifications."""
        self.syncdaemon_config.enable_show_all_notifications()

    def disable_show_all_notifications(self):
        """Disable showing all notifications."""
        self.syncdaemon_config.disable_show_all_notifications()


class Folders(Referenceable, SignalBroadcaster):
    """An interface to interact with User Defined Folders"""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'create',
        'delete',
        'get_folders',
        'subscribe',
        'unsubscribe',
        'get_info',
        'refresh_volumes',
    ]

    def __init__(self, volume_manager, fs_manager):
        """Creates the instance."""
        super(Folders, self).__init__()
        self.syncdaemon_folders = SyncdaemonFolders(volume_manager, fs_manager)

    def create(self, path):
        """Create a user defined folder in the specified path."""
        logger.debug('Folders.create: %r', path)
        try:
            self.syncdaemon_folders.create(path)
        except Exception, e:
            logger.exception('Error while creating udf: %r', path)
            self.emit_folder_create_error(path, str(e))

    def delete(self, folder_id):
        """Delete the folder specified by folder_id"""
        from ubuntuone.syncdaemon.volume_manager import VolumeDoesNotExist
        logger.debug('Folders.delete: %r', folder_id)
        try:
            self.syncdaemon_folders.delete(folder_id)
        except VolumeDoesNotExist, e:
            self.emit_folder_delete_error(folder_id, e)
        except Exception, e:
            logger.exception('Error while deleting volume: %r', folder_id)
            self.emit_folder_delete_error(folder_id, e)

    def get_folders(self):
        """Return the list of folders (a list of dicts)"""
        logger.debug('Folders.get_folders')
        return self.syncdaemon_folders.get_folders()

    def subscribe(self, folder_id):
        """Subscribe to the specified folder"""
        logger.debug('Folders.subscribe: %r', folder_id)
        self.syncdaemon_folders.subscribe(folder_id)

    def unsubscribe(self, folder_id):
        """Unsubscribe from the specified folder"""
        logger.debug('Folders.unsubscribe: %r', folder_id)
        self.syncdaemon_folders.unsubscribe(folder_id)

    def get_info(self, path):
        """Returns a dict containing the folder information."""
        logger.debug('Folders.get_info: %r', path)
        return self.syncdaemon_folders.get_info(path)

    def refresh_volumes(self):
        """Refresh the volumes list, requesting it to the server."""
        self.syncdaemon_folders.refresh_volumes()

    def emit_folder_created(self, folder):
        """Emit the FolderCreated signal"""
        udf_dict = get_udf_dict(folder)
        self.emit_signal('on_folder_created', udf_dict)

    def emit_folder_create_error(self, path, error):
        """Emit the FolderCreateError signal"""
        info = dict(path=path.decode('utf-8'))
        self.emit_signal('on_folder_create_error', info, str(error))

    def emit_folder_deleted(self, folder):
        """Emit the FolderCreated signal"""
        udf_dict = get_udf_dict(folder)
        self.emit_signal('on_folder_deleted', udf_dict)

    def emit_folder_delete_error(self, folder, error):
        """Emit the FolderCreateError signal"""
        udf_dict = get_udf_dict(folder)
        self.emit_signal('on_folder_delete_error', udf_dict, str(error))

    def emit_folder_subscribed(self, folder):
        """Emit the FolderSubscribed signal"""
        udf_dict = get_udf_dict(folder)
        self.emit_signal('on_folder_subscribed', udf_dict)

    def emit_folder_subscribe_error(self, folder_id, error):
        """Emit the FolderSubscribeError signal"""
        self.emit_signal('on_folder_subscribe_error', {'id':folder_id},
            str(error))

    def emit_folder_unsubscribed(self, folder):
        """Emit the FolderUnSubscribed signal"""
        udf_dict = get_udf_dict(folder)
        self.emit_signal('on_folder_unsubscribed', udf_dict)

    def emit_folder_unsubscribe_error(self, folder_id, error):
        """Emit the FolderUnSubscribeError signal"""
        self.emit_signal('on_folder_unsubscribe_error',
            {'id':folder_id}, str(error))


class PublicFiles(Referenceable, SignalBroadcaster):
    """An IPC interface for handling public files."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'change_public_access',
        'get_public_files',
    ]

    def __init__(self, fs_manager, action_queue):
        super(PublicFiles, self).__init__()
        self.syncdaemon_public_files = SyncdaemonPublicFiles(fs_manager,
            action_queue)

    def change_public_access(self, share_id, node_id, is_public):
        """Change the public access of a file."""
        logger.debug('PublicFiles.change_public_access: %r, %r, %r',
                     share_id, node_id, is_public)
        self.syncdaemon_public_files.change_public_access(share_id, node_id,
            is_public)

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
        info = dict(
            share_id=str(share_id) if share_id else '',
            node_id=str(node_id),
            is_public=bool_str(is_public),
            public_url=public_url if public_url else '',
            path=path)
        self.emit_signal('on_public_access_changed', info)

    def emit_public_access_change_error(self, share_id, node_id, error):
        """Emit the PublicAccessChangeError signal."""
        path = self.syncdaemon_public_files.get_path(share_id, node_id)
        info = dict(
            share_id=str(share_id) if share_id else '',
            node_id=str(node_id),
            path=path)
        self.emit_signal('on_public_access_change_error', info, str(error))

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
        self.emit_signal('on_public_files_list', files)

    def emit_public_files_list_error(self, error):
        """Emit the PublicFilesListError signal."""
        self.emit_signal('on_public_files_list_error', str(error))


class AllEventsSender(object):
    """Event listener that sends all of them through DBus."""

    def __init__(self, events):
        self.events = events

    def handle_default(self, event_name, **kwargs):
        """Handle all events."""
        event_dict = {'event_name': event_name}
        event_dict.update(kwargs)
        self.events.emit_event(event_dict)


class IPCRoot(object, Root):
    """Root object that exposes the diff referenceable objects."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'get_status',
        'get_events',
        'get_sync_daemon',
        'get_file_system',
        'get_shares',
        'get_config',
        'get_folders',
        'get_public_files']

    def __init__(self, ipc_interface, main, send_events=False,
                 all_events=AllEventsSender):
        """Create a new instance that will expose the objects."""
        super(IPCRoot, self).__init__()
        self.main = main
        self.event_queue = main.event_q
        self.action_queue = main.action_q
        self.fs_manager = main.fs
        self.volume_manager = main.vm
        self.send_events = send_events
        self.status = Status(self.main, self.action_queue, self.fs_manager)

        # event listeners
        self.events = Events(self.event_queue)
        self.event_listener = SyncdaemonEventListener(self)

        if self.send_events:
            self.all_events_sender = all_events(self.events)
            self.event_queue.subscribe(self.all_events_sender)

        self.sync = SyncDaemon(ipc_interface, self.main, self.volume_manager,
                               self.action_queue)
        self.fs = FileSystem(self.fs_manager, self.action_queue)
        self.shares = Shares(self.fs_manager, self.volume_manager)
        self.folders = Folders(self.volume_manager, self.fs_manager)
        self.public_files = PublicFiles(self.fs_manager, self.action_queue)
        self.config = Config(self.main, self.action_queue)
        self.event_queue.subscribe(self.event_listener)
        logger.info('Root initialized.')

    def get_status(self):
        """Return the status remote object."""
        return self.status

    def get_events(self):
        """Return the events remote object."""
        return self.events

    def get_sync_daemon(self):
        """Return the sync daemon remote object."""
        return self.sync

    def get_file_system(self):
        """Return the file system remote object."""
        return self.fs

    def get_shares(self):
        """Return the shares remote object."""
        return self.shares

    def get_config(self):
        """Return the config remote object."""
        return self.config

    def get_folders(self):
        """Return the folders remote object."""
        return self.folders

    def get_public_files(self):
        """Return the public files remote object."""
        return self.public_files


class IPCInterface(object):
    """ Holder of all exposed objects """
    test = False

    def __init__(self, main, send_events=False):
        """ Create the instance and add the exposed object to the
        specified bus.
        """
        super(IPCInterface, self).__init__()
        self.root = IPCRoot(self, main, send_events)
        self.listener = ipc_server_listen(PBServerFactory(self.root))
        self.main = main

        # on initialization, fake a SYS_NET_CONNECTED if appropriate
        if IPCInterface.test:
            # testing under sync; just do it
            logger.debug('using the fake NetworkManager')
            self.network_connected()
        else:
            self.network_connected()
            # register to future network changes
            self.network_manager = NetworkManager(
                                    connected_cb=self.network_connected,
                                    disconnected_cb=self.network_disconnected)
            self.network_manager_thread = Thread(
                target=self.network_manager.register, name='Network changes')
            self.network_manager_thread.daemon = True
            self.network_manager_thread.start()

        self.oauth_credentials = None
        self._deferred = None # for firing login/registration
        self.creds = None
        logger.info('IPC initialized.')

    def shutdown(self, with_restart=False):
        """Remove the registered object from the bus and unsubscribe from the
        event queue.
        """
        logger.info('IPC Shuttingdown !')
        self.listener.stopListening()
        if self.root.send_events:
            self.root.event_queue.unsubscribe(self.root.all_events_sender)
        if with_restart:
            self.listener.startListening()

    def network_connected(self):
        """Push the connected event."""
        self.root.event_queue.push('SYS_NET_CONNECTED')

    def network_disconnected(self):
        """Push the disconnected event."""
        self.root.event_queue.push('SYS_NET_DISCONNECTED')

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
            try:
                token = yield self._request_token(
                                            autoconnecting=autoconnecting)
            except Exception, e:
                logger.exception('failure while getting the token')
                raise NoAccessToken(e)

            if not token:
                raise NoAccessToken("got empty credentials.")

        self.main.event_q.push('SYS_USER_CONNECT', access_token=token)

    def _request_token(self, autoconnecting):
        """Request to SSO auth service to fetch the token."""
        # call ubuntu sso
        management = CredentialsManagementTool()
        # return the deferred, since we are no longer using signals
        if autoconnecting:
            return management.find_credentials()
        else:
            return management.register(window_id=0)  # no window ID

    def disconnect(self):
        """ Push the SYS_USER_DISCONNECT event. """
        self.main.event_q.push('SYS_USER_DISCONNECT')

    def quit(self):
        """ calls Main.quit. """
        logger.debug('Calling Main.quit')
        self.main.quit()
