# ubuntuone.syncdaemon.mute_filter - Mute Filter
#
# Author: Facundo Batista <facundo@canonical.com>
#
# Copyright 2009, 2010 Canonical Ltd.
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

"""Class that filters and mutes some events on some paths."""

import logging

class MuteFilter(object):
    """Stores what needs to be muted."""
    def __init__(self):
        self._cnt = {}
        self.log = logging.getLogger('ubuntuone.SyncDaemon.MuteFilter')

    def add(self, event, **data):
        """Add an event and data to the filter."""
        self.log.debug("Adding: %s %s", event, data)
        self._cnt.setdefault(event, []).append(data)

    def rm(self, event, **data):
        """Remove an event and data from the filter."""
        self.log.debug("Removing: %s %s", event, data)
        data_list = self._cnt[event]
        data_list.remove(data)
        if not data_list:
            del self._cnt[event]

    def pop(self, event, **data):
        """Pop an event and data from the filter, if there.

        Return if the event/data was in the filter at all.
        """
        try:
            data_list = self._cnt[event]
        except KeyError:
            return False

        try:
            data_list.remove(data)
        except ValueError:
            return False

        if not data_list:
            # reached zero
            del self._cnt[event]

        # log what happened and how many items we have left
        q = sum(len(x) for x in self._cnt.itervalues())
        self.log.debug("Blocking %s %s (%d left)", event, data, q)

        return True
