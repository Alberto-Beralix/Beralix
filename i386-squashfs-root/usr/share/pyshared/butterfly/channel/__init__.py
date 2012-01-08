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

from butterfly.handle import ButterflyHandleFactory

__all__ = ['ButterflyChannel']

logger = logging.getLogger('Butterfly.Channel')

class ButterflyChannel(object):
    def __init__(self, conn, props):
        # If we have InitiatorHandle set in our new channel, use that,
        if telepathy.CHANNEL_INTERFACE + '.InitiatorHandle' in props:
            self._initiator = conn.handle(telepathy.HANDLE_TYPE_CONTACT,
                props[telepathy.CHANNEL_INTERFACE + '.InitiatorHandle'])

        # otherwise use InitiatorID.
        elif telepathy.CHANNEL_INTERFACE + '.InitiatorID' in props:
            self._initiator = conn.ensure_handle(telepathy.HANDLE_TYPE_CONTACT,
                props[telepathy.CHANNEL_INTERFACE + '.InitiatorID'])

        # If we don't have either of the above but we requested the channel,
        # then we're the initiator.
        elif props[telepathy.CHANNEL_INTERFACE + '.Requested']:
            self._initiator = conn.GetSelfHandle()

        else:
            logger.warning('InitiatorID or InitiatorHandle not set on new channel')
            self._initiator = None

        # Don't implement the initiator properties if we don't have one.
        if self._initiator:
            self._implement_property_get(telepathy.CHANNEL_INTERFACE, {
                    'InitiatorHandle': lambda: dbus.UInt32(self._initiator.id),
                    'InitiatorID': lambda: self._initiator.name
                    })

            self._add_immutable_properties({
                    'InitiatorHandle': telepathy.CHANNEL_INTERFACE,
                    'InitiatorID': telepathy.CHANNEL_INTERFACE,
                    })
