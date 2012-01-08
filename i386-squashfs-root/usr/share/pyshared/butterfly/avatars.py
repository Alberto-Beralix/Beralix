# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2007 Johann Prieur <johann.prieur@gmail.com>
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
import imghdr
import hashlib
import dbus

import telepathy
import papyon
import papyon.event
import papyon.util.string_io as StringIO

from butterfly.util.decorator import async

__all__ = ['ButterflyAvatars']

logger = logging.getLogger('Butterfly.Avatars')

SUPPORTED_AVATAR_MIME_TYPES = dbus.Array(["image/png", "image/jpeg",
    "image/gif"], signature='s')
MINIMUM_AVATAR_PIXELS = dbus.UInt32(96)
RECOMMENDED_AVATAR_PIXELS = dbus.UInt32(96)
MAXIMUM_AVATAR_PIXELS = dbus.UInt32(192)
MAXIMUM_AVATAR_BYTES = dbus.UInt32(500 * 1024)

class ButterflyAvatars(\
        telepathy.server.ConnectionInterfaceAvatars,
        papyon.event.ContactEventInterface,
        papyon.event.ProfileEventInterface):

    def __init__(self):
        self._avatar_known = False
        telepathy.server.ConnectionInterfaceAvatars.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, self.msn_client)
        papyon.event.ProfileEventInterface.__init__(self, self.msn_client)

        dbus_interface = telepathy.CONNECTION_INTERFACE_AVATARS
        self._implement_property_get(dbus_interface, {
            'SupportedAvatarMIMETypes':
                lambda: SUPPORTED_AVATAR_MIME_TYPES,
            'MinimumAvatarHeight': lambda: MINIMUM_AVATAR_PIXELS,
            'MinimumAvatarWidth': lambda: MINIMUM_AVATAR_PIXELS,
            'RecommendedAvatarHeight': lambda: RECOMMENDED_AVATAR_PIXELS,
            'RecommendedAvatarWidth': lambda: RECOMMENDED_AVATAR_PIXELS,
            'MaximumAvatarHeight': lambda: MAXIMUM_AVATAR_PIXELS,
            'MaximumAvatarWidth': lambda: MAXIMUM_AVATAR_PIXELS,
            'MaximumAvatarBytes': lambda: MAXIMUM_AVATAR_BYTES,
            })

    def GetAvatarRequirements(self):
        return (SUPPORTED_AVATAR_MIME_TYPES,
                MINIMUM_AVATAR_PIXELS, MINIMUM_AVATAR_PIXELS,
                MAXIMUM_AVATAR_PIXELS, MAXIMUM_AVATAR_PIXELS,
                MAXIMUM_AVATAR_BYTES)

    def GetKnownAvatarTokens(self, contacts):
        result = {}
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            contact = handle.contact

            if contact is not None:
                msn_object = contact.msn_object
            else:
                msn_object = None

            if msn_object is not None:
                result[handle] = msn_object._data_sha.encode("hex")
            elif self._avatar_known:
                result[handle] = ""
        return result

    def RequestAvatars(self, contacts):
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            if handle == self._self_handle:
                contact = self.msn_client.profile
            else:
                contact = handle.contact
            if contact is not None:
                msn_object = contact.msn_object
                self.msn_client.msn_object_store.request(msn_object,
                        (self._msn_object_retrieved, handle), peer=contact)

    def SetAvatar(self, avatar, mime_type):
        self._avatar_known = True
        if not isinstance(avatar, str):
            avatar = "".join([chr(b) for b in avatar])
        msn_object = papyon.p2p.MSNObject(self.msn_client.profile,
                         len(avatar),
                         papyon.p2p.MSNObjectType.DISPLAY_PICTURE,
                         hashlib.sha1(avatar).hexdigest() + '.tmp',
                         "",
                         data=StringIO.StringIO(avatar))
        self.msn_client.profile.msn_object = msn_object
        avatar_token = msn_object._data_sha.encode("hex")
        logger.info("Setting self avatar to %s" % avatar_token)
        return avatar_token

    def ClearAvatar(self):
        self.msn_client.profile.msn_object = None
        self._avatar_known = True

    # papyon.event.ContactEventInterface
    def on_contact_msn_object_changed(self, contact):
        if contact.msn_object is not None:
            avatar_token = contact.msn_object._data_sha.encode("hex")
        else:
            avatar_token = ""
        handle = self.ensure_contact_handle(contact)
        self.AvatarUpdated(handle, avatar_token)

    # papyon.event.ProfileEventInterface
    def on_profile_msn_object_changed(self):
        msn_object = self.msn_client.profile.msn_object
        if msn_object is not None:
            avatar_token = msn_object._data_sha.encode("hex")
            logger.info("Self avatar changed to %s" % avatar_token)
            handle = self._self_handle
            self.AvatarUpdated(handle, avatar_token)

    @async
    def _msn_object_retrieved(self, msn_object, handle):
        if msn_object is not None and msn_object._data is not None:
            logger.info("Avatar retrieved %s" % msn_object._data_sha.encode("hex"))
            msn_object._data.seek(0, 0)
            avatar = msn_object._data.read()
            msn_object._data.seek(0, 0)
            type = imghdr.what('', avatar)
            if type is None: type = 'jpeg'
            avatar = dbus.ByteArray(avatar)
            token = msn_object._data_sha.encode("hex")
            self.AvatarRetrieved(handle, token, avatar, 'image/' + type)
        else:
            logger.info("Avatar retrieved but NULL")
