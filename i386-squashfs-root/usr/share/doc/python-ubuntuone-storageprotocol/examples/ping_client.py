# ubuntuone.storageprotocol.samples.ping_client - a ping client
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
"""A simple ping client
"""

from twisted.internet import reactor

from ubuntuone.storageprotocol.client import (
    StorageClientFactory, StorageClient)


class PingClient(StorageClient):
    """Simple client that calls a callback on connection."""

    def connectionMade(self):
        """Setup and call callback."""
        # pylint: disable=W0201
        StorageClient.connectionMade(self)
        print "Connection made."
        d = self.ping()

        def done(request):
            """We have the ping reply"""
            print "Ping RTT:", request.rtt
            reactor.stop()

        def error(failure):
            """Something went wrong."""
            print "Error:"
            print failure.getTraceback()
            reactor.stop()

        d.addCallbacks(done, error)


class PingClientFactory(StorageClientFactory):
    """A test oriented protocol factory."""
    # no init: pylint: disable=W0232

    protocol = PingClient

    def clientConnectionFailed(self, connector, reason):
        """We failed at connecting."""

        print 'Connection failed. Reason:', reason
        reactor.stop()


if __name__ == "__main__":
    # these 3 lines show the different ways of connecting a client to the
    # server

    # using tcp
    reactor.connectTCP('75.101.137.174', 80, PingClientFactory())

    # using ssl
    #reactor.connectSSL('localhost', 20101, StorageClientFactory(),
    #           ssl.ClientContextFactory())

    # using ssl over a proxy
    #from ubuntuone.storageprotocol import proxy_tunnel
    #proxy_tunnel.connectHTTPS('localhost', 3128,
    #        'localhost', 20101, StorageClientFactory(),
    #        user="test", passwd="test")

    reactor.run()
