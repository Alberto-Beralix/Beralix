
import dbus
import dbus.glib
import gobject
import sys

from account import connection_from_file

from telepathy.client.channel import Channel
from telepathy.constants import (
    CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_HANDLE_TYPE_LIST,
    CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_DISCONNECTED)
from telepathy.errors import NotAvailable
from telepathy.interfaces import (
    CHANNEL_INTERFACE_GROUP, CHANNEL_TYPE_CONTACT_LIST, CONN_INTERFACE)

def print_members(conn, chan):
    current, local_pending, remote_pending = (
        chan[CHANNEL_INTERFACE_GROUP].GetAllMembers())

    for member in current:
        print ' - %s' % (
            conn[CONN_INTERFACE].InspectHandles(
                CONNECTION_HANDLE_TYPE_CONTACT, [member])[0])

    if not current:
        print ' (none)'

class RosterClient:
    def __init__(self, conn):
        self.conn = conn

        conn[CONN_INTERFACE].connect_to_signal(
            'StatusChanged', self.status_changed_cb)

    def _request_list_channel(self, name):
        handle = self.conn[CONN_INTERFACE].RequestHandles(
            CONNECTION_HANDLE_TYPE_LIST, [name])[0]
        return self.conn.request_channel(
            CHANNEL_TYPE_CONTACT_LIST, CONNECTION_HANDLE_TYPE_LIST,
            handle, True)

    def status_changed_cb(self, state, reason):
        if state == CONNECTION_STATUS_DISCONNECTED:
            print 'disconnected: %s' % reason
            self.quit()
            return

        if state != CONNECTION_STATUS_CONNECTED:
            return

        print 'connected'

        for name in ('subscribe', 'publish', 'hide', 'allow', 'deny', 'known'):
            try:
                chan = self._request_list_channel(name)
            except dbus.DBusException:
                print "'%s' channel is not available" % name
                continue

            print '%s: members' % name
            print_members(self.conn, chan)

            chan[CHANNEL_INTERFACE_GROUP].connect_to_signal('MembersChanged',
                lambda *args: self.members_changed_cb(name, *args))

        print 'waiting for changes'

    def members_changed_cb(self, name, message, added, removed, local_pending,
            remote_pending, actor, reason):
        if added:
            for handle in added:
                print '%s: added: %d' % (name, added)

        if removed:
            for handle in removed:
                print '%s: removed: %d' % (name, added)

    def run(self):
        self.loop = gobject.MainLoop()

        try:
            self.loop.run()
        except KeyboardInterrupt:
            print 'interrupted'

    def quit(self):
        self.loop.quit()

if __name__ == '__main__':
    assert len(sys.argv) == 2
    conn = connection_from_file(sys.argv[1])
    client = RosterClient(conn)

    print "connecting"
    conn[CONN_INTERFACE].Connect()
    client.run()
    print "disconnecting"

    try:
        conn[CONN_INTERFACE].Disconnect()
    except dbus.DBusException:
        pass

