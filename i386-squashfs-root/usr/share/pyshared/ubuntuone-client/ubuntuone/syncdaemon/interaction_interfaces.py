# ubuntuone.syncdaemon.interfaces - ActionQueue interface
#
# Authors: Manuel de la Pena <manuel@canonical.com>
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
"""Interfaces used to interact with the sync daemon."""
import logging
import os
import uuid

from ubuntuone.syncdaemon import config
from ubuntuone.syncdaemon.action_queue import Download, Upload
from ubuntuone.platform import normpath

logger = logging.getLogger("ubuntuone.SyncDaemon.InteractionInterfaces")


def bool_str(value):
    """Return a string value that can be converted back to bool."""
    return 'True' if value else ''


def get_share_dict(share):
    """Get a dict with all the attributes of: share."""
    share_dict = share.__dict__.copy()
    if 'subscribed' not in share_dict:
        share_dict['subscribed'] = share.subscribed
    for k, v in share_dict.items():
        if v is None:
            share_dict[unicode(k)] = ''
        elif k == 'path':
            share_dict[unicode(k)] = v.decode('utf-8')
        elif k == 'accepted' or k == 'subscribed':
            share_dict[unicode(k)] = bool_str(v)
        else:
            share_dict[unicode(k)] = unicode(v)
    return share_dict


def get_udf_dict(udf):
    """Get a dict with all the attributes of: udf."""
    udf_dict = udf.__dict__.copy()
    for k, v in udf_dict.items():
        if v is None:
            udf_dict[unicode(k)] = ''
        elif k == 'subscribed':
            udf_dict[unicode(k)] = bool_str(v)
        elif k == 'path':
            udf_dict[unicode(k)] = v.decode('utf-8')
        elif k == 'suggested_path' and isinstance(v, str):
            udf_dict[unicode(k)] = v.decode('utf-8')
        else:
            udf_dict[unicode(k)] = unicode(v)
    return udf_dict


class SyncdaemonStatus(object):
    """Represent the status of the syncdaemon."""

    def __init__(self, main, action_queue, fs_manager):
        """Creates the instance."""
        super(SyncdaemonStatus, self).__init__()
        self.main = main
        self.action_queue = action_queue
        self.fs_manager = fs_manager

    def _get_current_state(self):
        """Get the current status of the system."""
        state = self.main.state_manager.state
        connection = self.main.state_manager.connection.state
        queues = self.main.state_manager.queues.state.name
        state_dict = {
            'name': state.name,
            'description': state.description,
            'is_error': bool_str(state.is_error),
            'is_connected': bool_str(state.is_connected),
            'is_online': bool_str(state.is_online),
            'queues': queues,
            'connection': connection,
        }
        return state_dict

    def current_status(self):
        """Return the current status of the system, one of: local_rescan,
        offline, trying_to_connect, server_rescan or online.
        """
        logger.debug('called current_status')
        return self._get_current_state()

    def current_downloads(self):
        """Return a list of files with a download in progress."""
        logger.debug('called current_downloads')
        current_downloads = []
        for cmd in self.action_queue.queue.waiting:
            if isinstance(cmd, Download) and cmd.running:
                entry = {
                    'path': cmd.path,
                    'share_id': cmd.share_id,
                    'node_id': cmd.node_id,
                    'n_bytes_read': str(cmd.n_bytes_read),
                }
                if cmd.deflated_size is not None:
                    entry['deflated_size'] = str(cmd.deflated_size)
                current_downloads.append(entry)
        return current_downloads

    def free_space(self, vol_id):
        """Return the free space for the given volume."""
        return self.main.vm.get_free_space(str(vol_id))

    def waiting(self):
        """Return a list of the operations in action queue."""
        logger.debug('called waiting')
        waiting = []
        for cmd in self.action_queue.queue.waiting:
            operation = cmd.__class__.__name__
            data = cmd.to_dict()
            waiting.append((operation, str(id(cmd)), data))
        return waiting

    def waiting_metadata(self):
        """Return a list of the operations in the meta-queue.

        As we don't have meta-queue anymore, this is faked.
        """
        logger.warning("called waiting_metadata - this method is deprecated, "
                       "use 'waiting' instead")
        waiting_metadata = []
        for cmd in self.action_queue.queue.waiting:
            if not isinstance(cmd, (Upload, Download)):
                operation = cmd.__class__.__name__
                data = cmd.to_dict()
                waiting_metadata.append((operation, data))
        return waiting_metadata

    def waiting_content(self):
        """Return a list of files that are waiting to be up- or downloaded.

        As we don't have content-queue anymore, this is faked.
        """
        logger.warning("called waiting_content - this method is deprecated, "
                       "use 'waiting' instead")
        waiting_content = []
        for cmd in self.action_queue.queue.waiting:
            if isinstance(cmd, (Upload, Download)):
                data = dict(path=cmd.path, share=cmd.share_id,
                            node=cmd.node_id, operation=cmd.__class__.__name__)
                waiting_content.append(data)
        return waiting_content

    def current_uploads(self):
        """return a list of files with a upload in progress"""
        logger.debug('called current_uploads')
        current_uploads = []
        for cmd in self.action_queue.queue.waiting:
            if isinstance(cmd, Upload) and cmd.running:
                entry = {
                    'path': cmd.path,
                    'share_id': cmd.share_id,
                    'node_id': cmd.node_id,
                    'n_bytes_written': str(cmd.n_bytes_written),
                }
                if cmd.deflated_size is not None:
                    entry['deflated_size'] = str(cmd.deflated_size)
                current_uploads.append(entry)
        return current_uploads

