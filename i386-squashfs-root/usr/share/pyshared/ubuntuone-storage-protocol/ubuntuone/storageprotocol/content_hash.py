# ubuntuone.storageprotocol.content_hash - content hash handling
#
# Author: Lucio Torre <lucio.torre@canonical.com>
#         Natalia B. Bidart <natalia.bidart@canonical.com>
#
# Copyright 2009-2010 Canonical Ltd.
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

"""Hash Handling Stuffs."""

import copy
import hashlib
import zlib


class ContentHash(object):
    """Encapsulate the generation of content hashes.

    We cant subclass openssl hash classes, so we do some
    composition to get similar methods.

    """
    method = lambda: None
    method_name = ""

    def __init__(self):
        self.hash_object = self.method()

    digest_size = property(lambda self: self.hash_object.digest_size)
    block_size = property(lambda self: self.hash_object.block_size)
    update = property(lambda self: self.hash_object.update)
    digest = property(lambda self: self.hash_object.digest)
    hexdigest = property(lambda self: self.hash_object.hexdigest)

    def copy(self):
        """Copy the generated hash."""
        cp = copy.copy(self)
        cp.hash_object = self.hash_object.copy()
        return cp

    def content_hash(self):
        """Add hex digest to content hash."""
        return self.method_name + ":" + self.hash_object.hexdigest()


class SHA1ContentHash(ContentHash):
    """Generate SHA1 of ContentHash."""

    method = hashlib.sha1
    method_name = "sha1"


class HiddenMagicHash(object):
    """The magic hash value, hidden.

    You can access the value by the internal attribute '_magic_hash', but
    note that this is on your own risk: never show that value anywhere, and
    don't make it touch disk at all (in logs, dumps, or any kind of
    data storing).
    """
    def __init__(self, magic_hash):
        self._magic_hash = magic_hash

    def __getstate__(self):
        """Avoid pickling."""
        raise NotImplementedError("Magic value can not be pickled.")


class MagicContentHash(ContentHash):
    """Generate the magic hash."""

    method = hashlib.sha1
    method_name = "magic_hash"

    def __init__(self):
        self.hash_object = self.method()
        self.update("Ubuntu One")

    def digest(self):
        """Forbidden access."""
        raise NotImplementedError("Can not access magic digest.")
    hexdigest = digest

    def content_hash(self):
        """Add hex digest to content hash."""
        value = self.method_name + ":" + self.hash_object.hexdigest()
        return HiddenMagicHash(value)

    def __getstate__(self):
        """Avoid pickling."""
        raise NotImplementedError("Magic hasher can not be pickled.")


# we can change these variables to change the method
content_hash_factory = SHA1ContentHash
magic_hash_factory = MagicContentHash


def crc32(data, previous_crc32=0):
    """A correct crc32 function.

    Always returns positive values.

    """
    return zlib.crc32(data, previous_crc32) & 0xFFFFFFFFL
