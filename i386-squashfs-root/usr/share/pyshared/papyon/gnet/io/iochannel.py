# -*- coding: utf-8 -*-
#
# Copyright (C) 2005  Ole André Vadla Ravnås <oleavr@gmail.com>
# Copyright (C) 2006-2007  Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2007  Johann Prieur <johann.prieur@gmail.com>
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
from papyon.gnet.constants import *
from papyon.gnet.errors import *
from papyon.gnet.resolver import *
from papyon.util.async import run
from abstract import AbstractClient

import gobject
import socket
from errno import *

__all__ = ['GIOChannelClient']

class OutgoingPacket(object):
    """Represents a packet to be sent over the IO channel"""
    def __init__(self, buffer, size, callback=None, errback=None):
        self.buffer = buffer
        self.size = size
        self._sent = 0
        self._callback = callback
        self._errback = errback

    def read(self, size=2048):
        if size is not None:
            return self.buffer[self._sent:][0:size]
        return self.buffer[self._sent:]

    def sent(self, size):
        """update how many bytes have been sent"""
        self._sent += size

    def is_complete(self):
        """return whether this packet was completely transmitted or not"""
        return self.size == self._sent

    def callback(self):
        """Run the callback function if supplied"""
        run(self._callback)

    def errback(self, error):
        """Run the errback function if supplied"""
        run(self._errback, error)


class GIOChannelClient(AbstractClient):
    """Base class for clients using GIOChannel facilities

        @sort: __init__, open, send, close
        @undocumented: do_*, _configure, _pre_open, _post_open

        @since: 0.1"""

    def __init__(self, host, port, domain=AF_INET, type=SOCK_STREAM):
        AbstractClient.__init__(self, host, port, domain, type)

    def _pre_open(self, io_object):
        io_object.setblocking(False)
        channel = gobject.IOChannel(io_object.fileno())
        channel.set_flags(channel.get_flags() | gobject.IO_FLAG_NONBLOCK)
        channel.set_encoding(None)
        channel.set_buffered(False)

        self._transport = io_object
        self._channel = channel

        self._source_id = None
        self._source_condition = 0
        self._outgoing_queue = []
        AbstractClient._pre_open(self)

    def _post_open(self):
        AbstractClient._post_open(self)
        self._watch_remove()

    def _open(self, host, port):
        resolver = HostnameResolver()
        resolver.query(host, (self.__open, host, port), (self.__open_failed,))

    def __open(self, resolve_response, host, port):
        host = resolve_response.answer[0][1]

        # Even though connect_ex *shouldn't* raise an exception,
        # sometimes it does, which is just great.
        try:
            err = self._transport.connect_ex((host, port))
        except socket.error, e:
            err = e.errno

        self._watch_set_cond(gobject.IO_PRI | gobject.IO_IN | gobject.IO_OUT |
                gobject.IO_HUP | gobject.IO_ERR | gobject.IO_NVAL,
                lambda chan, cond: self._post_open())
        if err in (0, EINPROGRESS, EALREADY, EWOULDBLOCK, EISCONN):
            return
        elif err in (EHOSTUNREACH, EHOSTDOWN, ECONNREFUSED, ECONNABORTED,
                ENETUNREACH, ENETDOWN, EBADFD):
            self.emit("error", IoConnectionFailed(self, str(err)))
            self._transport.close()

    def __open_failed(self, error):
        self.emit("error", error)
        self._transport.close()

    # convenience methods
    def _watch_remove(self):
        if self._source_id is not None:
            gobject.source_remove(self._source_id)
            self._source_id = None
            self._source_condition = 0

    def _watch_set_cond(self, cond, handler=None):
        self._watch_remove()
        self._source_condition = cond
        if handler is None:
            handler = self._io_channel_handler
        self._source_id = self._channel.add_watch(cond, handler)

    def _watch_add_cond(self, cond):
        if self._source_condition & cond == cond:
            return
        self._source_condition |= cond
        self._watch_set_cond(self._source_condition)

    def _watch_remove_cond(self, cond):
        if self._source_condition & cond == 0:
            return
        self._source_condition ^= cond
        self._watch_set_cond(self._source_condition)

    # public API
    def open(self):
        if not self._configure():
            return
        self._pre_open()
        self._open(self._host, self._port)

    def close(self):
        if self._status in (IoStatus.CLOSING, IoStatus.CLOSED):
            return
        self._status = IoStatus.CLOSING

        for packet in self._outgoing_queue:
            packet.errback(IoConnectionClosed(self, self._status))
        self._outgoing_queue = []

        self._watch_remove()
        try:
            self._channel.close()
            self._transport.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self._transport.close()
        self._status = IoStatus.CLOSED

    def disable(self):
        # Disable the channel without actually closing the socket
        # Rationnale: some other client might have the ownership of the socket
        if self._status in (IoStatus.CLOSING, IoStatus.CLOSED):
            return
        self._watch_remove()

    def send(self, buffer, callback=None, errback=None):
        if self._status != IoStatus.OPEN:
            run(errback, IoConnectionClosed(self, self._status))
            return
        self._outgoing_queue.append(OutgoingPacket(buffer, len(buffer),
            callback, errback))
        self._watch_add_cond(gobject.IO_OUT)
gobject.type_register(GIOChannelClient)
