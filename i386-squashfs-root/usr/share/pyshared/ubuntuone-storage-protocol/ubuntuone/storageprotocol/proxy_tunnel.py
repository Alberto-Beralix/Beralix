# ubuntuone.storageprotocol.proxy_tunnel - tunnel through proxies
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
"""Proxy tunelling"""
import base64

from twisted.internet.protocol import Protocol, ClientFactory, connectionDone
from twisted.internet import reactor, ssl


class ProxyTunnelClient(Protocol):
    """ Protocol to tunnel connections through a https proxy using
    the connect method.

    We send the command, do the auth and then proxy our calls to the
    original protocol.
    """
    MAX_LINE_LEN = 2 ** 14

    def __init__(self, *args, **kwargs):
        """Initialize the class."""
        self.__buffer = None
        self.client_protocol = None
        self.negotiation_done = False
        self.message = None
        self.status = None

    def sendHeader(self, name, value):
        """Send a header."""
        line = '%s: %s\r\n' % (name, value)
        self.transport.write(line)

    def connectionLost(self, reason=connectionDone):
        """The connection was lost."""
        if self.negotiation_done:
            self.client_protocol.connectionLost(reason)
        else:
            self.error(reason)

    def connectionMade(self):
        """Connection was established."""
        self.negotiation_done = False
        self.client_protocol = None
        self.__buffer = ""
        # send request
        line = "CONNECT %s:%s HTTP/1.0\r\n" % \
                (self.factory.host, self.factory.port)
        self.transport.write(line)
        # send headers
        self.sendHeader("Host", self.factory.host)
        # do auth
        user = self.factory.user
        if user is not None:
            auth_str = base64.b64encode("%s:%s" % (user, self.factory.passwd))
            self.sendHeader("Proxy-Authorization", "Basic %s" % auth_str)
        self.transport.write("\r\n")

    def error(self, reason):
        """Got an error."""
        self.factory.factory.clientConnectionFailed(self, reason)
        self.transport.loseConnection()

    def dataReceived(self, data):
        """Received some data."""
        if self.negotiation_done:
            self.client_protocol.dataReceived(data)
        else:
            self.__buffer = self.__buffer + data

            while not self.negotiation_done:
                try:
                    line, self.__buffer = self.__buffer.split("\r\n", 1)
                except ValueError:
                    if len(self.__buffer) > self.MAX_LINE_LEN:
                        self.error("Error in proxy negotiation: Line too long")
                    break
                else:
                    linelength = len(line)
                    if linelength > self.MAX_LINE_LEN:
                        self.error("Error in proxy negotiation: Line too long")
                        return
                    self.lineReceived(line)

    def lineReceived(self, line):
        """Received a line."""
        if line:
            parts = line.split(" ", 2)
            # pylint: disable=W0612
            version, status = parts[:2]
            if len(parts) == 3:
                message = parts[2]
            else:
                message = ""
            self.status = status
            self.message = message
        else:
            if self.status == "200":
                self.negotiation_done = True
                self.start()
            else:
                self.error("Error in proxy negotiation: " +
                           self.status + " " + self.message)

    def start(self):
        """Start doing stuf."""
        self.transport.startTLS(ssl.ClientContextFactory())
        protocol = self.factory.factory.buildProtocol(self.transport.getPeer())
        self.client_protocol = protocol
        protocol.makeConnection(self.transport)


class ProxyTunnelFactory(ClientFactory):
    """Factory class for the proxy tunnel."""
    protocol = ProxyTunnelClient

    def __init__(self, host, port, factory, user=None, passwd=None):
        """Initialize the factory class."""
        self.user = user
        self.passwd = passwd
        self.host = host
        self.port = port
        self.factory = factory

    def clientConnectionFailed(self, connector, reason):
        """Proxy client connection failed."""
        self.factory.clientConnectionFailed(connector,
            "Proxy connection error: %s" % (str(reason)))


def connectHTTPS(proxy_host, proxy_port, host, port, factory,
                 user=None, passwd=None):
    """
    use this function like reactor.connectTCP/connectSLL.
    it takes the usual parameters plus the proxy information.

    """
    pt_factory = ProxyTunnelFactory(host, port, factory, user, passwd)
    reactor.connectTCP(proxy_host, proxy_port, pt_factory)
