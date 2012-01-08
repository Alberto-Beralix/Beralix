# -*- coding: utf-8 -*-

# Author: Alejandro J. Cura <alecu@canonical.com>
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

"""tcpactivation: start a process if nothing listening in a given port."""

import subprocess

from twisted.internet import defer, protocol, reactor

LOCALHOST = "127.0.0.1"
DELAY_BETWEEN_CHECKS = 0.1
NUMBER_OF_CHECKS = 600

# twisted uses a different coding convention
# pylint: disable=C0103,W0232


def async_sleep(delay):
    """Fire the returned deferred after some specified delay."""
    d = defer.Deferred()
    # pylint: disable=E1101
    reactor.callLater(delay, d.callback, None)
    return d


class AlreadyStartedError(Exception):
    """The instance was already started."""


class ActivationTimeoutError(Exception):
    """Timeout while trying to start the instance."""


class NullProtocol(protocol.Protocol):
    """A protocol that drops the connection."""

    def connectionMade(self):
        """Just drop the connection."""
        self.transport.loseConnection()


class PortDetectFactory(protocol.ClientFactory):
    """Will detect if something is listening in a given port."""

    def __init__(self):
        """Initialize this instance."""
        self.d = defer.Deferred()

    def is_listening(self):
        """A deferred that will become True if something is listening."""
        return self.d

    def buildProtocol(self, addr):
        """Connected."""
        if not self.d.called:
            self.d.callback(True)
        return NullProtocol()

    def clientConnectionLost(self, connector, reason):
        """The connection was lost."""
        if not self.d.called:
            self.d.callback(False)

    def clientConnectionFailed(self, connector, reason):
        """The connection failed."""
        if not self.d.called:
            self.d.callback(False)


class ActivationConfig(object):
    """The configuration for tcp activation."""

    def __init__(self, service_name, command_line, port):
        """Initialize this instance."""
        self.service_name = service_name
        self.command_line = command_line
        self.port = port


class ActivationDetector(object):
    """Base class to detect if the service is running."""

    def __init__(self, config):
        """Initialize this instance."""
        self.config = config

    @defer.inlineCallbacks
    def is_already_running(self):
        """Check if the instance is already running."""
        factory = PortDetectFactory()
        # pylint: disable=E1101
        reactor.connectTCP(LOCALHOST, self.config.port, factory)
        result = yield factory.is_listening()
        defer.returnValue(result)


class ActivationClient(ActivationDetector):
    """A client for tcp activation."""

    # a classwide lock, so the server is started only once
    lock = defer.DeferredLock()

    @defer.inlineCallbacks
    def _wait_server_active(self):
        """Wait till the server is active."""
        for _ in xrange(NUMBER_OF_CHECKS):
            is_running = yield self.is_already_running()
            if is_running:
                defer.returnValue(None)
            yield async_sleep(DELAY_BETWEEN_CHECKS)
        raise ActivationTimeoutError()

    def _spawn_server(self):
        """Start running the server process."""
        # Without using close_fds=True, strange things happen
        # with logging on windows. More information at
        # http://bugs.python.org/issue4749
        subprocess.Popen(self.config.command_line, close_fds=True)

    @defer.inlineCallbacks
    def _do_get_active_port(self):
        """Get the port for the running instance, starting it if needed."""
        is_running = yield self.is_already_running()
        if not is_running:
            self._spawn_server()
            yield self._wait_server_active()
        defer.returnValue(self.config.port)

    @defer.inlineCallbacks
    def get_active_port(self):
        """Serialize the requests to _do_get_active_port."""
        yield self.lock.acquire()
        try:
            result = yield self._do_get_active_port()
            defer.returnValue(result)
        finally:
            self.lock.release()


class ActivationInstance(ActivationDetector):
    """A tcp activation server instance."""

    @defer.inlineCallbacks
    def get_port(self):
        """Get the port to run this service or fail if already started."""
        is_running = yield self.is_already_running()
        if is_running:
            raise AlreadyStartedError()
        defer.returnValue(self.config.port)
