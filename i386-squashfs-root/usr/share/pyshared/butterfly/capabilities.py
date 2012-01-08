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

import logging
import dbus

import telepathy
import papyon
import papyon.event

from butterfly.util.decorator import async

__all__ = ['ButterflyCapabilities']

logger = logging.getLogger('Butterfly.Capabilities')

class ButterflyCapabilities(
        telepathy.server.ConnectionInterfaceCapabilities,
        telepathy.server.ConnectionInterfaceContactCapabilities,
        papyon.event.ContactEventInterface):

    text_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_TEXT,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID'])

    audio_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialAudio'])

    av_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialAudio',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialVideo'])

    file_transfer_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_FILE_TRANSFER,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Requested',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Filename',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.Size',
          telepathy.CHANNEL_TYPE_FILE_TRANSFER + '.ContentType'])


    def __init__(self):
        telepathy.server.ConnectionInterfaceCapabilities.__init__(self)
        telepathy.server.ConnectionInterfaceContactCapabilities.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, self.msn_client)

        self._video_clients = []
        self._update_capabilities_calls = []


    ### Events handling ------------------------------------------------------

    # papyon.event.ContactEventInterface
    def on_contact_client_capabilities_changed(self, contact):
        handle = self.ensure_contact_handle(contact)
        if handle == self._self_handle:
            return # don't update our own capabilities using server ones
        self._update_capabilities(handle)
        self._update_contact_capabilities([handle])

    # papyon.event.AddressBookEventInterface
    def on_addressbook_contact_added(self, contact):
        """When we add a contact in our contact list, add the
        default capabilities to the contact"""
        if contact.is_member(papyon.Membership.FORWARD):
            handle = self.ensure_contact_handle(contact)
            self._add_default_capabilities([handle])
            self._update_contact_capabilities([handle])


    ### Capabilities interface -----------------------------------------------

    def _get_capabilities(self, contact):
        gen_caps = 0
        spec_caps = 0
        caps = contact.client_capabilities

        if caps.supports_sip_invite:
            gen_caps |= telepathy.CONNECTION_CAPABILITY_FLAG_CREATE
            gen_caps |= telepathy.CONNECTION_CAPABILITY_FLAG_INVITE
            spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_AUDIO
            spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_NAT_TRAVERSAL_STUN
            if caps.has_webcam:
                spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_VIDEO

        return gen_caps, spec_caps

    def _add_default_capabilities(self, handles):
        """Add the default capabilities to these contacts."""
        ret = []
        for handle in handles:
            new_flag = telepathy.CONNECTION_CAPABILITY_FLAG_CREATE

            ctype = telepathy.CHANNEL_TYPE_TEXT
            diff = self._diff_capabilities(handle, ctype, added_gen=new_flag)
            ret.append(diff)

            ctype = telepathy.CHANNEL_TYPE_FILE_TRANSFER
            diff = self._diff_capabilities(handle, ctype, added_gen=new_flag)
            ret.append(diff)

        self.CapabilitiesChanged(ret)

    def _update_capabilities(self, handle):
        ctype = telepathy.CHANNEL_TYPE_STREAMED_MEDIA

        new_gen, new_spec = self._get_capabilities(handle.contact)
        diff = self._diff_capabilities(handle, ctype, new_gen, new_spec)
        if diff is not None:
            self.CapabilitiesChanged([diff])


    ### ContactCapabilities interface ----------------------------------------

    def AdvertiseCapabilities(self, add, remove):
        for caps, specs in add:
            if caps == telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
                if specs & telepathy.CHANNEL_MEDIA_CAPABILITY_VIDEO:
                    self._msn_client.profile.client_id.has_webcam = True
                    self._msn_client.profile.client_id.supports_rtc_video = True
        for caps in remove:
            if caps == telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
                self._msn_client.profile.client_id.has_webcam = False

        return telepathy.server.ConnectionInterfaceCapabilities.\
            AdvertiseCapabilities(self, add, remove)

    def UpdateCapabilities(self, caps):
        if self._status != telepathy.CONNECTION_STATUS_CONNECTED:
            self._update_capabilities_calls.append(caps)
            return

        # We only care about voip.
        for client, classes, capabilities in caps:
            video = False
            for channel_class in classes:
                # Does this client support video?
                if channel_class[telepathy.CHANNEL_INTERFACE + '.ChannelType'] == \
                        telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
                    video = True
                    break

            if video and client not in self._video_clients:
                self._video_clients.append(client)
            elif not video and client in self._video_clients:
                # *Did* it used to support video?
                self._video_clients.remove(client)

        video = (len(self._video_clients) > 0)
        changed = False

        # We've got no more clients that support video; remove the cap.
        if not video and not self._video_clients:
            self._msn_client.profile.client_id.has_webcam = False
            changed = True

        # We want video.
        if video and (not self._msn_client.profile.client_id.has_webcam or
           not self._msn_client.profile.client_id.supports_rtc_video):
            self._msn_client.profile.client_id.has_webcam = True
            self._msn_client.profile.client_id.supports_rtc_video = True
            changed = True

        # Signal.
        if changed:
            updated = dbus.Dictionary({self._self_handle: self._contact_caps[self._self_handle]},
                signature='ua(a{sv}as)')
            self.ContactCapabilitiesChanged(updated)

    def _get_contact_capabilities(self, contact):
        contact_caps = []
        caps = contact.client_capabilities

        contact_caps.append(self.text_chat_class)
        contact_caps.append(self.file_transfer_class)
        if caps.supports_sip_invite:
            if caps.has_webcam:
                contact_caps.append(self.av_chat_class)
            else:
                contact_caps.append(self.audio_chat_class)

        return contact_caps

    def _update_contact_capabilities(self, handles):
        caps = {}
        for handle in handles:
            caps[handle] = self._get_contact_capabilities(handle.contact)
            self._contact_caps[handle] = caps[handle] # update global dict
        ret = dbus.Dictionary(caps, signature='ua(a{sv}as)')
        self.ContactCapabilitiesChanged(ret)


    ### Initialization -------------------------------------------------------

    @async
    def _populate_capabilities(self):
        """ Add the default capabilities to all contacts in our
        contacts list."""
        handles = set([self._self_handle])
        for contact in self.msn_client.address_book.contacts:
            if contact.is_member(papyon.Membership.FORWARD):
                handle = self.ensure_contact_handle(contact)
                handles.add(handle)
        self._add_default_capabilities(handles)
        self._update_contact_capabilities(handles)

        # These caps were updated before we were online.
        for caps in self._update_capabilities_calls:
            self.UpdateCapabilities(caps)
        self._update_capabilities_calls = []
