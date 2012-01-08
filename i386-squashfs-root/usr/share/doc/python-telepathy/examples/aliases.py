
"""
Print out the aliases of all contacts on the known list.
"""

import dbus.glib
import gobject
import sys

from account import connection_from_file

from telepathy.client import Channel
from telepathy.constants import (
    CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_HANDLE_TYPE_LIST,
    CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_DISCONNECTED)
from telepathy.interfaces import (
    CHANNEL_INTERFACE_GROUP, CHANNEL_TYPE_CONTACT_LIST, CONN_INTERFACE,
    CONN_INTERFACE_ALIASING)

class AliasesClient:
    def __init__(self, account_file):
        self.conn = connection_from_file(account_file,
            ready_handler=self.ready_cb)

        self.conn[CONN_INTERFACE].connect_to_signal(
            'StatusChanged', self.status_changed_cb)

    def _request_list_channel(self, name):
        handle = self.conn[CONN_INTERFACE].RequestHandles(
            CONNECTION_HANDLE_TYPE_LIST, [name])[0]
        chan_path = self.conn[CONN_INTERFACE].RequestChannel(
            CHANNEL_TYPE_CONTACT_LIST, CONNECTION_HANDLE_TYPE_LIST,
            handle, True)
        channel = Channel(self.conn.service_name, chan_path)
        return channel

    def status_changed_cb(self, state, reason):
        if state == CONNECTION_STATUS_DISCONNECTED:
            print 'disconnected: %s' % reason
            self.quit()
            return

    def ready_cb(self, conn):
        print 'connected and ready'

        known_channel = self._request_list_channel('known')
        current, local_pending, remote_pending = (
            known_channel[CHANNEL_INTERFACE_GROUP].GetAllMembers())
        names = conn[CONN_INTERFACE].InspectHandles(
                CONNECTION_HANDLE_TYPE_CONTACT, current)
        aliases = conn[CONN_INTERFACE_ALIASING].RequestAliases(current)

        for handle, name, alias in zip(current, names, aliases):
            print ' % 3d: %s (%s)' % (handle, alias, name)

        self.quit()

    def members_changed_cb(self, name, message, added, removed, local_pending,
            remote_pending, actor, reason):
        if added:
            for handle in added:
                print '%s: added: %d' % (name, added)

        if removed:
            for handle in removed:
                print '%s: removed: %d' % (name, added)

    def run(self):
        print "connecting"
        self.conn[CONN_INTERFACE].Connect()

        self.loop = gobject.MainLoop()

        try:
            self.loop.run()
        except KeyboardInterrupt:
            print 'interrupted'

        print "disconnecting"
        try:
            self.conn[CONN_INTERFACE].Disconnect()
        except dbus.DBusException:
            pass


    def quit(self):
        self.loop.quit()

if __name__ == '__main__':
    assert len(sys.argv) == 2
    client = AliasesClient(sys.argv[1])
    client.run()
