# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
#
# Copyright 2011 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The base object that holds a backend instance."""

from ubuntuone.controlpanel import backend


class Cache(object):
    """The base object that caches stuff."""

    logger = None
    _shared_objects = {}

    def __init__(self, *args, **kwargs):
        """Initialize the object using 'backend' as backend."""
        super(Cache, self).__init__()
        if self.logger is not None:
            self.logger.debug('%s: started.', self.__class__.__name__)

    def get_backend(self):
        """A cached ControlBackend instance."""
        if not self._shared_objects:
            self._shared_objects['backend'] = backend.ControlBackend()
        return self._shared_objects['backend']

    def set_backend(self, new_value):
        """Set a new ControlBackend instance."""
        self._shared_objects['backend'] = new_value

    backend = property(fget=get_backend, fset=set_backend)

    def clear(self):
        """Clear all cached objects."""
        self._shared_objects = {}
