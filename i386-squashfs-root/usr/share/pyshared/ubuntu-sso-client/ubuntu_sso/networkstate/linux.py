# -*- coding: utf-8 -*-
#
# networkstate - detect the current state of the network
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
"""Implementation of network state detection."""

import dbus

from ubuntu_sso.logger import setup_logging
logger = setup_logging("ubuntu_sso.networkstate")

# Values returned by the callback
ONLINE, OFFLINE, UNKNOWN = object(), object(), object()

NM_STATE_NAMES = {
    ONLINE: "online",
    OFFLINE: "offline",
    UNKNOWN: "unknown",
}

# Internal NetworkManager State constants
NM_STATE_UNKNOWN = 0
NM_STATE_UNKNOWN_LIST = [NM_STATE_UNKNOWN]
NM_STATE_ASLEEP_OLD = 1
NM_STATE_ASLEEP = 10
NM_STATE_ASLEEP_LIST = [NM_STATE_ASLEEP_OLD,
                        NM_STATE_ASLEEP]
NM_STATE_CONNECTING_OLD = 2
NM_STATE_CONNECTING = 40
NM_STATE_CONNECTING_LIST = [NM_STATE_CONNECTING_OLD,
                            NM_STATE_CONNECTING]
NM_STATE_CONNECTED_OLD = 3
NM_STATE_CONNECTED_LOCAL = 50
NM_STATE_CONNECTED_SITE = 60
NM_STATE_CONNECTED_GLOBAL = 70
# Specifically don't include local and site, as they won't let us get to server
NM_STATE_CONNECTED_LIST = [NM_STATE_CONNECTED_OLD,
                           NM_STATE_CONNECTED_GLOBAL]
NM_STATE_DISCONNECTED_OLD = 4
NM_STATE_DISCONNECTED = 20
# For us, local and site connections are the same as diconnected
NM_STATE_DISCONNECTED_LIST = [NM_STATE_DISCONNECTED_OLD,
                              NM_STATE_DISCONNECTED,
                              NM_STATE_CONNECTED_LOCAL,
                              NM_STATE_CONNECTED_SITE]

NM_DBUS_INTERFACE = "org.freedesktop.NetworkManager"
NM_DBUS_OBJECTPATH = "/org/freedesktop/NetworkManager"
DBUS_UNKNOWN_SERVICE = "org.freedesktop.DBus.Error.ServiceUnknown"


class NetworkManagerState(object):
    """Checks the state of NetworkManager thru DBus."""

    def __init__(self, result_cb, dbus_module=dbus):
        """Initialize this instance with a result and error callbacks."""
        self.result_cb = result_cb
        self.dbus = dbus_module
        self.state_signal = None

    def call_result_cb(self, state):
        """Return the state thru the result callback."""
        if self.state_signal:
            self.state_signal.remove()
        self.result_cb(state)

    def got_state(self, state):
        """Called by DBus when the state is retrieved from NM."""
        if state in NM_STATE_CONNECTED_LIST:
            self.call_result_cb(ONLINE)
        elif state in NM_STATE_CONNECTING_LIST:
            logger.debug("Currently connecting, waiting for signal")
        else:
            self.call_result_cb(OFFLINE)

    def got_error(self, error):
        """Called by DBus when the state is retrieved from NM."""
        if isinstance(error, self.dbus.exceptions.DBusException) and \
                error.get_dbus_name() == DBUS_UNKNOWN_SERVICE:
            logger.debug("Network Manager not present")
            self.call_result_cb(UNKNOWN)
        else:
            logger.error("Error contacting NetworkManager: %s" % \
                             str(error))
            self.call_result_cb(UNKNOWN)

    def state_changed(self, state):
        """Called when a signal is emmited by Network Manager."""
        if int(state) in NM_STATE_CONNECTED_LIST:
            self.call_result_cb(ONLINE)
        elif int(state) in NM_STATE_DISCONNECTED_LIST:
            self.call_result_cb(OFFLINE)
        else:
            logger.debug("Not yet connected: continuing to wait")

    def find_online_state(self):
        """Get the network state and return it thru the set callback."""
        try:
            sysbus = self.dbus.SystemBus()
            nm_proxy = sysbus.get_object(NM_DBUS_INTERFACE,
                                         NM_DBUS_OBJECTPATH,
                                         follow_name_owner_changes=True)
            nm_if = self.dbus.Interface(nm_proxy, NM_DBUS_INTERFACE)
            self.state_signal = nm_if.connect_to_signal(
                        signal_name="StateChanged",
                        handler_function=self.state_changed,
                        dbus_interface=NM_DBUS_INTERFACE)
            nm_proxy.Get(NM_DBUS_INTERFACE, "State",
                         reply_handler=self.got_state,
                         error_handler=self.got_error)
        except Exception, e:  # pylint: disable=W0703
            self.got_error(e)
