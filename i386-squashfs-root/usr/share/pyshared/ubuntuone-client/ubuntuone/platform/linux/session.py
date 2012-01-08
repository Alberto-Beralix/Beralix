# ubuntuone.platform.linux.session
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
"""Inhibit session logout when busy thru the Gnome Session DBus service."""

import dbus

from twisted.internet import defer

SESSION_MANAGER_BUSNAME = "org.gnome.SessionManager"
SESSION_MANAGER_IFACE = "org.gnome.SessionManager"
SESSION_MANAGER_PATH = "/org/gnome/SessionManager"

INHIBIT_LOGGING_OUT = 1
INHIBIT_USER_SWITCHING = 2
INHIBIT_SUSPENDING_COMPUTER = 4
INHIBIT_SESSION_IDLE = 8
INHIBIT_LOGOUT_SUSPEND = INHIBIT_LOGGING_OUT | INHIBIT_SUSPENDING_COMPUTER

APP_ID = "Ubuntu One"
TOPLEVEL_XID = 0

class Inhibitor(object):
    """An object representing an inhibition, that can be cancelled."""


    def __init__(self):
        """Initialize this instance."""
        self.cookie = None
        bus = dbus.SessionBus()
        obj = bus.get_object(bus_name=SESSION_MANAGER_BUSNAME,
                             object_path=SESSION_MANAGER_PATH,
                             follow_name_owner_changes=True)
        self.proxy = dbus.Interface(object=obj,
                                    dbus_interface=SESSION_MANAGER_IFACE)

    def inhibit(self, flags, reason):
        """Inhibit some events with a given reason."""
        d = defer.Deferred()

        def inhibit_handler(cookie):
            """Got the cookie for this inhibition."""
            self.cookie = cookie
            d.callback(self)

        self.proxy.Inhibit(APP_ID, TOPLEVEL_XID, reason, flags,
                           reply_handler=inhibit_handler,
                           error_handler=d.errback)
        return d

    def cancel(self):
        """Cancel the inhibition for the current cookie."""
        d = defer.Deferred()
        self.proxy.Uninhibit(self.cookie,
                             reply_handler=lambda: d.callback(self),
                             error_handler=d.errback)
        return d

def inhibit_logout_suspend(reason):
    """Inhibit the suspend and logout. The result can be cancelled."""
    return Inhibitor().inhibit(INHIBIT_LOGOUT_SUSPEND, reason)