class SyncdaemonFileSystem(object):
    """An interface to the FileSystem Manager."""

    def __init__(self, fs_manager, action_queue):
        """Creates the instance."""
        super(SyncdaemonFileSystem, self).__init__()
        self.fs_manager = fs_manager
        self.action_queue = action_queue

    def get_metadata(self, path):
        """Return the metadata (as a dict) for the specified path."""
        logger.debug('get_metadata by path: %r', path)
        real_path = os.path.realpath(path.encode('utf-8'))
        mdobj = self.fs_manager.get_by_path(real_path)
        md_dict = self._mdobj_dict(mdobj)
        md_dict['path'] = path
        return md_dict

    def get_metadata_by_node(self, share_id, node_id):
        """Return the metadata (as a dict) for the specified share/node."""
        logger.debug('get_metadata by share: %r  node: %r', share_id, node_id)
        mdobj = self.fs_manager.get_by_node_id(share_id, node_id)
        md_dict = self._mdobj_dict(mdobj)
        path = self.fs_manager.get_abspath(mdobj.share_id, mdobj.path)
        md_dict['path'] = path
        return md_dict

    def get_metadata_and_quick_tree_synced(self, path):
        """Return the dict with the attributes of the metadata for
        the specified path, including the quick subtree status.
        """
        logger.debug('get_metadata_and_quick_tree_synced: %r', path)
        real_path = os.path.realpath(path.encode('utf-8'))
        mdobj = self.fs_manager.get_by_path(real_path)
        md_dict = self._mdobj_dict(mdobj)
        md_dict['path'] = path
        if self._path_in_queue(real_path):
            md_dict['quick_tree_synced'] = ''
        else:
            md_dict['quick_tree_synced'] = 'synced'
        return md_dict

    def _path_in_queue(self, path):
        """Return whether there are queued commands pertaining to the path."""
        for cmd in self.action_queue.queue.waiting:
            share_id = getattr(cmd, 'share_id', None)
            node_id = getattr(cmd, 'node_id', None)
            if share_id is not None and node_id is not None:
                # XXX: nested try/excepts in a loop are probably a
                # sign that I'm doing something wrong - or that
                # somebody is :)
                this_path = ''
                try:
                    node_md = self.fs_manager.get_by_node_id(share_id, node_id)
                except KeyError:
                    # maybe it's actually the mdid?
                    try:
                        node_md = self.fs_manager.get_by_mdid(node_id)
                    except KeyError:
                        # hm, nope. Dunno what to do then
                        pass
                    else:
                        this_path = self.fs_manager.get_abspath(share_id,
                                                                node_md.path)
                else:
                    this_path = self.fs_manager.get_abspath(share_id,
                                                            node_md.path)
                if this_path.startswith(path):
                    return True
        return False

    def _mdobj_dict(self, mdobj):
        """Returns a dict from a MDObject."""
        md_dict = {}
        for k, v in mdobj.__dict__.items():
            if k == 'info':
                continue
            elif k == 'path':
                md_dict[str(k)] = v.decode('utf-8')
            else:
                md_dict[str(k)] = str(v)
        if mdobj.__dict__.get('info', None):
            for k, v in mdobj.info.__dict__.items():
                md_dict['info_' + str(k)] = str(v)
        return md_dict

    def get_dirty_nodes(self):
        """Rerturn a list of dirty nodes."""
        mdobjs = self.fs_manager.get_dirty_nodes()
        dirty_nodes = []
        for mdobj in mdobjs:
            dirty_nodes.append(self._mdobj_dict(mdobj))
        return dirty_nodes


