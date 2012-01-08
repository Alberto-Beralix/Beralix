import dbus
import dbus.glib
import gobject
import sys
import gst

import tpfarsight
import farsight

from account import connection_from_file

from telepathy.client.channel import Channel
from telepathy.constants import (
    CONNECTION_HANDLE_TYPE_NONE, CONNECTION_HANDLE_TYPE_CONTACT,
    CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_DISCONNECTED,
    MEDIA_STREAM_TYPE_AUDIO, MEDIA_STREAM_TYPE_VIDEO)
from telepathy.interfaces import (
    CHANNEL_INTERFACE, CHANNEL_INTERFACE_GROUP, CHANNEL_TYPE_STREAMED_MEDIA,
    CONN_INTERFACE, CONN_INTERFACE_CAPABILITIES)

import logging
logging.basicConfig()

class Call:
    def __init__(self, account_file):
        self.conn = connection_from_file(account_file,
            ready_handler=self.ready_cb)
        self.channel = None
        self.fschannel = None
        self.pipeline = gst.Pipeline()
        self.pipeline.get_bus().add_watch(self.async_handler)

        self.conn[CONN_INTERFACE].connect_to_signal('StatusChanged',
            self.status_changed_cb)
        self.conn[CONN_INTERFACE].connect_to_signal('NewChannel',
            self.new_channel_cb)

    def async_handler (self, bus, message):
        if self.tfchannel != None:
            self.tfchannel.bus_message(message)
        return True

    def run_main_loop(self):
        self.loop = gobject.MainLoop()
        self.loop.run()

    def run(self):
        print "connecting"
        self.conn[CONN_INTERFACE].Connect()

        try:
            self.run_main_loop()
        except KeyboardInterrupt:
            print "killed"

            if self.channel:
                print "closing channel"
                self.channel[CHANNEL_INTERFACE].Close()

        try:
            print "disconnecting"
            self.conn[CONN_INTERFACE].Disconnect()
        except dbus.DBusException:
            pass

    def quit(self):
        if self.loop:
            self.loop.quit()
            self.loop = None

    def status_changed_cb(self, state, reason):
        if state == CONNECTION_STATUS_DISCONNECTED:
            print 'connection closed'
            self.quit()

    def ready_cb(self, conn):
        pass

    def request_channel_error_cb(self, exception):
        print 'error:', exception
        self.quit()

    def new_channel_cb(self, object_path, channel_type, handle_type, handle,
            suppress_handler):
        if channel_type != CHANNEL_TYPE_STREAMED_MEDIA:
            return

        self.chan_handle_type = handle_type
        self.chan_handle = handle

        print "new streamed media channel"
        Channel(self.conn.service_name, object_path,
                ready_handler=self.channel_ready_cb)

    def src_pad_added (self, stream, pad, codec):
        type = stream.get_property ("media-type")
        if type == farsight.MEDIA_TYPE_AUDIO:
            sink = gst.parse_bin_from_description("audioconvert ! audioresample ! audioconvert ! autoaudiosink", True)
        elif type == farsight.MEDIA_TYPE_VIDEO:
            sink = gst.parse_bin_from_description("ffmpegcolorspace ! videoscale ! autovideosink", True)

        self.pipeline.add(sink)
        pad.link(sink.get_pad("sink"))
        sink.set_state(gst.STATE_PLAYING)

    def stream_created(self, channel, stream):
        stream.connect ("src-pad-added", self.src_pad_added)
        srcpad = stream.get_property ("sink-pad")

        type = stream.get_property ("media-type")

        if type == farsight.MEDIA_TYPE_AUDIO:
            src = gst.element_factory_make ("audiotestsrc")
            src.set_property("is-live", True)
        elif type == farsight.MEDIA_TYPE_VIDEO:
            src = gst.element_factory_make ("videotestsrc")
            src.set_property("is-live", True)

        self.pipeline.add(src)
        src.get_pad("src").link(srcpad)
        src.set_state(gst.STATE_PLAYING)

    def session_created (self, channel, conference, participant):
        self.pipeline.add(conference)
        self.pipeline.set_state(gst.STATE_PLAYING)

    def get_codec_config (self, channel, stream_id, media_type, direction):
        print "got codec config"
        if media_type == farsight.MEDIA_TYPE_VIDEO:
            codecs = [ farsight.Codec(farsight.CODEC_ID_ANY, "H264",
                farsight.MEDIA_TYPE_VIDEO, 0) ]
            if self.conn.GetProtocol() == "sip" :
                codecs += [ farsight.Codec(farsight.CODEC_ID_DISABLE, "THEORA",
                                        farsight.MEDIA_TYPE_VIDEO, 0) ]
            else:
                codecs += [ farsight.Codec(farsight.CODEC_ID_ANY, "THEORA",
                                        farsight.MEDIA_TYPE_VIDEO, 0) ]
            codecs += [
                farsight.Codec(farsight.CODEC_ID_ANY, "H263",
                                        farsight.MEDIA_TYPE_VIDEO, 0),
                farsight.Codec(farsight.CODEC_ID_DISABLE, "DV",
                                        farsight.MEDIA_TYPE_VIDEO, 0),
                farsight.Codec(farsight.CODEC_ID_ANY, "JPEG",
                                        farsight.MEDIA_TYPE_VIDEO, 0),
                farsight.Codec(farsight.CODEC_ID_ANY, "MPV",
                                        farsight.MEDIA_TYPE_VIDEO, 0),
            ]

            return codecs
        else:
            return None

    def channel_ready_cb(self, channel):
        print "channel ready"
        channel[CHANNEL_INTERFACE].connect_to_signal('Closed', self.closed_cb)
        channel[CHANNEL_INTERFACE_GROUP].connect_to_signal('MembersChanged',
            self.members_changed_cb)
        channel[CHANNEL_TYPE_STREAMED_MEDIA].connect_to_signal(
            'StreamError', self.stream_error_cb)

        self.channel = channel

        tfchannel = tpfarsight.Channel(self.conn.service_name,
            self.conn.object_path, channel.object_path)

        self.tfchannel = tfchannel
        tfchannel.connect ("session-created", self.session_created)
        tfchannel.connect ("stream-created", self.stream_created)
        tfchannel.connect ("stream-get-codec-config", self.get_codec_config)

        print "Channel ready"

    def stream_error_cb(self, *foo):
        print 'error: %r' % (foo,)
        self.channel.close()

    def closed_cb(self):
        print "channel closed"
        self.quit()

    def members_changed_cb(self, message, added, removed, local_pending,
            remote_pending, actor, reason):
        print 'MembersChanged', (
            added, removed, local_pending, remote_pending, actor, reason)

