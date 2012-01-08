# ubuntuone.syncdaemon.action_queue - Action queue
#
# Author: John Lenton <john.lenton@canonical.com>
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
# Author: Facundo Batista <facundo@canonical.com>
#
# Copyright 2009, 2010, 2011 Canonical Ltd.
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
"""The ActionQueue is where actions to be performed on the server are
queued up and then executed.

The idea is that there are two queues,
one for metadata and another for content; the metadata queue has
priority over the content queue.

"""
import base64
import simplejson
import logging
import os
import random
import re
import tempfile
import traceback
import uuid
import zlib

from collections import deque, defaultdict
from functools import wraps, partial
from urllib import urlencode
from urllib2 import urlopen, Request, HTTPError
from urlparse import urljoin

import OpenSSL.SSL

from zope.interface import implements
from twisted.internet import reactor, defer, threads, task
from twisted.internet import error as twisted_errors
from twisted.names import client as dns_client
from twisted.python.failure import Failure, DefaultException

from oauth import oauth
from ubuntuone import clientdefs
from ubuntuone.platform import platform, remove_file
from ubuntuone.storageprotocol import protocol_pb2, content_hash
from ubuntuone.storageprotocol import errors as protocol_errors
from ubuntuone.storageprotocol.client import (
    ThrottlingStorageClient, ThrottlingStorageClientFactory
)
from ubuntuone.storageprotocol.context import get_ssl_context
from ubuntuone.syncdaemon.interfaces import IActionQueue, IMarker
from ubuntuone.syncdaemon.logger import mklog, TRACE
from ubuntuone.syncdaemon import config

logger = logging.getLogger("ubuntuone.SyncDaemon.ActionQueue")

# I want something which repr() is "---" *without* the quotes :)
UNKNOWN = type('', (), {'__repr__': lambda _: '---'})()

# Regular expression to validate an e-mail address
EREGEX = "^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$"

# progress threshold to emit a download/upload progress event: 64Kb
TRANSFER_PROGRESS_THRESHOLD = 64*1024*1024

def passit(func):
    """Pass the value on for the next deferred, while calling func with it."""

    @wraps(func)
    def wrapper(a):
        """Do it."""
        func(a)
        return a

    return wrapper


class DeferredInterrupted(Exception):
    """To stop the run when pausing."""


class InterruptibleDeferred(defer.Deferred):
    """Receives a deferred, and wraps it, also behaving like a deferred.

    If the original deferred is triggered, that is passed, and can not be
    interrupted any more. If it's interrupted, then it silences the original
    deferred, no matter what.
    """
    def __init__(self, d):
        defer.Deferred.__init__(self)
        self.interrupted = False

        self.original_deferred = d
        d.addBoth(self.filter)

    def filter(self, result):
        """Pass the result if not interrupted."""
        if not self.interrupted:
            self.callback(result)

    def interrupt(self):
        """Interrupt only if original not called."""
        if not self.original_deferred.called:
            self.interrupted = True
            self.errback(DeferredInterrupted())



class PathLockingTree(object):
    """Tree that stores deferreds in the nodes."""

    def __init__(self):
        self.logger = logging.getLogger("ubuntuone.SyncDaemon.PathLockingTree")
        self.root = dict(children_nodes={})
        self.count = 0

    def acquire(self, *elements, **modifiers):
        """Acquire the lock for the elements.

        Return a deferred that will be triggered (when the lock is
        released) with a function to be called when the work is done.

        Example using inlineCallbacks syntax:

            release = yield plt.acquire(*elements)
            ...
            release()
        """
        # process the modifiers (this will not needed in Python 3, :)
        on_parent = modifiers.get('on_parent', False)
        on_children = modifiers.get('on_children', False)
        logger = modifiers.get('logger', self.logger)

        wait_for = []
        deferred = defer.Deferred()
        end_mark = len(elements) - 1
        parent_mark = len(elements) - 2
        self.count += 1
        desc = self.root
        for pos, element in enumerate(elements):
            # get previous child or create a new one just empty, not using
            # setdefault to avoid creating structures if not needed
            children_nodes = desc['children_nodes']
            if element in children_nodes:
                node = children_nodes[element]
            else:
                node = dict(node_deferreds=set(),
                            children_nodes={}, children_deferreds=set())
                children_nodes[element] = node

            # add the deferreds of the parent if asked for it
            if pos == parent_mark and on_parent:
                wait_for.extend(node['node_deferreds'])

            # add the deferred to the node only at the end of the path
            if pos == end_mark:
                wait_for.extend(node['node_deferreds'])
                node['node_deferreds'].add(deferred)

                # add the deferreds of the children, if asked for it
                if on_children:
                    wait_for.extend(node['children_deferreds'])
            else:
                node['children_deferreds'].add(deferred)

            desc = node

        logger.debug("pathlock acquiring on %s (on_parent=%s, on_children=%s);"
                     " wait for: %d", elements, on_parent,
                     on_children, len(wait_for))
        deferred_list = defer.DeferredList(wait_for)
        deferred_list.addCallback(lambda _: partial(self._release, deferred,
                                                    elements, logger))
        return deferred_list

    def _release(self, deferred, elements, logger):
        """Release the callback and clean the tree."""
        # clean the tree first!
        # keep here every node and its child element, to backtrack
        branch = []

        # remove the deferred from children_deferreds except in the end
        self.count -= 1
        desc = self.root
        for element in elements[:-1]:
            branch.append((desc, element))
            node = desc['children_nodes'][element]
            node['children_deferreds'].remove(deferred)
            desc = node

        # for the final node, remove it from node_deferreds
        branch.append((desc, elements[-1]))
        node = desc['children_nodes'][elements[-1]]
        node['node_deferreds'].remove(deferred)

        # backtrack
        while branch:
            if node['node_deferreds'] or node['children_nodes']:
                # node is not empty, done cleaning the branch!
                break

            # node is empty! remove it
            node, element = branch.pop()
            del node['children_nodes'][element]


        # finally, log and release the deferred
        logger.debug("pathlock releasing %s; remaining: %d", elements,
                                                             self.count)
        deferred.callback(True)


class NamedTemporaryFile(object):
    """Like tempfile.NamedTemporaryFile, but working in 2.5.

    Also WRT the delete argument. Actually, one of these
    NamedTemporaryFile()s is the same as a
    tempfile.NamedTemporaryFile(delete=False) from 2.6.

    Or so the theory goes.

    """

    def __init__(self):
        fileno, self.name = tempfile.mkstemp()

        # build a file object from the descriptor; note that this will *not*
        # create a new file descriptor at the OS level
        self._fh = os.fdopen(fileno, 'w+b')

    def __getattr__(self, attr):
        """Proxy everything else (other than .name) on to self._fh."""
        return getattr(self._fh, attr)


def sanitize_message(message):
    """Remove bytes and magic hash, return arguments to log()."""
    if message.type == protocol_pb2.Message.BYTES:
        return ('start - processMessage: id: %s, type: %s',
                message.id, message.type)
    elif message.type == protocol_pb2.Message.PUT_CONTENT:
        lines = [ line for line in str(message).split("\n")
                if not line.strip().startswith("magic_hash:") ]
        return ('start - processMessage: %s',
                " ".join(lines))
    else:
        return ('start - processMessage: %s',
                str(message).replace("\n", " "))


class LoggingStorageClient(ThrottlingStorageClient):
    """A subclass of StorageClient that logs.

    Specifically, it adds logging to processMessage and sendMessage.
    """

    def __init__(self):
        ThrottlingStorageClient.__init__(self)
        self.log = logging.getLogger('ubuntuone.SyncDaemon.StorageClient')
        # configure the handler level to be < than DEBUG
        self.log_trace = partial(self.log.log, TRACE)

    def log_message(self, message):
        """Log the messages in the trace log."""
        if self.log.isEnabledFor(TRACE):
            self.log_trace(*sanitize_message(message))

    def processMessage(self, message):
        """Wrapper that logs the message and result."""
        self.log_message(message)
        if message.id in self.requests:
            req = self.requests[message.id]
            req.deferred.addCallbacks(self.log_success, self.log_error)
        result = ThrottlingStorageClient.processMessage(self, message)
        self.log_trace('end - processMessage: id: %s - result: %s',
                       message.id, result)
        return result

    def log_error(self, failure):
        """Logging errback for requests."""
        self.log_trace('request error: %s', failure)
        return failure

    def log_success(self, result):
        """Logging callback for requests."""
        self.log_trace('request finished: %s', result)
        if getattr(result, '__dict__', None):
            self.log_trace('result.__dict__: %s', result.__dict__)
        return result

    def sendMessage(self, message):
        """Wrapper that logs the message and result."""
        # don't log the full message if it's of type BYTES
        self.log_message(message)
        result = ThrottlingStorageClient.sendMessage(self, message)
        self.log_trace('end - sendMessage: id: %s', message.id)
        return result


class PingManager(object):
    """Handle the ping/pong with the server."""

    _ping_delay = 600  # 10 minutes
    _timeout_delay = 180  # 3 minutes

    def __init__(self, client):
        self.client = client
        self._loop = task.LoopingCall(self._do_ping)
        self._loop.start(self._ping_delay, now=False)
        self._timeout_call = None
        self._running = True

    @defer.inlineCallbacks
    def _do_ping(self):
        """Ping the server just to use the network."""
        self.client.log.trace("Sending ping")
        self._timeout_call = reactor.callLater(self._timeout_delay,
                                               self._disconnect)
        req = yield self.client.ping()
        self.client.log.debug("Ping! rtt: %.3f segs", req.rtt)
        self._timeout_call.cancel()

    def _disconnect(self):
        """Never got the pong, disconnect."""
        self.stop()
        self.client.log.info("No Pong response, disconnecting the client")
        self.client.transport.loseConnection()

    def _stop(self):
        """Really stop all calls."""
        self._loop.stop()
        if self._timeout_call is not None and self._timeout_call.active():
            self._timeout_call.cancel()

    def stop(self):
        """Stop all the calls if still running."""
        if self._running:
            self._running = False
            self._stop()