class SyncdaemonShares(object):
    """An interface to interact with shares."""

    def __init__(self, fs_manager, volume_manager):
        """Create the instance."""
        super(SyncdaemonShares, self).__init__()
        self.fs_manager = fs_manager
        self.vm = volume_manager

    def get_volume(self, share_id):
        """Return the volume for the given share."""
        return self.vm.get_volume(share_id)

    def get_create_error_share_info(self, share_info):
        """Get the share info used for errors."""
        path = self.fs_manager.get_by_mdid(str(share_info['marker'])).path
        share_info.update(dict(path=path))
        return share_info

    def get_shares(self):
        """Return a list of dicts, each dict represents a share."""
        logger.debug('called get_shares')
        shares = []
        for share_id, share in self.vm.shares.items():
            if share_id == '':
                continue
            share_dict = get_share_dict(share)
            shares.append(share_dict)
        return shares

    def accept_share(self, share_id, reply_handler=None, error_handler=None):
        """Accept a share.

        A ShareAnswerOk|Error signal will be fired in the future as a
        success/failure indicator.

        """
        logger.debug('accept_share: %r', share_id)
        if str(share_id) in self.vm.shares:
            self.vm.accept_share(str(share_id), True)
            reply_handler()
        else:
            error_handler(ValueError("The share with id: %s don't exists" % \
                                     str(share_id)))

    def reject_share(self, share_id, reply_handler=None, error_handler=None):
        """Reject a share."""
        logger.debug('reject_share: %r', share_id)
        if str(share_id) in self.vm.shares:
            self.vm.accept_share(str(share_id), False)
            reply_handler()
        else:
            error_handler(ValueError("The share with id: %s don't exists" % \
                                     str(share_id)))

    def delete_share(self, share_id):
        """Delete a Share, both kinds: "to me" and "from me"."""
        from ubuntuone.syncdaemon.volume_manager import VolumeDoesNotExist
        logger.debug('delete_share: %r', share_id)
        try:
            self.vm.delete_volume(str(share_id))
        except VolumeDoesNotExist:
            # isn't a volume! it might be a "share from me (a.k.a shared)"
            self.vm.delete_share(str(share_id))

    def subscribe(self, share_id):
        """Subscribe to the specified share."""
        logger.debug('Shares.subscribe: %r', share_id)
        d = self.vm.subscribe_share(str(share_id))
        msg = 'subscribe_share for id %r failed with %r'
        d.addErrback(lambda f: logger.error(msg, share_id, f))

    def unsubscribe(self, share_id):
        """Unsubscribe from the specified share."""
        logger.debug('Shares.unsubscribe: %r', share_id)
        self.vm.unsubscribe_share(str(share_id))

    def create_share(self, path, username, name, access_level):
        """Share a subtree to the user identified by username.

        @param path: that path to share (the root of the subtree)
        @param username: the username to offer the share to
        @param name: the name of the share
        @param access_level: 'View' or 'Modify'
        """
        logger.debug('create share: %r, %r, %r, %r',
                     path, username, name, access_level)
        path = path.encode("utf8")
        username = unicode(username)
        name = unicode(name)
        access_level = str(access_level)
        try:
            self.fs_manager.get_by_path(path)
        except KeyError:
            raise ValueError("path '%r' does not exist" % path)
        self.vm.create_share(path, username, name, access_level)

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
            self.create_share(path, user, name, access_level)

    def refresh_shares(self):
        """Refresh the share list, requesting it to the server."""
        self.vm.refresh_shares()

    def get_shared(self):
        """Returns a list of dicts, each dict represents a shared share.
        A share might not have the path set, as we might be still fetching the
        nodes from the server. In this cases the path is ''
        """
        logger.debug('called get_shared')
        shares = []
        for share_id, share in self.vm.shared.items():
            if share_id == '':
                continue
            share_dict = get_share_dict(share)
            shares.append(share_dict)
        return shares

