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

import dbus
import telepathy
import telepathy.constants
import papyon
from papyon.service.description.AB.constants import \
    ContactGeneral, ContactAnnotations

from butterfly.util.decorator import async

__all__ = ['ButterflyAliasing']

logger = logging.getLogger('Butterfly.Aliasing')

class ButterflyAliasing(
        telepathy.server.ConnectionInterfaceAliasing,
        papyon.event.ContactEventInterface,
        papyon.event.ProfileEventInterface):

    def __init__(self):
        telepathy.server.ConnectionInterfaceAliasing.__init__(self)
        papyon.event.ContactEventInterface.__init__(self, self.msn_client)
        papyon.event.ProfileEventInterface.__init__(self, self.msn_client)

    def GetAliasFlags(self):
        return telepathy.constants.CONNECTION_ALIAS_FLAG_USER_SET

    def RequestAliases(self, contacts):
        logger.debug("Called RequestAliases")
        return [self._get_alias(handle_id) for handle_id in contacts]

    def GetAliases(self, contacts):
        logger.debug("Called GetAliases")

        result = dbus.Dictionary(signature='us')
        for contact in contacts:
            result[contact] = self._get_alias(contact)
        return result

    def SetAliases(self, aliases):
        for handle_id, alias in aliases.iteritems():
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            if handle != self._self_handle:
                if alias == handle.name:
                    alias = u""
                contact = handle.contact
                if contact is None or \
                        (not contact.is_member(papyon.Membership.FORWARD)):
                    handle.pending_alias = alias
                    continue

                new_alias = alias.encode("utf-8")
                old_alias = contact.infos.get(ContactGeneral.ANNOTATIONS, {}).\
                    get(ContactAnnotations.NICKNAME, None)
                if new_alias == old_alias:
                    continue

                infos = {ContactGeneral.ANNOTATIONS :
                            {ContactAnnotations.NICKNAME : new_alias}
                        }
                self.msn_client.address_book.update_contact_infos(contact, infos)
            else:
                self.msn_client.profile.display_name = alias.encode('utf-8')
                logger.info("Self alias changed to '%s'" % alias)
                self.AliasesChanged(((self._self_handle, alias), ))

    # papyon.event.ContactEventInterface
    def on_contact_display_name_changed(self, contact):
        self._contact_alias_changed(contact)

    # papyon.event.ContactEventInterface
    def on_contact_infos_changed(self, contact, updated_infos):
        alias = updated_infos.get(ContactGeneral.ANNOTATIONS, {}).\
            get(ContactAnnotations.NICKNAME, None)

        if alias is not None or alias != "":
            self._contact_alias_changed(contact)

    # papyon.event.ContactEventInterface
    def on_contact_memberships_changed(self, contact):
        handle = self.ensure_contact_handle(contact)
        if contact.is_member(papyon.Membership.FORWARD):
            alias = handle.pending_alias
            if alias is not None:
                infos = {ContactGeneral.ANNOTATIONS : \
                            {ContactAnnotations.NICKNAME : alias.encode('utf-8')}
                        }
                self.msn_client.address_book.\
                    update_contact_infos(contact, infos)
                handle.pending_alias = None

    # papyon.event.ProfileEventInterface
    def on_profile_display_name_changed(self):
        self._contact_alias_changed(self.msn_client.profile)

    def _get_alias(self, handle_id):
        """Get the alias from one handle id"""
        handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        if handle == self._self_handle:
            display_name = self.msn_client.profile.display_name
            if display_name == "":
                display_name = handle.get_name().split('@', 1)[0]
                display_name = display_name.replace("_", " ")
            alias = unicode(display_name, 'utf-8')
        else:
            contact = handle.contact
            if handle.pending_alias is not None:
                alias = handle.pending_alias
            elif contact is None:
                alias = handle.account
            else:
                alias = contact.infos.get(ContactGeneral.ANNOTATIONS, {}).\
                    get(ContactAnnotations.NICKNAME, None)
                if alias == "" or alias is None:
                     alias = contact.display_name
                alias = unicode(alias, 'utf-8')
        return alias

    @async
    def _contact_alias_changed(self, contact):
        alias = None

        handle = self.ensure_contact_handle(contact)
        if handle != self._self_handle:
            alias = contact.infos.get(ContactGeneral.ANNOTATIONS, {}).\
                get(ContactAnnotations.NICKNAME, None)

        if alias == "" or alias is None:
            alias = contact.display_name

        alias = unicode(alias, 'utf-8')
        logger.info("Contact %s alias changed to '%s'" % (unicode(handle), alias))
        self.AliasesChanged([(handle, alias)])

