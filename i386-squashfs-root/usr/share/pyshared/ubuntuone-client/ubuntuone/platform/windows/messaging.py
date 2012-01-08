# ubuntuone.syncdaemon.platform.messaging - Messages to the user
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
"""Module that implements sending messages to the end user."""

# TODO: We may want to enable different messaging systems. When none
# of them are available, we should fall back to silently discarding
# messages.

from ubuntuone.status.messaging import AbstractMessaging

APPLICATION_NAME = 'Ubuntu One Client'


class Messaging(AbstractMessaging):
    """Notification of the end user."""

    # pylint: disable=R0913
    def show_message(self, sender, callback=None, message_time=None,
                     message_count=None, icon=None):
        """Show a message in the messaging menu."""
        # TODO: make this work
    # pylint: enable=R0913

    def update_count(self, sender, add_count):
        """Update the count for an existing indicator."""
        # TODO: make this work


def hide_message(indicator):            # pylint: disable=W0613
    """Remove the message once it has been dealt with."""
    # TODO: make this work


def open_volumes(the_indicator, message_time=None):  # pylint: disable=W0613
    """Open the control panel to the shares tab."""
    # TODO: make this work
