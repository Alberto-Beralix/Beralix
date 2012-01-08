# ubuntuone.storageprotocol.request - base classes for
#                                             network client and server
#
# Author: Lucio Torre <lucio.torre@canonical.com>
#
# Copyright 2009 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
The base classes for the network client and server.

This classes provide the message serialization, delivery, request
tracking and message handling.
"""


import struct
import time

from twisted.internet.protocol import Protocol, connectionDone
from twisted.internet.interfaces import IPushProducer
from twisted.internet import defer
# pylint and zope dont work
# pylint: disable=E0611,F0401
from zope.interface import implements

from ubuntuone.storageprotocol import protocol_pb2, validators
from ubuntuone.storageprotocol.errors import (
    StorageProtocolError, StorageProtocolErrorSizeTooBig,
    StorageProtocolProtocolError, StorageRequestError,
    RequestCancelledError, error_to_exception)


# the max possible packet size is 2**32 (32 bits for size)
# although we will not allow packets that big for now
# this is something we CANT change later
# (two bytes overhead per packet against smaller size)
SIZE_FMT = "!I"
SIZE_FMT_SIZE = struct.calcsize(SIZE_FMT)
MAX_MESSAGE_SIZE = 2 ** 16
UNKNOWN_HASH = "unknown"
# XXX lucio.torre, wild guess on payload size, fix with something better
MAX_PAYLOAD_SIZE = MAX_MESSAGE_SIZE - 300

# it's mandatory to always send the share when referring to a node in the
# client/server operations. '' is a special share name that means that
# the referred is the own root node, and not any of the shares
ROOT = ''


class RequestHandler(Protocol):
    """the base class for a network peer.

    @cvar REQUEST_ID_START:  the request id starting number. replace this in
    client subclasses. servers should start at 0, clients should start at 1.
    @cvar PROTOCOL_VERSION: the protocol version for this peer.
    """
    implements(IPushProducer)

    SIZE, MESSAGE = range(2)
    REQUEST_ID_START = 0
    PROTOCOL_VERSION = 3

    def __init__(self):
        """RequestHandler creation is done by the factory."""
        self.request_counter = self.REQUEST_ID_START
        # an id:request registry
        self.requests = {}
        self.pending_length = SIZE_FMT_SIZE
        self.waiting_for = self.SIZE
        self.pending_parts = []
        self.producing = True

    def get_new_request_id(self):
        """get a new and unused request id."""
        # register this request id
        request_id = self.request_counter
        # we increment the request counter by two;
        # clients allocate even-numbered request IDs
        # (0, 2, 4, ...) and servers allocate
        # odd-numbered request IDs (1, 3, 5, ...).
        self.request_counter += 2
        return request_id

    def connectionLost(self, reason=connectionDone):
        """Abort any outstanding requests when we lose our connection."""
        Protocol.connectionLost(self, reason)
        requests = self.requests.values()
        for request in requests:
            request.stopProducing()
            if request.started:
                request.cancel()
            try:
                # also removes from self.requests
                request.error(reason)
            except defer.AlreadyCalledError:
                # cancel may already have error-ed the request
                continue

    def addProducer(self, who):
        """add self as a producer as we have new requests."""
        if not self.requests:
            self.transport.registerProducer(self, streaming=True)
        if self.producing:
            who.resumeProducing()

    def removeProducer(self, who):
        "remove self as producer if there are no more requests."
        if not self.requests:
            self.transport.unregisterProducer()

    def resumeProducing(self):
        """IPushProducedInterface."""
        for request in self.requests.values():
            request.resumeProducing()
        self.producing = True

    def stopProducing(self):
        """IPushProducedInterface."""
        for request in self.requests.values():
            request.stopProducing()
        self.producing = False

    def pauseProducing(self):
        """IPushProducedInterface."""
        for request in self.requests.values():
            request.pauseProducing()
        self.producing = False

    def dataReceived(self, data):
        """handle new data."""
        try:
            self.buildMessage(data)
        except StorageProtocolError, e:
            # here we handle and should log all protocol errors
            self.transport.loseConnection()
            print "ERROR:", e

    def write(self, data):
        """transport API to capture bytes written"""
        self.transport.write(data)

    def writeSequence(self, data):
        """transport API to capture bytes written in a sequence"""
        self.transport.writeSequence(data)

    def buildMessage(self, data):
        """create messages from data received."""
        # more parts for the old message
        while len(data) > self.pending_length:
            # split and create a new message
            p = self.pending_length
            self.buildMessage(data[:p])
            data = data[p:]
        else:
            # just more data
            self.pending_parts.append(data)
            self.pending_length -= len(data)

            if self.pending_length == 0:
                # we have a finished message
                buf = "".join(self.pending_parts)
                self.pending_parts = []
                if self.waiting_for == self.SIZE:
                    # send an error if size is too big, close connection
                    sz = struct.unpack(SIZE_FMT, buf)[0]
                    if sz > MAX_MESSAGE_SIZE:
                        # we cant answer this request because we cant
                        # parse it, so we just drop the connection
                        self.transport.loseConnection()
                        raise StorageProtocolErrorSizeTooBig("message too big")

                    self.pending_length = sz
                    self.waiting_for = self.MESSAGE
                else:
                    self.waiting_for = self.SIZE
                    self.pending_length = SIZE_FMT_SIZE
                    message = protocol_pb2.Message()
                    message.ParseFromString(buf)
                    self.processMessage(message)

    def processMessage(self, message):
        """ process an incoming message.

        if this message is part of an active request, we just tell the request
        to handle the message.
        if its a new message, we call self.handle_MESSAGENAME.
        """
        result = None
        is_invalid = validators.validate_message(message)

        if is_invalid:
            self.log.error("Validation error: " + ", ".join(is_invalid))
            comment = ("Validation error:\n"
                       + "\n".join(is_invalid))
            if len(comment) > MAX_PAYLOAD_SIZE - 100:
                comment = comment[:MAX_PAYLOAD_SIZE - 112] + ' [truncated]'
            error_message = protocol_pb2.Message()
            error_message.id = message.id
            error_message.type = protocol_pb2.Message.ERROR
            error_message.error.type = protocol_pb2.Error.PROTOCOL_ERROR
            error_message.error.comment = comment
            self.sendMessage(error_message)
        else:
            if message.id in self.requests:
                target = self.requests[message.id].processMessage
                try:
                    result = target(message)
                except Exception, e:  # pylint: disable=W0703
                    self.requests[message.id].error(e)
            else:
                name = protocol_pb2.Message.DESCRIPTOR \
                     .enum_types_by_name['MessageType'] \
                     .values_by_number[message.type].name

                handler = getattr(self, "handle_" + name, None)
                if handler is not None:
                    result = handler(message)
                else:
                    raise Exception("peer cant handle message '%s' {%s}" % (
                            name,
                            str(message).replace("\n", " ")))
        return result

    def sendMessage(self, message):
        """send a message over the pipe.

        handles len+data plus message serialization.
        """
        m = message.SerializeToString()
        self.write(struct.pack(SIZE_FMT, len(m)))
        self.write(m)

    def handle_PING(self, message):
        """handle an incoming ping message."""
        response = protocol_pb2.Message()
        response.id = message.id
        response.type = protocol_pb2.Message.PONG
        self.sendMessage(response)

    def handle_NOOP(self, message):
        """handle an incoming noop message."""
        pass  # no-op

    def ping(self):
        """ ping the other end

        will return a deferred that will get called with
        the request object when completed.
        """
        p = Ping(self)
        p.start()
        return p.deferred

    def noop(self):
        """send a noop"""
        p = Noop(self)
        p.start()
        return p.deferred


class Request(object):
    """base class for requests.

    requests talk with request handlers to get a request id and
    receive all messages for that id. users of this class must make
    sure to call done or error to clean up the request from the request
    handler's index.

    @ivar deferred: the deferred that will be signaled on completion or error.
    @ivar id: the request id or None if not started
    """
    implements(IPushProducer)

    __slots__ = ('protocol', 'id', 'deferred', 'producer', 'started',
                 'finished', 'cancelled', 'producing')

    def __init__(self, protocol):
        """created a request.

        @param protocol: the request handler.
        """
        self.protocol = protocol
        self.id = None
        # create this completion deferred
        # XXX lucio.torre, create timeout helpers and defaults
        self.deferred = defer.Deferred()
        self.producer = None
        self.started = False
        self.finished = False
        self.cancelled = False
        self.producing = False

    def resumeProducing(self):
        """IPushProducedInterface."""
        if self.producer:
            self.producer.resumeProducing()
        self.producing = True

    def stopProducing(self):
        """IPushProducedInterface."""
        if self.producer:
            self.producer.stopProducing()
        self.producing = False

    def pauseProducing(self):
        """IPushProducedInterface."""
        if self.producer:
            self.producer.pauseProducing()
        self.producing = False

    def registerProducer(self, producer, streaming):
        """Part of the IConsumer interface, we dont implement write because
        we send packets, not bytes."""
        if not streaming:
            raise NotImplementedError("Pull producers not yet implemented")
        self.producer = producer
        if self.producing:
            self.producer.resumeProducing()

    def unregisterProducer(self):
        """IConsumer interface."""
        self.producer = None

    def start(self, selfid=None):
        """start the message exchange.

        will setup the request and call self._start to start the message
        exchange.
        """
        self.protocol.addProducer(self)
        if selfid is None:
            self.id = self.protocol.get_new_request_id()
            self.protocol.requests[self.id] = self
        else:
            self.id = selfid

        self.started = True
        return self._start()

    def done(self):
        """call this to signal that the request finished successfully"""
        self.cleanup()
        self.deferred.callback(self)

    def error(self, failure):
        """call this to signal that the request finished with failure

        @param failure: the failure instance
        """
        self.cleanup()
        self.deferred.errback(failure)

    def cleanup(self):
        """remove the reference to self from the request handler"""
        self.finished = True
        self.started = False
        del self.protocol.requests[self.id]
        self.protocol.removeProducer(self)

    def sendMessage(self, message):
        """send a message with this request id

        @param message: the protocol_pb2.Message instance
        """
        message.id = self.id
        self.protocol.sendMessage(message)

    def sendError(self, error_type, comment=None, free_space_info=None):
        """create and send an error message of type error_type

        @param error_type: a value from protocol_pb2.Error
        """
        message = protocol_pb2.Message()
        message.id = self.id
        message.type = protocol_pb2.Message.ERROR
        message.error.type = error_type
        if comment is not None:
            message.error.comment = comment
        if free_space_info is not None:
            message.free_space_info.share_id = free_space_info['share_id']
            message.free_space_info.free_bytes = free_space_info['free_bytes']
        self.sendMessage(message)

    def _start(self):
        """override this method to start the request."""
        raise NotImplementedError("request needs to do something")

    def _default_process_message(self, message):
        """Map ERROR message to a specific exception."""
        if message.type == protocol_pb2.Message.ERROR:
            error_class = error_to_exception(message.error.type)
        else:
            error_class = StorageRequestError
        self.error(error_class(self, message))

    def processMessage(self, message):
        """handle an incoming message for this request. override this.

        @param message: the protocol_pb2.Message instance.
        """
        pass

    def cancel(self):
        """We should stop this request."""
        # if the request already finished, it can't be cancelled!
        if self.finished:
            return True

        cancellable = self.started and not self.cancelled
        self.cancelled = True
        if cancellable:
            # if the request has some special work to do when cancelled, do it!
            custom_cancel = getattr(self, "_cancel", None)
            if custom_cancel is not None:
                custom_cancel()

    def cancel_filter(self, function):
        """Raises RequestCancelledError if the request is cancelled.

        This methods exists to be used in a addCallback sequence to assure
        that it does not continue if the request is cancelled, like:

        >>> d.addCallback(cancel_filter(foo))
        >>> d.addCallbacks(done_callback, error_errback)

        Note that you may receive RequestCancelledError in your
        'error_errback' func.
        """
        def _f(*args, **kwargs):
            '''Function to be called from twisted when its time arrives.'''
            if self.cancelled:
                raise RequestCancelledError("The request id=%d is cancelled! "
                                            "(before calling %r)" %
                                                        (self.id, function))
            return function(*args, **kwargs)
        return _f


class RequestResponse(Request):
    """A request that is created in response to an incoming message.

    @ivar source_message: the message the generated this request.
    """

    __slots__ = ('source_message',)

    # pylint: disable=W0223
    def __init__(self, protocol, message):
        """Create a request response.

        @param protocol: the request handler.
        @param message: the source message.
        """
        Request.__init__(self, protocol)
        self.source_message = message

    def start(self):
        """Register this request and start response."""
        result = Request.start(self, self.source_message.id)
        return result


class Ping(Request):
    """Request to ping the other peer.

    @ivar rtt: will contain the round trip time when completed.
    """

    __slots__ = ('_start_time', 'rtt')

    def _start(self):
        """start the request sending a ping message."""
        # pylint: disable=W0201
        self.rtt = 0
        self._start_time = time.time()
        message = protocol_pb2.Message()
        message.id = self.id
        message.type = protocol_pb2.Message.PING
        self.sendMessage(message)

    def processMessage(self, message):
        """calculate rtt if message is pong, error otherwise"""
        if message.type == protocol_pb2.Message.PONG:
            # pylint: disable=W0201
            # attributes are created in completion
            self.rtt = time.time() - self._start_time
            self.done()
        else:
            if message.type == protocol_pb2.Message.ERROR:
                if message.error.type == protocol_pb2.Error.PROTOCOL_ERROR:
                    exc = StorageProtocolProtocolError
                else:
                    exc = StorageProtocolError
                msg = message.error.comment
            else:
                exc = RuntimeError
                msg = "Unknown ping error:" + str(message)
            self.error(exc(msg))


class Noop(Request):
    """NOOP request"""

    def _start(self):
        """start the request sending a noop message."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.NOOP
        self.sendMessage(message)
        self.done()
