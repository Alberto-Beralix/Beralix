#
# Author: Alejandro J. Cura <alecu@canonical.com>
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

"""Inhibit session logout when busy."""

from twisted.internet import defer

INHIBIT_LOGGING_OUT = 1
INHIBIT_USER_SWITCHING = 2
INHIBIT_SUSPENDING_COMPUTER = 4
INHIBIT_SESSION_IDLE = 8
INHIBIT_LOGOUT_SUSPEND = INHIBIT_LOGGING_OUT | INHIBIT_SUSPENDING_COMPUTER


class Inhibitor(object):
    """An object representing an inhibition, that can be cancelled."""

    def inhibit(self, flags, reason):
        """Inhibit some events with a given reason."""
        return defer.succeed(None)

    def cancel(self):
        """Cancel the inhibition for the current cookie."""
        return defer.succeed(None)


def inhibit_logout_suspend(reason):
    """Inhibit the suspend and logout. The result can be cancelled."""
    return Inhibitor().inhibit(INHIBIT_LOGOUT_SUSPEND, reason)