class ActionQueueProtocol(LoggingStorageClient):
    """This is the Action Queue version of the StorageClient protocol."""

    factory = None

    def __init__(self):
        LoggingStorageClient.__init__(self)
        user_config = config.get_user_config()
        self.max_payload_size = user_config.get_max_payload_size()
        self.ping_manager = None

    def connectionMade(self):
        """A new connection was made."""
        self.log.info('Connection made.')
        LoggingStorageClient.connectionMade(self)
        self.factory.event_queue.push('SYS_CONNECTION_MADE')
        if self.ping_manager is not None:
            self.ping_manager.stop()
        self.ping_manager = PingManager(self)

    def connectionLost(self, reason):
        """The connection was lost."""
        self.log.info('Connection lost, reason: %s.', reason)
        if self.ping_manager is not None:
            self.ping_manager.stop()
            self.ping_manager = None
        LoggingStorageClient.connectionLost(self, reason)


class Marker(str):
    """A uuid4-based marker class."""

    implements(IMarker)

    def __new__(cls):
        return super(Marker, cls).__new__(cls, uuid.uuid4())

    def __repr__(self):
        return "marker:%s" % self


class ZipQueue(object):
    """A queue of files to be compressed for upload.

    Parts of this were shamelessly copied from
    twisted.internet.defer.DeferredSemaphore.

    See bug #373984

    """

    def __init__(self):
        self.waiting = deque()
        self.tokens = self.limit = 10

    def acquire(self):
        """Return a deferred which fires on token acquisition."""
        assert self.tokens >= 0, "Tokens should never be negative"
        d = defer.Deferred()
        if not self.tokens:
            self.waiting.append(d)
        else:
            self.tokens = self.tokens - 1
            d.callback(self)
        return d

    def release(self):
        """Release the token.

        Should be called by whoever did the acquire() when the shared
        resource is free.
        """
        assert self.tokens < self.limit, "Too many tokens!"
        self.tokens = self.tokens + 1
        if self.waiting:
            # someone is waiting to acquire token
            self.tokens = self.tokens - 1
            d = self.waiting.popleft()
            d.callback(self)

    def _compress(self, deferred, upload, fileobj):
        """Compression background task.

        Here we also calculate other need values, like magic hash, to make
        the most of the file reading.
        """
        filename = getattr(fileobj, 'name', '<?>')
        failed = False

        try:
            if upload.cancelled:
                # avoid compression if command already cancelled
                return
            upload.log.debug('compressing: %r', filename)
            # we need to compress the file completely to figure out its
            # compressed size. So streaming is out :(
            upload.tempfile = f = NamedTemporaryFile()
            zipper = zlib.compressobj()
            magic_hasher = content_hash.magic_hash_factory()
            while not upload.cancelled:
                data = fileobj.read(4096)
                if not data:
                    f.write(zipper.flush())
                    # no flush/sync because we don't need this to persist
                    # on disk; if the machine goes down, we'll lose it
                    # anyway (being in /tmp and all)
                    break
                f.write(zipper.compress(data))
                magic_hasher.update(data)
            upload.deflated_size = f.tell()

            # keep the file open, but reset its position
            # to zero, ready to be read later
            f.seek(0)

            upload.magic_hash = magic_hasher.content_hash()
        except Exception, e: # pylint: disable-msg=W0703
            failed = True
            reactor.callFromThread(deferred.errback, e)
        finally:
            # avoid triggering the deferred if already failed!
            if not failed:
                reactor.callFromThread(deferred.callback, True)

    @defer.inlineCallbacks
    def zip(self, upload):
        """Acquire, do the compression in a thread, release."""
        deferred = defer.Deferred()

        yield self.acquire()
        try:
            try:
                fileobj = upload.fileobj_factory()
            except StandardError, e:
                # maybe the user deleted the file before we got to upload it
                upload.log.warn("Unable to build fileobj (%s: '%s') so "
                                "cancelling the upload.", type(e), e)
                upload.cancel()
                return

            reactor.callInThread(self._compress, deferred, upload, fileobj)
        finally:
            self.release()

        # let's wait _compress to finish
        try:
            yield deferred
        finally:
            fileobj.close()


class RequestQueue(object):
    """Pool of commands being run."""

    def __init__(self, action_queue):
        self.action_queue = action_queue
        self.waiting = []
        self.hashed_waiting = {}
        self.active = False
        self.active_deferred = defer.Deferred()

        # transfers semaphore
        user_config = config.get_user_config()
        simult_transfers = user_config.get_simult_transfers()
        self.transfers_semaphore = defer.DeferredSemaphore(simult_transfers)

    def __len__(self):
        """Return the length of the waiting queue."""
        return len(self.waiting)

    def queue(self, command):
        """Add a command to the queue."""
        # check if the queue and head was empty before this command
        first_added = not self.waiting

        # puts the command where it was asked for
        self.waiting.append(command)
        self.action_queue.event_queue.push('SYS_QUEUE_ADDED',
                                           command=command)

        # add to the hashed waiting if it needs to be unique
        if command.uniqueness is not None:
            self.hashed_waiting[command.uniqueness] = command

        # if nothing running, and this command is the first in the
        # queue, send the signal
        if first_added:
            self.action_queue.event_queue.push('SYS_QUEUE_WAITING')

    def unqueue(self, command):
        """Unqueue a command."""
        self.waiting.remove(command)
        self.hashed_waiting.pop(command.uniqueness, None)
        self.action_queue.event_queue.push('SYS_QUEUE_REMOVED',
                                           command=command)
        if len(self.waiting) == 0:
            self.action_queue.event_queue.push('SYS_QUEUE_DONE')

    def run(self):
        """Go active and run all commands in the queue."""
        self.active = True
        self.active_deferred.callback(True)

    def stop(self):
        """Stop the pool and cleanup the running commands."""
        self.active = False
        self.active_deferred = defer.Deferred()
        for command in self.waiting:
            command.pause()

    def node_is_queued(self, cmdclass, share_id, node_id):
        """True if a command is queued for that node."""
        uniqueness = (cmdclass.__name__, share_id, node_id)
        return uniqueness in self.hashed_waiting

    def remove(self, command):
        """Remove a command from 'waiting', if there.

        This is a handy method for those commands with uniqueness, it should
        not be called from other commands.
        """
        if command.uniqueness in self.hashed_waiting:
            del self.hashed_waiting[command.uniqueness]
            self.waiting.remove(command)


class DeferredMap(object):
    """A mapping of deferred values.

    Return deferreds for a key that are fired (succesfully or not) later.
    """

    def __init__(self):
        self.waiting = defaultdict(list)

    def get(self, key):
        """Return a deferred for the given key."""
        d = defer.Deferred()
        self.waiting[key].append(d)
        return d

    def set(self, key, value):
        """We've got the value for a key!

        If it was waited, fire the waiting deferreds and remove the key.
        """
        if key in self.waiting:
            deferreds = self.waiting.pop(key)
            for d in deferreds:
                d.callback(value)

    def err(self, key, failure):
        """Something went terribly wrong in the process of getting a value.

        Break the news to the waiting deferreds and remove the key.
        """
        if key in self.waiting:
            deferreds = self.waiting.pop(key)
            for d in deferreds:
                d.errback(failure)


class ConditionsLocker(object):
    """Structure to hold commands waiting because of conditions.

    On each call to lock it will return a deferred for the received
    command. When check_conditions is called, it will trigger each
    command deferred if it's runnable.
    """
    def __init__(self):
        self.locked = {}

    def get_lock(self, command):
        """Return the deferred that will lock the command."""
        if command not in self.locked:
            self.locked[command] = defer.Deferred()
        return self.locked[command]

    def check_conditions(self):
        """Check for all commands' conditions, and release accordingly."""
        for cmd in self.locked.keys():
            if cmd.is_runnable:
                deferred = self.locked.pop(cmd)
                deferred.callback(True)

    def cancel_command(self, command):
        """The command was cancelled, if lock hold, release it and clean."""
        if command in self.locked:
            deferred = self.locked.pop(command)
            deferred.callback(True)


class UploadProgressWrapper(object):
    """A wrapper around the file-like object used for Uploads.

    It adjusts automatically the transfer variables in the command.

    fd is the file-like object used for uploads.
    """

    __slots__ = ('fd', 'command')

    def __init__(self, fd, command):
        self.fd = fd
        self.command = command
        self.command.n_bytes_written = 0
        self.command.n_bytes_written_last = 0

    def read(self, size=None):
        """Read at most size bytes from the file-like object.

        Keep track of the number of bytes that have been read.
        """
        data = self.fd.read(size)
        self.command.n_bytes_written += len(data)
        self.command.progress_hook()
        return data

    def seek(self, offset):
        """Move to new file position."""
        self.fd.seek(offset)
        self.command.n_bytes_written = offset
        self.command.n_bytes_written_last = offset

    def __getattr__(self, attr):
        """Proxy all the rest."""
        return getattr(self.fd, attr)


