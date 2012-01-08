import dbus.glib
import gobject
import logging
import sys

from time import sleep

from account import connection_from_file

from telepathy.client.channel import Channel
from telepathy.constants import (
    CONNECTION_HANDLE_TYPE_NONE as HANDLE_TYPE_NONE,
    CONNECTION_HANDLE_TYPE_ROOM as HANDLE_TYPE_ROOM,
    CONNECTION_STATUS_CONNECTED,
    CHANNEL_TEXT_MESSAGE_TYPE_NORMAL)
from telepathy.interfaces import CHANNEL_TYPE_ROOM_LIST, CONN_INTERFACE

logging.basicConfig()

class RoomListExample:
    def __init__(self, conn):
        self.conn = conn

        conn[CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)

    def run(self):
        print "main loop running"
        self.loop = gobject.MainLoop()
        self.loop.run()

    def quit(self):
        if self.loop:
            self.loop.quit()
            self.loop = None

    def status_changed_cb(self, state, reason):
        if state != CONNECTION_STATUS_CONNECTED:
            return
        print "connection became ready, requesting channel"

        try:
            channel = conn.request_channel(
                CHANNEL_TYPE_ROOM_LIST, HANDLE_TYPE_NONE, 0, True)
        except Exception, e:
            print e
            self.quit()
            return

        print "Connecting to ListingRooms"
        channel[CHANNEL_TYPE_ROOM_LIST].connect_to_signal('ListingRooms',
                                                         self.listing_cb)
        print "Connecting to GotRooms"
        channel[CHANNEL_TYPE_ROOM_LIST].connect_to_signal('GotRooms',
                                                         self.rooms_cb)
        print "Calling ListRooms"
        channel[CHANNEL_TYPE_ROOM_LIST].ListRooms()

    def listing_cb(self, listing):
        if listing:
            print "Listing rooms..."
        else:
            print "Finished listing rooms"
            self.quit()

    def rooms_cb(self, rooms):
        handles = [room[0] for room in rooms]
        names = self.conn[CONN_INTERFACE].InspectHandles(HANDLE_TYPE_ROOM,
                                                         handles)

        for i in xrange(len(rooms)):
            handle, ctype, info = rooms[i]
            name = names[i]
            print "Found room:", name
            print "\t", ctype
            for key in info:
                print "\t", repr(str(key)), " => ", repr(info[key])

if __name__ == '__main__':
    conn = connection_from_file(sys.argv[1])

    ex = RoomListExample(conn)

    print "connecting"
    conn[CONN_INTERFACE].Connect()

    try:
        ex.run()
    except KeyboardInterrupt:
        print "killed"

    print "disconnecting"
    conn[CONN_INTERFACE].Disconnect()
