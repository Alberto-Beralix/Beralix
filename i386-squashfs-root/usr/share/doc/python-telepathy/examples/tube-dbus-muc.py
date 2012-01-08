
import dbus.glib
import gobject
import sys
import time
from dbus.service import method, signal, Object
from dbus import  PROPERTIES_IFACE

from telepathy.client import Channel
from telepathy.interfaces import (
        CONN_INTERFACE, CHANNEL_INTERFACE_GROUP,
        CHANNEL_TYPE_TEXT, CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS,
        CHANNEL_INTERFACE_TUBE, CHANNEL_TYPE_DBUS_TUBE)
from telepathy.constants import (
        CONNECTION_HANDLE_TYPE_CONTACT,
        CONNECTION_HANDLE_TYPE_ROOM, CONNECTION_STATUS_CONNECTED,
        CONNECTION_STATUS_DISCONNECTED, CONNECTION_STATUS_CONNECTING,
        SOCKET_ACCESS_CONTROL_CREDENTIALS,
        TUBE_CHANNEL_STATE_LOCAL_PENDING, TUBE_CHANNEL_STATE_REMOTE_PENDING,
        TUBE_CHANNEL_STATE_OPEN, TUBE_CHANNEL_STATE_NOT_OFFERED)

from account import connection_from_file
from tubeconn import TubeConnection

SERVICE = "org.freedesktop.Telepathy.Tube.Test"
IFACE = SERVICE
PATH = "/org/freedesktop/Telepathy/Tube/Test"


tube_state = {TUBE_CHANNEL_STATE_LOCAL_PENDING : 'local pending',\
              TUBE_CHANNEL_STATE_REMOTE_PENDING : 'remote pending',\
              TUBE_CHANNEL_STATE_OPEN : 'open',
              TUBE_CHANNEL_STATE_NOT_OFFERED: 'not offered'}

loop = None

class Client:
    def __init__(self, account_file, muc_id):
        self.conn = connection_from_file(account_file, ready_handler=self.ready_cb)
        self.muc_id = muc_id

        self.conn[CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)

        self.test = None
        self.joined = False
        self.tube = None

    def run(self):
        global loop

        self.conn[CONN_INTERFACE].Connect()

        loop = gobject.MainLoop()
        try:
            loop.run()
        finally:
            try:
                self.conn[CONN_INTERFACE].Disconnect()
            except:
                pass

    def status_changed_cb(self, state, reason):
        if state == CONNECTION_STATUS_CONNECTING:
            print 'connecting'
        elif state == CONNECTION_STATUS_CONNECTED:
            print 'connected'
        elif state == CONNECTION_STATUS_DISCONNECTED:
            print 'disconnected'
            loop.quit()

    def ready_cb(self, conn):
        self.conn[CONNECTION_INTERFACE_REQUESTS].connect_to_signal ("NewChannels",
                self.new_channels_cb)

        self.self_handle = self.conn[CONN_INTERFACE].GetSelfHandle()

    def join_muc(self):
        # workaround to be sure that the muc service is fully resolved in
        # Salut.
        time.sleep(2)

        print "join muc", self.muc_id
        chan_path, props = self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
            CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_TEXT,
            CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
            CHANNEL_INTERFACE + ".TargetID": self.muc_id})

        self.channel_text = Channel(self.conn.dbus_proxy.bus_name, chan_path)

        self.self_handle = self.channel_text[CHANNEL_INTERFACE_GROUP].GetSelfHandle()
        self.channel_text[CHANNEL_INTERFACE_GROUP].connect_to_signal(
                "MembersChanged", self.text_channel_members_changed_cb)

        if self.self_handle in self.channel_text[CHANNEL_INTERFACE_GROUP].GetMembers():
            self.joined = True
            self.muc_joined()

    def new_channels_cb(self, channels):
        if self.tube is not None:
            return

        for path, props in channels:
            if props[CHANNEL_INTERFACE + ".ChannelType"] == CHANNEL_TYPE_DBUS_TUBE:
                self.tube = Channel(self.conn.dbus_proxy.bus_name, path)

                self.tube[CHANNEL_INTERFACE_TUBE].connect_to_signal(
                        "TubeChannelStateChanged", self.tube_channel_state_changed_cb)
                self.tube[CHANNEL_INTERFACE].connect_to_signal(
                        "Closed", self.tube_closed_cb)

                self.got_tube(props)

    def got_tube(self, props):
        initiator_id = props[CHANNEL_INTERFACE + ".InitiatorID"]
        service = props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]

        state = self.tube[PROPERTIES_IFACE].Get(CHANNEL_INTERFACE_TUBE, 'State')

        print "new D-Bus tube offered by %s. Service: %s. State: %s" % (
            initiator_id, service, tube_state[state])

    def tube_opened (self):
        group_iface = self.channel_text[CHANNEL_INTERFACE_GROUP]

        tube_conn = TubeConnection(self.conn, self.tube, self.tube_addr,
                group_iface=group_iface)

        self.test = Test(tube_conn, self.conn)

    def tube_channel_state_changed_cb(self, state):
        print "tube state changed:", tube_state[state]
        if state == TUBE_CHANNEL_STATE_OPEN:
            self.tube_opened()

    def tube_closed_cb(self):
        print "tube closed", id

    def text_channel_members_changed_cb(self, message, added, removed,
            local_pending, remote_pending, actor, reason):
        if self.self_handle in added and not self.joined:
            self.joined = True
            self.muc_joined()

    def muc_joined(self):
        pass