class ActionQueue(ThrottlingStorageClientFactory, object):
    """The ActionQueue itself."""

    implements(IActionQueue)
    protocol = ActionQueueProtocol

    def __init__(self, event_queue, main, host, port, dns_srv,
                 use_ssl=False, disable_ssl_verify=False,
                 read_limit=None, write_limit=None, throttling_enabled=False,
                 connection_timeout=30):
        ThrottlingStorageClientFactory.__init__(self, read_limit=read_limit,
                                      write_limit=write_limit,
                                      throttling_enabled=throttling_enabled)
        self.event_queue = event_queue
        self.main = main
        self.host = host
        self.port = port
        self.dns_srv = dns_srv
        self.use_ssl = use_ssl
        self.disable_ssl_verify = disable_ssl_verify
        self.connection_timeout = connection_timeout

        # credentials
        self.token = None
        self.consumer = None

        self.client = None # an instance of self.protocol

        # is a twisted.internet.tcp/ssl.Connector instance
        self.connector = None # created on reactor.connectTCP/SSL
        # we need to track down if a connection is in progress
        # to avoid double connections
        self.connect_in_progress = False

        self.queue = RequestQueue(self)
        self.pathlock = PathLockingTree()
        self.uuid_map = DeferredMap()
        self.zip_queue = ZipQueue()
        self.conditions_locker = ConditionsLocker()

        self.estimated_free_space = {}
        event_queue.subscribe(self)

    def check_conditions(self):
        """Check conditions in the locker, to release all the waiting ops."""
        self.conditions_locker.check_conditions()

    def have_sufficient_space_for_upload(self, share_id, upload_size):
        """Returns True if we have sufficient space for the given upload."""
        free = self.main.vm.get_free_space(share_id)
        enough = free is None or free >= upload_size
        if not enough:
            logger.info("Not enough space for upload %s bytes (available: %s)",
                        upload_size, free)
            self.event_queue.push('SYS_QUOTA_EXCEEDED', volume_id=share_id,
                                  free_bytes=free)

        return enough

    def handle_SYS_USER_CONNECT(self, access_token):
        """Stow the access token away for later use."""
        self.token = oauth.OAuthToken(access_token['token'],
                                      access_token['token_secret'])
        self.consumer = oauth.OAuthConsumer(access_token['consumer_key'],
                                            access_token['consumer_secret'])

    def _cleanup_connection_state(self, *args):
        """Reset connection state."""
        self.client = None
        self.connector = None
        self.connect_in_progress = False

    def _share_change_callback(self, info):
        """Called by the client when notified that a share changed."""
        self.event_queue.push('SV_SHARE_CHANGED', info=info)

    def _share_delete_callback(self, share_id):
        """Called by the client when notified that a share was deleted."""
        self.event_queue.push('SV_SHARE_DELETED', share_id=share_id)

    def _share_answer_callback(self, share_id, answer):
        """Called by the client when it gets a share answer notification."""
        self.event_queue.push('SV_SHARE_ANSWERED',
                              share_id=str(share_id), answer=answer)

    def _free_space_callback(self, share_id, free_bytes):
        """Called by the client when it gets a free space notification."""
        self.event_queue.push('SV_FREE_SPACE',
                              share_id=str(share_id), free_bytes=free_bytes)

    def _account_info_callback(self, account_info):
        """Called by the client when it gets an account info notification."""
        self.event_queue.push('SV_ACCOUNT_CHANGED',
                              account_info=account_info)

    def _volume_created_callback(self, volume):
        """Process new volumes."""
        self.event_queue.push('SV_VOLUME_CREATED', volume=volume)

    def _volume_deleted_callback(self, volume_id):
        """Process volume deletion."""
        self.event_queue.push('SV_VOLUME_DELETED', volume_id=volume_id)

    def _volume_new_generation_callback(self, volume_id, generation):
        """Process new volumes."""
        self.event_queue.push('SV_VOLUME_NEW_GENERATION',
                              volume_id=volume_id, generation=generation)

    def _lookup_srv(self):
        """Do the SRV lookup.

        Return a deferred whose callback is going to be called with
        (host, port). If we can't do the lookup, the default host, port
        is used.

        """

        def on_lookup_ok(results):
            """Get a random host from the SRV result."""
            logger.debug('SRV lookup done, choosing a server.')
            # pylint: disable-msg=W0612
            records, auth, add = results
            if not records:
                raise ValueError('No available records.')
            # pick a random server
            record = random.choice(records)
            logger.debug('Using record: %r', record)
            if record.payload:
                return record.payload.target.name, record.payload.port
            else:
                logger.info('Empty SRV record, fallback to %r:%r',
                            self.host, self.port)
                return self.host, self.port

        def on_lookup_error(failure):
            """Return the default host/post on a DNS SRV lookup failure."""
            logger.info("SRV lookup error, fallback to %r:%r \n%s",
                        self.host, self.port, failure.getTraceback())
            return self.host, self.port

        if self.dns_srv:
            # lookup the DNS SRV records
            d = dns_client.lookupService(self.dns_srv, timeout=[3, 2])
            d.addCallback(on_lookup_ok)
            d.addErrback(on_lookup_error)
            return d
        else:
            return defer.succeed((self.host, self.port))

    def _make_connection(self, result):
        """Do the real connect call."""
        host, port = result
        ssl_context = get_ssl_context(self.disable_ssl_verify)
        if self.use_ssl:
            self.connector = reactor.connectSSL(host, port, factory=self,
                                                contextFactory=ssl_context,
                                                timeout=self.connection_timeout)
        else:
            self.connector = reactor.connectTCP(host, port, self,
                                                timeout=self.connection_timeout)

    def connect(self):
        """Start the circus going."""
        # avoid multiple connections
        if self.connect_in_progress:
            msg = "Discarding new connection attempt, there is a connector!"
            logger.warning(msg)
            return

        self.connect_in_progress = True
        d = self._lookup_srv()
        # DNS lookup always succeeds, proceed to actually connect
        d.addCallback(self._make_connection)

    def buildProtocol(self, addr):
        """Build the client and store it. Connect callbacks."""
        # XXX: Very Important Note: within the storageprotocol project,
        # ThrottlingStorageClient.connectionMade sets self.factory.client
        # to self *if* self.factory.client is not None.
        # Since buildProcotol is called before connectionMade, the latter
        # does nothing (safely).
        self.client = ThrottlingStorageClientFactory.buildProtocol(self, addr)

        self.client.set_share_change_callback(self._share_change_callback)
        self.client.set_share_answer_callback(self._share_answer_callback)
        self.client.set_free_space_callback(self._free_space_callback)
        self.client.set_account_info_callback(self._account_info_callback)
        # volumes
        self.client.set_volume_created_callback(self._volume_created_callback)
        self.client.set_volume_deleted_callback(self._volume_deleted_callback)
        self.client.set_volume_new_generation_callback(
                                        self._volume_new_generation_callback)

        logger.info('Connection made.')
        return self.client

    def startedConnecting(self, connector):
        """Called when a connection has been started."""
        logger.info('Connection started to host %s, port %s.',
                    connector.host, connector.port)

    def disconnect(self):
        """Disconnect the client.

        This shouldn't be called if the client is already disconnected.

        """
        if self.connector is not None:
            self.connector.disconnect()
            self._cleanup_connection_state()
        else:
            msg = 'disconnect() was called when the connector was None.'
            logger.warning(msg)

        logger.debug("Disconnected.")

    def clientConnectionFailed(self, connector, reason):
        """Called when the connect() call fails."""
        self._cleanup_connection_state()
        self.event_queue.push('SYS_CONNECTION_FAILED')
        logger.info('Connection failed: %s', reason.getErrorMessage())

    def clientConnectionLost(self, connector, reason):
        """The client connection went down."""
        self._cleanup_connection_state()
        self.event_queue.push('SYS_CONNECTION_LOST')
        logger.warning('Connection lost: %s', reason.getErrorMessage())

    @defer.inlineCallbacks
    def _send_request_and_handle_errors(self, request, request_error,
                                        event_error, event_ok,
                                        handle_exception=True,
                                        args=(), kwargs={}):
        """Send 'request' to the server, using params 'args' and 'kwargs'.

        Expect 'request_error' as valid error, and push 'event_error' in that
        case. Do generic error handling for the rest of the protocol errors.

        """
        # if the client changes while we're waiting, this message is
        # old news and should be discarded (the message would
        # typically be a failure: timeout or disconnect). So keep the
        # original client around for comparison.
        client = self.client
        req_name = request.__name__
        failure = None
        event = None
        result = None
        try:
            try:
                result = yield request(*args, **kwargs)
            finally:
                # common handling for all cases
                if client is not self.client:
                    msg = "Client mismatch while processing the request '%s'" \
                          ", client (%r) is not self.client (%r)."
                    logger.warning(msg, req_name, client, self.client)
                    return
        except request_error, failure:
            event = event_error
            self.event_queue.push(event_error, error=str(failure))
        except (twisted_errors.ConnectionLost,
                twisted_errors.ConnectionDone,
                OpenSSL.SSL.Error), failure:
            # connection ended, just don't do anything: the SYS_CONNECTION_ETC
            # will be sent by normal client/protocol mechanisms, and logging
            # will be done later in this function.
            pass
        except protocol_errors.AuthenticationRequiredError, failure:
            # we need to separate this case from the rest because an
            # AuthenticationRequiredError is an StorageRequestError,
            # and we treat it differently.
            event = 'SYS_UNKNOWN_ERROR'
            self.event_queue.push(event)
        except protocol_errors.StorageRequestError, failure:
            event = 'SYS_SERVER_ERROR'
            self.event_queue.push(event, error=str(failure))
        except Exception, failure:
            if handle_exception:
                event = 'SYS_UNKNOWN_ERROR'
                self.event_queue.push(event)
            else:
                raise
        else:
            logger.info("The request '%s' finished OK.", req_name)
            if event_ok is not None:
                self.event_queue.push(event_ok)

        if failure is not None:
            if event is None:
                logger.info("The request '%s' failed with the error: %s",
                             req_name, failure)
            else:
                logger.info("The request '%s' failed with the error: %s "
                            "and was handled with the event: %s",
                            req_name, failure, event)
        else:
            defer.returnValue(result)

    def check_version(self):
        """Check if the client protocol version matches that of the server."""
        check_version_d = self._send_request_and_handle_errors(
            request=self.client.protocol_version,
            request_error=protocol_errors.UnsupportedVersionError,
            event_error='SYS_PROTOCOL_VERSION_ERROR',
            event_ok='SYS_PROTOCOL_VERSION_OK'
        )
        return check_version_d

    @defer.inlineCallbacks
    def set_capabilities(self, caps):
        """Set the capabilities with the server."""

        @defer.inlineCallbacks
        def caps_raising_if_not_accepted(capability_method, caps, msg):
            """Discuss capabilities with the server."""
            client_caps = getattr(self.client, capability_method)
            req = yield client_caps(caps)
            if not req.accepted:
                raise StandardError(msg)
            defer.returnValue(req)

        error_msg = "The server doesn't have the requested capabilities"
        query_caps_d = self._send_request_and_handle_errors(
            request=caps_raising_if_not_accepted,
            request_error=StandardError,
            event_error='SYS_SET_CAPABILITIES_ERROR',
            event_ok=None,
            args=('query_caps', caps, error_msg)
        )
        req = yield query_caps_d

        # req can be None if set capabilities failed, error is handled by
        # _send_request_and_handle_errors
        if not req:
            return

        error_msg = "The server denied setting '%s' capabilities" % caps
        set_caps_d = self._send_request_and_handle_errors(
            request=caps_raising_if_not_accepted,
            request_error=StandardError,
            event_error='SYS_SET_CAPABILITIES_ERROR',
            event_ok='SYS_SET_CAPABILITIES_OK',
            args=('set_caps', caps, error_msg)
        )
        yield set_caps_d

    @defer.inlineCallbacks
    def authenticate(self):
        """Authenticate against the server using stored credentials."""
        metadata = {'version':clientdefs.VERSION,
                    'platform':platform}
        authenticate_d = self._send_request_and_handle_errors(
            request=self.client.oauth_authenticate,
            request_error=protocol_errors.AuthenticationFailedError,
            event_error='SYS_AUTH_ERROR', event_ok='SYS_AUTH_OK',
            # XXX: handle self.token is None or self.consumer is None?
            args=(self.consumer, self.token, metadata)
        )
        req = yield authenticate_d

        # req can be None if the auth failed, but it's handled by
        # _send_request_and_handle_errors
        if req:
            # log the session_id
            logger.note('Session ID: %r', str(req.session_id))

    @defer.inlineCallbacks
    def query_volumes(self):
        """Get the list of volumes.

        This method will *not* queue a command, the request will be
        executed right away.
        """
        result = yield self._send_request_and_handle_errors(
            request=self.client.list_volumes,
            request_error=None, event_error=None,
            event_ok=None, handle_exception=False)
        defer.returnValue(result.volumes)

    def make_file(self, share_id, parent_id, name, marker, path):
        """See .interfaces.IMetaQueue."""
        return MakeFile(self.queue, share_id, parent_id,
                        name, marker, path).go()

    def make_dir(self, share_id, parent_id, name, marker, path):
        """See .interfaces.IMetaQueue."""
        return MakeDir(self.queue, share_id, parent_id,
                       name, marker, path).go()

    def move(self, share_id, node_id, old_parent_id, new_parent_id,
             new_name, path_from, path_to):
        """See .interfaces.IMetaQueue."""
        return Move(self.queue, share_id, node_id, old_parent_id,
                    new_parent_id, new_name, path_from, path_to).go()

    def unlink(self, share_id, parent_id, node_id, path, is_dir):
        """See .interfaces.IMetaQueue."""
        return Unlink(self.queue, share_id, parent_id, node_id, path,
                      is_dir).go()

    def inquire_free_space(self, share_id):
        """See .interfaces.IMetaQueue."""
        return FreeSpaceInquiry(self.queue, share_id).go()

    def inquire_account_info(self):
        """See .interfaces.IMetaQueue."""
        return AccountInquiry(self.queue).go()

    def list_shares(self):
        """See .interfaces.IMetaQueue."""
        return ListShares(self.queue).go()

    def answer_share(self, share_id, answer):
        """See .interfaces.IMetaQueue."""
        return AnswerShare(self.queue, share_id, answer).go()

    def create_share(self, node_id, share_to, name, access_level,
                     marker, path):
        """See .interfaces.IMetaQueue."""
        return CreateShare(self.queue, node_id, share_to, name,
                           access_level, marker, path).go()

    def delete_share(self, share_id):
        """See .interfaces.IMetaQueue."""
        return DeleteShare(self.queue, share_id).go()

    def create_udf(self, path, name, marker):
        """See .interfaces.IMetaQueue."""
        return CreateUDF(self.queue, path, name, marker).go()

    def list_volumes(self):
        """See .interfaces.IMetaQueue."""
        return ListVolumes(self.queue).go()

    def delete_volume(self, volume_id, path):
        """See .interfaces.IMetaQueue."""
        return DeleteVolume(self.queue, volume_id, path).go()

    def change_public_access(self, share_id, node_id, is_public):
        """See .interfaces.IMetaQueue."""
        return ChangePublicAccess(self.queue, share_id,
                                  node_id, is_public).go()

    def get_public_files(self):
        """See .interfaces.IMetaQueue."""
        return GetPublicFiles(self.queue).go()

    def download(self, share_id, node_id, server_hash, path, fileobj_factory):
        """See .interfaces.IContentQueue.download."""
        return Download(self.queue, share_id, node_id, server_hash,
                        path, fileobj_factory).go()

    def upload(self, share_id, node_id, previous_hash, hash, crc32,
               size, path, fileobj_factory, upload_id=None):
        """See .interfaces.IContentQueue."""
        return Upload(self.queue, share_id, node_id, previous_hash,
                      hash, crc32, size, path, fileobj_factory,
                      upload_id=upload_id).go()

    def _cancel_op(self, share_id, node_id, cmdclass):
        """Generalized form of cancel_upload and cancel_download."""
        logstr = "cancel_" + cmdclass.__name__.lower()
        log = mklog(logger, logstr, share_id, node_id)
        uniqueness = (cmdclass.__name__, share_id, node_id)
        if uniqueness in self.queue.hashed_waiting:
            queued_command = self.queue.hashed_waiting[uniqueness]
            log.debug('external cancel attempt')
            queued_command.cancel()

    def cancel_upload(self, share_id, node_id):
        """See .interfaces.IContentQueue."""
        self._cancel_op(share_id, node_id, Upload)

    def cancel_download(self, share_id, node_id):
        """See .interfaces.IContentQueue."""
        self._cancel_op(share_id, node_id, Download)

    def node_is_with_queued_move(self, share_id, node_id):
        """True if a Move is queued for that node."""
        return self.queue.node_is_queued(Move, share_id, node_id)

    def get_delta(self, volume_id, generation):
        """See .interfaces.IMetaQueue."""
        return GetDelta(self.queue, volume_id, generation).go()

    def rescan_from_scratch(self, volume_id):
        """See .interfaces.IMetaQueue."""
        return GetDeltaFromScratch(self.queue, volume_id).go()

    def handle_SYS_ROOT_RECEIVED(self, root_id, mdid):
        """Demark the root node_id."""
        self.uuid_map.set(mdid, root_id)


