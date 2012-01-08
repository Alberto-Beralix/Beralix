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

from ubuntuone.status.notification import AbstractNotification

APPLICATION_NAME = 'Ubuntu One Client'


class Notification(AbstractNotification):
    """Notification of the end user."""

    # pylint: disable=W0231
    def __init__(self, application_name=APPLICATION_NAME):
        self.application_name = application_name
    # pylint: enable=W0231

    def send_notification(self, title, message, icon=None, append=False):
        """Send a notification using the underlying library."""
        # TODO: Send notifications. Dummy class is here to not break
        # on windows.
