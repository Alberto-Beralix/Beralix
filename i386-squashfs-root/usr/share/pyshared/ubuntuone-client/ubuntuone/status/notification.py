# ubuntuone.status.notification - User Notification
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
"""Module that defines the interfaces for notification of the end user."""

from abc import ABCMeta, abstractmethod

APPLICATION_NAME = 'Ubuntu One Client'


class AbstractNotification(object):
    """Abstract Base Class for notification implementations."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def send_notification(self, title, message, icon=None, append=False):
        """Send a notification to the end user."""
