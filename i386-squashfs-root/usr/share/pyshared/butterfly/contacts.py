# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2009 Olivier Le Thanh Duong <olivier@lethanh.be>
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
import time

import telepathy
import telepathy.errors
import papyon
import dbus

__all__ = ['ButterflyContacts']

logger = logging.getLogger('Butterfly.Contacts')

class ButterflyContacts(
        telepathy.server.ConnectionInterfaceContacts,
        papyon.event.ContactEventInterface,
        papyon.event.ProfileEventInterface):

    attributes = {
        telepathy.CONNECTION : 'contact-id',
        telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE : 'presence',
        telepathy.CONNECTION_INTERFACE_ALIASING : 'alias',
        telepathy.CONNECTION_INTERFACE_AVATARS : 'token',
        telepathy.CONNECTION_INTERFACE_CAPABILITIES : 'caps',
        telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES : 'capabilities'
        }

    def __init__(self):
        telepathy.server.ConnectionInterfaceContacts.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, self.msn_client)
        papyon.event.ProfileEventInterface.__init__(self, self.msn_client)

        dbus_interface = telepathy.CONNECTION_INTERFACE_CONTACTS

        self._implement_property_get(dbus_interface, \
                {'ContactAttributeInterfaces' : self.get_contact_attribute_interfaces})

    # Overwrite the dbus attribute to get the sender argument
    @dbus.service.method(telepathy.CONNECTION_INTERFACE_CONTACTS, in_signature='auasb',
                            out_signature='a{ua{sv}}', sender_keyword='sender')
    def GetContactAttributes(self, handles, interfaces, hold, sender):
        #InspectHandle already checks we're connected, the handles and handle type.
        supported_interfaces = set()
        for interface in interfaces:
            if interface in self.attributes:
                supported_interfaces.add(interface)
            else:
                logger.debug("Ignoring unsupported interface %s" % interface)

        handle_type = telepathy.HANDLE_TYPE_CONTACT
        ret = dbus.Dictionary(signature='ua{sv}')
        for handle in handles:
            ret[handle] = dbus.Dictionary(signature='sv')

        functions = {
            telepathy.CONNECTION :
                lambda x: zip(x, self.InspectHandles(handle_type, x)),
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE :
                lambda x: self.GetPresences(x).items(),
            telepathy.CONNECTION_INTERFACE_ALIASING :
                lambda x: self.GetAliases(x).items(),
            telepathy.CONNECTION_INTERFACE_AVATARS :
                lambda x: self.GetKnownAvatarTokens(x).items(),
            telepathy.CONNECTION_INTERFACE_CAPABILITIES :
                lambda x: self.GetCapabilities(x).items(),
            telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES :
                lambda x: self.GetContactCapabilities(x).items()
            }

        #Hold handles if needed
        if hold:
            self.HoldHandles(handle_type, handles, sender)

        # Attributes from the interface org.freedesktop.Telepathy.Connection
        # are always returned, and need not be requested explicitly.
        supported_interfaces.add(telepathy.CONNECTION)

        for interface in supported_interfaces:
            interface_attribute = interface + '/' + self.attributes[interface]
            results = functions[interface](handles)
            for handle, value in results:
                ret[int(handle)][interface_attribute] = value
        return ret

    def get_contact_attribute_interfaces(self):
        return self.attributes.keys()
