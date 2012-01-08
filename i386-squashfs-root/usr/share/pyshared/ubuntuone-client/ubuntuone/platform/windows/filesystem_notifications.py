#
# Authors: Manuel de la Pena <manuel@canonical.com>
#          Natalia B. Bidart <natalia.bidart@canonical.com>
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

"""File notifications on windows."""

import logging
import os

from uuid import uuid4

from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from pywintypes import OVERLAPPED
from win32api import CloseHandle
from win32con import (
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    FILE_FLAG_BACKUP_SEMANTICS,
    FILE_NOTIFY_CHANGE_FILE_NAME,
    FILE_NOTIFY_CHANGE_DIR_NAME,
    FILE_NOTIFY_CHANGE_ATTRIBUTES,
    FILE_NOTIFY_CHANGE_SIZE,
    FILE_NOTIFY_CHANGE_LAST_WRITE,
    FILE_NOTIFY_CHANGE_SECURITY,
    OPEN_EXISTING)
from win32file import (
    AllocateReadBuffer,
    CreateFileW,
    GetOverlappedResult,
    ReadDirectoryChangesW,
    FILE_FLAG_OVERLAPPED,
    FILE_NOTIFY_INFORMATION)
from win32event import (
    CreateEvent,
    INFINITE,
    SetEvent,
    WaitForMultipleObjects,
    WAIT_OBJECT_0)
from ubuntuone.platform.windows.pyinotify import (
    Event,
    WatchManagerError,
    ProcessEvent,
    IN_OPEN,
    IN_CLOSE_NOWRITE,
    IN_CLOSE_WRITE,
    IN_CREATE,
    IN_IGNORED,
    IN_ISDIR,
    IN_DELETE,
    IN_MOVED_FROM,
    IN_MOVED_TO,
    IN_MODIFY)
from ubuntuone.platform.windows.os_helper import (
    is_valid_syncdaemon_path,
    is_valid_windows_path,
    get_syncdaemon_valid_path,
    windowspath,
)
from ubuntuone import logger

# our logging level
TRACE = logger.TRACE

# constant found in the msdn documentation:
# http://msdn.microsoft.com/en-us/library/ff538834(v=vs.85).aspx
FILE_LIST_DIRECTORY = 0x0001
FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x00000020
FILE_NOTIFY_CHANGE_CREATION = 0x00000040

# a map between the few events that we have on windows and those
# found in pyinotify
WINDOWS_ACTIONS = {
  1: IN_CREATE,
  2: IN_DELETE,
  3: IN_MODIFY,
  4: IN_MOVED_FROM,
  5: IN_MOVED_TO}

# translates quickly the event and it's is_dir state to our standard events
NAME_TRANSLATIONS = {
    IN_OPEN: 'FS_FILE_OPEN',
    IN_CLOSE_NOWRITE: 'FS_FILE_CLOSE_NOWRITE',
    IN_CLOSE_WRITE: 'FS_FILE_CLOSE_WRITE',
    IN_CREATE: 'FS_FILE_CREATE',
    IN_CREATE | IN_ISDIR: 'FS_DIR_CREATE',
    IN_DELETE: 'FS_FILE_DELETE',
    IN_DELETE | IN_ISDIR: 'FS_DIR_DELETE',
    IN_MOVED_FROM: 'FS_FILE_DELETE',
    IN_MOVED_FROM | IN_ISDIR: 'FS_DIR_DELETE',
    IN_MOVED_TO: 'FS_FILE_CREATE',
    IN_MOVED_TO | IN_ISDIR: 'FS_DIR_CREATE'}

# the default mask to be used in the watches added by the FilesystemMonitor
# class
FILESYSTEM_MONITOR_MASK = FILE_NOTIFY_CHANGE_FILE_NAME | \
    FILE_NOTIFY_CHANGE_DIR_NAME | \
    FILE_NOTIFY_CHANGE_ATTRIBUTES | \
    FILE_NOTIFY_CHANGE_SIZE | \
    FILE_NOTIFY_CHANGE_LAST_WRITE | \
    FILE_NOTIFY_CHANGE_SECURITY | \
    FILE_NOTIFY_CHANGE_LAST_ACCESS

THREADPOOL_MAX = 20

