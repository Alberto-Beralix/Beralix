# ubuntuone.platform.linux - linux platform imports
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
"""Linux import for ubuntuone-client

This module has to have all linux specific modules and provide the api required
to support the linux platform."""

platform = "linux"

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from twisted.internet import defer

from ubuntuone.platform.linux.os_helper import (
    access,
    allow_writes,
    can_write,
    get_path_list,
    is_link,
    is_root,
    listdir,
    make_dir,
    make_link,
    move_to_trash,
    normpath,
    open_file,
    path_exists,
    read_link,
    recursive_move,
    remove_dir,
    remove_file,
    remove_link,
    remove_tree,
    rename,
    set_application_name,
    set_dir_readonly,
    set_dir_readwrite,
    set_file_readonly,
    set_file_readwrite,
    set_no_rights,
    stat_path,
    walk,
)
from ubuntuone.platform.linux.logger import setup_filesystem_logging, get_filesystem_logger
from ubuntuone.platform.linux.filesystem_notifications import FilesystemMonitor
from ubuntuone.platform.linux.notification import Notification


class ExternalInterface(object):
    """An ExternalInterface implemented with a DBus interface."""

    def __init__(self, main, glib_loop=False, broadcast_events=False,
                 dbus_iface=None):
        # avoid circular dependencies

        if dbus_iface is None:
            from ubuntuone.platform.linux import dbus_interface
            if not glib_loop:
                self.bus = dbus.SessionBus()
            else:
                loop = DBusGMainLoop(set_as_default=True)
                self.bus = dbus.SessionBus(loop)

            self.dbus_iface = dbus_interface.DBusInterface(
                self.bus, main, send_events=broadcast_events)

        else:
            self.dbus_iface = dbus_iface
            self.bus = None

    def _get_credentials(self):
        return self.dbus_iface.oauth_credentials

    def _set_credentials(self, credentials):
        self.dbus_iface.oauth_credentials = credentials

    oauth_credentials = property(fget=_get_credentials, fset=_set_credentials)

    def shutdown(self, with_restart):
        self.dbus_iface.shutdown(with_restart)

    def connect(self, *args, **kwargs):
        self.dbus_iface.connect(*args, **kwargs)


def is_already_running():
    """Check if there is another instance registered in DBus."""
    from ubuntuone.platform.linux import dbus_interface
    bus = dbus.SessionBus()
    request = bus.request_name(dbus_interface.DBUS_IFACE_NAME,
                               dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
    if request == dbus.bus.REQUEST_NAME_REPLY_EXISTS:
        return defer.succeed(True)
    else:
        return defer.succeed(False)
