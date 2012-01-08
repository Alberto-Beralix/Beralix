# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
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

# Implementation of the SimplePresence specification at :
# http://telepathy.freedesktop.org/spec.html#org.freedesktop.Telepathy.Connection.Interface.SimplePresence

import logging
import time

import dbus
import telepathy
import telepathy.constants
import telepathy.errors
import papyon

from butterfly.util.decorator import async

__all__ = ['ButterflyPresence']

logger = logging.getLogger('Butterfly.Presence')


class ButterflyPresenceMapping(object):
    ONLINE = 'available'
    AWAY = 'away'
    BUSY = 'dnd'
    IDLE = 'xa'
    BRB = 'brb'
    PHONE = 'phone'
    LUNCH = 'lunch'
    INVISIBLE = 'hidden'
    OFFLINE = 'offline'

    to_papyon = {
            ONLINE:     papyon.Presence.ONLINE,
            AWAY:       papyon.Presence.AWAY,
            BUSY:       papyon.Presence.BUSY,
            IDLE:       papyon.Presence.IDLE,
            BRB:        papyon.Presence.BE_RIGHT_BACK,
            PHONE:      papyon.Presence.ON_THE_PHONE,
            LUNCH:      papyon.Presence.OUT_TO_LUNCH,
            INVISIBLE:  papyon.Presence.INVISIBLE,
            OFFLINE:    papyon.Presence.OFFLINE
            }

    to_telepathy = {
            papyon.Presence.ONLINE:         ONLINE,
            papyon.Presence.AWAY:           AWAY,
            papyon.Presence.BUSY:           BUSY,
            papyon.Presence.IDLE:           IDLE,
            papyon.Presence.BE_RIGHT_BACK:  BRB,
            papyon.Presence.ON_THE_PHONE:   PHONE,
            papyon.Presence.OUT_TO_LUNCH:   LUNCH,
            papyon.Presence.INVISIBLE:      INVISIBLE,
            papyon.Presence.OFFLINE:        OFFLINE
            }

    to_presence_type = {
            ONLINE:     dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AVAILABLE),
            AWAY:       dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AWAY),
            BUSY:       dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_BUSY),
            IDLE:       dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY),
            BRB:        dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AWAY),
            PHONE:      dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_BUSY),
            LUNCH:      dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY),
            INVISIBLE:  dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_HIDDEN),
            OFFLINE:    dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_OFFLINE)
            }

