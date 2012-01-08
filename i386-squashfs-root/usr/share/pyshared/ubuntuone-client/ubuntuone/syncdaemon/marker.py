# ubuntuone.syncdaemon.marker - marker for MDIDs
#
# Author: Lucio Torre <lucio.torre@canonical.com>
#
# Copyright 2009 Canonical Ltd.
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
""" a marker for mdids """

from zope.interface import implements

from ubuntuone.syncdaemon.interfaces import IMarker

class MDMarker(str):
    """A marker that has the mdid inside, for action queue."""
    implements(IMarker)

    def __repr__(self):
        return "marker:%s" % self
