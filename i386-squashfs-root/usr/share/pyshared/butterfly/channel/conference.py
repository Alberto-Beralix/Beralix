# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2007 Johann Prieur <johann.prieur@gmail.com>
# Copyright (C) 2009-2010 Collabora, Ltd.
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

from butterfly.channel.muc import ButterflyMucChannel

__all__ = ['ButterflyConferenceChannel']

logger = logging.getLogger('Butterfly.ConferenceChannel')

class ButterflyConferenceChannel(
        ButterflyMucChannel,
        telepathy.server.ChannelInterfaceConference):

    def __init__(self, conn, manager, conversation, props, object_path=None):
        ButterflyMucChannel.__init__(self, conn, manager, conversation, props, object_path)
        telepathy.server.ChannelInterfaceConference.__init__(self)

        _, _, handle = manager._get_type_requested_handle(props)

        # Get the channels listed in InitialChannels
        ic = self._get_initial_channels(props)

        # Steal the first channel's conversation
        steal_channel = ic.pop()
        logger.info('Stealing switchboard from channel %s' % steal_channel._object_path)
        self._conversation = steal_channel.steal_conversation()

        # Make sure we actually have stolen a switchboard.
        if self._conversation is None:
            raise telepathy.Offline("Channel %s does not have a conversation; "
                "did the contact go offline?" % steal_channel._object_path)

        # Connect to conversation events
        papyon.event.ConversationEventInterface.__init__(self, self._conversation)

        # Invite contacts in InitialInvitee{IDs,Handles}
        self._invite_initial_invitees(props, ic)

    def _get_initial_channels(self, props):
        logger.info('Getting channels from InitialChannels')
        ic_paths = props[CHANNEL_INTERFACE_CONFERENCE + '.InitialChannels']
        ic = set()

        for channel in self._conn_ref()._channels:
            if channel._object_path in ic_paths:
                ic.add(channel)

        if not ic:
            raise telepathy.InvalidArgument("Couldn't find any channels referred to in InitialChannels")

        if len(ic) != len(ic_paths):
            raise telepathy.InvalidArgument("Couldn't find all channels referred to in InitialChannels")

        self._conference_initial_channels = ic.copy()
        self._conference_channels = ic.copy()

        return ic

    def _invite_initial_invitees(self, props, ic):
        # Invite all other participants in other channels from InitialChannels
        while ic:
            channel = ic.pop()
            if channel._conversation is None:
                continue

            for contact in channel.get_participants():
                if contact not in self._conversation.participants:
                    logger.info('Inviting %s into channel' % contact.id)
                    self._conversation.invite_user(contact)

        self._conference_initial_invitees = []

        # Get IntitialInviteeHandles
        for invitee_handle in props.get(CHANNEL_INTERFACE_CONFERENCE + '.InitialInviteeHandles', []):
            handle = self._conn_ref().handle(telepathy.HANDLE_TYPE_CONTACT, invitee_handle)

            if handle is None or handle.contact is None:
                raise telepathy.NotAvailable('Contact with handle %u not available' % invitee_handle)

            if handle not in self._conference_initial_invitees:
                self._conference_initial_invitees.append(handle)

        # Get InitialInviteeIDs
        for invitee_id in props.get(CHANNEL_INTERFACE_CONFERENCE + '.InitialInviteeIDs', []):
            handle = self._conn_ref().ensure_handle(telepathy.HANDLE_TYPE_CONTACT, invitee_id)

            if handle is None or handle.contact is None:
                raise telepathy.NotAvailable('Contact "%s" not available' % invitee_id)

            if handle not in self._conference_initial_invitees:
                self._conference_initial_invitees.append(handle)

        # Actually invite all the initial invitees
        for handle in self._conference_initial_invitees:
            logger.info('Inviting initial invitee, %s into channel' % handle.account)
            self._conversation.invite_user(handle.contact)
