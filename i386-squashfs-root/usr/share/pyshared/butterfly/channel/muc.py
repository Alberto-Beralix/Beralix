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

import telepathy
import papyon
import papyon.event

from butterfly.util.decorator import async
from butterfly.channel.text import ButterflyTextChannel

__all__ = ['ButterflyMucChannel']

logger = logging.getLogger('Butterfly.MucChannel')

class ButterflyMucChannel(
        ButterflyTextChannel,
        telepathy.server.ChannelInterfaceGroup):

    def __init__(self, conn, manager, conversation, props, object_path=None):
        ButterflyTextChannel.__init__(self, conn, manager, conversation, props, object_path)
        telepathy.server.ChannelInterfaceGroup.__init__(self)

        # We would only ever be given a conversation on being invited to an
        # existing MUC.
        if conversation:
            self._conversation = conversation
            papyon.event.ConversationEventInterface.__init__(self, self._conversation)

        self.GroupFlagsChanged(telepathy.CHANNEL_GROUP_FLAG_CAN_ADD, 0)

        # This is done in an idle so that classes which subclass this one
        # can do stuff in their __init__ but will still benefit from this method
        # being called.
        self.__add_initial_participants()

    def RemoveMembers(self, contacts, message):
        # Group interface, only removing ourself is supported
        if int(self._conn.self_handle) in contacts:
            self.Close()
        else :
            raise telepathy.PermissionDenied

    # papyon.event.ConversationEventInterface
    def on_conversation_user_joined(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s joined" % unicode(handle))

        if handle not in self._members:
            self.MembersChanged('', [handle], [], [], [],
                    handle, telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED)

    # papyon.event.ConversationEventInterface
    def on_conversation_user_left(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s left" % unicode(handle))

        self.MembersChanged('', [], [handle], [], [],
                handle, telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    def AddMembers(self, contacts, message):
        for handle_id in contacts:
            handle = self._conn_ref().handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            logger.info('Inviting new contact, %s, to chat' % handle.account)
            self._conversation.invite_user(handle.contact)

    @async
    def __add_initial_participants(self):
        handles = []
        handles.append(self._conn.self_handle)
        if self._conversation:
            for participant in self._conversation.participants:
                handle = self._conn.ensure_contact_handle(contact)
                handles.append(handle)

        if handles:
            self.MembersChanged('', handles, [], [], [],
                    0, telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)