class SyncdaemonConfig(object):
    """The Syncdaemon config/settings dbus interface."""

    def __init__(self, main, action_queue):
        """Creates the instance.

        @param bus: the BusName of this DBusExposedObject.
        """
        super(SyncdaemonConfig, self).__init__()
        self.main = main
        self.action_queue = action_queue

    def get_throttling_limits(self, reply_handler=None, error_handler=None):
        """Get the read/write limit from AQ and return a dict.
        Returns a dict(download=int, upload=int), if int is -1 the value isn't
        configured.
        The values are bytes/second
        """
        logger.debug("called get_throttling_limits")
        try:
            aq = self.action_queue
            download = -1
            upload = -1
            if aq.readLimit is not None:
                download = aq.readLimit
            if aq.writeLimit is not None:
                upload = aq.writeLimit
            info = dict(download=download,
                        upload=upload)
            if reply_handler:
                reply_handler(info)
            else:
                return info
            # pylint: disable-msg=W0703
        except Exception, e:
            if error_handler:
                error_handler(e)
            else:
                raise

    def set_throttling_limits(self, download, upload,
                         reply_handler=None, error_handler=None):
        """Set the read and write limits. The expected values are bytes/sec."""
        logger.debug("called set_throttling_limits")
        try:
            # modify and save the config file
            user_config = config.get_user_config()
            user_config.set_throttling_read_limit(download)
            user_config.set_throttling_write_limit(upload)
            user_config.save()
            # modify AQ settings
            aq = self.action_queue
            if download == -1:
                download = None
            if upload == -1:
                upload = None
            aq.readLimit = download
            aq.writeLimit = upload
            if reply_handler:
                reply_handler()
            # pylint: disable-msg=W0703
        except Exception, e:
            if error_handler:
                error_handler(e)
            else:
                raise

    def enable_bandwidth_throttling(self, reply_handler=None,
                                    error_handler=None):
        """Enable bandwidth throttling."""
        try:
            self._set_throttling_enabled(True)
            if reply_handler:
                reply_handler()
            # pylint: disable-msg=W0703
        except Exception, e:
            if error_handler:
                error_handler(e)
            else:
                raise

    def disable_bandwidth_throttling(self, reply_handler=None,
                                     error_handler=None):
        """Disable bandwidth throttling."""
        try:
            self._set_throttling_enabled(False)
            if reply_handler:
                reply_handler()
            # pylint: disable-msg=W0703
        except Exception, e:
            if error_handler:
                error_handler(e)
            else:
                raise

    def _set_throttling_enabled(self, enabled):
        """Set throttling enabled value and save the config"""
        # modify and save the config file
        user_config = config.get_user_config()
        user_config.set_throttling(enabled)
        user_config.save()
        # modify AQ settings
        if enabled:
            self.action_queue.enable_throttling()
        else:
            self.action_queue.disable_throttling()

    def bandwidth_throttling_enabled(self, reply_handler=None,
                                     error_handler=None):
        """Returns True (actually 1) if bandwidth throttling is enabled and
        False (0) otherwise.
        """
        enabled = self.action_queue.throttling_enabled
        if reply_handler:
            reply_handler(enabled)
        else:
            return enabled

    def udf_autosubscribe_enabled(self):
        """Return the udf_autosubscribe config value."""
        return config.get_user_config().get_udf_autosubscribe()

    def enable_udf_autosubscribe(self):
        """Enable UDF autosubscribe."""
        user_config = config.get_user_config()
        user_config.set_udf_autosubscribe(True)
        user_config.save()

    def disable_udf_autosubscribe(self):
        """Enable UDF autosubscribe."""
        user_config = config.get_user_config()
        user_config.set_udf_autosubscribe(False)
        user_config.save()

    def share_autosubscribe_enabled(self):
        """Return the share_autosubscribe config value."""
        return config.get_user_config().get_share_autosubscribe()

    def enable_share_autosubscribe(self):
        """Enable UDF autosubscribe."""
        user_config = config.get_user_config()
        user_config.set_share_autosubscribe(True)
        user_config.save()

    def disable_share_autosubscribe(self):
        """Enable UDF autosubscribe."""
        user_config = config.get_user_config()
        user_config.set_share_autosubscribe(False)
        user_config.save()

    def set_files_sync_enabled(self, enabled):
        """Enable/disable file sync service."""
        logger.debug('called set_files_sync_enabled %d', enabled)
        user_config = config.get_user_config()
        user_config.set_files_sync_enabled(bool(int(enabled)))
        user_config.save()

    def files_sync_enabled(self):
        """Return the files_sync_enabled config value."""
        logger.debug('called files_sync_enabled')
        return config.get_user_config().get_files_sync_enabled()

    def autoconnect_enabled(self):
        """Return the autoconnect config value."""
        return config.get_user_config().get_autoconnect()

    def set_autoconnect_enabled(self, enabled):
        """Enable syncdaemon autoconnect."""
        user_config = config.get_user_config()
        user_config.set_autoconnect(enabled)
        user_config.save()

    def show_all_notifications_enabled(self):
        """Return the show_all_notifications config value."""
        return config.get_user_config().get_show_all_notifications()

    def enable_show_all_notifications(self):
        """Enable showing all notifications."""
        user_config = config.get_user_config()
        user_config.set_show_all_notifications(True)
        user_config.save()
        self.main.status_listener.show_all_notifications = True

    def disable_show_all_notifications(self):
        """Disable showing all notifications."""
        user_config = config.get_user_config()
        user_config.set_show_all_notifications(False)
        user_config.save()
        self.main.status_listener.show_all_notifications = False


