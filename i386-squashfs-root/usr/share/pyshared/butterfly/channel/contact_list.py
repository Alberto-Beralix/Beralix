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

import logging
import weakref

import telepathy
import papyon
import papyon.event

from butterfly.util.decorator import async
from butterfly.channel import ButterflyChannel

__all__ = ['ButterflyContactListChannelFactory']

logger = logging.getLogger('Butterfly.ContactListChannel')

class HandleMutex(object):
    def __init__(self):
        self._handles = set()
        self._keys = {}
        self._callbacks = {}

    def is_locked(self, handle):
        return (handle in self._handles)

    def is_owned(self, key, handle):
        return (handle in self._handles and self._keys[handle] == key)

    def lock(self, key, handle):
        if self.is_locked(handle):
            return False
        self._handles.add(handle)
        self._keys[handle] = key
        return True

    def unlock(self, key, handle):
        if not self.is_owned(key, handle):
            return
        self._handles.remove(handle)
        del self._keys[handle]
        callbacks = self._callbacks.get(handle, [])[:]
        self._callbacks[handle] = []
        for callback in callbacks:
            callback[0](*callback[1:])

    def add_callback(self, key, handle, callback):
        if self.is_owned(key, handle):
            return
        if not self.is_locked(handle):
            callback[0](*callback[1:])
        else:
            self._callbacks.setdefault(handle, []).append(callback)

class Lockable(object):
    def __init__(self, mutex, key, cb_name):
        self._mutex = mutex
        self._key = key
        self._cb_name = cb_name

    def __call__(self, func):
        def method(object, handle, *args, **kwargs):
            def finished_cb(*user_data):
                self._mutex.unlock(self._key, handle)

            def unlocked_cb():
                self._mutex.lock(self._key, handle)
                kwargs[self._cb_name] = finished_cb
                if func(object, handle, *args, **kwargs):
                    finished_cb()

            self._mutex.add_callback(self._key, handle, (unlocked_cb,))

        return method

mutex = HandleMutex()


def ButterflyContactListChannelFactory(connection, manager, handle, props):
    handle = connection.handle(
        props[telepathy.CHANNEL_INTERFACE + '.TargetHandleType'],
        props[telepathy.CHANNEL_INTERFACE + '.TargetHandle'])

    if handle.get_name() == 'stored':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'subscribe':
        channel_class = ButterflySubscribeListChannel
    elif handle.get_name() == 'publish':
        channel_class = ButterflyPublishListChannel
    elif handle.get_name() == 'hide':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'allow':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'deny':
        raise telepathy.errors.NotImplemented
    else:
        logger.error("Unknown list type : " + handle.get_name())
        raise telepathy.errors.InvalidHandle
    return channel_class(connection, manager, props)