class ActionQueueCommand(object):
    """Base of all the action queue commands."""

    # the info used in the protocol errors is hidden, but very useful!
    # pylint: disable-msg=W0212
    suppressed_error_messages = (
        [x for x in protocol_errors._error_mapping.values()
         if x is not protocol_errors.InternalError] +
        [protocol_errors.RequestCancelledError,
         twisted_errors.ConnectionDone, twisted_errors.ConnectionLost]
    )

    retryable_errors = (
        protocol_errors.TryAgainError,
        protocol_errors.QuotaExceededError,
        twisted_errors.ConnectionDone,
        twisted_errors.ConnectionLost,
    )

    logged_attrs = ('running',)
    possible_markers = ()
    is_runnable = True
    uniqueness = None

    __slots__ = ('_queue', 'running', 'pathlock_release', 'log',
                 'markers_resolved_deferred', 'action_queue', 'cancelled',
                 'running_deferred')

    def __init__(self, request_queue):
        """Initialize a command instance."""
        self._queue = request_queue
        self.action_queue = request_queue.action_queue
        self.running = False
        self.log = None
        self.markers_resolved_deferred = defer.Deferred()
        self.pathlock_release = None
        self.cancelled = False
        self.running_deferred = None

    def to_dict(self):
        """Dump logged attributes to a dict."""
        return dict((n, getattr(self, n, None)) for n in self.logged_attrs)

    def make_logger(self):
        """Create a logger for this object."""
        share_id = getattr(self, "share_id", UNKNOWN)
        node_id = getattr(self, "node_id", None) or \
                      getattr(self, "marker", UNKNOWN)
        self.log = mklog(logger, self.__class__.__name__,
                         share_id, node_id, **self.to_dict())

    @defer.inlineCallbacks
    def demark(self):
        """Arrange to have maybe_markers realized."""
        # we need to issue all the DeferredMap.get's right now, to be
        # dereferenced later
        waiting_structure = []
        for name in self.possible_markers:
            marker = getattr(self, name)

            # if a marker, get the real value; if not, it's already there, so
            # no action needed
            if IMarker.providedBy(marker):
                self.log.debug("waiting for the real value of %r", marker)
                d = self.action_queue.uuid_map.get(marker)
                waiting_structure.append((name, marker, d))

        # now, we wait for all the dereferencings... if any
        for (name, marker, deferred) in waiting_structure:
            try:
                value = yield deferred
            except Exception, e:
                # on first failure, errback the marker resolved flag, and
                # quit waiting for other deferreds
                self.log.error("failed %r", marker)
                self.markers_resolved_deferred.errback(e)
                break
            else:
                self.log.debug("for %r got value %r", marker, value)
                old_uniqueness = self.uniqueness
                setattr(self, name, value)

                # as the attr changed (been demarked), need to reput itself
                # in the hashed_waiting, if was there before and not cancelled
                if old_uniqueness in self._queue.hashed_waiting:
                    if not self.cancelled:
                        del self._queue.hashed_waiting[old_uniqueness]
                        self._queue.hashed_waiting[self.uniqueness] = self
        else:
            # fire the deferred only if all markers finished ok
            self.markers_resolved_deferred.callback(True)

    def finish(self):
        """The command ended."""
        self.running = False
        self._queue.unqueue(self)

    def _should_be_queued(self):
        """Return True if the command should be queued."""
        return True

    def cleanup(self):
        """Do whatever is needed to clean up from a failure.

        For example, stop producers and others that aren't cleaned up
        appropriately on their own.  Note that this may be called more
        than once.
        """

    def _start(self):
        """Do the specialized pre-run setup."""
        return defer.succeed(None)

    def pause(self):
        """Pause the command."""
        self.log.debug('pausing')
        if self.running_deferred is not None:
            self.running_deferred.interrupt()
        self.cleanup()

    @defer.inlineCallbacks
    def go(self):
        """Execute all the steps for a command."""
        # create the log
        self.make_logger()

        # queue if should, otherwise all is done
        if not self._should_be_queued():
            return

        self.log.debug('queueing')
        self._queue.queue(self)

        # set up basic marker failure handler and demark
        def f(failure):
            self.log.debug("failing because marker failed: %s", failure)
            self.cancelled = True
            self.cleanup()
            self.handle_failure(failure)
            self.finish()
        self.markers_resolved_deferred.addErrback(f)
        self.demark()

        # acquire the pathlock; note that the pathlock_release may be None
        # if the command didn't need to acquire any pathlock
        self.pathlock_release = yield self._acquire_pathlock()
        if self.cancelled:
            if self.pathlock_release is not None:
                self.log.debug('releasing the pathlock because of cancelled')
                self.pathlock_release()
            return

        try:
            yield self.run()
        except Exception, exc:
            self.log.exception("Error running the command: %s "
                               "(traceback follows)", exc)
        finally:
            if self.pathlock_release is not None:
                self.pathlock_release()

    @defer.inlineCallbacks
    def run(self):
        """Run the command."""
        self.log.debug('starting')
        yield self._start()
        self.log.debug('started')

        while True:
            if self.cancelled:
                yield self.markers_resolved_deferred
                self.log.debug('cancelled before trying to run')
                break

            # if queue not active, wait for it and check again
            if not self._queue.active:
                self.log.debug('not running because of inactive queue')
                yield self._queue.active_deferred
                self.log.debug('unblocked: queue active')
                continue

            if not self.is_runnable:
                self.log.debug('not running because of conditions')
                yield self.action_queue.conditions_locker.get_lock(self)
                self.log.debug('unblocked: conditions ok')
                continue

            try:
                yield self.markers_resolved_deferred
                self.log.debug('running')
                self.running = True
                d = self._run()
                self.running_deferred = InterruptibleDeferred(d)
                result = yield self.running_deferred

            except DeferredInterrupted:
                self.running_deferred = None
                continue
            except Exception, exc:
                self.running_deferred = None
                if self.cancelled:
                    self.log.debug('cancelled while running')
                    break
                if exc.__class__ in self.suppressed_error_messages:
                    self.log.warn('failure: %s', exc)
                else:
                    self.log.exception('failure: %s (traceback follows)', exc)
                self.cleanup()

                if exc.__class__ in self.retryable_errors:
                    self.log.debug('retrying')
                    self.handle_retryable(Failure(exc))
                    continue
                else:
                    self.handle_failure(Failure(exc))
            else:
                if self.cancelled:
                    self.log.debug('cancelled while running')
                    break
                self.log.debug('success')
                self.handle_success(result)

            # finish the command
            self.finish()
            return

    def cancel(self):
        """Cancel the command.

        Also cancel the command in the conditions locker.

        Do nothing if already cancelled (as cancellation can come from other
        thread, it can come at any time, so we need to support double
        cancellation safely).

        Return True if the command was really cancelled.
        """
        if self.cancelled:
            return False

        self.cancelled = True
        self.log.debug('cancelled')
        self.action_queue.conditions_locker.cancel_command(self)
        self.cleanup()
        self.finish()
        return True

    def _acquire_pathlock(self):
        """Acquire pathlock; overwrite if needed."""
        return defer.succeed(None)

    def handle_success(self, success):
        """Do anthing that's needed to handle success of the operation."""

    def handle_failure(self, failure):
        """Do anthing that's needed to handle failure of the operation."""

    def handle_retryable(self, failure):
        """Had that failure, but the command will be retried."""

    def __str__(self, str_attrs=None):
        """Return a str representation of the instance."""
        if str_attrs is None:
            str_attrs = self.logged_attrs
        name = self.__class__.__name__
        if len(str_attrs) == 0:
            return name
        attrs = [str(attr) + '=' + str(getattr(self, attr, None) or 'None') \
                 for attr in str_attrs]
        return ''.join([name, '(', ', '.join([attr for attr in attrs]), ')'])


