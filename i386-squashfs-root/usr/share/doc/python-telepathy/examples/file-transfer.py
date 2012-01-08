import dbus.glib
import sys
import dbus
import gobject
import socket
import os
import sys
import fcntl
import time

from dbus import PROPERTIES_IFACE
from telepathy.client import (Connection, Channel)
from telepathy.interfaces import (CONN_INTERFACE,
    CONNECTION_INTERFACE_REQUESTS,
    CONNECTION_INTERFACE_CONTACT_CAPABILITIES,
    CHANNEL, CHANNEL_INTERFACE, CHANNEL_TYPE_FILE_TRANSFER,
    CLIENT)
from telepathy.constants import (CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_STATUS_CONNECTING,
    CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_DISCONNECTED, SOCKET_ADDRESS_TYPE_UNIX,
    SOCKET_ACCESS_CONTROL_LOCALHOST, FILE_TRANSFER_STATE_NONE, FILE_TRANSFER_STATE_PENDING, FILE_TRANSFER_STATE_ACCEPTED,
    FILE_TRANSFER_STATE_OPEN, FILE_TRANSFER_STATE_COMPLETED, FILE_TRANSFER_STATE_CANCELLED)

from account import connection_from_file

loop = None


ft_states = ['none', 'pending', 'accepted', 'open', 'completed', 'cancelled']

class FTClient(object):
    def __init__(self, account_file):
        self.conn = connection_from_file(account_file, ready_handler=self.ready_cb)

        self.conn[CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)

    def run(self):
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
        print "ready"
        self.conn[CONNECTION_INTERFACE_REQUESTS].connect_to_signal('NewChannels',
            self.new_channels_cb)

        self.self_handle = self.conn[CONN_INTERFACE].GetSelfHandle()
        self.self_id = self.conn[CONN_INTERFACE].InspectHandles(CONNECTION_HANDLE_TYPE_CONTACT,
            [self.self_handle])[0]
        print "I am %s" % self.self_id

        try:
            self.conn[CONNECTION_INTERFACE_CONTACT_CAPABILITIES].UpdateCapabilities([
                (CLIENT + ".FtExample", [
                    { CHANNEL_INTERFACE + ".ChannelType":
                        CHANNEL_TYPE_FILE_TRANSFER,
                      CHANNEL_INTERFACE + ".TargetHandleType":
                        CONNECTION_HANDLE_TYPE_CONTACT },
                ], [ ]),
            ])
        except:
            pass


        if not self.is_ft_present():
            print "FileTransfer is not implemented on this ConnectionManager"
            sys.exit(1)

    def is_ft_present(self):
        # check if we can request FT channels
        properties = self.conn[PROPERTIES_IFACE].GetAll(CONNECTION_INTERFACE_REQUESTS)
        classes =  properties['RequestableChannelClasses']
        for fixed_prop, allowed_prop in classes:
            if fixed_prop[CHANNEL + '.ChannelType'] == CHANNEL_TYPE_FILE_TRANSFER:
                return True

        return False

    def new_channels_cb(self, channels):
        for path, props in channels:
            if props[CHANNEL + '.ChannelType'] == CHANNEL_TYPE_FILE_TRANSFER:
                print "new FileTransfer channel"
                self.ft_channel = Channel(self.conn.service_name, path)

                self.ft_channel[CHANNEL_TYPE_FILE_TRANSFER].connect_to_signal('FileTransferStateChanged',
                        self.ft_state_changed_cb)
                self.ft_channel[CHANNEL_TYPE_FILE_TRANSFER].connect_to_signal('TransferredBytesChanged',
                        self.ft_transferred_bytes_changed_cb)
                self.ft_channel[CHANNEL_TYPE_FILE_TRANSFER].connect_to_signal('InitialOffsetDefined',
                        self.ft_initial_offset_defined_cb)
                self.got_ft_channel()

                self.file_name = props[CHANNEL_TYPE_FILE_TRANSFER + '.Filename']
                self.file_size = props[CHANNEL_TYPE_FILE_TRANSFER + '.Size']

    def ft_state_changed_cb(self, state, reason):
        print "file transfer is now in state %s" % ft_states[state]

    def ft_transferred_bytes_changed_cb(self, count):
        per_cent = (float(count) / self.file_size) * 100
        print "%.u%s transferred" % (per_cent, '%')

    def ft_initial_offset_defined_cb(self, offset):
        self.initial_offset = offset

