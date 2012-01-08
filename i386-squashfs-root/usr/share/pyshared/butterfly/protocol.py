# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2010 Collabora Ltd.
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

import logging
import dbus

import telepathy
import papyon
import papyon.event

from butterfly.connection import ButterflyConnection
from butterfly.presence import ButterflyPresenceMapping

__all__ = ['ButterflyProtocol']

logger = logging.getLogger('Butterfly.Protocol')

class ButterflyProtocol(telepathy.server.Protocol,
                        telepathy.server.ProtocolInterfacePresence):

    _proto = "msn"
    _vcard_field = ""
    _english_name = "MSN"
    _icon = "im-msn"

    _secret_parameters = set([
            'password',
            'http-proxy-password',
            'https-proxy-password'
            ])
    _mandatory_parameters = {
            'account' : 's',
            'password' : 's'
            }
    _optional_parameters = {
            'server' : 's',
            'port' : 'q',
            'http-proxy-server' : 's',
            'http-proxy-port' : 'q',
            'http-proxy-username' : 's',
            'http-proxy-password' : 's',
            'https-proxy-server' : 's',
            'https-proxy-port' : 'q',
            'https-proxy-username' : 's',
            'https-proxy-password' : 's',
            'http-method' : 'b',
            }
    _parameter_defaults = {
            'server' : u'messenger.hotmail.com',
            'port' : 1863,
            'http-method' : False
            }

    _requestable_channel_classes = [
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_TEXT),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_TEXT),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_NONE)},
         [telepathy.CHANNEL_INTERFACE_CONFERENCE + '.InitialChannels',
          telepathy.CHANNEL_INTERFACE_CONFERENCE + '.InitialInviteeHandles',
          telepathy.CHANNEL_INTERFACE_CONFERENCE + '.InitialInviteeIDs',
          telepathy.CHANNEL_INTERFACE_CONFERENCE + '.InitialMessage',
          telepathy.CHANNEL_INTERFACE_CONFERENCE + '.SupportsNonMerges']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_GROUP)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_LIST)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_STREAMED_MEDIA),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialAudio',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialVideo']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_FILE_TRANSFER),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.ContentType',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Filename',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Size',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.ContentHash',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Description',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Date'])
        ]

    _supported_interfaces = [
            telepathy.CONNECTION_INTERFACE_ALIASING,
            telepathy.CONNECTION_INTERFACE_AVATARS,
            telepathy.CONNECTION_INTERFACE_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_PRESENCE,
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE,
            telepathy.CONNECTION_INTERFACE_CONTACTS,
            telepathy.CONNECTION_INTERFACE_REQUESTS,
            telepathy.CONNECTION_INTERFACE_MAIL_NOTIFICATION
        ]

    _statuses = {
            ButterflyPresenceMapping.ONLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_AVAILABLE,
                True, True),
            ButterflyPresenceMapping.AWAY:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True),
            ButterflyPresenceMapping.BUSY:(
                telepathy.CONNECTION_PRESENCE_TYPE_BUSY,
                True, True),
            ButterflyPresenceMapping.IDLE:(
                telepathy.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY,
                True, True),
            ButterflyPresenceMapping.BRB:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True),
            ButterflyPresenceMapping.PHONE:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True),
            ButterflyPresenceMapping.LUNCH:(
                telepathy.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY,
                True, True),
            ButterflyPresenceMapping.INVISIBLE:(
                telepathy.CONNECTION_PRESENCE_TYPE_HIDDEN,
                True, False),
            ButterflyPresenceMapping.OFFLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_OFFLINE,
                True, False)
            }


    def __init__(self, connection_manager):
        telepathy.server.Protocol.__init__(self, connection_manager, 'msn')
        telepathy.server.ProtocolInterfacePresence.__init__(self)

    def create_connection(self, connection_manager, parameters):
        return ButterflyConnection(self, connection_manager, parameters)