class OutgoingCall(Call):
    def __init__(self, account_file, contact):
        Call.__init__(self, account_file)
        self.contact = contact
        self.calling = False

    def start_call(self):
        self.calling = True
        self.conn[CONN_INTERFACE].RequestChannel(
            CHANNEL_TYPE_STREAMED_MEDIA, CONNECTION_HANDLE_TYPE_NONE,
            0, True, reply_handler=lambda *stuff: None,
            error_handler=self.request_channel_error_cb)

    def got_handle_capabilities(self, caps):
        if self.calling:
            return
        for c in caps:
            if c[1] == CHANNEL_TYPE_STREAMED_MEDIA:
                self.start_call()
                return
        print "No media capabilities found, waiting...."

    def capabilities_changed_cb(self, caps):
        for x in caps:
            if x[0] == self.handle:
                self.got_handle_capabilities([[x[0],x[1],x[3],x[5]]])

    def ready_cb(self, conn):
        handle = self.conn[CONN_INTERFACE].RequestHandles(
            CONNECTION_HANDLE_TYPE_CONTACT, [self.contact])[0]
        self.handle = handle

        if CONN_INTERFACE_CAPABILITIES in self.conn.get_valid_interfaces():
            self.conn[CONN_INTERFACE_CAPABILITIES].connect_to_signal(
                'CapabilitiesChanged', self.capabilities_changed_cb)
            self.got_handle_capabilities(
                self.conn[CONN_INTERFACE_CAPABILITIES].GetCapabilities(
                    [handle]))
        else:
            # CM doesn't have capabilities support, assume they can do audio
            # and video
            self.start_call()

    def channel_ready_cb(self, channel):
        Call.channel_ready_cb(self, channel)

        channel[CHANNEL_INTERFACE_GROUP].AddMembers([self.handle], "")

        print "requesting audio/video streams"

        try:
            channel[CHANNEL_TYPE_STREAMED_MEDIA].RequestStreams(
                self.handle,
                [MEDIA_STREAM_TYPE_AUDIO, MEDIA_STREAM_TYPE_VIDEO]);
        except dbus.DBusException, e:
            print "failed:", e
            print "requesting audio stream"

            try:
                channel[CHANNEL_TYPE_STREAMED_MEDIA].RequestStreams(
                    self.handle, [MEDIA_STREAM_TYPE_AUDIO]);
            except dbus.DBusException, e:
                print "failed:", e
                print "giving up"
                self.quit()

class IncomingCall(Call):
    def ready_cb(self, conn):
        if CONN_INTERFACE_CAPABILITIES in self.conn.get_valid_interfaces():
            self.conn[CONN_INTERFACE_CAPABILITIES].AdvertiseCapabilities(
                [(CHANNEL_TYPE_STREAMED_MEDIA, 3)], [])

    def channel_ready_cb(self, channel):
        Call.channel_ready_cb(self, channel)

        print "accepting incoming call"
        pending = channel[CHANNEL_INTERFACE_GROUP].GetLocalPendingMembers()
        channel[CHANNEL_INTERFACE_GROUP].AddMembers(pending, "")

    def closed_cb(self):
        print "channel closed"
        self.channel = None
        print "waiting for incoming call"

if __name__ == '__main__':
    gobject.threads_init()

    args = sys.argv[1:]

    assert len(args) in (1, 2)

    if len(args) > 1:
        call = OutgoingCall(args[0], args[1])
    else:
        call = IncomingCall(args[0])

    call.run()
