# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2009 Collabora Ltd.
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

import logging
import weakref
import dbus

import telepathy
import papyon
import papyon.event

from butterfly.util.decorator import async
from butterfly.media import ButterflyStreamHandler
from butterfly.media.constants import *
from papyon.media.constants import *

__all__ = ['ButterflySessionHandler']

logger = logging.getLogger('Butterfly.SessionHandler')

class ButterflySessionHandler (telepathy.server.MediaSessionHandler):
    def __init__(self, connection, channel, session):
        self._conn = connection
        self._session = session
        self._stream_handlers = {}
        self._next_stream_id = 0
        self._type = session.type
        self._ready = False
        self._pending_handlers = []

        path = channel._object_path + "/sessionhandler1"
        telepathy.server.MediaSessionHandler.__init__(self, connection._name, path)

    @property
    def next_stream_id(self):
        self._next_stream_id += 1
        return self._next_stream_id

    @property
    def subtype(self):
        if self._type == MediaSessionType.WEBCAM_SEND:
            return "msncamsend"
        elif self._type == MediaSessionType.WEBCAM_RECV:
            return "msncamrecv"
        else:
            return "rtp"

    @property
    def type(self):
        return self._type

    def get_stream_path(self, id):
        return "%s/stream%d" % (self._object_path, id)

    def Ready(self):
        logger.info("Session ready")
        self._ready = True
        for handler in self._pending_handlers:
            self.NewStream(handler=handler)
        self._pending_handlers = []

    def Error(self, code, message):
        logger.error("Session received error %i: %s" % (code, message))

    def GetStream(self, id):
        return self._stream_handlers[id]

    def FindStream(self, stream):
        for handler in self.ListStreams():
            if handler.stream.name == stream.name:
                return handler
        return None

    def HasStreams(self):
        return bool(self._stream_handlers)

    def ListStreams(self):
        return self._stream_handlers.values()

    def CreateStream(self, stream_type, direction):
        name = StreamNames[stream_type]
        stream = self._session.create_stream(name, direction, True)
        handler = self.HandleStream(stream)
        self._session.add_stream(stream)
        return handler

    def HandleStream(self, stream):
        handler = ButterflyStreamHandler(self._conn, self, stream)
        logger.info("Added stream handler %i" % handler.id)
        self._stream_handlers[handler.id] = handler
        return handler

    def NewStream(self, stream=None, handler=None):
        if handler is None and stream is None:
            logger.error("A stream or a handler must be given to NewStream")
            return
        if handler is None:
            handler = self.FindStream(stream)
        if not self._ready:
            self._pending_handlers.append(handler)
            return handler
        logger.info("New stream handler %i" % handler.id)
        path = self.get_stream_path(handler.id)
        self.NewStreamHandler(path, handler.id, handler.type, handler.direction)
        return handler

    def RemoveStream(self, id):
        logger.info("Removed stream handler %i" % id)
        if id in self._stream_handlers:
            handler = self._stream_handlers[id]
            handler.remove_from_connection()
            del self._stream_handlers[id]