class InitiatorClient(Client):
    def __init__(self, account_file, muc_id):
        Client.__init__(self, account_file, muc_id)

    def ready_cb(self, conn):
        Client.ready_cb(self, conn)

        self.join_muc()

    def muc_joined(self):
        Client.muc_joined(self)

        print "muc joined. Create the tube"

        self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
            CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_DBUS_TUBE,
            CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
            CHANNEL_INTERFACE + ".TargetID": self.muc_id,
            CHANNEL_TYPE_DBUS_TUBE + ".ServiceName": SERVICE})

    def got_tube(self, props):
        Client.got_tube(self, props)

        params = dbus.Dictionary({"login": "badger", "a_int" : 69},
                signature='sv')

        print "Offer tube"
        self.tube_addr = self.tube[CHANNEL_TYPE_DBUS_TUBE].Offer(params,
            SOCKET_ACCESS_CONTROL_CREDENTIALS)

    def tube_opened (self):
        Client.tube_opened(self)

        self._emit_test_signal();
        gobject.timeout_add (20000, self._emit_test_signal)

    def _emit_test_signal (self):
        print "emit Hello"
        self.test.Hello()
        return True

class JoinerClient(Client):
    def __init__(self, account_file, muc_id):
        Client.__init__(self, account_file, muc_id)

    def ready_cb(self, conn):
        Client.ready_cb(self, conn)

        self.join_muc()

    def got_tube(self, props):
        Client.got_tube(self, props)

        print "Accept tube"
        self.tube_addr = self.tube[CHANNEL_TYPE_DBUS_TUBE].Accept(SOCKET_ACCESS_CONTROL_CREDENTIALS)


    def tube_opened (self):
        Client.tube_opened(self)

        self.test.tube.add_signal_receiver(self.hello_cb, 'Hello', IFACE,
            path=PATH, sender_keyword='sender')

    def hello_cb (self, sender=None):
        sender_handle = self.test.tube.bus_name_to_handle[sender]
        sender_id = self.conn[CONN_INTERFACE].InspectHandles(
                CONNECTION_HANDLE_TYPE_CONTACT, [sender_handle])[0]
        self_id = self.conn[CONN_INTERFACE].InspectHandles(
                CONNECTION_HANDLE_TYPE_CONTACT, [self.self_handle])[0]

        print "Hello from %s" % sender

        text = "I'm %s and thank you for your hello" % self_id
        self.test.tube.get_object(sender, PATH).Say(text, dbus_interface=IFACE)

class Test(Object):
    def __init__(self, tube, conn):
        super(Test, self).__init__(tube, PATH)
        self.tube = tube
        self.conn = conn

    @signal(dbus_interface=IFACE, signature='')
    def Hello(self):
        pass

    @method(dbus_interface=IFACE, in_signature='s', out_signature='b')
    def Say(self, text):
        print "I say: %s" % text
        return True

def usage():
    print "python %s [account-file] [muc]\n" \
            "python %s [account-file] [muc] --initiator"\
            % (sys.argv[0], sys.argv[0])

if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args) == 2:
        client = JoinerClient(args[0], args[1])
    elif len(args) == 3 and args[2] == '--initiator':
        client = InitiatorClient(args[0], args[1])
    else:
        usage()
        sys.exit(0)

    client.run()
