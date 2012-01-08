# -*- coding: utf-8 -*-

# Authors: Alejandro J. Cura <alecu@canonical.com>
# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""Client to use other DBus services."""

import dbus.service

from ubuntuone.controlpanel.logger import setup_logging


logger = setup_logging('sd_client')


def get_syncdaemon_proxy(object_path, dbus_interface):
    """Get a DBus proxy for syncdaemon at 'object_path':'dbus_interface'."""
    logger.debug('get_syncdaemon_proxy: object_path %r, dbus_interface %r',
                 object_path, dbus_interface)
    bus = dbus.SessionBus()
    obj = bus.get_object(bus_name='com.ubuntuone.SyncDaemon',
                         object_path=object_path,
                         follow_name_owner_changes=True)
    proxy = dbus.Interface(object=obj, dbus_interface=dbus_interface)
    return proxy


def set_status_changed_handler(handler):
    """Connect 'handler' with syncdaemon's StatusChanged signal."""
    proxy = get_syncdaemon_proxy('/status', 'com.ubuntuone.SyncDaemon.Status')
    sig = proxy.connect_to_signal('StatusChanged', handler)
    return proxy, sig