# The implementation of the code that is provided as the pyinotify substitute
class Watch(object):
    """Implement the same functions as pyinotify.Watch."""

    def __init__(self, watch_descriptor, path, mask, auto_add, processor,
        buf_size=8192):
        super(Watch, self).__init__()
        self.log = logging.getLogger('ubuntuone.SyncDaemon.platform.windows.' +
            'filesystem_notifications.Watch')
        self.log.setLevel(TRACE)
        self._processor = processor
        self._buf_size = buf_size
        self._wait_stop = CreateEvent(None, 0, 0, None)
        self._overlapped = OVERLAPPED()
        self._overlapped.hEvent = CreateEvent(None, 0, 0, None)
        self._watching = False
        self._descriptor = watch_descriptor
        self._auto_add = auto_add
        self._ignore_paths = []
        self._cookie = None
        self._source_pathname = None
        self._process_thread = None
        self._watch_handle = None
        # remember the subdirs we have so that when we have a delete we can
        # check if it was a remove
        self._subdirs = []
        # ensure that we work with an abspath and that we can deal with
        # long paths over 260 chars.
        if not path.endswith(os.path.sep):
            path += os.path.sep
        self._path = os.path.abspath(path)
        self._mask = mask
        # this deferred is fired when the watch has started monitoring
        # a directory from a thread
        self._watch_started_deferred = defer.Deferred()
        # and this one is fired when the watch has stopped
        self._watch_stopped_deferred = defer.Deferred()

    @is_valid_windows_path(path_indexes=[1])
    def _path_is_dir(self, path):
        """Check if the path is a dir and update the local subdir list."""
        self.log.debug('Testing if path %r is a dir', path)
        is_dir = False
        if os.path.exists(path):
            is_dir = os.path.isdir(path)
        else:
            self.log.debug('Path "%s" was deleted subdirs are %s.',
                path, self._subdirs)
            # we removed the path, we look in the internal list
            if path in self._subdirs:
                is_dir = True
                self._subdirs.remove(path)
        if is_dir:
            self.log.debug('Adding %s to subdirs %s', path, self._subdirs)
            self._subdirs.append(path)
        return is_dir

    def _process_events(self, events):
        """Process the events from the queue."""
        # do not do it if we stop watching and the events are empty
        if not self._watching:
            return

        # we transform the events to be the same as the one in pyinotify
        # and then use the proc_fun
        for action, file_name in events:
            if any([file_name.startswith(path)
                        for path in self._ignore_paths]):
                continue
            # map the windows events to the pyinotify ones, tis is dirty but
            # makes the multiplatform better, linux was first :P
            syncdaemon_path = get_syncdaemon_valid_path(
                                        os.path.join(self._path, file_name))
            is_dir = self._path_is_dir(os.path.join(self._path, file_name))
            if is_dir:
                self._subdirs.append(file_name)
            mask = WINDOWS_ACTIONS[action]
            head, tail = os.path.split(file_name)
            if is_dir:
                mask |= IN_ISDIR
            event_raw_data = {
                'wd': self._descriptor,
                'dir': is_dir,
                'mask': mask,
                'name': tail,
                'path': '.'}
            # by the way in which the win api fires the events we know for
            # sure that no move events will be added in the wrong order, this
            # is kind of hacky, I dont like it too much
            if WINDOWS_ACTIONS[action] == IN_MOVED_FROM:
                self._cookie = str(uuid4())
                self._source_pathname = tail
                event_raw_data['cookie'] = self._cookie
            if WINDOWS_ACTIONS[action] == IN_MOVED_TO:
                event_raw_data['src_pathname'] = self._source_pathname
                event_raw_data['cookie'] = self._cookie
            event = Event(event_raw_data)
            # FIXME: event deduces the pathname wrong and we need to manually
            # set it
            event.pathname = syncdaemon_path
            # add the event only if we do not have an exclude filter or
            # the exclude filter returns False, that is, the event will not
            # be excluded
            self.log.debug('Event is %s.', event)
            self._processor(event)

    def _call_deferred(self, f, *args):
        """Executes the deferred call avoiding possible race conditions."""
        if not self._watch_started_deferred.called:
            f(*args)

    def _watch_wrapper(self):
        """Wrap _watch, and errback on any unhandled error."""
        try:
            self._watch()
        except Exception:
            reactor.callFromThread(self._call_deferred,
                self._watch_started_deferred.errback, Failure())

    def _watch(self):
        """Watch a path that is a directory."""
        self.log.debug('Adding watch for %r (exists? %r is dir? %r).',
                       self._path,
                       os.path.exists(self._path), os.path.isdir(self._path))
        # we are going to be using the ReadDirectoryChangesW whihc requires
        # a directory handle and the mask to be used.
        self._watch_handle = CreateFileW(
            self._path,
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OVERLAPPED,
            None)

        try:
            self._watch_loop(self._watch_handle)
        finally:
            CloseHandle(self._watch_handle)
            self._watch_handle = None
            reactor.callFromThread(self.stopped.callback, True)

    def _watch_loop(self, handle):
        """The loop where we watch the directory."""
        while True:
            # important information to know about the parameters:
            # param 1: the handle to the dir
            # param 2: the size to be used in the kernel to store events
            # that might be lost while the call is being performed. This
            # is complicated to fine tune since if you make lots of watcher
            # you migh used too much memory and make your OS to BSOD
            buf = AllocateReadBuffer(self._buf_size)
            ReadDirectoryChangesW(
                handle,
                buf,
                self._auto_add,
                self._mask,
                self._overlapped,
            )
            if not self._watch_started_deferred.called:
                reactor.callFromThread(self._call_deferred,
                    self._watch_started_deferred.callback, True)
            # wait for an event and ensure that we either stop or read the
            # data
            rc = WaitForMultipleObjects((self._wait_stop,
                                         self._overlapped.hEvent),
                                         0, INFINITE)
            if rc == WAIT_OBJECT_0:
                # Stop event
                break
            # if we continue, it means that we got some data, lets read it
            data = GetOverlappedResult(handle, self._overlapped, True)
            # lets ead the data and store it in the results
            events = FILE_NOTIFY_INFORMATION(buf, data)
            self.log.debug('Events from ReadDirectoryChangesW are %s', events)
            reactor.callFromThread(self._process_events, events)

    @is_valid_windows_path(path_indexes=[1])
    def ignore_path(self, path):
        """Add the path of the events to ignore."""
        if not path.endswith(os.path.sep):
            path += os.path.sep
        if path.startswith(self._path):
            path = path[len(self._path):]
            self._ignore_paths.append(path)

    @is_valid_windows_path(path_indexes=[1])
    def remove_ignored_path(self, path):
        """Reaccept path."""
        if not path.endswith(os.path.sep):
            path += os.path.sep
        if path.startswith(self._path):
            path = path[len(self._path):]
            if path in self._ignore_paths:
                self._ignore_paths.remove(path)

    def start_watching(self):
        """Tell the watch to start processing events."""
        for current_child in os.listdir(self._path):
            full_child_path = os.path.join(self._path, current_child)
            if os.path.isdir(full_child_path):
                self._subdirs.append(full_child_path)
        # start to diff threads, one to watch the path, the other to
        # process the events.
        self.log.debug('Start watching path.')
        self._watching = True
        reactor.callInThread(self._watch_wrapper)
        return self._watch_started_deferred

    def stop_watching(self):
        """Tell the watch to stop processing events."""
        self.log.info('Stop watching %s', self._path)
        SetEvent(self._wait_stop)
        self._watching = False
        self._subdirs = []
        return self.stopped

    def update(self, mask, auto_add=False):
        """Update the info used by the watcher."""
        self.log.debug('update(%s, %s)', mask, auto_add)
        self._mask = mask
        self._auto_add = auto_add

    @property
    def path(self):
        """Return the patch watched."""
        return self._path

    @property
    def auto_add(self):
        return self._auto_add

    @property
    def started(self):
        """A deferred that will be called when the watch is running."""
        return self._watch_started_deferred

    @property
    def stopped(self):
        """A deferred fired when the watch thread has finished."""
        return self._watch_stopped_deferred


