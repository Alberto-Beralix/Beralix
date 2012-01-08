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

"""The syncdaemon client."""

import sys
import warnings

# pylint: disable=E0611
from ubuntuone.platform import tools
# pylint: enable=E0611
from ubuntuone.controlpanel.logger import setup_logging


logger = setup_logging('sd_client')


class SyncDaemonClient(object):
    """An abstraction to SyncDaemonTool."""

    def __init__(self):
        """Get a proxy for the SyncDaemonTool."""
        self.status_changed_handler = None
        self.proxy = tools.SyncDaemonTool()

    def get_throttling_limits(self):
        """Get the speed limits from the syncdaemon."""
        return self.proxy.get_throttling_limits()

    def set_throttling_limits(self, limits):
        """Set the speed limits on the syncdaemon."""
        dload = int(limits["download"])
        uload = int(limits["upload"])
        return self.proxy.set_throttling_limits(dload, uload)

    def bandwidth_throttling_enabled(self):
        """Get the state of throttling in the syncdaemon."""
        return self.proxy.is_throttling_enabled()

    def enable_bandwidth_throttling(self):
        """Enable the speed limits in the syncdaemon."""
        return self.proxy.enable_throttling(True)

    def disable_bandwidth_throttling(self):
        """Disable the speed limits in the syncdaemon."""
        return self.proxy.enable_throttling(False)

    def autoconnect_enabled(self):
        """Get the state of autoconnect in the syncdaemon."""
        return self.proxy.is_autoconnect_enabled()

    def enable_autoconnect(self):
        """Enable autoconnect in the syncdaemon."""
        return self.proxy.enable_autoconnect(True)

    def disable_autoconnect(self):
        """Disable autoconnect in the syncdaemon."""
        return self.proxy.enable_autoconnect(False)

    def show_all_notifications_enabled(self):
        """Get the state of show_all_notifications in the syncdaemon."""
        return self.proxy.is_show_all_notifications_enabled()

    def enable_show_all_notifications(self):
        """Enable show_all_notifications in the syncdaemon."""
        return self.proxy.enable_show_all_notifications(True)

    def disable_show_all_notifications(self):
        """Disable show_all_notifications in the syncdaemon."""
        return self.proxy.enable_show_all_notifications(False)

    def share_autosubscribe_enabled(self):
        """Get the state of share_autosubscribe in the syncdaemon."""
        return self.proxy.is_share_autosubscribe_enabled()

    def enable_share_autosubscribe(self):
        """Enable share_autosubscribe in the syncdaemon."""
        return self.proxy.enable_share_autosubscribe(True)

    def disable_share_autosubscribe(self):
        """Disable share_autosubscribe in the syncdaemon."""
        return self.proxy.enable_share_autosubscribe(False)

    def udf_autosubscribe_enabled(self):
        """Get the state of udf_autosubscribe in the syncdaemon."""
        return self.proxy.is_udf_autosubscribe_enabled()

    def enable_udf_autosubscribe(self):
        """Enable udf_autosubscribe in the syncdaemon."""
        return self.proxy.enable_udf_autosubscribe(True)

    def disable_udf_autosubscribe(self):
        """Disable udf_autosubscribe in the syncdaemon."""
        return self.proxy.enable_udf_autosubscribe(False)

    def get_root_dir(self):
        """Retrieve the root information from syncdaemon."""
        return self.proxy.get_root_dir()

    def get_shares_dir(self):
        """Retrieve the shares information from syncdaemon."""
        return self.proxy.get_shares_dir()

    def get_shares_dir_link(self):
        """Retrieve the shares information from syncdaemon."""
        return self.proxy.get_shares_dir_link()

    def get_folders(self):
        """Retrieve the folders information from syncdaemon."""
        return self.proxy.get_folders()

    def create_folder(self, path):
        """Create a new folder through syncdaemon."""
        return self.proxy.create_folder(path)

    def subscribe_folder(self, folder_id):
        """Subscribe to 'folder_id'."""
        return self.proxy.subscribe_folder(folder_id)

    def unsubscribe_folder(self, folder_id):
        """Unsubscribe 'folder_id'."""
        return self.proxy.unsubscribe_folder(folder_id)

    def get_shares(self):
        """Retrieve the shares information from syncdaemon."""
        return self.proxy.get_shares()

    def subscribe_share(self, share_id):
        """Subscribe to 'share_id'."""
        return self.proxy.subscribe_share(share_id)

    def unsubscribe_share(self, share_id):
        """Unsubscribe 'share_id'."""
        return self.proxy.unsubscribe_share(share_id)

    def get_current_status(self):
        """Retrieve the current status from syncdaemon."""
        return self.proxy.get_status()

    def file_sync_enabled(self):
        """Get if file sync service is enabled."""
        return self.proxy.is_files_sync_enabled()

    def enable_file_sync(self):
        """Enable the file sync service."""
        return self.proxy.enable_files_sync(True)

    def disable_file_sync(self):
        """Enable the file sync service."""
        return self.proxy.enable_files_sync(False)

    def files_sync_enabled(self):
        """Get if file sync service is enabled."""
        warnings.warn('use file_sync_enabled instead', DeprecationWarning)
        return self.file_sync_enabled()

    def set_files_sync_enabled(self, enabled):
        """Set the file sync service to be 'enabled'."""
        warnings.warn('use {enable/disable}_file_sync instead',
                      DeprecationWarning)
        if enabled:
            return self.enable_file_sync()
        else:
            return self.disable_file_sync()

    def connect_file_sync(self):
        """Connect the file sync service."""
        return self.proxy.connect()

    def disconnect_file_sync(self):
        """Disconnect the file sync service."""
        return self.proxy.disconnect()

    def start_file_sync(self):
        """Start the file sync service."""
        return self.proxy.start()

    def stop_file_sync(self):
        """Stop the file sync service."""
        return self.proxy.quit()

    def set_status_changed_handler(self, handler):
        """Set the status handler function."""
        self.status_changed_handler = handler
        if sys.platform.startswith("linux"):
            # pylint: disable=W0404
            from ubuntuone.controlpanel.sd_client import linux
            result = linux.set_status_changed_handler(handler)
        else:
            result = self.proxy.set_status_changed_handler(handler)
        return result