class ButterflyListChannel(
        ButterflyChannel,
        telepathy.server.ChannelTypeContactList,
        telepathy.server.ChannelInterfaceGroup,
        papyon.event.AddressBookEventInterface):
    "Abstract Contact List channels"

    def __init__(self, connection, manager, props, object_path=None):
        self._conn_ref = weakref.ref(connection)
        telepathy.server.ChannelTypeContactList.__init__(self, connection, manager, props,
            object_path=object_path)
        ButterflyChannel.__init__(self, connection, props)
        telepathy.server.ChannelInterfaceGroup.__init__(self)
        papyon.event.AddressBookEventInterface.__init__(self, connection.msn_client)
        self._populate(connection)

    def GetLocalPendingMembersWithInfo(self):
        return []

    # papyon.event.AddressBookEventInterface
    def on_addressbook_contact_added(self, contact):
        added = set()
        local_pending = set()
        remote_pending = set()

        ad, lp, rp = self._filter_contact(contact)
        if ad or lp or rp:
            handle = self._conn.ensure_contact_handle(contact)
            if ad: added.add(handle)
            if lp: local_pending.add(handle)
            if rp: remote_pending.add(handle)
            msg = contact.attributes.get('invite_message', '')
            self.MembersChanged(msg, added, (), local_pending, remote_pending, 0,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    # papyon.event.AddressBookEventInterface
    def on_addressbook_contact_deleted(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        ad, lp, rp = self._filter_contact(contact)
        if self._contains_handle(handle) and not ad:
            self.MembersChanged('', (), [handle], (), (), 0,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    # papyon.event.AddressBookEventInterface
    def on_addressbook_contact_blocked(self, contact):
        pass

    # papyon.event.AddressBookEventInterface
    def on_addressbook_contact_unblocked(self, contact):
        pass

    @async
    def _populate(self, connection):
        added = set()
        local_pending = set()
        remote_pending = set()

        for contact in connection.msn_client.address_book.contacts:
            ad, lp, rp = self._filter_contact(contact)
            if ad or lp or rp:
                handle = self._conn.ensure_contact_handle(contact)
                if ad: added.add(handle)
                if lp: local_pending.add(handle)
                if rp: remote_pending.add(handle)
        self.MembersChanged('', added, (), local_pending, remote_pending, 0,
                telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    def _filter_contact(self, contact):
        return (False, False, False)

    def _contains_handle(self, handle):
        members, local_pending, remote_pending = self.GetAllMembers()
        return (handle in members) or (handle in local_pending) or \
                (handle in remote_pending)


class ButterflySubscribeListChannel(ButterflyListChannel,
        papyon.event.ContactEventInterface):
    """Subscribe List channel.

    This channel contains the list of contact to whom the current used is
    'subscribed', basically this list contains the contact for whom you are
    supposed to receive presence notification."""

    def __init__(self, connection, manager, props):
        ButterflyListChannel.__init__(self, connection, manager, props,
            object_path='RosterChannel/List/subscribe')
        papyon.event.ContactEventInterface.__init__(self, connection.msn_client)
        self.GroupFlagsChanged(telepathy.CHANNEL_GROUP_FLAG_CAN_ADD |
                telepathy.CHANNEL_GROUP_FLAG_CAN_REMOVE, 0)

    def AddMembers(self, contacts, message):
        for h in contacts:
            self._add(h, message)

    def RemoveMembers(self, contacts, message):
        for h in contacts:
            self._remove(h)

    def _filter_contact(self, contact):
        return (contact.is_member(papyon.Membership.FORWARD) and not
                contact.is_member(papyon.Membership.PENDING), False, False)

    @Lockable(mutex, 'add_subscribe', 'finished_cb')
    def _add(self, handle_id, message, finished_cb):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        if handle is self._conn.GetSelfHandle():
            return True # don't add ourself
        if handle.contact is not None and \
           handle.contact.is_member(papyon.Membership.FORWARD):
            return True # contact already there

        account = handle.account
        network = handle.network
        groups = list(handle.pending_groups)
        handle.pending_groups = set()
        ab = self._conn.msn_client.address_book

        # We redefine these two callbacks for two reasons:
        #
        #  1. For failed, we can give a nice warning.
        #
        #  2. For both callbacks, it is more than likely that calling
        #     finished_cb() will unlock the mutex and the publish
        #     channel underneath's _add function will be called. If we
        #     keep handle in scope, it won't be disposed and the
        #     publish channel will have the same handle. This fixes a
        #     few bugs:
        #
        #      I. When the contact doesn't actually exist, calling
        #         finished_cb after the handle gets disposed means it
        #         will no longer be in the connection's handle
        #         dictionary and the publish channel's _add() will
        #         raise InvalidHandle (see fd.o#27553). This isn't
        #         actually a problem as the function should return
        #         anyway but it doesn't get a chance to unlock the
        #         mutex and it throws an unhandled exception which
        #         apport users think is crazy.
        #
        #     II. Similar to above, but when the contact does
        #         actually exist then the publish list wants to act
        #         appropriately. If the handle has already been
        #         disposed then it'll raise the same exception and
        #         won't call the appropriate AB method.
        #
        #    III. When a contact is actually added, instead of the
        #         handle already having been disposed of, it stays
        #         around for a bit so you don't add handle n and then
        #         MembersChanged gets fired for handle n+1.
        #
        # If these cases aren't in fact in play when this is called,
        # then not only am I surprised, but no damage is done.

        def failed_cb(error_code, *cb_args):
            logger.warning('Failed to add messenger contact; '
                           'error code: %s' % error_code)
            finished_cb()
            handle

        def done_cb(*cb_args):
            finished_cb()
            handle

        ab.add_messenger_contact(account,
                network_id=network,
                auto_allow=False,
                invite_message=message.encode('utf-8'),
                groups=groups,
                done_cb=(done_cb,),
                failed_cb=(failed_cb,))

    @Lockable(mutex, 'rem_subscribe', 'finished_cb')
    def _remove(self, handle_id, finished_cb):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        contact = handle.contact
        if handle is self._conn.GetSelfHandle():
            return True # don't try to remove ourself
        if contact is None or not contact.is_member(papyon.Membership.FORWARD):
            return True # contact not in address book

        ab = self._conn.msn_client.address_book
        ab.delete_contact(contact, done_cb=(finished_cb,),
                failed_cb=(finished_cb,))

    # papyon.event.ContactEventInterface
    def on_contact_memberships_changed(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        if contact.is_member(papyon.Membership.FORWARD):
            self.MembersChanged('', [handle], (), (), (), 0,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED)
            if len(handle.pending_groups) > 0:
                ab = self._conn.msn_client.address_book
                for group in handle.pending_groups:
                    ab.add_contact_to_group(group, contact)
                handle.pending_groups = set()


class ButterflyPublishListChannel(ButterflyListChannel,
        papyon.event.ContactEventInterface):

    def __init__(self, connection, manager, props):
        ButterflyListChannel.__init__(self, connection, manager, props,
            object_path='RosterChannel/List/publish')
        papyon.event.ContactEventInterface.__init__(self, connection.msn_client)
        self.GroupFlagsChanged(telepathy.CHANNEL_GROUP_FLAG_CAN_ADD |
                telepathy.CHANNEL_GROUP_FLAG_CAN_REMOVE, 0)

    def AddMembers(self, contacts, message):
        for handle_id in contacts:
            self._add(handle_id, message)

    def RemoveMembers(self, contacts, message):
        for handle_id in contacts:
            self._remove(handle_id)

    def GetLocalPendingMembersWithInfo(self):
        result = []
        for contact in self._conn.msn_client.address_book.contacts:
            if not contact.is_member(papyon.Membership.PENDING):
                continue
            handle = self._conn.ensure_contact_handle(contact)
            result.append((handle, handle,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED,
                    contact.attributes.get('invite_message', '')))
        return result

    def _filter_contact(self, contact):
        return (contact.is_member(papyon.Membership.ALLOW),
                contact.is_member(papyon.Membership.PENDING),
                False)

    @Lockable(mutex, 'add_publish', 'finished_cb')
    def _add(self, handle_id, message, finished_cb):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        contact = handle.contact
        if handle is self._conn.GetSelfHandle():
            return True # don't add ourself
        if contact is not None and contact.is_member(papyon.Membership.ALLOW):
            return True # contact is already allowed
        if contact is None:
            logger.debug('Cannot allow/accept None contact %s' % handle.get_name())
            return True # contact doesn't actually exist

        account = handle.account
        network = handle.network
        ab = self._conn.msn_client.address_book
        if contact is not None and contact.is_member(papyon.Membership.PENDING):
            ab.accept_contact_invitation(contact, False,
                    done_cb=(finished_cb,), failed_cb=(finished_cb,))
        else:
            ab.allow_contact(account, network,
                    done_cb=(finished_cb,), failed_cb=(finished_cb,))

    @Lockable(mutex, 'rem_publish', 'finished_cb')
    def _remove(self, handle_id, finished_cb):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        contact = handle.contact
        ab = self._conn.msn_client.address_book
        if handle is self._conn.GetSelfHandle():
            return True # don't try to remove ourself
        if contact.is_member(papyon.Membership.PENDING):
            ab.decline_contact_invitation(contact, False, done_cb=(finished_cb,),
                    failed_cb=(finished_cb,))
        elif contact.is_member(papyon.Membership.ALLOW):
            ab.disallow_contact(contact, done_cb=(finished_cb,),
                    failed_cb=(finished_cb,))
        else:
            return True # contact is neither pending or allowed

    # papyon.event.ContactEventInterface
    def on_contact_memberships_changed(self, contact):
        handle = self._conn.ensure_contact_handle(contact)
        if self._contains_handle(handle):
            if contact.is_member(papyon.Membership.PENDING):
                # Nothing worth our attention
                return

            if contact.is_member(papyon.Membership.ALLOW):
                # Contact accepted
                self.MembersChanged('', [handle], (), (), (), 0,
                        telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED)
            else:
                # Contact rejected
                self.MembersChanged('', (), [handle], (), (), 0,
                        telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)
