import sys
import dbus

from telepathy.constants import CONNECTION_HANDLE_TYPE_ROOM

from stream_tube_client import StreamTubeJoinerClient, \
        StreamTubeInitiatorClient

class StreamTubeInitiatorMucClient(StreamTubeInitiatorClient):
    def __init__(self, account_file, muc_id, socket_path=None):
        StreamTubeInitiatorClient.__init__(self, account_file, muc_id, None, socket_path)

    def ready_cb(self, conn):
        StreamTubeInitiatorClient.ready_cb(self, conn)

        self.join_muc()

    def muc_joined(self):
        StreamTubeInitiatorClient.muc_joined(self)

        print "muc joined. Create the tube"
        self.create_tube(CONNECTION_HANDLE_TYPE_ROOM, self.muc_id)

class StreamTubeJoinerMucClient(StreamTubeJoinerClient):
    def __init__(self, account_file, muc_id, connect_trivial_client):
        StreamTubeJoinerClient.__init__(self, account_file, muc_id, None,
                connect_trivial_client)

    def ready_cb(self, conn):
        StreamTubeJoinerClient.ready_cb(self, conn)

        self.join_muc()

def usage():
    print "Usage:\n" \
            "Offer a stream tube to [muc] using the trivial stream server:\n" \
            "\tpython %s [account-file] [muc] --initiator\n" \
            "Accept a stream tube from [muc] and connect it to the trivial stream client:\n" \
            "\tpython %s [account-file] [muc]\n" \
            "Offer a stream tube to [muc] using the socket [IP]:[port]:\n" \
            "\tpython %s [account-file] [muc] [IP] [port]\n" \
            "Accept a stream tube from [muc] and wait for connections from an external client:\n" \
            "\tpython %s [account-file] [muc] --no-trivial-client\n" \
            % (sys.argv[0], sys.argv[0], sys.argv[0], sys.argv[0])

if __name__ == '__main__':
    args = sys.argv[1:]

    if len(args) == 3 and args[2] == '--initiator':
        client = StreamTubeInitiatorMucClient(args[0], args[1])
    elif len(args) == 2:
        client = StreamTubeJoinerMucClient(args[0], args[1], True)
    elif len(args) == 4:
        client = StreamTubeInitiatorMucClient(args[0], args[1], (args[2], dbus.UInt16(args[3])))
    elif len(args) == 3 and args[2] == '--no-trivial-client':
        client = StreamTubeJoinerMucClient(args[0], args[1], False)
    else:
        usage()
        sys.exit(0)

    client.run()
