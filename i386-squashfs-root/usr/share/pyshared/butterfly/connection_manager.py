# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import telepathy
import gobject
import dbus
import logging

from butterfly.protocol import ButterflyProtocol

__all__ = ['ButterflyConnectionManager']

logger = logging.getLogger('Butterfly.ConnectionManager')


class ButterflyConnectionManager(telepathy.server.ConnectionManager):
    """Butterfly connection manager
    
    Implements the org.freedesktop.Telepathy.ConnectionManager interface"""

    def __init__(self, shutdown_func=None):
        "Initializer"
        telepathy.server.ConnectionManager.__init__(self, 'butterfly')

        self._implement_protocol('msn', ButterflyProtocol)

        self._shutdown = shutdown_func
        logger.info("Connection manager created")

    def disconnected(self, conn):
        def shutdown():
            if self._shutdown is not None and \
                    len(self._connections) == 0:
                self._shutdown()
            return False
        result = telepathy.server.ConnectionManager.disconnected(self, conn)
        gobject.timeout_add_seconds(5, shutdown)

    def quit(self):
        "Terminates all connections. Must be called upon quit"
        conns = self._connections.copy()
        for connection in conns:
            connection.Disconnect()
        logger.info("Connection manager quitting")