class WatchManager(object):
    """Implement the same functions as pyinotify.WatchManager.

    All paths passed to methods in this class should be windows paths.

    """

    def __init__(self, processor):
        """Init the manager to keep trak of the different watches."""
        super(WatchManager, self).__init__()
        self._processor = processor
        self.log = logging.getLogger('ubuntuone.SyncDaemon.platform.windows.'
            + 'filesystem_notifications.WatchManager')
        self.log.setLevel(TRACE)
        self._wdm = {}
        self._wd_count = 0
        self._ignored_paths = []

    def stop(self):
        """Close the manager and stop all watches."""
        self.log.debug('Stopping watches.')
        wait_list = []
        for current_wd in self._wdm:
            wait_list.append(self._wdm[current_wd].stop_watching())
            self.log.debug('Stopping Watch on %r.', self._wdm[current_wd].path)
        return defer.DeferredList(wait_list)

    def get_watch(self, wd):
        """Return the watch with the given descriptor."""
        return self._wdm[wd]

    @defer.inlineCallbacks
    def del_watch(self, wd):
        """Delete the watch with the given descriptor."""
        try:
            watch = self._wdm[wd]
            yield watch.stop_watching()
            del self._wdm[wd]
            self.log.debug('Watch %s removed.', wd)
        except KeyError, e:
            logging.error(str(e))

    def _add_single_watch(self, path, mask, auto_add=False,
        quiet=True):
        if path in self._ignored_paths:
            # simply removed it from the filter
            self._ignored_paths.remove(path)
            return
        # we need to add a new watch
        self.log.debug('add_single_watch(%s, %s, %s, %s)', path, mask,
            auto_add, quiet)

        # adjust the number of threads based on the UDFs watched
        reactor.suggestThreadPoolSize(THREADPOOL_MAX + self._wd_count + 1)
        self._wdm[self._wd_count] = Watch(self._wd_count, path,
                                          mask, auto_add, self._processor)
        d = self._wdm[self._wd_count].start_watching()
        self._wd_count += 1
        self.log.debug('Watch count increased to %s', self._wd_count)
        return d

    @is_valid_windows_path(path_indexes=[1])
    def add_watch(self, path, mask, auto_add=False,
        quiet=True):
        """Add a new path tp be watch.

        The method will ensure that the path is not already present.
        """
        if not isinstance(path, unicode):
            e = NotImplementedError("No implementation on windows.")
            return defer.fail(e)
        wd = self.get_wd(path)
        if wd is None:
            self.log.debug('Adding single watch on %r', path)
            return self._add_single_watch(path, mask, auto_add, quiet)
        else:
            self.log.debug('Watch already exists on %r', path)
            return self._wdm[wd].started

    def update_watch(self, wd, mask=None, rec=False,
                     auto_add=False, quiet=True):
        raise NotImplementedError("Not implemented on windows.")

    @is_valid_windows_path(path_indexes=[1])
    def get_wd(self, path):
        """Return the watcher that is used to watch the given path."""
        if not path.endswith(os.path.sep):
            path = path + os.path.sep
        for current_wd in self._wdm:
            watch_path = self._wdm[current_wd].path
            if ((watch_path == path or (
                    watch_path in path and self._wdm[current_wd].auto_add))
                    and path not in self._ignored_paths):
                return current_wd

    def get_path(self, wd):
        """Return the path watched by the wath with the given wd."""
        watch = self._wdm.get(wd)
        if watch:
            return watch.path

    @defer.inlineCallbacks
    def rm_watch(self, wd, rec=False, quiet=True):
        """Remove the the watch with the given wd."""
        try:
            watch = self._wdm[wd]
            yield watch.stop_watching()
            del self._wdm[wd]
        except KeyError, err:
            self.log.error(str(err))
            if not quiet:
                raise WatchManagerError('Watch %s was not found' % wd, {})

    @is_valid_windows_path(path_indexes=[1])
    def rm_path(self, path):
        """Remove a watch to the given path."""
        wd = self.get_wd(path)
        if wd is not None:
            self.log.debug('Adding exclude filter for %r', path)
            self._wdm[wd].ignore_path(path)