class MakeThing(ActionQueueCommand):
    """Base of MakeFile and MakeDir."""

    __slots__ = ('share_id', 'parent_id', 'name', 'marker', 'path')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__
    possible_markers = 'parent_id',

    def __init__(self, request_queue, share_id, parent_id, name, marker, path):
        super(MakeThing, self).__init__(request_queue)
        self.share_id = share_id
        self.parent_id = parent_id
        # Unicode boundary! the name is Unicode in protocol and server, but
        # here we use bytes for paths
        self.name = name.decode("utf8")
        self.marker = marker
        self.path = path

    def _run(self):
        """Do the actual running."""
        maker = getattr(self.action_queue.client, self.client_method)
        return maker(self.share_id, self.parent_id, self.name)

    def handle_success(self, request):
        """It worked! Push the event."""
        # note that we're not getting the new name from the answer
        # message, if we would get it, we would have another Unicode
        # boundary with it
        d = dict(marker=self.marker, new_id=request.new_id,
                 new_generation=request.new_generation,
                 volume_id=self.share_id)
        self.action_queue.event_queue.push(self.ok_event_name, **d)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        self.action_queue.event_queue.push(self.error_event_name,
                                           marker=self.marker,
                                           failure=failure)

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), on_parent=True,
                                                               logger=self.log)


class MakeFile(MakeThing):
    """Make a file."""
    __slots__ = ()
    ok_event_name = 'AQ_FILE_NEW_OK'
    error_event_name = 'AQ_FILE_NEW_ERROR'
    client_method = 'make_file'


class MakeDir(MakeThing):
    """Make a directory."""
    __slots__ = ()
    ok_event_name = 'AQ_DIR_NEW_OK'
    error_event_name = 'AQ_DIR_NEW_ERROR'
    client_method = 'make_dir'


class Move(ActionQueueCommand):
    """Move a file or directory."""
    __slots__ = ('share_id', 'node_id', 'old_parent_id',
                 'new_parent_id', 'new_name', 'path_from', 'path_to')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__
    possible_markers = 'node_id', 'old_parent_id', 'new_parent_id'

    def __init__(self, request_queue, share_id, node_id, old_parent_id,
                 new_parent_id, new_name, path_from, path_to):
        super(Move, self).__init__(request_queue)
        self.share_id = share_id
        self.node_id = node_id
        self.old_parent_id = old_parent_id
        self.new_parent_id = new_parent_id
        # Unicode boundary! the name is Unicode in protocol and server, but
        # here we use bytes for paths
        self.new_name = new_name.decode("utf8")
        self.path_from = path_from
        self.path_to = path_to

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return (self.__class__.__name__, self.share_id, self.node_id)

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.move(self.share_id,
                                             self.node_id,
                                             self.new_parent_id,
                                             self.new_name)

    def handle_success(self, request):
        """It worked! Push the event."""
        d = dict(share_id=self.share_id, node_id=self.node_id,
                 new_generation=request.new_generation)
        self.action_queue.event_queue.push('AQ_MOVE_OK', **d)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        self.action_queue.event_queue.push('AQ_MOVE_ERROR',
                                           error=failure.getErrorMessage(),
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           old_parent_id=self.old_parent_id,
                                           new_parent_id=self.new_parent_id,
                                           new_name=self.new_name)

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        parts_from = self.path_from.split(os.path.sep)
        parts_to = self.path_to.split(os.path.sep)

        def multiple_release(list_result):
            """Multiple release.

            Get the result of both deferred and return one function
            to call both.
            """
            release1 = list_result[0][1]
            release2 = list_result[1][1]

            def release_them():
                """Efectively release them."""
                release1()
                release2()
            return release_them

        # get both locks and merge them
        d1 = pathlock.acquire(*parts_from, on_parent=True,
                              on_children=True, logger=self.log)
        d2 = pathlock.acquire(*parts_to, on_parent=True, logger=self.log)
        dl = defer.DeferredList([d1, d2])
        dl.addCallback(multiple_release)
        return dl


class Unlink(ActionQueueCommand):
    """Unlink a file or dir."""
    __slots__ = ('share_id', 'node_id', 'parent_id', 'path', 'is_dir')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__
    possible_markers = 'node_id', 'parent_id'

    def __init__(self, request_queue, share_id, parent_id, node_id, path,
                 is_dir):
        super(Unlink, self).__init__(request_queue)
        self.share_id = share_id
        self.node_id = node_id
        self.parent_id = parent_id
        self.path = path
        self.is_dir = is_dir

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.unlink(self.share_id, self.node_id)

    def handle_success(self, request):
        """It worked! Push the event."""
        d = dict(share_id=self.share_id, parent_id=self.parent_id,
                 node_id=self.node_id, new_generation=request.new_generation,
                 was_dir=self.is_dir, old_path=self.path)
        self.action_queue.event_queue.push('AQ_UNLINK_OK', **d)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        self.action_queue.event_queue.push('AQ_UNLINK_ERROR',
                                           error=failure.getErrorMessage(),
                                           share_id=self.share_id,
                                           parent_id=self.parent_id,
                                           node_id=self.node_id)

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), on_parent=True,
                                on_children=True, logger=self.log)


