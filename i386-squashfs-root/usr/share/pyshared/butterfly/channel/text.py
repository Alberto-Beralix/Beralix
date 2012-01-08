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

import gobject
import logging
import weakref
import time
import re

import dbus
import telepathy
import papyon
import papyon.event
from telepathy._generated.Channel_Interface_Messages import ChannelInterfaceMessages
from telepathy.interfaces import CHANNEL_INTERFACE_MESSAGES

from butterfly.channel import ButterflyChannel

__all__ = ['ButterflyTextChannel']

logger = logging.getLogger('Butterfly.TextChannel')

class ButterflyTextChannel(
        ButterflyChannel,
        telepathy.server.ChannelTypeText,
        telepathy.server.ChannelInterfaceChatState,
        ChannelInterfaceMessages,
        papyon.event.ContactEventInterface,
        papyon.event.ConversationEventInterface):

    def __init__(self, conn, manager, conversation, props, object_path=None):
        self._recv_id = 0
        self._conn_ref = weakref.ref(conn)
        self._send_typing_notification_timeout = 0
        self._typing_notifications = dict()

        self._conversation = None
        self._pending_messages2 = {}

        telepathy.server.ChannelTypeText.__init__(self, conn, manager, props,
            object_path=object_path)
        ButterflyChannel.__init__(self, conn, props)
        telepathy.server.ChannelInterfaceChatState.__init__(self)
        ChannelInterfaceMessages.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, conn.msn_client)

        self._implement_property_get(CHANNEL_INTERFACE_MESSAGES, {
            'SupportedContentTypes': lambda: ["text/plain"] ,
            'MessagePartSupportFlags': lambda: 0,
            'DeliveryReportingSupport': lambda: telepathy.DELIVERY_REPORTING_SUPPORT_FLAG_RECEIVE_FAILURES,
            'PendingMessages': lambda: dbus.Array(self._pending_messages2.values(), signature='aa{sv}')
            })

        self._add_immutables({
            'SupportedContentTypes': CHANNEL_INTERFACE_MESSAGES,
            'MessagePartSupportFlags': CHANNEL_INTERFACE_MESSAGES,
            'DeliveryReportingSupport': CHANNEL_INTERFACE_MESSAGES,
            })


    def __del__(self):
        self._remove_typing_timeouts()

    def _remove_typing_timeouts(self):
        # Remove any timeouts we had running.
        if self._send_typing_notification_timeout != 0:
            gobject.source_remove(self._send_typing_notification_timeout)
            self._send_typing_notification_timeout = 0
            handle = self._conn.self_handle
            self.ChatStateChanged(handle, telepathy.CHANNEL_CHAT_STATE_ACTIVE)

        for handle, tag in self._typing_notifications.items():
            gobject.source_remove(tag)
            self.ChatStateChanged(handle, telepathy.CHANNEL_CHAT_STATE_ACTIVE)
        self._typing_notifications = dict()

    def steal_conversation(self):
        if self._conversation is None:
            return None

        ret = self._conversation
        self._conversation = None

        self._remove_typing_timeouts()

        # We don't want this object to receive events regarding the conversation
        # that has been stolen. It would be nice if papyon had an API to do this,
        # as opposed to having to access the _events_handlers weak set of the
        # conversation we're losing.
        self._client = None
        ret._events_handlers.remove(self)

        return ret

    def get_participants(self):
        if self._conversation:
            return self._conversation.participants
        else:
            return set()

    def _send_typing_notification(self):
        # No need to emit ChatStateChanged in this method because it will not
        # have changed from composing otherwise this source will have been
        # removed.

        if self._conversation is not None:
            # Send this notification and keep sending them.
            self._conversation.send_typing_notification()
            return True
        else:
            # Don't bother sending anymore as we have no conversation.
            self._send_typing_notification_timeout = 0
            return False

    def _send_text_message(self, message_type, text):
        "Send a simple text message, return true if sent correctly"
        if self._conversation is not None:
            if message_type == telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL:
                logger.info("Sending message : %s" % unicode(text))
                self._conversation.send_text_message(papyon.ConversationMessage(text))
            else:
                raise telepathy.NotImplemented("Unhandled message type")
            return True
        else:
            logger.warning('Tried sending a message with no conversation')
            return False

    def _signal_text_sent(self, timestamp, message_type, text):
        headers = {'message-sent' : timestamp,
                   'message-type' : message_type
                  }
        body = {'content-type': 'text/plain',
                'content': text
               }
        message = [headers, body]
        self.Sent(timestamp, message_type, text)
        self.MessageSent(message, 0, '')

    def _signal_text_received(self, id, timestamp, sender, type, flags, sender_nick, text):
        self.Received(id, timestamp, sender, type, flags, text)
        headers = dbus.Dictionary({dbus.String('message-received') : dbus.UInt64(timestamp),
                   dbus.String('pending-message-id') : dbus.UInt32(id),
                   dbus.String('message-sender') : dbus.UInt32(sender),
                   dbus.String('message-type') : dbus.UInt32(type)
                  }, signature='sv')

        if sender_nick not in (None, ''):
            sender_nick = unicode(sender_nick, "utf-8")
            headers[dbus.String('sender-nickname')] = dbus.String(sender_nick)

        body = dbus.Dictionary({dbus.String('content-type'): dbus.String('text/plain'),
                dbus.String('content'): dbus.String(text)
               }, signature='sv')
        message = dbus.Array([headers, body], signature='a{sv}')
        self.MessageReceived(message)

    def SetChatState(self, state):
        # Not useful if we dont have a conversation.
        if self._conversation is not None:
            if state == telepathy.CHANNEL_CHAT_STATE_COMPOSING:
                # User has started typing.
                self._conversation.send_typing_notification()

                # If we haven't already set a timeout, add one for every 5s.
                if self._send_typing_notification_timeout == 0:
                    self._send_typing_notification_timeout = \
                        gobject.timeout_add_seconds(5, self._send_typing_notification)

            else:
                # User is gone/inactive/active/paused, which basically means "not typing".
                # If we have a timeout for sending typing notifications, remove it.
                if self._send_typing_notification_timeout != 0:
                    gobject.source_remove(self._send_typing_notification_timeout)
                    self._send_typing_notification_timeout = 0

        self.ChatStateChanged(self._conn.GetSelfHandle(), state)

    @dbus.service.method(telepathy.CHANNEL_TYPE_TEXT, in_signature='us', out_signature='',
                         async_callbacks=('_success', '_error'))
    def Send(self, message_type, text, _success, _error):
        if self._send_text_message(message_type, text):
            # The function MUST return before emitting the signals
            _success()
            timestamp = int(time.time())
            self._signal_text_sent(timestamp, message_type, text)

    def Close(self):
        if self._conversation is not None:
            self._conversation.leave()
            self._conversation = None
        self._remove_typing_timeouts()
        telepathy.server.ChannelTypeText.Close(self)

    def GetPendingMessageContent(self, message_id, parts):
        # We don't support pending message
        raise telepathy.InvalidArgument()

    @dbus.service.method(telepathy.CHANNEL_INTERFACE_MESSAGES, in_signature='aa{sv}u',
                         out_signature='s', async_callbacks=('_success', '_error'))
    def SendMessage(self, message, flags, _success, _error):
        headers = message.pop(0)
        message_type = int(headers.get('message-type', telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL))
        if message_type != telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL:
                raise telepathy.NotImplemented("Unhandled message type")
        text = None
        for part in message:
            if part.get("content-type", None) ==  "text/plain":
                text = part['content']
                break
        if text is None:
                raise telepathy.NotImplemented("Unhandled message type")

        if self._send_text_message(message_type, text):
            timestamp = int(time.time())
            # The function MUST return before emitting the signals
            _success('')
            self._signal_text_sent(timestamp, message_type, text)

    def AcknowledgePendingMessages(self, ids):
        for id in ids:
            if id in self._pending_messages2:
                del self._pending_messages2[id]

        telepathy.server.ChannelTypeText.AcknowledgePendingMessages(self, ids)
        self.PendingMessagesRemoved(ids)

    def ListPendingMessages(self, clear):
        if clear:
            ids = self._pending_messages2.keys()
            self._pending_messages2 = {}
            self.PendingMessagesRemoved(ids)

        return telepathy.server.ChannelTypeText.ListPendingMessages(self, clear)

    # Redefine GetSelfHandle since we use our own handle
    #  as Butterfly doesn't have channel specific handles
    def GetSelfHandle(self):
        return self._conn.GetSelfHandle()

    def _contact_typing_notification_timeout(self, handle):
        # Contact hasn't sent a typing notification for ten seconds. He or she
        # has probably stopped typing.
        del self._typing_notifications[handle]
        self.ChatStateChanged(handle, telepathy.CHANNEL_CHAT_STATE_ACTIVE)
        return False

    # papyon.event.ConversationEventInterface
    def on_conversation_user_typing(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        logger.info("User %s is typing" % unicode(handle))

        # Remove any previous timeout.
        if handle in self._typing_notifications:
            gobject.source_remove(self._typing_notifications[handle])
            del self._typing_notifications[handle]

        # Add a new timeout of 10 seconds. If we don't receive another typing
        # notification in that time, the contact has probably stopped typing,
        # so we should set the chat state back to active for that handle.
        self._typing_notifications[handle] = \
            gobject.timeout_add_seconds(10, self._contact_typing_notification_timeout, handle)

        self.ChatStateChanged(handle, telepathy.CHANNEL_CHAT_STATE_COMPOSING)

    # papyon.event.ConversationEventInterface
    def on_conversation_message_received(self, sender, message):
        id = self._recv_id
        timestamp = int(time.time())
        handle = self._conn.ensure_contact_handle(sender)
        type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
        logger.info("User %s sent a message" % unicode(handle))
        content = re.sub('\r\n', '\n', message.content)
        content = re.sub('\r', '\n', content)
        self._signal_text_received(id, timestamp, handle, type, 0, message.display_name, content)
        self._recv_id += 1

    # papyon.event.ConversationEventInterface
    def on_conversation_nudge_received(self, sender):
        # We used to use (MESSAGE_TYPE_ACTION, "nudge") to send nudges, and our own
        # "$contact sent you a nudge" string when receiving, but that's not very nice.
        # We should implement this properly at some point. See fd.o#24699.
        handle = self._conn.ensure_contact_handle(sender)
        logger.info("User %s sent a nudge" % unicode(handle))

    # papyon.event.ConversationEventInterface
    def on_conversation_error(self, error_type, error):
        logger.warning("Conversation error %s %s" % (str(error_type),
            str(error)))
        if error_type == papyon.event.ConversationErrorType.MESSAGE:
            timestamp = int(time.time())
            self.SendError(telepathy.CHANNEL_TEXT_SEND_ERROR_UNKNOWN, timestamp,
                    telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL, "")

    @dbus.service.signal(telepathy.CHANNEL_INTERFACE_MESSAGES, signature='aa{sv}')
    def MessageReceived(self, message):
        id = message[0]['pending-message-id']
        self._pending_messages2[id] = dbus.Array(message, signature='a{sv}')
