
"""
Example Telepathy chatroom client.
"""

import sys

import dbus.glib
import gobject

import telepathy

from account import connection_from_file

class ChatroomClient:
    def __init__(self, conn, chatroom):
        self.conn = conn
        self.chatroom = chatroom

        conn[telepathy.CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)

    def status_changed_cb(self, status, reason):
        if status == telepathy.CONNECTION_STATUS_CONNECTED:
            room_handle = self.conn[telepathy.CONN_INTERFACE].RequestHandles(
                telepathy.HANDLE_TYPE_ROOM, [self.chatroom])[0]
            channel = self.conn.request_channel(telepathy.CHANNEL_TYPE_TEXT,
                telepathy.HANDLE_TYPE_ROOM, room_handle, True)
            channel[telepathy.CHANNEL_TYPE_TEXT].connect_to_signal(
                'Received', self.received_cb)
            gobject.io_add_watch(sys.stdin, gobject.IO_IN, self.stdin_cb)

            self.channel = channel

    def received_cb(self, id, timestamp, sender, type, flags, text):
        self.channel[telepathy.CHANNEL_TYPE_TEXT].AcknowledgePendingMessages(
            [id])
        contact = self.conn[telepathy.CONN_INTERFACE].InspectHandles(
            telepathy.HANDLE_TYPE_CONTACT, [sender])[0]
        print '<%s> %s' % (contact, text)

    def stdin_cb(self, fd, condition):
        text = fd.readline()[:-1]
        self.channel[telepathy.CHANNEL_TYPE_TEXT].Send(
            telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL, text)
        return True

if __name__ == '__main__':
    account_file, chatroom = sys.argv[1], sys.argv[2]
    conn = connection_from_file(account_file)
    client = ChatroomClient(conn, chatroom)
    conn[telepathy.CONN_INTERFACE].Connect()
    loop = gobject.MainLoop()

    try:
        loop.run()
    except KeyboardInterrupt:
        print 'interrupted'

    print 'disconnecting'

    try:
        conn[telepathy.CONN_INTERFACE].Disconnect()
    except dbus.DBusException:
        pass