class ListShares(ActionQueueCommand):
    """List shares shared to me."""
    __slots__ = ()

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return self.__class__.__name__

    def _should_be_queued(self):
        """If other ListShares is queued, don't queue this one."""
        return self.uniqueness not in self._queue.hashed_waiting

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.list_shares()

    def handle_success(self, success):
        """It worked! Push the event."""
        self.action_queue.event_queue.push('AQ_SHARES_LIST',
                                           shares_list=success)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        self.action_queue.event_queue.push('AQ_LIST_SHARES_ERROR',
                                           error=failure.getErrorMessage())


class FreeSpaceInquiry(ActionQueueCommand):
    """Inquire about free space."""

    __slots__ = ()

    def __init__(self, request_queue, share_id):
        """Initialize the instance."""
        super(FreeSpaceInquiry, self).__init__(request_queue)
        self.share_id = share_id

    def _run(self):
        """Do the query."""
        return self.action_queue.client.get_free_space(self.share_id)

    def handle_success(self, success):
        """Publish the free space information."""
        self.action_queue.event_queue.push('SV_FREE_SPACE',
                                           share_id=success.share_id,
                                           free_bytes=success.free_bytes)

    def handle_failure(self, failure):
        """Publish the error."""
        self.action_queue.event_queue.push('AQ_FREE_SPACE_ERROR',
                                           error=failure.getErrorMessage())


class AccountInquiry(ActionQueueCommand):
    """Query user account information."""

    __slots__ = ()

    def _run(self):
        """Make the actual request."""
        return self.action_queue.client.get_account_info()

    def handle_success(self, success):
        """Publish the account information to the event queue."""
        self.action_queue.event_queue.push('SV_ACCOUNT_CHANGED',
                                           account_info=success)

    def handle_failure(self, failure):
        """Publish the error."""
        self.action_queue.event_queue.push('AQ_ACCOUNT_ERROR',
                                           error=failure.getErrorMessage())


class AnswerShare(ActionQueueCommand):
    """Answer a share offer."""

    __slots__ = ('share_id', 'answer')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, share_id, answer):
        super(AnswerShare, self).__init__(request_queue)
        self.share_id = share_id
        self.answer = answer

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.accept_share(self.share_id,
                                                     self.answer)

    def handle_success(self, success):
        """It worked! Push the event."""
        self.action_queue.event_queue.push('AQ_ANSWER_SHARE_OK',
                                           share_id=self.share_id,
                                           answer=self.answer)

    def handle_failure(self, failure):
        """It didn't work. Push the event."""
        self.action_queue.event_queue.push('AQ_ANSWER_SHARE_ERROR',
                                           share_id=self.share_id,
                                           answer=self.answer,
                                           error=failure.getErrorMessage())


class CreateShare(ActionQueueCommand):
    """Offer a share to somebody."""

    __slots__ = ('node_id', 'share_to', 'name', 'access_level',
                 'marker', 'use_http', 'path')
    possible_markers = 'node_id',
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, node_id, share_to, name, access_level,
                 marker, path):
        super(CreateShare, self).__init__(request_queue)
        self.node_id = node_id
        self.share_to = share_to
        self.name = name
        self.access_level = access_level
        self.marker = marker
        self.use_http = False
        self.path = path

        if share_to and re.match(EREGEX, share_to):
            self.use_http = True

    def _create_share_http(self, node_id, user, name, read_only, deferred):
        """Create a share using the HTTP Web API method."""

        url = "https://one.ubuntu.com/files/api/offer_share/"
        method = oauth.OAuthSignatureMethod_PLAINTEXT()
        request = oauth.OAuthRequest.from_consumer_and_token(
            http_url=url,
            http_method="POST",
            oauth_consumer=self.action_queue.consumer,
            token=self.action_queue.token)
        request.sign_request(method, self.action_queue.consumer,
                             self.action_queue.token)
        data = dict(offer_to_email=user,
                    read_only=read_only,
                    node_id=node_id,
                    share_name=name)
        pdata = urlencode(data)
        headers = request.to_header()
        req = Request(url, pdata, headers)
        try:
            urlopen(req)
        except HTTPError, e:
            reactor.callFromThread(deferred.errback, Failure(e))

        reactor.callFromThread(deferred.callback, None)

    def _run(self):
        """Do the actual running."""
        if self.use_http:
            # External user, do the HTTP REST method
            deferred = defer.Deferred()
            d = threads.deferToThread(self._create_share_http,
                                      self.node_id, self.share_to,
                                      self.name, self.access_level != 'Modify',
                                      deferred)
            d.addErrback(deferred.errback)
            return deferred
        else:
            return self.action_queue.client.create_share(self.node_id,
                                                         self.share_to,
                                                         self.name,
                                                         self.access_level)

    def handle_success(self, success):
        """It worked! Push the event."""
        # We don't get a share_id back from the HTTP REST method
        if not self.use_http:
            self.action_queue.event_queue.push('AQ_CREATE_SHARE_OK',
                                               share_id=success.share_id,
                                               marker=self.marker)
        else:
            self.action_queue.event_queue.push('AQ_SHARE_INVITATION_SENT',
                                               marker=self.marker)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        self.action_queue.event_queue.push('AQ_CREATE_SHARE_ERROR',
                                           marker=self.marker,
                                           error=failure.getErrorMessage())

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), logger=self.log)


class DeleteShare(ActionQueueCommand):
    """Delete a offered Share."""

    __slots__ = ('share_id',)
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, share_id):
        super(DeleteShare, self).__init__(request_queue)
        self.share_id = share_id

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.delete_share(self.share_id)

    def handle_success(self, success):
        """It worked! Push the event."""
        self.action_queue.event_queue.push('AQ_DELETE_SHARE_OK',
                                           share_id=self.share_id)

    def handle_failure(self, failure):
        """It didn't work. Push the event."""
        self.action_queue.event_queue.push('AQ_DELETE_SHARE_ERROR',
                                           share_id=self.share_id,
                                           error=failure.getErrorMessage())


class CreateUDF(ActionQueueCommand):
    """Create a new User Defined Folder."""

    __slots__ = ('path', 'name', 'marker')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, path, name, marker):
        super(CreateUDF, self).__init__(request_queue)
        self.path = path
        # XXX Unicode boundary?
        self.name = name
        self.marker = marker

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.create_udf(self.path, self.name)

    def handle_success(self, success):
        """It worked! Push the success event."""
        kwargs = dict(marker=self.marker,
                      volume_id=success.volume_id,
                      node_id=success.node_id)
        self.action_queue.event_queue.push('AQ_CREATE_UDF_OK', **kwargs)

    def handle_failure(self, failure):
        """It didn't work! Push the failure event."""
        self.action_queue.event_queue.push('AQ_CREATE_UDF_ERROR',
                                           marker=self.marker,
                                           error=failure.getErrorMessage())

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), logger=self.log)


class ListVolumes(ActionQueueCommand):
    """List all the volumes for a given user."""

    __slots__ = ()

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return self.__class__.__name__

    def _should_be_queued(self):
        """If other ListVolumes is queued, don't queue this one."""
        return self.uniqueness not in self._queue.hashed_waiting

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.list_volumes()

    def handle_success(self, success):
        """It worked! Push the success event."""
        self.action_queue.event_queue.push('AQ_LIST_VOLUMES',
                                           volumes=success.volumes)

    def handle_failure(self, failure):
        """It didn't work! Push the failure event."""
        self.action_queue.event_queue.push('AQ_LIST_VOLUMES_ERROR',
                                           error=failure.getErrorMessage())


class DeleteVolume(ActionQueueCommand):
    """Delete an exsistent volume."""

    __slots__ = ('volume_id', 'marker', 'path')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, volume_id, path):
        super(DeleteVolume, self).__init__(request_queue)
        self.volume_id = volume_id
        self.path = path

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.delete_volume(self.volume_id)

    def handle_success(self, success):
        """It worked! Push the success event."""
        self.action_queue.event_queue.push('AQ_DELETE_VOLUME_OK',
                                           volume_id=self.volume_id)

    def handle_failure(self, failure):
        """It didn't work! Push the failure event."""
        self.action_queue.event_queue.push('AQ_DELETE_VOLUME_ERROR',
                                           volume_id=self.volume_id,
                                           error=failure.getErrorMessage())

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), logger=self.log)


class DeltaList(list):
    """A list with a small and fixed representation.

    We use delta lists instead of regular lists when we push deltas into
    the event queue so when we log the arguments of the event that was pushed
    we dont flood the logs.
    """

    def __init__(self, source):
        super(DeltaList, self).__init__()
        self[:] = source

    def __repr__(self):
        """A short representation for the list."""
        return "<DeltaList(len=%s)>" % (len(self),)

    __str__ = __repr__


