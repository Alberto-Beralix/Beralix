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
import weakref
import time
import re

import dbus
import telepathy
import papyon
import papyon.event

from butterfly.channel.text import ButterflyTextChannel

__all__ = ['ButterflyImChannel']

logger = logging.getLogger('Butterfly.ImChannel')

class ButterflyImChannel(ButterflyTextChannel):

    def __init__(self, conn, manager, conversation, props, object_path=None):
        ButterflyTextChannel.__init__(self, conn, manager, conversation, props, object_path)

        _, _, handle = manager._get_type_requested_handle(props)

        if handle.contact is None:
            raise telepathy.NotAvailable('Contact not available')

        self._pending_offline_messages = {}
        contact = handle.contact
        if conversation is None:
            if contact.presence != papyon.Presence.OFFLINE:
                client = conn.msn_client
                conversation = papyon.Conversation(client, [contact])
            self._conversation = conversation

        if self._conversation:
            self._offline_contact = None
            self._offline_handle = None
            papyon.event.ConversationEventInterface.__init__(self, self._conversation)
        else:
            self._offline_handle = handle
            self._offline_contact = contact

        self._initial_handle = handle

        self._oim_box_ref = weakref.ref(conn.msn_client.oim_box)

    def steal_conversation(self):
        # Set offline contact details for this 1-1 chat.
        self._offline_handle = self._initial_handle
        self._offline_contact = self._initial_handle.contact

        # If this 1-1 chat has been idle for sometime, the switchboard will
        # close, so the participant list will be an empty set. If we then
        # create a channel with the conference interface and then try and
        # extend from this conversation, there won't be any participants.
        # Let's reinvite them now.
        if self._conversation:
            if len(self._conversation.participants) == 0:
                self._conversation.invite_user(self._initial_handle.contact)

        return ButterflyTextChannel.steal_conversation(self)

    def get_participants(self):
        # If we have no conversation, our contact is probably offline,
        # so we don't actually want this to return our offline contact
        # as adding him or her to a MUC won't work either.
        if self._conversation is None:
            return ButterflyTextChannel.get_participants(self)
        else:
            return set([self._initial_handle.contact])

    def _send_text_message(self, message_type, text):
        if self._conversation is None and self._offline_contact.presence != papyon.Presence.OFFLINE:
            contact = self._offline_contact
            logger.info('Contact %s still connected, inviting him to the text channel before sending message' % unicode(contact))
            client = self._conn_ref().msn_client
            self._conversation = papyon.Conversation(client, [contact])
            papyon.event.ConversationEventInterface.__init__(self, self._conversation)
            self._offline_contact = None
            self._offline_handle = None

        if self._conversation is not None:
            # Actually send the message.
            return ButterflyTextChannel._send_text_message(self, message_type, text)
        else:
            if message_type == telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL:
                logger.info("Sending offline message : %s" % unicode(text))
                self._oim_box_ref().send_message(self._offline_contact, text.encode("utf-8"))
                #FIXME : Check if the message was sent correctly?
            else:
                raise telepathy.NotImplemented("Unhandled message type for offline contact")
            return True

    # Rededefine AcknowledgePendingMessages to remove offline messages
    # from the oim box.
    def AcknowledgePendingMessages(self, ids):
        ButterflyTextChannel.AcknowledgePendingMessages(self, ids)

        messages = []
        for id in ids:
            if id in self._pending_offline_messages.keys():
                messages.append(self._pending_offline_messages[id])
                del self._pending_offline_messages[id]
        self._oim_box_ref().delete_messages(messages)

    # Rededefine ListPendingMessages to remove offline messages
    # from the oim box.
    def ListPendingMessages(self, clear):
        if clear:
            messages = self._pending_offline_messages.values()
            self._oim_box_ref().delete_messages(messages)
        return ButterflyTextChannel.ListPendingMessages(self, clear)

    # papyon.event.ConversationEventInterface
    def on_conversation_user_joined(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s joined" % unicode(handle))

        if self._initial_handle == handle:
            return

        props = {
            telepathy.CHANNEL + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_TEXT),
            telepathy.CHANNEL + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_NONE),
            CHANNEL_INTERFACE_CONFERENCE + '.InitialChannels': dbus.Array([self._object_path], signature='o'),
            CHANNEL_INTERFACE_CONFERENCE + '.InitialInviteeIDs': dbus.Array([dbus.String(handle.get_name())], signature='s'),
            telepathy.CHANNEL + '.Requested': dbus.Boolean(False)
            }

        new_channel = self._conn_ref()._channel_manager.channel_for_props(props,
            signal=True, conversation=None)

        logger.info('Created new MUC channel to replace this 1-1 one: %s' % \
            new_channel._object_path)

    # papyon.event.ConversationEventInterface
    def on_conversation_closed(self):
        logger.info('Conversation closed')
        self._offline_contact = self._initial_handle.contact
        self._offline_handle = self._initial_handle
        self._conversation = None

    # papyon.event.ContactEventInterface
    def on_contact_presence_changed(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        # Recreate a conversation if our contact join
        if self._offline_contact == contact and contact.presence != papyon.Presence.OFFLINE:
            logger.info('Contact %s connected, inviting him to the text channel' % unicode(handle))
            client = self._conn_ref().msn_client
            self._conversation = papyon.Conversation(client, [contact])
            papyon.event.ConversationEventInterface.__init__(self, self._conversation)
            self._offline_contact = None
            self._offline_handle = None
        #FIXME : I really hope there is no race condition between the time
        # the contact accept the invitation and the time we send him a message
        # Can a user refuse an invitation? what happens then?

    # Public API
    def offline_message_received(self, message):
        # @message a papyon.OfflineIM.OfflineMessage
        id = self._recv_id
        sender = message.sender
        timestamp = time.mktime(message.date.timetuple())
        text = re.sub('\r\n', '\n', message.text)
        text = re.sub('\r', '\n', text)

        # Map the id to the offline message so we can remove it
        # when acked by the client
        self._pending_offline_messages[id] = message

        handle = self._conn.ensure_contact_handle(sender)
        type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
        logger.info("User %r sent a offline message" % handle)
        self._signal_text_received(id, timestamp, handle, type, 0, message.display_name, text)

        self._recv_id += 1

    def attach_conversation(self, conversation):
        # @conversation a papyon.ConversationInterface
        if self._conversation:
            if self._conversation is conversation:
                logger.warning("Trying to reattach the same switchboard to a channel, do nothing")
                return
            else:
                logger.warning("Attaching to a channel which already have a switchboard, leaving previous one")
                self._conversation.leave()
        else:
            self._offline_contact = None
            self._offline_handle = None
        self._conversation = conversation
        papyon.event.ConversationEventInterface.__init__(self, self._conversation)