class FTReceiverClient(FTClient):
    def ready_cb(self, conn):
        FTClient.ready_cb(self, conn)

        print "waiting for file transfer offer"

    def got_ft_channel(self):
        print "accept FT"
        self.sock_addr = self.ft_channel[CHANNEL_TYPE_FILE_TRANSFER].AcceptFile(
            SOCKET_ADDRESS_TYPE_UNIX, SOCKET_ACCESS_CONTROL_LOCALHOST, "", 0,
            byte_arrays=True)

    def ft_state_changed_cb(self, state, reason):
        FTClient.ft_state_changed_cb(self, state, reason)

        if state == FILE_TRANSFER_STATE_OPEN:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.sock_addr)

            path = self.create_output_path()
            if self.initial_offset == 0:
                out = file(path, 'w')
            else:
                out = file(path, 'a')

            # Set non-blocking
            fcntl.fcntl(out, fcntl.F_SETFL, os.O_NONBLOCK)

            read = self.initial_offset
            while read < self.file_size:
                data = s.recv(self.file_size - read)
                read += len(data)
                out.write(data)

            out.close()
            print "received file: %s" % path

    def create_output_path(self):
        for i in range(30):
            if i == 0:
                name = self.file_name
            else:
                name = "%s.%d" % (self.file_name, i)

            path = os.path.join('/tmp', name)
            if not os.path.exists(path):
                return path

class FTSenderClient(FTClient):
    def __init__(self, account_file, contact, filename):
        FTClient.__init__(self, account_file)

        self.contact = contact
        self.file_to_offer = filename

    def ready_cb(self, conn):
        FTClient.ready_cb(self, conn)

        # Wait a bit so the other side is aware about us. If he's not,
        # he'll automatically reject the XMPP connection.
        time.sleep(3)

        handle = self.conn.RequestHandles(CONNECTION_HANDLE_TYPE_CONTACT, [self.contact])[0]

        file_name = os.path.basename(self.file_to_offer)
        info = os.stat(self.file_to_offer)
        size = info.st_size

        # Request FT channel
        self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
            CHANNEL + '.ChannelType': CHANNEL_TYPE_FILE_TRANSFER,
            CHANNEL + '.TargetHandleType': CONNECTION_HANDLE_TYPE_CONTACT,
            CHANNEL + '.TargetHandle': handle,
            CHANNEL_TYPE_FILE_TRANSFER + '.ContentType': 'application/octet-stream',
            CHANNEL_TYPE_FILE_TRANSFER + '.Filename': file_name,
            CHANNEL_TYPE_FILE_TRANSFER + '.Size': size,
            CHANNEL_TYPE_FILE_TRANSFER + '.Description': "I'm testing file transfer using Telepathy",
            CHANNEL_TYPE_FILE_TRANSFER + '.InitialOffset': 0})

    def got_ft_channel(self):
        print "Offer %s to %s" % (self.file_to_offer, self.contact)
        self.sock_addr = self.ft_channel[CHANNEL_TYPE_FILE_TRANSFER].ProvideFile(SOCKET_ADDRESS_TYPE_UNIX,
            SOCKET_ACCESS_CONTROL_LOCALHOST, "", byte_arrays=True)

    def ft_state_changed_cb(self, state, reason):
        FTClient.ft_state_changed_cb(self, state, reason)

        if state == FILE_TRANSFER_STATE_OPEN:
            # receive file
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.sock_addr)

            f = file(self.file_to_offer, 'r')
            f.seek(self.initial_offset)

            fcntl.fcntl(f, fcntl.F_SETFL, os.O_NONBLOCK)
            s.send(f.read())
            f.close()

def usage():
    print "Usage:\n" \
            "Send [file] to [contact]:\n" \
            "\tpython %s [account-file] [contact] [file]\n" \
            "Accept a file transfer from a contact:\n" \
            "\tpython %s [account-file]\n" \
            % (sys.argv[0], sys.argv[0])

if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args) == 3:
        account_file = args[0]
        contact = args[1]
        filename = args[2]
        client = FTSenderClient(account_file, contact, filename)
    elif len(args) == 1:
        account_file = args[0]
        client = FTReceiverClient(account_file)
    else:
        usage()
        sys.exit(0)

    client.run()