class GetDelta(ActionQueueCommand):
    """Get a delta from a generation for a volume."""

    __slots__ = ('volume_id', 'generation')
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, volume_id, generation):
        super(GetDelta, self).__init__(request_queue)
        self.volume_id = volume_id
        self.generation = generation

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.get_delta(self.volume_id,
                                                  self.generation)

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return (self.__class__.__name__, self.volume_id)

    def _should_be_queued(self):
        """Determine if the command should be queued or other removed."""
        if self.uniqueness in self._queue.hashed_waiting:
            # other GetDelta for same volume! leave the smaller one
            queued_command = self._queue.hashed_waiting[self.uniqueness]
            if queued_command.generation > self.generation:
                if not queued_command.running:
                    # don't remove anything if already running!
                    m = "removing previous command because bigger gen num: %s"
                    self.log.debug(m, queued_command)
                    self._queue.remove(queued_command)
            else:
                self.log.debug("not queueing self because there's other "
                               "command with less or same gen num")
                return False

        # no similar command, or removed the previous command (if not running)
        return True

    def handle_success(self, request):
        """It worked! Push the success event."""
        data = dict(
            volume_id=self.volume_id,
            delta_content=DeltaList(request.response),
            end_generation=request.end_generation,
            full=request.full,
            free_bytes=request.free_bytes,
        )
        self.action_queue.event_queue.push('AQ_DELTA_OK', **data)

    def handle_failure(self, failure):
        """It didn't work! Push the failure event."""
        if failure.check(protocol_errors.CannotProduceDelta):
            self.action_queue.event_queue.push('AQ_DELTA_NOT_POSSIBLE',
                                               volume_id=self.volume_id)
        else:
            self.action_queue.event_queue.push('AQ_DELTA_ERROR',
                                               volume_id=self.volume_id,
                                               error=failure.getErrorMessage())

    def make_logger(self):
        """Create a logger for this object."""
        self.log = mklog(logger, 'GetDelta', self.volume_id,
                         None, generation=self.generation)


class GetDeltaFromScratch(ActionQueueCommand):
    """Get a delta from scratch."""

    __slots__ = ('volume_id',)
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, volume_id):
        super(GetDeltaFromScratch, self).__init__(request_queue)
        self.volume_id = volume_id

    def _run(self):
        """Do the actual running."""
        return self.action_queue.client.get_delta(self.volume_id,
                                                  from_scratch=True)

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return (self.__class__.__name__, self.volume_id)

    def _should_be_queued(self):
        """Determine if the command should be queued."""
        if self.uniqueness in self._queue.hashed_waiting:
            # other GetDeltaFromScratch for same volume! skip self
            m = "GetDeltaFromScratch already queued, not queueing self"
            self.log.debug(m)
            return False

        return True

    def handle_success(self, request):
        """It worked! Push the success event."""
        data = dict(
            volume_id=self.volume_id,
            delta_content=DeltaList(request.response),
            end_generation=request.end_generation,
            free_bytes=request.free_bytes,
        )
        self.action_queue.event_queue.push('AQ_RESCAN_FROM_SCRATCH_OK', **data)

    def handle_failure(self, failure):
        """It didn't work! Push the failure event."""
        self.action_queue.event_queue.push('AQ_RESCAN_FROM_SCRATCH_ERROR',
                                           volume_id=self.volume_id,
                                           error=failure.getErrorMessage())

    def make_logger(self):
        """Create a logger for this object."""
        self.log = mklog(logger, 'GetDeltaFromScratch', self.volume_id, None)



class ChangePublicAccess(ActionQueueCommand):
    """Change the public access of a file."""

    __slots__ = ('share_id', 'node_id', 'is_public')
    possible_markers = 'node_id',

    def __init__(self, request_queue, share_id, node_id, is_public):
        super(ChangePublicAccess, self).__init__(request_queue)
        self.share_id = share_id
        self.node_id = node_id
        self.is_public = is_public

    def _change_public_access_http(self):
        """Change public access using the HTTP Web API method."""

        # Construct the node key.
        node_key = base64.urlsafe_b64encode(self.node_id.bytes).strip("=")
        if self.share_id is not None:
            node_key = "%s:%s" % (
                base64.urlsafe_b64encode(self.share_id.bytes).strip("="),
                node_key)

        url = "https://one.ubuntu.com/files/api/set_public/%s" % (node_key,)
        method = oauth.OAuthSignatureMethod_PLAINTEXT()
        request = oauth.OAuthRequest.from_consumer_and_token(
            http_url=url,
            http_method="POST",
            oauth_consumer=self.action_queue.consumer,
            token=self.action_queue.token)
        request.sign_request(method, self.action_queue.consumer,
                             self.action_queue.token)
        data = dict(is_public=bool(self.is_public))
        pdata = urlencode(data)
        headers = request.to_header()
        req = Request(url, pdata, headers)
        response = urlopen(req)
        return simplejson.load(response)

    def _run(self):
        """See ActionQueueCommand."""
        return threads.deferToThread(self._change_public_access_http)

    def handle_success(self, success):
        """See ActionQueueCommand."""
        self.action_queue.event_queue.push('AQ_CHANGE_PUBLIC_ACCESS_OK',
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           is_public=success['is_public'],
                                           public_url=success['public_url'])

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        if issubclass(failure.type, HTTPError):
            message = failure.value.read()
        else:
            message = failure.getErrorMessage()
        self.action_queue.event_queue.push('AQ_CHANGE_PUBLIC_ACCESS_ERROR',
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           error=message)


class GetPublicFiles(ActionQueueCommand):
    """Get the list of public files."""

    __slots__ = ('_url',)
    logged_attrs = ActionQueueCommand.logged_attrs + __slots__

    def __init__(self, request_queue, base_url='https://one.ubuntu.com'):
        super(GetPublicFiles, self).__init__(request_queue)
        self._url = urljoin(base_url, 'files/api/public_files')

    def _get_public_files_http(self):
        """Get public files list using the HTTP Web API method."""

        method = oauth.OAuthSignatureMethod_PLAINTEXT()
        request = oauth.OAuthRequest.from_consumer_and_token(
            http_url=self._url,
            http_method="GET",
            oauth_consumer=self.action_queue.consumer,
            token=self.action_queue.token)
        request.sign_request(method, self.action_queue.consumer,
                             self.action_queue.token)
        headers = request.to_header()
        req = Request(self._url, headers=headers)
        response = urlopen(req)
        files = simplejson.load(response)
        # translate nodekeys to (volume_id, node_id)
        for pf in files:
            _, node_id = self.split_nodekey(pf.pop('nodekey'))
            volume_id = pf['volume_id']
            pf['volume_id'] = '' if volume_id is None else volume_id
            pf['node_id'] = node_id
        return files

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return self.__class__.__name__

    def _should_be_queued(self):
        """If other ListVolumes is queued, don't queue this one."""
        return self.uniqueness not in self._queue.hashed_waiting

    def _run(self):
        """See ActionQueueCommand."""
        return threads.deferToThread(self._get_public_files_http)

    def handle_success(self, success):
        """See ActionQueueCommand."""
        self.action_queue.event_queue.push('AQ_PUBLIC_FILES_LIST_OK',
                                           public_files=success)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        if issubclass(failure.type, HTTPError):
            message = failure.value.read()
        else:
            message = failure.getErrorMessage()
        self.action_queue.event_queue.push('AQ_PUBLIC_FILES_LIST_ERROR',
                                           error=message)

    def split_nodekey(self, nodekey):
        """Split a node key into a share_id, node_id."""
        if nodekey is None:
            return None, None
        if ":" in nodekey:
            parts = nodekey.split(":")
            return self.decode_uuid(parts[0]), self.decode_uuid(parts[1])
        else:
            return '', self.decode_uuid(nodekey)

    def decode_uuid(self, encoded):
        """Return a uuid from the encoded value.

        If the value isn't UUID, just return the decoded value
        """
        if encoded:
            data = str(encoded) + '=' * (len(encoded) % 4)
            value = base64.urlsafe_b64decode(data)
        try:
            return str(uuid.UUID(bytes=value))
        except ValueError:
            return value


