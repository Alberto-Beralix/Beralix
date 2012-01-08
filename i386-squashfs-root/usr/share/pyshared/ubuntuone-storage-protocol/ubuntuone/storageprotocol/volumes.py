# -*- coding: utf-8 -*-
#
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
#
# Copyright 2009 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""The volumes abstraction."""

import uuid

from ubuntuone.storageprotocol import protocol_pb2

# these are valid, pylint: disable=C0103
_direction_prot2nice = {
    protocol_pb2.Shares.FROM_ME: "from_me",
    protocol_pb2.Shares.TO_ME:   "to_me",
}
_direction_nice2prot = dict((y, x) for x, y in _direction_prot2nice.items())

_access_prot2nice = {
    protocol_pb2.Shares.VIEW: "View",
    protocol_pb2.Shares.MODIFY: "Modify",
}
_access_nice2prot = dict((y, x) for x, y in _access_prot2nice.items())
# pylint: enable=C0103


class Volume(object):
    """A generic volume."""

    def __init__(self, volume_id, node_id, generation, free_bytes):
        """Create the volume."""
        self.volume_id = volume_id
        self.node_id = node_id
        self.generation = generation
        self.free_bytes = free_bytes

    @classmethod
    def from_params(cls, **kwargs):
        """Creates the object from given parameters."""
        result = cls(**kwargs)
        return result

    @classmethod
    def from_msg(cls, msg):
        """Creates the object using the information from a message."""
        raise NotImplementedError

    def __eq__(self, other):
        result = (self.volume_id == other.volume_id and
                  self.node_id == other.node_id and
                  self.free_bytes == other.free_bytes and
                  self.generation == other.generation)
        return result


class ShareVolume(Volume):
    """A volume representing an accepted Share."""

    def __init__(self, volume_id, node_id, generation,
                 free_bytes, direction, share_name,
                 other_username, other_visible_name, accepted, access_level):
        """Create the share."""
        super(ShareVolume, self).__init__(volume_id, node_id,
                                          generation, free_bytes)
        self.direction = direction
        self.share_name = share_name
        self.other_username = other_username
        self.other_visible_name = other_visible_name
        self.accepted = accepted
        self.access_level = access_level

    @classmethod
    def from_msg(cls, msg):
        """Creates the object using the information from a message."""
        kwargs = dict(
            volume_id=uuid.UUID(msg.share_id),
            node_id=uuid.UUID(msg.subtree),
            generation=msg.generation,
            free_bytes=msg.free_bytes,
            direction=_direction_prot2nice[msg.direction],
            share_name=msg.share_name,
            other_username=msg.other_username,
            other_visible_name=msg.other_visible_name,
            accepted=msg.accepted,
            access_level=_access_prot2nice[msg.access_level])
        result = cls(**kwargs)
        return result

    def __eq__(self, other):
        result = (super(ShareVolume, self).__eq__(other) and
                  self.direction == other.direction and
                  self.share_name == other.share_name and
                  self.other_username == other.other_username and
                  self.other_visible_name == other.other_visible_name and
                  self.accepted == other.accepted and
                  self.access_level == other.access_level)
        return result


class UDFVolume(Volume):
    """A volume representing a User Defined Folder."""

    def __init__(self, volume_id, node_id, generation,
                 free_bytes, suggested_path):
        """Create the UDF."""
        super(UDFVolume, self).__init__(volume_id, node_id,
                                        generation, free_bytes)
        self.suggested_path = suggested_path

    @classmethod
    def from_msg(cls, msg):
        """Creates the object using the information from a message."""
        kwargs = dict(
            volume_id=uuid.UUID(msg.volume),
            node_id=uuid.UUID(msg.node),
            generation=msg.generation,
            free_bytes=msg.free_bytes,
            suggested_path=msg.suggested_path)
        result = cls(**kwargs)
        return result

    def __eq__(self, other):
        result = (super(UDFVolume, self).__eq__(other) and
                  self.suggested_path == other.suggested_path)
        return result


class RootVolume(Volume):
    """A volume representing a Root-root."""

    def __init__(self, node_id, generation, free_bytes):
        """Create the volume."""
        super(RootVolume, self).__init__(
            volume_id=None, node_id=node_id,
            generation=generation,
            free_bytes=free_bytes)

    @classmethod
    def from_msg(cls, msg):
        """Creates the object using the information from a message."""
        kwargs = dict(
            node_id=uuid.UUID(msg.node),
            generation=msg.generation,
            free_bytes=msg.free_bytes)
        result = cls(**kwargs)
        return result
