# -*- coding: utf-8 -*-
#
# papyon - a python client library for Msn
#
# Copyright (C) 2009-2010 Collabora Ltd.
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

from papyon.gnet.constants import *
from papyon.gnet.io import *
from papyon.msnp.constants import *
from papyon.sip.message import SIPResponse, SIPRequest, SIPMessageParser, SIPVia

import base64
import gobject
import logging
import uuid
import xml.dom.minidom

logger = logging.getLogger('papyon.sip.transport')

class SIPBaseTransport(gobject.GObject):
    """Base class for SIP transports."""

    __gsignals__ = {
        "message-received": (gobject.SIGNAL_RUN_FIRST,
            gobject.TYPE_NONE,
            ([object]))
    }

    @property
    def protocol(self):
        raise NotImplementedError

    @property
    def ip(self):
        raise NotImplementedError

    @property
    def port(self):
        raise NotImplementedError

    def __init__(self):
        gobject.GObject.__init__(self)
        self._parser = SIPMessageParser()
        self._parser.connect("message-parsed", self.on_message_parsed)

    def on_message_parsed(self, parser, message):
        self.emit("message-received", message)

    def send(self, message, callback=None, errback=None):
        if type(message) is SIPRequest:
            message.add_header("Via", SIPVia(self.protocol, self.ip, self.port))
            message.add_header("Max-Forwards", 70)
        self._send(message, callback, errback)

    def _send(self, message):
        raise NotImplementedError

    def log_message(self, prefix, message):
        for line in message.splitlines():
            logger.debug(prefix + " " + line)


class SIPTunneledTransport(SIPBaseTransport):
    """Default SIP transport with newer MSNP versions (>= 18). The messages
       are base64 encoded and sent to the notication server using a UBN
       command."""

    def __init__(self, protocol):
        SIPBaseTransport.__init__(self)
        self._protocol = protocol
        self._protocol.connect("buddy-notification-received",
                self.on_notification_received)

    @property
    def protocol(self):
        return "tcp"

    @property
    def ip(self):
        return "127.0.0.1"

    @property
    def port(self):
        return 50390

    def _send(self, message, callback, errback):
        call_id = message.call_id
        if type(message) is SIPResponse:
            contact = message.From.uri.replace("sip:", "")
        else:
            contact = message.To.uri.replace("sip:", "")
        #FIXME hack
        guid = None
        if ";mepid=" in contact:
            contact, guid = contact.split(";mepid=")
            guid = uuid.UUID(guid)
        self.log_message(">>", str(message))
        data = base64.b64encode(str(message))
        data = '<sip e="base64" fid="1" i="%s"><msg>%s</msg></sip>' % \
                (call_id, data)
        data = data.replace("\r\n", "\n").replace("\n", "\r\n")
        self._protocol.send_user_notification(data, contact, guid,
                UserNotificationTypes.TUNNELED_SIP, callback, errback)

    def on_notification_received(self, protocol, peer, peer_guid, type, message):
        if type is not UserNotificationTypes.TUNNELED_SIP:
            return
        try:
            doc = xml.dom.minidom.parseString(message)
            sip = doc.firstChild
            if sip is None or sip.tagName != 'sip':
                raise ValueError("Expected node was 'sip' but is %r" % sip)
            msg = sip.firstChild
            if msg is None or msg.tagName != 'msg':
                raise ValueError("Expected node was 'msg' but is %r" % msg)
            chunk = msg.firstChild.data
            if "e" in sip.attributes.keys():
                encoding = sip.attributes["e"].value
                if encoding == "base64":
                    chunk = base64.b64decode(chunk)
                else:
                    raise ValueError("Unknown message encoding %s" % encoding)
        except Exception, err:
            logger.warning("Invalid tunneled SIP message: %s" % message)
            logger.exception(err)
        else:
            self.log_message("<<", chunk)
            self._parser.append(chunk)
