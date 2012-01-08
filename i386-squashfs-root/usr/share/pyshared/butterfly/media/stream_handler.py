# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2009 Collabora Ltd.
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

from constants import *

import base64
import logging

import dbus
import telepathy
import papyon
import papyon.event

from papyon.media import *

__all__ = ['ButterflyStreamHandler']

logger = logging.getLogger('Butterfly.StreamHandler')

class ButterflyStreamHandler (
        telepathy.server.DBusProperties,
        telepathy.server.MediaStreamHandler,
        papyon.event.MediaStreamEventInterface):

    def __init__(self, connection, session, stream):
        self._id = session.next_stream_id
        path = session.get_stream_path(self._id)
        self._conn = connection
        self._session = session
        self._stream = stream
        self._interfaces = set()
        self._callbacks = {}

        self._ready = False
        self._accepted = False
        self._state = telepathy.MEDIA_STREAM_STATE_CONNECTING
        self._direction = stream.direction
        if self._stream.created_locally:
            self._pending_send = telepathy.MEDIA_STREAM_PENDING_REMOTE_SEND
        else:
            self._pending_send = telepathy.MEDIA_STREAM_PENDING_LOCAL_SEND
        self._type = StreamTypes[stream.name]

        self._remote_candidates = None
        self._remote_codecs = None

        telepathy.server.DBusProperties.__init__(self)
        telepathy.server.MediaStreamHandler.__init__(self, connection._name, path)

        self._implement_property_get(telepathy.interfaces.MEDIA_STREAM_HANDLER,
            {'CreatedLocally': lambda: self.created_locally,
             'NATTraversal': lambda: self.nat_traversal,
             'STUNServers': lambda: self.stun_servers,
             'RelayInfo': lambda: self.relay_info})

        if stream._remote_candidates:
            self.on_remote_candidates_received(stream._remote_candidates)
        if stream._remote_codecs:
            self.on_remote_codecs_received(stream._remote_codecs)
        papyon.event.MediaStreamEventInterface.__init__(self, stream)

    @property
    def id(self):
        return self._id

    @property
    def type(self):
        return self._type

    @property
    def direction(self):
        return self._direction

    @property
    def pending_send(self):
        return self._pending_send

    @property
    def state(self):
        return self._state

    @property
    def stream(self):
        return self._stream

    @property
    def created_locally(self):
        return self._stream.created_locally

    @property
    def ready_for_candidates(self):
        return self._ready and (self._stream.created_locally or self._accepted)

    @property
    def nat_traversal(self):
        if self._session.type is MediaSessionType.SIP:
            return "wlm-8.5"
        elif self._session.type is MediaSessionType.TUNNELED_SIP:
            return "wlm-2009"
        else:
            return "none"

    @property
    def relay_info(self):
        relays = dbus.Array([], signature="a{sv}")
        for i, relay in enumerate(self._stream.relays):
            dict = self.convert_relay(relay)
            dict["component"] = dbus.UInt32(i + 1)
            relays.append(dict)
        return relays

    @property
    def stun_servers(self):
        servers = dbus.Array([], signature="(su)")
        if self._session.type in (MediaSessionType.SIP, MediaSessionType.TUNNELED_SIP):
            servers.append(((STUN_SERVER_IP, dbus.UInt32(STUN_SERVER_PORT))))
        return servers

    def set_direction(self, direction, pending_send):
        self._direction = direction
        self._pending_send = pending_send

    def connect(self, signal, cb):
        self._callbacks.setdefault(signal, []).append(cb)

    def emit(self, signal, *args):
        callbacks = self._callbacks.get(signal, [])
        for cb in callbacks:
            cb(self, *args)

    def Ready(self, codecs):
        logger.info("Stream %i is ready" % self._id)
        self._ready = True
        is_webcam = (self._session.type is MediaSessionType.WEBCAM_SEND or
                     self._session.type is MediaSessionType.WEBCAM_RECV)

        if self._remote_codecs:
            self.SetRemoteCodecs(self._remote_codecs)
        if self._remote_candidates and self.ready_for_candidates:
            self.SetRemoteCandidateList(self._remote_candidates)

        self.SetStreamPlaying(self._direction &
                telepathy.MEDIA_STREAM_DIRECTION_RECEIVE)
        self.SetStreamSending(self._direction &
                telepathy.MEDIA_STREAM_DIRECTION_SEND)

        if self.created_locally or is_webcam:
            self.SetLocalCodecs(codecs)

    def send_candidates(self):
        self._accepted = True
        if self._remote_candidates and self.ready_for_candidates:
            self.SetRemoteCandidateList(self._remote_candidates)

    def StreamState(self, state):
        logger.info("Stream %i state changed to %i" % (self._id, state))
        self._state = state
        self.emit("state-changed", state)

    def Error(self, code, message):
        logger.error("Stream %i received error %i: %s" % (self._id, code, message))
        self.emit("error", code, message)
        self.Close()

    def NewNativeCandidate(self, id, transports):
        logger.info("Stream %i received new native candidate %s" % (self._id, id))
        candidates = []
        for transport in transports:
            candidates.append(self.convert_tp_candidate(id, transport))
        for candidate in candidates:
            self._stream.new_local_candidate(candidate)

    def NativeCandidatesPrepared(self):
        logger.info("Stream %i natice candidates are prepared" % self._id)
        self._stream.local_candidates_prepared()

    def NewActiveCandidatePair(self, native_id, remote_id):
        logger.info("Stream %i new active candidate pair %s %s" % (self._id,
            native_id, remote_id))
        self._stream.new_active_candidate_pair(native_id, remote_id)

    def SetLocalCodecs(self, codecs):
        logger.info("Stream %i received local codecs" % self._id)
        list = self.convert_tp_codecs(codecs)
        self._stream.set_local_codecs(list)

    def SupportedCodecs(self, codecs):
        logger.info("Stream %i received supported codecs" % self._id)
        list = self.convert_tp_codecs(codecs)
        self._stream.set_local_codecs(list)

    def CodecChoice(self, codec_id):
        logger.info("Stream %i codec choice is %i" % (self._id, codec_id))

    def CodecsUpdated(self, codecs):
        logger.info("Stream %i received updated codecs" % self._id)

    #papyon.event.MediaStreamEventInterface
    def on_remote_candidates_received(self, candidates):
        list = self.convert_media_candidates(candidates)
        self._remote_candidates = list
        if list and self.ready_for_candidates:
            self.SetRemoteCandidateList(list)

    #papyon.event.MediaStreamEventInterface
    def on_remote_codecs_received(self, codecs):
        list = self.convert_media_codecs(codecs)
        self._remote_codecs = list
        if self._stream.created_locally:
            self.SetRemoteCodecs(list)

    #papyon.event.MediaStreamEventInterface
    def on_stream_closed(self):
        logger.info("Stream %i closed" % self._id)
        self._state = telepathy.MEDIA_STREAM_STATE_DISCONNECTED
        self.emit("state-changed", self._state)
        self.Close()

    def convert_media_codecs(self, codecs):
        list = []
        for codec in codecs:
            list.append(self.convert_media_codec(codec))
        return list


    # Conversion functions between papyon objects and telepathy structures

    def convert_media_codec(self, codec):
        return (codec.payload, codec.encoding, self._type, codec.clockrate, 0,
                codec.params)

    def convert_tp_codecs(self, codecs):
        list = []
        for codec in codecs:
            payload, encoding, ctype, clockrate, channels, params = codec
            c = MediaCodec(payload, encoding, clockrate, params)
            list.append(c)
        return list

    def convert_media_candidates(self, candidates):
        array = {}
        for c in candidates:
            if c.transport == "UDP":
                proto = telepathy.MEDIA_STREAM_BASE_PROTO_UDP
            else:
                proto = telepathy.MEDIA_STREAM_BASE_PROTO_TCP

            if c.type == "host":
                type = telepathy.MEDIA_STREAM_TRANSPORT_TYPE_LOCAL
            elif c.type == "srflx" or c.type == "prflx":
                type = telepathy.MEDIA_STREAM_TRANSPORT_TYPE_DERIVED
            elif c.type == "relay":
                type = telepathy.MEDIA_STREAM_TRANSPORT_TYPE_RELAY
            else:
                type = telepathy.MEDIA_STREAM_TRANSPORT_TYPE_LOCAL

            if c.priority is not None:
                preference = float(c.priority) / PRIORITY_FACTOR
            else:
                preference = 1.0

            transport = (c.component_id, c.ip, c.port, proto, self._session.subtype,
                    DEFAULT_PROFILE, preference, type, c.username, c.password)
            array.setdefault(c.foundation, []).append(transport)
        return array.items()

    def convert_tp_candidate(self, id, transport):
        (component_id, ip, port, proto, subtype, profile,
                preference, ttype, username, password) = transport

        component_id = int(component_id)
        port = int(port)
        priority = int(preference * PRIORITY_FACTOR)

        if proto == telepathy.MEDIA_STREAM_BASE_PROTO_UDP:
            proto = "UDP"
        elif proto == telepathy.MEDIA_STREAM_BASE_PROTO_TCP:
            proto = "TCP"

        if ttype == telepathy.MEDIA_STREAM_TRANSPORT_TYPE_LOCAL:
            ttype = "host"
            base_addr = None
            base_port = None
        elif ttype == telepathy.MEDIA_STREAM_TRANSPORT_TYPE_DERIVED:
            ttype = "srflx"
            local_ip = self._conn.msn_client.local_ip
            base_addr = local_ip
            base_port = port
        elif ttype == telepathy.MEDIA_STREAM_TRANSPORT_TYPE_RELAY:
            ttype = "relay"
            local_ip = self._conn.msn_client.local_ip
            base_addr = local_ip
            base_port = port

        return MediaCandidate(id, component_id, proto, priority,
                username, password, ttype, ip, port, base_addr, base_port)

    def convert_relay(self, relay):
        info = {"ip": relay.ip, "port": dbus.UInt32(relay.port),
                "username": relay.username, "password": relay.password}
        return dbus.Dictionary(info, signature="sv")
