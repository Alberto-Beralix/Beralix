# ubuntuone.syncdaemon.platform.notification - User Notification
#
# Author: Eric Casteleijn <eric.casteleijn@canonical.com>
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
"""Module that implements notification of the end user."""

# TODO: We may want to enable different notifiers. When none of them
# are available, we should fall back to silently discarding
# notifications.

import sys
NOTIFY_MODULE = None
if 'gi' in sys.modules:
    try:
        from gi.repository import Notify
        Notify # pyflakes
        NOTIFY_MODULE = 'gi'
    except ImportError:
        pass
else:
    try:
        import pynotify as Notify
        NOTIFY_MODULE = 'pynotify'
    except ImportError:
        pass

from ubuntuone.status.notification import AbstractNotification

APPLICATION_NAME = 'Ubuntu One Client'
ICON_NAME = "ubuntuone"

class Notification(AbstractNotification):
    """Notification of the end user."""

    # pylint: disable=W0231
    def __init__(self, application_name=APPLICATION_NAME):
        self.application_name = application_name
        self.notification = None
    # pylint: enable=W0231

    def send_notification(self, title, message, icon=ICON_NAME, append=False):
        """Send a notification using the underlying library."""
        if not NOTIFY_MODULE:
            return

        if self.notification is None:
            Notify.init(self.application_name)
            if NOTIFY_MODULE == 'gi':
                self.notification = Notify.Notification.new(title, message, icon)
            else:
                self.notification = Notify.Notification(title, message, icon)
        else:
            self.notification.update(title, message, icon)
        if append:
            self.notification.set_hint_string('x-canonical-append', '')
        self.notification.show()