class ButterflyPresence(telepathy.server.ConnectionInterfacePresence,
        telepathy.server.ConnectionInterfaceSimplePresence,
        papyon.event.ContactEventInterface,
        papyon.event.ProfileEventInterface):

    def __init__(self):
        telepathy.server.ConnectionInterfacePresence.__init__(self)
        telepathy.server.ConnectionInterfaceSimplePresence.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, self.msn_client)
        papyon.event.ProfileEventInterface.__init__(self, self.msn_client)

        self._implement_property_get(
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE, {
                'Statuses' : lambda: self._protocol.statuses
            })


    def GetStatuses(self):
        # the arguments are in common to all on-line presences
        arguments = {'message' : 's'}

        # you get one of these for each status
        # {name:(type, self, exclusive, {argument:types}}
        return {
            ButterflyPresenceMapping.ONLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_AVAILABLE,
                True, True, arguments),
            ButterflyPresenceMapping.AWAY:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True, arguments),
            ButterflyPresenceMapping.BUSY:(
                telepathy.CONNECTION_PRESENCE_TYPE_BUSY,
                True, True, arguments),
            ButterflyPresenceMapping.IDLE:(
                telepathy.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY,
                True, True, arguments),
            ButterflyPresenceMapping.BRB:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True, arguments),
            ButterflyPresenceMapping.PHONE:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True, arguments),
            ButterflyPresenceMapping.LUNCH:(
                telepathy.CONNECTION_PRESENCE_TYPE_EXTENDED_AWAY,
                True, True, arguments),
            ButterflyPresenceMapping.INVISIBLE:(
                telepathy.CONNECTION_PRESENCE_TYPE_HIDDEN,
                True, True, {}),
            ButterflyPresenceMapping.OFFLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_OFFLINE,
                True, True, {})
        }

    def RequestPresence(self, contacts):
        presences = self.get_presences(contacts)
        self.PresenceUpdate(presences)

    def GetPresence(self, contacts):
        return self.get_presences(contacts)

    def SetStatus(self, statuses):
        status, arguments = statuses.items()[0]
        if status == ButterflyPresenceMapping.OFFLINE:
            self.Disconnect()

        presence = ButterflyPresenceMapping.to_papyon[status]
        message = arguments.get('message', u'')

        logger.info("Setting Presence to '%s'" % presence)
        logger.info("Setting Personal message to '%s'" % message)

        message.encode("utf-8")

        if self._status != telepathy.CONNECTION_STATUS_CONNECTED:
            self._initial_presence = presence
            self._initial_personal_message = message
        else:
            self.msn_client.profile.personal_message = message
            self.msn_client.profile.presence = presence

    def get_presences(self, contacts):
        presences = {}
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            contact = handle.contact

            if contact is not None:
                presence = ButterflyPresenceMapping.to_telepathy[contact.presence]
                personal_message = unicode(contact.personal_message, "utf-8")
            else:
                presence = ButterflyPresenceMapping.OFFLINE
                personal_message = u""

            arguments = {}
            if personal_message:
                arguments = {'message' : personal_message}

            presences[handle] = (0, {presence : arguments}) # TODO: Timestamp
        return presences


    # SimplePresence

    def GetPresences(self, contacts):
        return self.get_simple_presences(contacts)

    def SetPresence(self, status, message):
        if status == ButterflyPresenceMapping.OFFLINE:
            self.Disconnect()

        try:
            presence = ButterflyPresenceMapping.to_papyon[status]
        except KeyError:
            raise telepathy.errors.InvalidArgument

        logger.info("Setting Presence to '%s'" % presence)
        logger.info("Setting Personal message to '%s'" % message)

        message = message.encode("utf-8")

        if self._status != telepathy.CONNECTION_STATUS_CONNECTED:
            self._initial_presence = presence
            self._initial_personal_message = message
        else:
            self.msn_client.profile.personal_message = message
            self.msn_client.profile.presence = presence

    def get_simple_presences(self, contacts):
        presences = dbus.Dictionary(signature='u(uss)')
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            contact = handle.contact

            if contact is not None:
                presence = ButterflyPresenceMapping.to_telepathy[contact.presence]
                personal_message = unicode(contact.personal_message, "utf-8")
            else:
                presence = ButterflyPresenceMapping.OFFLINE
                personal_message = u""

            presence_type = ButterflyPresenceMapping.to_presence_type[presence]

            presences[handle] = dbus.Struct((presence_type, presence,
                personal_message), signature='uss')
        return presences

    # papyon.event.ContactEventInterface
    def on_contact_presence_changed(self, contact):
        handle = self.ensure_contact_handle(contact)
        logger.info("Contact %s presence changed to '%s'" % (unicode(handle),
            contact.presence))
        self._presence_changed(handle, contact.presence, contact.personal_message)

    # papyon.event.ContactEventInterface
    on_contact_personal_message_changed = on_contact_presence_changed

    # papyon.event.ProfileEventInterface
    def on_profile_presence_changed(self):
        profile = self.msn_client.profile
        self._presence_changed(self._self_handle,
                profile.presence, profile.personal_message)

    # papyon.event.ProfileEventInterface
    on_profile_personal_message_changed = on_profile_presence_changed

    @async
    def _presence_changed(self, handle, presence, personal_message):
        presence = ButterflyPresenceMapping.to_telepathy[presence]
        presence_type = ButterflyPresenceMapping.to_presence_type[presence]
        personal_message = unicode(personal_message, "utf-8")

        self.PresencesChanged({handle: (presence_type, presence, personal_message)})

        arguments = {}
        if personal_message:
            arguments = {'message' : personal_message}

        self.PresenceUpdate({handle: (int(time.time()), {presence:arguments})})