class SyncdaemonFolders(object):
    """A dbus interface to interact with User Defined Folders"""

    def __init__(self, volume_manager, fs_manager):
        """Create the instance."""
        super(SyncdaemonFolders, self).__init__()
        self.vm = volume_manager
        self.fs = fs_manager

    def create(self, path):
        """Create a user defined folder in the specified path."""
        logger.debug('Folders.create: %r', path)
        path = normpath(path.encode('utf-8'))
        self.vm.create_udf(path)

    def delete(self, folder_id):
        """Delete the folder specified by folder_id"""
        logger.debug('Folders.delete: %r', folder_id)
        self.vm.delete_volume(str(folder_id))

    def get_folders(self):
        """Return the list of folders (a list of dicts)"""
        logger.debug('Folders.get_folders')
        return [get_udf_dict(udf) for udf in self.vm.udfs.values()]

    def subscribe(self, folder_id):
        """Subscribe to the specified folder"""
        logger.debug('Folders.subscribe: %r', folder_id)
        try:
            self.vm.subscribe_udf(str(folder_id))
        except Exception:
            logger.exception('Error while subscribing udf: %r', folder_id)
            raise

    def unsubscribe(self, folder_id):
        """Unsubscribe from the specified folder"""
        logger.debug('Folders.unsubscribe: %r', folder_id)
        try:
            self.vm.unsubscribe_udf(str(folder_id))
        except Exception:
            logger.exception('Error while unsubscribing udf: %r', folder_id)
            raise

    def get_info(self, path):
        """Return a dict containing the folder information."""
        logger.debug('Folders.get_info: %r', path)
        mdobj = self.fs.get_by_path(path.encode('utf-8'))
        udf = self.vm.udfs.get(mdobj.share_id, None)
        if udf is None:
            return dict()
        else:
            return get_udf_dict(udf)

    def refresh_volumes(self):
        """Refresh the volumes list, requesting it to the server."""
        self.vm.refresh_volumes()


class SyncdaemonPublicFiles(object):
    """A DBus interface for handling public files."""

    def __init__(self, fs_manager, action_queue):
        super(SyncdaemonPublicFiles, self).__init__()
        self.fs = fs_manager
        self.aq = action_queue

    def get_path(self, share_id, node_id):
        """Get the path of the public file with the given ids."""
        share_id = str(share_id) if share_id else ''
        node_id = str(node_id)
        try:
            relpath = self.fs.get_by_node_id(share_id,
                                             node_id).path
        except KeyError:
            path=''
        else:
            path=self.fs.get_abspath(share_id, relpath)
        return path

    def change_public_access(self, share_id, node_id, is_public):
        """Change the public access of a file."""
        logger.debug('PublicFiles.change_public_access: %r, %r, %r',
                     share_id, node_id, is_public)
        if share_id:
            share_id = uuid.UUID(share_id)
        else:
            share_id = None
        node_id = uuid.UUID(node_id)
        self.aq.change_public_access(share_id, node_id, is_public)

    def get_public_files(self):
        """Request the list of public files to the server.

        The result will be send in a PublicFilesList signal.
        """
        return self.aq.get_public_files()


class SyncdaemonEvents(object):
    """The events of the system translated to IPC signals.

    @param bus_name: the BusName of this DBusExposedObject.
    @param event_queue: the Event Queue
    """
    def __init__(self, event_queue):
        super(SyncdaemonEvents, self).__init__()
        self.event_queue = event_queue

    def push_event(self, event_name, args):
        """Push an event to the event queue."""
        logger.debug('push_event: %r with %r', event_name, args)
        str_args = dict((str(k), str(v)) for k, v in args.items())
        self.event_queue.push(str(event_name), **str_args)


class SyncdaemonService(object):
    """ The Daemon dbus interface. """

    def __init__(self, service, main, volume_manager, action_queue):
        """ Creates the instance.

        @param bus: the BusName of this DBusExposedObject.
        """
        super(SyncdaemonService, self).__init__()
        self.service = service
        self.main = main
        self.volume_manager = volume_manager
        self.action_queue = action_queue

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
        return self.main.get_rootdir()

    def get_sharesdir(self):
        """ Returns the shares dir/mount point. """
        logger.debug('called get_sharesdir')
        return self.main.get_sharesdir()

    def get_sharesdir_link(self):
        """ Returns the shares dir/mount point. """
        logger.debug('called get_sharesdir_link')
        return self.main.get_sharesdir_link()

    def wait_for_nirvana(self, last_event_interval,
                         reply_handler=None, error_handler=None):
        """ call the reply handler when there are no more
        events or transfers.
        """
        logger.debug('called wait_for_nirvana')
        d = self.main.wait_for_nirvana(last_event_interval)
        d.addCallbacks(reply_handler, error_handler)
        return d

    def quit(self, reply_handler=None, error_handler=None):
        """ shutdown the syncdaemon. """
        logger.debug('Quit requested')
        if reply_handler:
            reply_handler()
        self.service.quit()

    def rescan_from_scratch(self, volume_id):
        """Request a rescan from scratch of the volume with volume_id."""
        # check that the volume exists
        volume = self.volume_manager.get_volume(str(volume_id))
        self.action_queue.rescan_from_scratch(volume.volume_id)