class NotifyProcessor(ProcessEvent):
    """Processor that takes care of dealing with the events.

    This interface will be exposed to syncdaemon, ergo all passed
    and returned paths must be a sequence of BYTES encoded with utf8.

    Also, they must not be literal paths, that is the \\?\ prefix should not be
    in the path.

    """

    def __init__(self, monitor, ignore_config=None):
        # XXX: avoid circular imports.
        from ubuntuone.syncdaemon.filesystem_notifications import (
            GeneralINotifyProcessor
        )
        self.general_processor = GeneralINotifyProcessor(monitor,
            self.handle_dir_delete, NAME_TRANSLATIONS,
            self.platform_is_ignored, IN_IGNORED, ignore_config=ignore_config)
        self.held_event = None

    def rm_from_mute_filter(self, event, paths):
        """Remove event from the mute filter."""
        self.general_processor.rm_from_mute_filter(event, paths)

    def add_to_mute_filter(self, event, paths):
        """Add an event and path(s) to the mute filter."""
        self.general_processor.add_to_mute_filter(event, paths)

    @is_valid_syncdaemon_path(path_indexes=[1])
    def platform_is_ignored(self, path):
        """Should we ignore this path in the current platform.?"""
        # don't support links yet
        if path.endswith('.lnk'):
            return True
        return False

    @is_valid_syncdaemon_path(path_indexes=[1])
    def is_ignored(self, path):
        """Should we ignore this path?"""
        return self.general_processor.is_ignored(path)

    def release_held_event(self, timed_out=False):
        """Release the event on hold to fulfill its destiny."""
        self.general_processor.push_event(self.held_event)
        self.held_event = None

    def process_IN_MODIFY(self, event):
        """Capture a modify event and fake an open ^ close write events."""
        # lets ignore dir changes
        if event.dir:
            return
        # on windows we just get IN_MODIFY, lets always fake
        # an OPEN & CLOSE_WRITE couple
        raw_open = raw_close = {
           'wd': event.wd,
           'dir': event.dir,
           'name': event.name,
           'path': event.path}
        # caculate the open mask
        raw_open['mask'] = IN_OPEN
        # create the event using the raw data, then fix the pathname param
        open_event = Event(raw_open)
        open_event.pathname = event.pathname
        # push the open
        self.general_processor.push_event(open_event)
        raw_close['mask'] = IN_CLOSE_WRITE
        close_event = Event(raw_close)
        close_event.pathname = event.pathname
        # push the close event
        self.general_processor.push_event(close_event)

    def process_IN_MOVED_FROM(self, event):
        """Capture the MOVED_FROM to maybe syntethize FILE_MOVED."""
        if self.held_event is not None:
            self.general_processor.log.warn('Lost pair event of %s',
                                            self.held_event)
        self.held_event = event

    def _fake_create_event(self, event):
        """Fake the creation of an event."""
        # this is the case of a MOVE from an ignored path (links for example)
        # to a valid path
        if event.dir:
            evtname = "FS_DIR_"
        else:
            evtname = "FS_FILE_"
        self.general_processor.eq_push(evtname + "CREATE", path=event.pathname)
        if not event.dir:
            self.general_processor.eq_push('FS_FILE_CLOSE_WRITE',
                                            path=event.pathname)

    def _fake_delete_create_event(self, event):
        """Fake the deletion and the creation."""
        # this is the case of a MOVE from a watch UDF to a diff UDF which
        # means that we have to copy the way linux works.
        if event.dir:
            evtname = "FS_DIR_"
        else:
            evtname = "FS_FILE_"
        m = "Delete because of different shares: %r"
        self.log.info(m, self.held_event.pathname)
        self.general_processor.eq_push(evtname + "DELETE",
                                       path=self.held_event.pathname)
        self.general_processor.eq_push(evtname + "CREATE", path=event.pathname)
        if not event.dir:
            self.general_processor.eq_push('FS_FILE_CLOSE_WRITE',
                                            path=event.pathname)

    def process_IN_MOVED_TO(self, event):
        """Capture the MOVED_TO to maybe syntethize FILE_MOVED."""
        if self.held_event is not None:
            if event.cookie == self.held_event.cookie:
                f_path_dir = os.path.split(self.held_event.pathname)[0]
                t_path_dir = os.path.split(event.pathname)[0]

                is_from_forreal = not self.is_ignored(self.held_event.pathname)
                is_to_forreal = not self.is_ignored(event.pathname)
                if is_from_forreal and is_to_forreal:
                    f_share_id = self.general_processor.get_path_share_id(
                        f_path_dir)
                    t_share_id = self.general_processor.get_path_share_id(
                        t_path_dir)
                    if f_share_id != t_share_id:
                        # if the share_id are != push a delete/create
                        self._fake_delete_create_event(event)
                    else:
                        if event.dir:
                            evtname = "FS_DIR_"
                        else:
                            evtname = "FS_FILE_"
                        self.general_processor.eq_push(evtname + "MOVE",
                            path_from=self.held_event.pathname,
                            path_to=event.pathname)
                elif is_to_forreal:
                    # this is the case of a MOVE from something ignored
                    # to a valid filename
                    self._fake_create_event(event)

                self.held_event = None
                return
            else:
                self.release_held_event()
                self.general_processor.push_event(event)
        else:
            # We should never get here on windows, I really do not know how we
            # got here
            self.general_processor.log.warn(
                            'Cookie does not match the previoues held event!')
            self.general_processor.log.warn('Ignoring %s', event)

    def process_default(self, event):
        """Push the event into the EventQueue."""
        if self.held_event is not None:
            self.release_held_event()
        self.general_processor.push_event(event)

    @is_valid_syncdaemon_path(path_indexes=[1])
    def handle_dir_delete(self, fullpath):
        """Some special work when a directory is deleted."""
        # remove the watch on that dir from our structures, this mainly tells
        # the monitor to remove the watch which is fowaded to a watch manager.
        self.general_processor.rm_watch(fullpath)

        # handle the case of move a dir to a non-watched directory
        paths = self.general_processor.get_paths_starting_with(fullpath,
            include_base=False)

        paths.sort(reverse=True)
        for path, is_dir in paths:
            m = "Pushing deletion because of parent dir move: (is_dir=%s) %r"
            self.general_processor.log.info(m, is_dir, path)
            if is_dir:
                # same as the above remove
                self.general_processor.rm_watch(path)
                self.general_processor.eq_push('FS_DIR_DELETE', path=path)
            else:
                self.general_processor.eq_push('FS_FILE_DELETE', path=path)

    @is_valid_syncdaemon_path(path_indexes=[1])
    def freeze_begin(self, path):
        """Puts in hold all the events for this path."""
        self.general_processor.freeze_begin(path)

    def freeze_rollback(self):
        """Unfreezes the frozen path, reseting to idle state."""
        self.general_processor.freeze_rollback()

    def freeze_commit(self, events):
        """Unfreezes the frozen path, sending received events if not dirty.

        If events for that path happened:
            - return True
        else:
            - push the here received events, return False
        """
        return self.general_processor.freeze_commit(events)

    @property
    def mute_filter(self):
        """Return the mute filter used by the processor."""
        return self.general_processor.filter

    @property
    def frozen_path(self):
        """Return the frozen path."""
        return self.general_processor.frozen_path

    @property
    def log(self):
        """Return the logger of the instance."""
        return self.general_processor.log