class Download(ActionQueueCommand):
    """Get the contents of a file."""

    __slots__ = ('share_id', 'node_id', 'server_hash', 'fileobj_factory',
                 'fileobj', 'gunzip', 'path', 'download_req', 'tx_semaphore',
                 'deflated_size', 'n_bytes_read_last', 'n_bytes_read')
    logged_attrs = ActionQueueCommand.logged_attrs + (
                    'share_id', 'node_id', 'server_hash', 'path')
    possible_markers = 'node_id',

    def __init__(self, request_queue, share_id, node_id, server_hash, path,
                 fileobj_factory):
        super(Download, self).__init__(request_queue)
        self.share_id = share_id
        self.node_id = node_id
        self.server_hash = server_hash
        self.fileobj_factory = fileobj_factory
        self.fileobj = None
        self.gunzip = None
        self.path = path
        self.download_req = None
        self.n_bytes_read = 0
        self.n_bytes_read_last = 0
        self.deflated_size = None
        self.tx_semaphore = None

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return (self.__class__.__name__, self.share_id, self.node_id)

    def _should_be_queued(self):
        """Queue but keeping uniqueness."""
        for uniq in [(Upload.__name__, self.share_id, self.node_id),
                     (Download.__name__, self.share_id, self.node_id)]:
            if uniq in self._queue.hashed_waiting:
                previous_command = self._queue.hashed_waiting[uniq]
                did_cancel = previous_command.cancel()
                if did_cancel:
                    m = "Previous command cancelled because uniqueness: %s"
                else:
                    m = ("Tried to cancel other command because uniqueness, "
                         "but couldn't: %s")
                self.log.debug(m, previous_command)
        return True

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), logger=self.log)

    def cancel(self):
        """Cancel the download."""
        if self.download_req is not None:
            self.download_req.cancel()
        return super(Download, self).cancel()

    @defer.inlineCallbacks
    def _start(self):
        """Just acquire the transfers semaphore."""
        self.tx_semaphore = yield self._queue.transfers_semaphore.acquire()
        if self.cancelled:
            # release the semaphore and stop working!
            self.log.debug("semaphore released after acquiring, "
                           "command cancelled")
            self.tx_semaphore = self.tx_semaphore.release()
            return
        self.log.debug('semaphore acquired')

    def finish(self):
        """Release the semaphore if already acquired."""
        if self.tx_semaphore is not None:
            self.tx_semaphore = self.tx_semaphore.release()
            self.log.debug('semaphore released')
        super(Download, self).finish()

    def _run(self):
        """Do the actual running."""
        # start or reset the file object, and get a new decompressor
        if self.fileobj is None:
            try:
                self.fileobj = self.fileobj_factory()
            except StandardError:
                self.log.debug(traceback.format_exc())
                msg = DefaultException('unable to build fileobj'
                                       ' (file went away?)'
                                       ' so aborting the download.')
                return defer.fail(Failure(msg))
        else:
            self.fileobj.seek(0, 0)
            self.fileobj.truncate(0)
            self.n_bytes_read = 0
            self.n_bytes_read_last = 0
        self.gunzip = zlib.decompressobj()

        self.action_queue.event_queue.push('AQ_DOWNLOAD_STARTED',
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           server_hash=self.server_hash)

        req = self.action_queue.client.get_content_request(
            self.share_id, self.node_id, self.server_hash,
            offset=self.n_bytes_read,
            callback=self.downloaded_cb, node_attr_callback=self.node_attr_cb)
        self.download_req = req
        return req.deferred

    def handle_success(self, _):
        """It worked! Push the event."""
        self.sync()
        # send a COMMIT, the Nanny will issue the FINISHED if it's ok
        self.action_queue.event_queue.push('AQ_DOWNLOAD_COMMIT',
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           server_hash=self.server_hash)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        if failure.check(protocol_errors.DoesNotExistError):
            self.action_queue.event_queue.push('AQ_DOWNLOAD_DOES_NOT_EXIST',
                                               share_id=self.share_id,
                                               node_id=self.node_id)
        else:
            self.action_queue.event_queue.push('AQ_DOWNLOAD_ERROR',
                                               error=failure.getErrorMessage(),
                                               share_id=self.share_id,
                                               node_id=self.node_id,
                                               server_hash=self.server_hash)

    def downloaded_cb(self, bytes):
        """A streaming decompressor."""
        self.n_bytes_read += len(bytes)
        self.fileobj.write(self.gunzip.decompress(bytes))
        self.fileobj.flush()     # not strictly necessary but nice to
                                 # see the downloaded size
        self.progress_hook()

    def progress_hook(self):
        """Send event if accumulated enough progress."""
        read_since_last = self.n_bytes_read - self.n_bytes_read_last
        if read_since_last >= TRANSFER_PROGRESS_THRESHOLD:
            event_data = dict(share_id=self.share_id, node_id=self.node_id,
                              n_bytes_read=self.n_bytes_read,
                              deflated_size=self.deflated_size)
            self.action_queue.event_queue.push('AQ_DOWNLOAD_FILE_PROGRESS',
                                               **event_data)
            self.n_bytes_read_last = self.n_bytes_read

    def node_attr_cb(self, **kwargs):
        """Update command information with node attributes."""
        self.deflated_size = kwargs['deflated_size']

    def sync(self):
        """Flush the buffers and sync them to disk if possible."""
        remains = self.gunzip.flush()
        if remains:
            self.fileobj.write(remains)
        self.fileobj.flush()
        if getattr(self.fileobj, 'fileno', None) is not None:
            # it's a real file, with a fileno! Let's sync its data
            # out to disk
            os.fsync(self.fileobj.fileno())
        self.fileobj.close()


class Upload(ActionQueueCommand):
    """Upload stuff to a file."""

    __slots__ = ('share_id', 'node_id', 'previous_hash', 'hash', 'crc32',
                 'size', 'fileobj_factory', 'magic_hash',
                 'deflated_size', 'tempfile', 'upload_req', 'tx_semaphore',
                 'n_bytes_written_last', 'path', 'n_bytes_written', 'upload_id')

    logged_attrs = ActionQueueCommand.logged_attrs + (
                    'share_id', 'node_id', 'previous_hash', 'hash', 'crc32',
                    'size', 'upload_id', 'path')
    retryable_errors = ActionQueueCommand.retryable_errors + (
                                        protocol_errors.UploadInProgressError,)
    possible_markers = 'node_id',

    def __init__(self, request_queue, share_id, node_id, previous_hash, hash,
                 crc32, size, path, fileobj_factory, upload_id=None):
        super(Upload, self).__init__(request_queue)
        self.share_id = share_id
        self.node_id = node_id
        self.previous_hash = previous_hash
        self.hash = hash
        self.crc32 = crc32
        self.size = size
        self.fileobj_factory = fileobj_factory
        self.upload_id = upload_id
        self.tempfile = None
        self.path = path
        self.upload_req = None
        self.n_bytes_written_last = 0
        self.n_bytes_written = 0
        self.deflated_size = None
        self.tx_semaphore = None
        self.magic_hash = None

    @property
    def is_runnable(self):
        """Tell if the upload is ok to be carried on.

        Return True if there is sufficient space available to complete
        the upload, or if the upload is cancelled so it can pursue
        its fate.
        """
        if self.cancelled:
            return True
        else:
            return self.action_queue.have_sufficient_space_for_upload(
                                                    self.share_id, self.size)

    def _should_be_queued(self):
        """Queue but keeping uniqueness."""
        for uniq in [(Upload.__name__, self.share_id, self.node_id),
                     (Download.__name__, self.share_id, self.node_id)]:
            if uniq in self._queue.hashed_waiting:
                previous_command = self._queue.hashed_waiting[uniq]
                did_cancel = previous_command.cancel()
                if did_cancel:
                    m = "Previous command cancelled because uniqueness: %s"
                else:
                    m = ("Tried to cancel other command because uniqueness, "
                         "but couldn't: %s")
                self.log.debug(m, previous_command)
        return True

    @property
    def uniqueness(self):
        """Info for uniqueness."""
        return (self.__class__.__name__, self.share_id, self.node_id)

    def _acquire_pathlock(self):
        """Acquire pathlock."""
        pathlock = self.action_queue.pathlock
        return pathlock.acquire(*self.path.split(os.path.sep), logger=self.log)

    def cancel(self):
        """Cancel the upload."""
        if self.upload_req is not None:
            producer = self.upload_req.producer
            if producer is not None and producer.finished:
                # can not cancel if already sent the EOF
                return False

            self.upload_req.cancel()
        return super(Upload, self).cancel()

    def cleanup(self):
        """Cleanup: stop the producer."""
        self.log.debug('cleanup')
        if self.upload_req is not None and self.upload_req.producer is not None:
            self.log.debug('stopping the producer')
            self.upload_req.producer.stopProducing()

    @defer.inlineCallbacks
    def _start(self):
        """Do the specialized pre-run setup."""
        self.tx_semaphore = yield self._queue.transfers_semaphore.acquire()
        if self.cancelled:
            # release the semaphore and stop working!
            self.log.debug("semaphore released after acquiring, "
                           "command cancelled")
            self.tx_semaphore = self.tx_semaphore.release()
            return
        self.log.debug('semaphore acquired')

        yield self.action_queue.zip_queue.zip(self)

    def finish(self):
        """Release the semaphore if already acquired."""
        if self.tx_semaphore is not None:
            self.tx_semaphore = self.tx_semaphore.release()
            self.log.debug('semaphore released')
        super(Upload, self).finish()

    def _run(self):
        """Do the actual running."""
        self.action_queue.event_queue.push('AQ_UPLOAD_STARTED',
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           hash=self.hash)

        f = UploadProgressWrapper(self.tempfile, self)

        # access here the magic hash value, don't log anywhere, and
        # just send it
        magic_hash = self.magic_hash._magic_hash
        req = self.action_queue.client.put_content_request(
            self.share_id, self.node_id, self.previous_hash, self.hash,
            self.crc32, self.size, self.deflated_size, f,
            upload_id=self.upload_id, upload_id_cb=self._upload_id_cb,
            magic_hash=magic_hash)
        self.upload_req = req
        d = req.deferred
        d.addBoth(passit(lambda _: self.tempfile.close()))
        return d

    def _upload_id_cb(self, upload_id):
        """Handle the received upload_id, save it in the metadata."""
        self.log.debug("got upload_id from server: %s", upload_id)
        self.action_queue.main.fs.set_by_node_id(
            self.node_id, self.share_id, upload_id=upload_id)
        self.upload_id = upload_id

    def progress_hook(self):
        """Send event if accumulated enough progress."""
        written_since_last = self.n_bytes_written - self.n_bytes_written_last
        if  written_since_last >= TRANSFER_PROGRESS_THRESHOLD:
            event_data = dict(share_id=self.share_id, node_id=self.node_id,
                              n_bytes_written=self.n_bytes_written,
                              deflated_size=self.deflated_size)
            self.action_queue.event_queue.push('AQ_UPLOAD_FILE_PROGRESS',
                                               **event_data)
            self.n_bytes_written_last = self.n_bytes_written

    def handle_success(self, request):
        """It worked! Push the event."""
        # remove the temporary file
        remove_file(self.tempfile.name)

        # send the event
        d = dict(share_id=self.share_id, node_id=self.node_id, hash=self.hash,
                 new_generation=request.new_generation)
        self.action_queue.event_queue.push('AQ_UPLOAD_FINISHED', **d)

    def handle_retryable(self, failure):
        """For a retryable failure."""
        if failure.check(protocol_errors.QuotaExceededError):
            error = failure.value
            self.action_queue.event_queue.push('SYS_QUOTA_EXCEEDED',
                                               volume_id=str(error.share_id),
                                               free_bytes=error.free_bytes)

    def handle_failure(self, failure):
        """It didn't work! Push the event."""
        remove_file(self.tempfile.name)
        self.action_queue.event_queue.push('AQ_UPLOAD_ERROR',
                                           error=failure.getErrorMessage(),
                                           share_id=self.share_id,
                                           node_id=self.node_id,
                                           hash=self.hash)