class SyncdaemonEventListener(object):
    """An Event Queue Listener."""

    def __init__(self, interact_interface):
        """The interact interface that contains all the exposed methods."""
        super(SyncdaemonEventListener, self).__init__()
        self.interface = interact_interface

    def handle_AQ_DOWNLOAD_STARTED(self, share_id, node_id, server_hash):
        """Handle AQ_DOWNLOAD_STARTED."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_download_started(path)
        except KeyError, e:
            args = dict(message='The md is gone before sending '
                        'DownloadStarted signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('DownloadStarted', args)

    def handle_AQ_DOWNLOAD_FILE_PROGRESS(self, share_id, node_id,
                                         n_bytes_read, deflated_size):
        """Handle AQ_DOWNLOAD_FILE_PROGRESS."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
        except KeyError, e:
            args = dict(message='The md is gone before sending '
                        'DownloadFileProgress signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('DownloadFileProgress',
                                                     args)
        else:
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_download_file_progress(path,
                                                 n_bytes_read=n_bytes_read,
                                                 deflated_size=deflated_size
                                                               )

    def handle_AQ_DOWNLOAD_FINISHED(self, share_id, node_id, server_hash):
        """Handle AQ_DOWNLOAD_FINISHED."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_download_finished(path)
        except KeyError, e:
            # file is gone before we got this
            args = dict(message='The md is gone before sending '
                        'DownloadFinished signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('DownloadFinished', args)

    def handle_AQ_DOWNLOAD_ERROR(self, share_id, node_id, server_hash, error,
                                 event='AQ_DOWNLOAD_ERROR'):
        """Handle AQ_DOWNLOAD_ERROR."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_download_finished(path, error=error)
        except KeyError, e:
            # file is gone before we got this
            args = dict(message='The md is gone before sending '
                        'DownloadFinished signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id),
                        download_error=str(error))
            self.interface.status.emit_signal_error('DownloadFinished', args)

    def handle_AQ_UPLOAD_STARTED(self, share_id, node_id, hash):
        """Handle AQ_UPLOAD_STARTED."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_upload_started(path)
        except KeyError, e:
            args = dict(message='The md is gone before sending '
                        'UploadStarted signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('UploadStarted', args)

    def handle_AQ_UPLOAD_FILE_PROGRESS(self, share_id, node_id,
                                         n_bytes_written, deflated_size):
        """Handle AQ_UPLOAD_FILE_PROGRESS."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
        except KeyError, e:
            args = dict(message='The md is gone before sending '
                        'UploadFileProgress signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('UploadFileProgress',
                                                     args)
        else:
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_upload_file_progress(path,
                                                n_bytes_written=n_bytes_written,
                                                deflated_size=deflated_size
                                                             )

    def handle_AQ_UPLOAD_FINISHED(self, share_id, node_id, hash,
                                  new_generation):
        """Handle AQ_UPLOAD_FINISHED."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id,
                                                              node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_upload_finished(path)
        except KeyError, e:
            # file is gone before we got this
            args = dict(message='The metadata is gone before sending '
                        'UploadFinished signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id))
            self.interface.status.emit_signal_error('UploadFinished', args)

    def handle_SV_ACCOUNT_CHANGED(self, account_info):
        """Handle SV_ACCOUNT_CHANGED."""
        self.interface.status.emit_account_changed(account_info)

    def handle_AQ_UPLOAD_ERROR(self, share_id, node_id, error, hash):
        """Handle AQ_UPLOAD_ERROR."""
        try:
            mdobj = self.interface.fs_manager.get_by_node_id(share_id, node_id)
            if mdobj.is_dir:
                return
            path = self.interface.fs_manager.get_abspath(share_id, mdobj.path)
            self.interface.status.emit_upload_finished(path, error=error)
        except KeyError, e:
            # file is gone before we got this
            args = dict(message='The metadata is gone before sending '
                        'UploadFinished signal',
                        error=str(e),
                        share_id=str(share_id),
                        node_id=str(node_id),
                        upload_error=str(error))
            self.interface.status.emit_signal_error('UploadFinished', args)

    def handle_FS_INVALID_NAME(self, dirname, filename):
        """Handle FS_INVALID_NAME."""
        self.interface.status.emit_invalid_name(dirname, filename)

    def handle_SYS_BROKEN_NODE(self, volume_id, node_id, mdid, path):
        """Handle SYS_BROKEN_NODE."""
        self.interface.status.emit_broken_node(volume_id, node_id, mdid, path)

    def handle_SYS_STATE_CHANGED(self, state):
        """Handle SYS_STATE_CHANGED."""
        logger.debug('emitting state changed: %r', state)
        self.interface.status.emit_status_changed(state)

    def handle_SV_FREE_SPACE(self, share_id, free_bytes):
        """Handle SV_FREE_SPACE event, emit ShareChanged signal."""
        self.interface.shares.emit_free_space(share_id, free_bytes)

    def handle_AQ_CREATE_SHARE_OK(self, share_id, marker):
        """Handle AQ_CREATE_SHARE_OK event, emit ShareCreated signal."""
        share = self.interface.volume_manager.shared.get(str(share_id))
        share_dict = {}
        if share:
            # pylint: disable-msg=W0212
            share_dict.update(get_share_dict(share))
        else:
            share_dict.update(dict(volume_id=str(share_id)))
        self.interface.shares.emit_share_created(share_dict)

    def handle_AQ_CREATE_SHARE_ERROR(self, marker, error):
        """Handle AQ_CREATE_SHARE_ERROR event, emit ShareCreateError signal."""
        self.interface.shares.emit_share_create_error(dict(marker=marker),
                                                       error)

    def handle_AQ_ANSWER_SHARE_OK(self, share_id, answer):
        """ handle AQ_ANSWER_SHARE_OK event, emit ShareAnswerOk signal. """
        self.interface.shares.emit_share_answer_response(str(share_id), answer)

    def handle_AQ_ANSWER_SHARE_ERROR(self, share_id, answer, error):
        """Handle AQ_ANSWER_SHARE_ERROR event, emit ShareAnswerError signal."""
        self.interface.shares.emit_share_answer_response(str(share_id), answer,
                                                          error)
    def handle_VM_UDF_SUBSCRIBED(self, udf):
        """Handle VM_UDF_SUBSCRIBED event, emit FolderSubscribed signal."""
        self.interface.folders.emit_folder_subscribed(udf)

    def handle_VM_UDF_SUBSCRIBE_ERROR(self, udf_id, error):
        """Handle VM_UDF_SUBSCRIBE_ERROR, emit FolderSubscribeError signal."""
        self.interface.folders.emit_folder_subscribe_error(udf_id, error)

    def handle_VM_UDF_UNSUBSCRIBED(self, udf):
        """Handle VM_UDF_UNSUBSCRIBED event, emit FolderUnSubscribed signal."""
        self.interface.folders.emit_folder_unsubscribed(udf)

    def handle_VM_UDF_UNSUBSCRIBE_ERROR(self, udf_id, error):
        """Handle VM_UDF_UNSUBSCRIBE_ERROR, emit FolderUnSubscribeError."""
        self.interface.folders.emit_folder_unsubscribe_error(udf_id, error)

    def handle_VM_UDF_CREATED(self, udf):
        """Handle VM_UDF_CREATED event, emit FolderCreated signal."""
        self.interface.folders.emit_folder_created(udf)

    def handle_VM_UDF_CREATE_ERROR(self, path, error):
        """Handle VM_UDF_CREATE_ERROR event, emit FolderCreateError signal."""
        self.interface.folders.emit_folder_create_error(path, error)

    def handle_VM_SHARE_SUBSCRIBED(self, share):
        """Handle VM_SHARE_SUBSCRIBED event, emit ShareSubscribed signal."""
        self.interface.shares.emit_share_subscribed(share)

    def handle_VM_SHARE_SUBSCRIBE_ERROR(self, share_id, error):
        """Handle VM_SHARE_SUBSCRIBE_ERROR, emit ShareSubscribeError signal."""
        self.interface.shares.emit_share_subscribe_error(share_id, error)

    def handle_VM_SHARE_UNSUBSCRIBED(self, share):
        """Handle VM_SHARE_UNSUBSCRIBED event, emit ShareUnSubscribed."""
        self.interface.shares.emit_share_unsubscribed(share)

    def handle_VM_SHARE_UNSUBSCRIBE_ERROR(self, share_id, error):
        """Handle VM_SHARE_UNSUBSCRIBE_ERROR, emit ShareUnSubscribeError."""
        self.interface.shares.emit_share_unsubscribe_error(share_id, error)

    def handle_VM_SHARE_CREATED(self, share_id):
        """Handle VM_SHARE_CREATED event, emit NewShare event."""
        self.interface.shares.emit_new_share(share_id)

    def handle_VM_SHARE_DELETED(self, share):
        """Handle VM_SHARE_DELETED event, emit NewShare event."""
        self.interface.shares.emit_share_changed('deleted', share)

    def handle_VM_SHARE_DELETE_ERROR(self, share_id, error):
        """Handle VM_DELETE_SHARE_ERROR event, emit ShareCreateError signal."""
        self.interface.shares.ShareDeleteError(dict(volume_id=share_id), error)

    def handle_VM_VOLUME_DELETED(self, volume):
        """Handle VM_VOLUME_DELETED event.

        Emits FolderDeleted or ShareChanged signal.

        """
        from ubuntuone.syncdaemon.volume_manager import Share, UDF

        if isinstance(volume, Share):
            self.interface.shares.emit_share_changed('deleted', volume)
        elif isinstance(volume, UDF):
            self.interface.folders.emit_folder_deleted(volume)
        else:
            logger.error("Unable to handle VM_VOLUME_DELETE for "
                     "volume_id=%r as it's not a share or UDF", volume.id)

    def handle_VM_VOLUME_DELETE_ERROR(self, volume_id, error):
        """Handle VM_VOLUME_DELETE_ERROR event, emit ShareDeleted event."""
        from ubuntuone.syncdaemon.volume_manager import Share, UDF, \
            VolumeDoesNotExist

        try:
            volume = self.interface.volume_manager.get_volume(volume_id)
        except VolumeDoesNotExist:
            logger.error("Unable to handle VM_VOLUME_DELETE_ERROR for "
                         "volume_id=%r, no such volume.", volume_id)
        else:
            if isinstance(volume, Share):
                self.interface.shares.emit_share_delete_error(volume, error)
            elif isinstance(volume, UDF):
                self.interface.folders.emit_folder_delete_error(volume, error)
            else:
                logger.error("Unable to handle VM_VOLUME_DELETE_ERROR for "
                         "volume_id=%r as it's not a share or UDF", volume_id)

    def handle_VM_SHARE_CHANGED(self, share_id):
        """ handle VM_SHARE_CHANGED event, emit's ShareChanged signal. """
        share = self.interface.volume_manager.shares.get(share_id)
        self.interface.shares.emit_share_changed('changed', share)

    def handle_AQ_CHANGE_PUBLIC_ACCESS_OK(self, share_id, node_id,
                                          is_public, public_url):
        """Handle the AQ_CHANGE_PUBLIC_ACCESS_OK event."""
        self.interface.public_files.emit_public_access_changed(
            share_id, node_id, is_public, public_url)

    def handle_AQ_CHANGE_PUBLIC_ACCESS_ERROR(self, share_id, node_id, error):
        """Handle the AQ_CHANGE_PUBLIC_ACCESS_ERROR event."""
        self.interface.public_files.emit_public_access_change_error(
            share_id, node_id, error)

    def handle_SYS_ROOT_MISMATCH(self, root_id, new_root_id):
        """Handle the SYS_ROOT_MISMATCH event."""
        self.interface.sync.emit_root_mismatch(root_id, new_root_id)

    def handle_AQ_PUBLIC_FILES_LIST_OK(self, public_files):
        """Handle the AQ_PUBLIC_FILES_LIST_OK event."""
        self.interface.public_files.emit_public_files_list(public_files)

    def handle_AQ_PUBLIC_FILES_LIST_ERROR(self, error):
        """Handle the AQ_PUBLIC_FILES_LIST_ERROR event."""
        self.interface.public_files.emit_public_files_list_error(error)

    def handle_SYS_QUOTA_EXCEEDED(self, volume_id, free_bytes):
        """Handle the SYS_QUOTA_EXCEEDED event."""
        from ubuntuone.syncdaemon.volume_manager import UDF

        volume = self.interface.volume_manager.get_volume(str(volume_id))

        volume_dict = {}
        if isinstance(volume, UDF):
            volume_dict = get_udf_dict(volume)
        else:
            # either a Share or Root
            volume_dict = get_share_dict(volume)

        # be sure that the volume has the most updated free bytes info
        volume_dict['free_bytes'] = str(free_bytes)

        self.interface.sync.emit_quota_exceeded(volume_dict)

    def handle_SYS_QUEUE_ADDED(self, command):
        """Handle SYS_QUEUE_ADDED.

        The content and meta queue changed signals are deprecacted and
        will go away in a near future.
        """
        if isinstance(command, (Upload, Download)):
            self.interface.status.emit_content_queue_changed()
        else:
            self.interface.status.emit_metaqueue_changed()

        data = command.to_dict()
        op_name = command.__class__.__name__
        op_id = id(command)
        self.interface.status.emit_requestqueue_added(op_name, op_id, data)

    def handle_SYS_QUEUE_REMOVED(self, command):
        """Handle SYS_QUEUE_REMOVED.

        The content and meta queue changed signals are deprecacted and
        will go away in a near future.
        """
        if isinstance(command, (Upload, Download)):
            self.interface.status.emit_content_queue_changed()
        else:
            self.interface.status.emit_metaqueue_changed()

        data = command.to_dict()
        op_name = command.__class__.__name__
        op_id = id(command)
        self.interface.status.emit_requestqueue_removed(op_name, op_id, data)