class FilesystemMonitor(object):
    """Manages the signals from filesystem."""

    def __init__(self, eq, fs, ignore_config=None, timeout=1):
        self.log = logging.getLogger('ubuntuone.SyncDaemon.FSMonitor')
        self.log.setLevel(TRACE)
        self.fs = fs
        self.eq = eq
        self._processor = NotifyProcessor(self, ignore_config)
        self._watch_manager = WatchManager(self._processor)

    def add_to_mute_filter(self, event, **info):
        """Add info to mute filter in the processor."""
        self._processor.add_to_mute_filter(event, info)

    def rm_from_mute_filter(self, event, **info):
        """Remove info to mute filter in the processor."""
        self._processor.rm_from_mute_filter(event, info)

    def shutdown(self):
        """Prepares the EQ to be closed."""
        return self._watch_manager.stop()

    @windowspath(path_indexes=[1])
    def rm_watch(self, dirpath):
        """Remove watch from a dir."""
        # trust the implementation of the manager
        self._watch_manager.rm_path(dirpath)

    @windowspath(path_indexes=[1])
    def add_watch(self, dirpath):
        """Add watch to a dir."""
        # the logic to check if the watch is already set
        # is all in WatchManager.add_watch
        return self._watch_manager.add_watch(dirpath,
                             FILESYSTEM_MONITOR_MASK, auto_add=True)

    def add_watches_to_udf_ancestors(self, volume):
        """Add a inotify watch to volume's ancestors if it's an UDF."""
        # On windows there is no need to add the watches to the ancestors
        # so we will always return true. The reason for this is that the
        # handles that we open stop the user from renaming the ancestors of
        # the UDF, for a user to do that he has to unsync the udf first
        return defer.succeed(True)

    def is_frozen(self):
        """Checks if there's something frozen."""
        return self._processor.frozen_path is not None

    @is_valid_syncdaemon_path(path_indexes=[1])
    def freeze_begin(self, path):
        """Puts in hold all the events for this path."""
        if self._processor.frozen_path is not None:
            raise ValueError("There's something already frozen!")
        self._processor.freeze_begin(path)

    def freeze_rollback(self):
        """Unfreezes the frozen path, reseting to idle state."""
        if self._processor.frozen_path is None:
            raise ValueError("Rolling back with nothing frozen!")
        self._processor.freeze_rollback()

    def freeze_commit(self, events):
        """Unfreezes the frozen path, sending received events if not dirty.

        If events for that path happened:
            - return True
        else:
            - push the here received events, return False
        """
        if self._processor.frozen_path is None:
            raise ValueError("Commiting with nothing frozen!")

        d = defer.execute(self._processor.freeze_commit, events)
        return d
