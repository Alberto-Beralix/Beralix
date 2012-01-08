# ubuntuone.platform.linux.event_logging
#
# Author: Alejandro J. Cura <alecu@canonical.com>
#
# Copyright 2010 Canonical Ltd.
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
"""Builds a syncdaemon listener that logs events if ZG is installed."""

def is_zeitgeist_installed():
    """Return true if zeitgeist is installed."""
    try:
        import zeitgeist
        import zeitgeist.mimetypes
        # use the above module in some way so pylint does not complain
        assert(zeitgeist is not None)
        return True
    except (ImportError, AttributeError):
        return False

def get_listener(fsm, vm):
    """Build a listener if zg is installed."""
    if is_zeitgeist_installed():
        from ubuntuone.eventlog import zg_listener
        return zg_listener.ZeitgeistListener(fsm, vm)
    else:
        return None
