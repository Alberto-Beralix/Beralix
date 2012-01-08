# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2010 Collabora Ltd.
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
import time
import tempfile
import os
import shutil

import dbus
import gobject
import telepathy
import papyon
import papyon.event
import socket

from butterfly.util.decorator import async

from telepathy.interfaces import CHANNEL_TYPE_FILE_TRANSFER

__all__ = ['ButterflyFileTransferChannel']

logger = logging.getLogger('Butterfly.FileTransferChannel')


class ButterflyFileTransferChannel(telepathy.server.ChannelTypeFileTransfer):

    def __init__(self, conn, manager, session, handle, props, object_path=None):
        telepathy.server.ChannelTypeFileTransfer.__init__(self, conn, manager, props,
            object_path=object_path)

        self._handle = handle
        self._conn_ref = weakref.ref(conn)
        self._state = 0
        self._transferred = 0

        self._receiving = not props[telepathy.CHANNEL + '.Requested']
        self.socket = None
        self._tmpdir = None

        self._last_ltb_emitted = 0
        self._progress_timer = 0

        # Incoming.
        if session is None:
            type = telepathy.CHANNEL_TYPE_FILE_TRANSFER
            filename = props.get(type + ".Filename", None)
            size = props.get(type + ".Size", None)

            if filename is None or size is None:
                raise telepathy.InvalidArgument(
                    "New file transfer channel requires Filename and Size properties")

            client = conn.msn_client
            session = client.ft_manager.send(handle.contact, filename, size)

        self._session = session
        self._filename = session.filename
        self._size = session.size

        handles = []
        handles.append(session.connect("accepted", self._transfer_accepted))
        handles.append(session.connect("rejected", self._transfer_rejected))
        handles.append(session.connect("canceled", self._transfer_canceled))
        handles.append(session.connect("progressed", self._transfer_progressed))
        handles.append(session.connect("completed", self._transfer_completed))
        handles.append(session.connect("disposed", self._transfer_disposed))
        self._handles = handles

        self._sources = []

        dbus_interface = telepathy.CHANNEL_TYPE_FILE_TRANSFER
        self._implement_property_get(dbus_interface, {
                'State' : lambda: dbus.UInt32(self.state),
                'ContentType': lambda: self.content_type,
                'Filename': lambda: self.filename,
                'Size': lambda: dbus.UInt64(self.size),
                'Description': lambda: self.description,
                'AvailableSocketTypes': lambda: self.socket_types,
                'TransferredBytes': lambda: self.transferred,
                'InitialOffset': lambda: self.offset
                })

        self._add_immutables({
                'Filename': CHANNEL_TYPE_FILE_TRANSFER,
                'Size': CHANNEL_TYPE_FILE_TRANSFER,
                })

        self.set_state(telepathy.FILE_TRANSFER_STATE_PENDING,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_REQUESTED)

    @property
    def state(self):
        return self._state

    @property
    def content_type(self):
        return "application/octet-stream"

    @property
    def filename(self):
        return self._filename

    @property
    def size(self):
        return self._size

    @property
    def description(self):
        return ""

    @property
    def socket_types(self):
        return {telepathy.SOCKET_ADDRESS_TYPE_UNIX:
                [telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST,
                 telepathy.SOCKET_ACCESS_CONTROL_CREDENTIALS]}

    @property
    def transferred(self):
        return self._transferred

    @property
    def offset(self):
        return 0

    def set_state(self, state, reason):
        if self._state == state:
            return
        logger.debug("State change: %u -> %u (reason: %u)" % (self._state, state, reason))
        self._state = state
        self.FileTransferStateChanged(state, reason)

    def AcceptFile(self, address_type, access_control, param, offset):
        logger.debug("Accept file")

        if address_type not in self.socket_types.keys():
            raise telepathy.NotImplemented("Socket type %u is unsupported" % address_type)

        self.socket = self.add_listener()
        self.channel = self.add_io_channel(self.socket)
        self.set_state(telepathy.FILE_TRANSFER_STATE_PENDING,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_REQUESTED)
        self.InitialOffsetDefined(0)
        self.set_state(telepathy.FILE_TRANSFER_STATE_OPEN,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_NONE)
        return self.socket.getsockname()

    def ProvideFile(self, address_type, access_control, param):
        logger.debug("Provide file")

        if address_type not in self.socket_types.keys():
            raise telepathy.NotImplemented("Socket type %u is unsupported" % address_type)

        self.socket = self.add_listener()
        self.channel = self.add_io_channel(self.socket)
        return self.socket.getsockname()

    def Close(self):
        logger.debug("Close")

        try:
            self.cancel()
            if self.state != telepathy.FILE_TRANSFER_STATE_COMPLETED:
                self.set_state(telepathy.FILE_TRANSFER_STATE_CANCELLED,
                    telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_LOCAL_STOPPED)

            self.cleanup()
        except:
            pass

        telepathy.server.ChannelTypeFileTransfer.Close(self)

    def cancel(self):
        if self._receiving and self.state == telepathy.FILE_TRANSFER_STATE_PENDING:
            self._session.reject()
        elif self.state not in (telepathy.FILE_TRANSFER_STATE_CANCELLED,
                              telepathy.FILE_TRANSFER_STATE_COMPLETED):
            self._session.cancel()

    def cleanup(self):
        if self.socket:
            self.socket.close()
            self.socket = None

        if self._tmpdir:
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

        for handle in self._handles:
            self._session.disconnect(handle)
        self._handles = []
        self._session = None

    def GetSelfHandle(self):
        return self._conn.GetSelfHandle()

    def add_listener(self):
        """Create a listener socket"""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self._tmpdir = tempfile.mkdtemp(prefix="butterfly")
        sock.bind(os.path.join(self._tmpdir, "ft-socket"))
        sock.listen(1)
        return sock

    def add_io_channel(self, sock):
        """Set up notification on the socket via a giochannel"""
        sock.setblocking(False)
        channel = gobject.IOChannel(sock.fileno())
        channel.set_flags(channel.get_flags() | gobject.IO_FLAG_NONBLOCK)
        self._sources.append(channel.add_watch(gobject.IO_IN,
            self._socket_connected))
        self._sources.append(channel.add_watch(gobject.IO_HUP | gobject.IO_ERR,
            self._socket_disconnected))
        return channel

    def _socket_connected(self, channel, condition):
        logger.debug("Client socket connected")
        sock = self.socket.accept()[0]
        for source in self._sources:
            gobject.source_remove(source)
        channel.close()
        if self._receiving:
            buffer = DataBuffer(sock)
            self._session.set_receive_data_buffer(buffer, self.size)
            # Notify the other end we accepted the FT
            self._session.accept()
        else:
            buffer = DataBuffer(sock, self.size)
            self._session.send(buffer)
        self.socket = sock

    def _socket_disconnected(self, channel, condition):
        logger.debug("Client socket disconnected")
        for source in self._sources:
            gobject.source_remove(source)
        channel.close()

        self.cancel()
        self.set_state(telepathy.FILE_TRANSFER_STATE_CANCELLED,
                       telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_LOCAL_ERROR)

    def _transfer_accepted(self, session):
        logger.debug("Transfer has been accepted")
        self.set_state(telepathy.FILE_TRANSFER_STATE_ACCEPTED,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_REQUESTED)
        self.set_state(telepathy.FILE_TRANSFER_STATE_OPEN,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_NONE)

    def _transfer_rejected(self, session):
        logger.debug("Transfer has been declined")
        self.set_state(telepathy.FILE_TRANSFER_STATE_CANCELLED,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_REMOTE_STOPPED)

    def _transfer_canceled(self, session):
        logger.debug("Transfer has been cancelled")
        self.set_state(telepathy.FILE_TRANSFER_STATE_CANCELLED,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_REMOTE_STOPPED)

    def _transfer_completed(self, session, data):
        logger.debug("Transfer completed")
        self.set_state(telepathy.FILE_TRANSFER_STATE_COMPLETED,
            telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_NONE)

    def _transfer_disposed(self, session):
        if self.state not in (telepathy.FILE_TRANSFER_STATE_CANCELLED,
                              telepathy.FILE_TRANSFER_STATE_COMPLETED):
            logger.debug("Transfer has been disposed before completion")
            self.set_state(telepathy.FILE_TRANSFER_STATE_CANCELLED,
                telepathy.FILE_TRANSFER_STATE_CHANGE_REASON_LOCAL_STOPPED)

    def _transfer_progressed(self, session, size):
        self._transferred += size

        def emit_signal():
            self.TransferredBytesChanged(self.transferred)
            self._last_ltb_emitted = time.time()
            self._progress_timer = 0
            return False

        # If the transfer has finished send an update right away.
        if self.transferred >= self.size:
            emit_signal()
            return

        # A progress update signal is already scheduled.
        if self._progress_timer != 0:
            return

        # Only emit the TransferredBytes signal if it has been one
        # second since its last emission.
        interval = time.time() - self._last_ltb_emitted
        if interval >= 1:
            emit_signal()
            return

        # Get it in microseconds.
        interval /= 1000

        # Protect against clock skew, if the interval is negative the
        # worst thing that can happen is that we wait an extra second
        # before emitting the signal.
        interval = int(abs(interval))

        if interval > 1000:
            emit_signal()
        else:
            self._progress_timer = gobject.timeout_add(1000 - interval,
                emit_signal)

class DataBuffer(object):

    def __init__(self, socket, size=0):
        self._socket = socket
        self._size = size
        self._offset = 0
        self._buffer = ""

    def seek(self, offset, position):
        if position == 0:
            self._offset = offset
        elif position == 2:
            self._offset = self._size

    def tell(self):
        return self._offset

    def read(self, max_size=None):
        if max_size is None:
            # we can't read all the data;
            # let's just return the last chunk
            return self._buffer
        max_size = min(max_size, self._size - self._offset)
        data = self._socket.recv(max_size)
        self._buffer = data
        self._offset += len(data)
        return data

    def write(self, data):
        self._buffer = data
        self._size += len(data)
        self._offset += len(data)
        self._socket.send(data)
