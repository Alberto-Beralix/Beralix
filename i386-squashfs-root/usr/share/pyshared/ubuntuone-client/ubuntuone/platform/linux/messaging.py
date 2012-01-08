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

import dbus
import subprocess

from time import time

try:
    import indicate
    USE_INDICATE = True
except ImportError:
    USE_INDICATE = False

DBUS_BUS_NAME = 'com.ubuntuone.controlpanel.gui'
DBUS_PATH = '/gui'
DBUS_IFACE_GUI = 'com.ubuntuone.controlpanel.gui'
TRANSLATION_DOMAIN = 'ubuntuone-control-panel'

from ubuntuone.status.messaging import AbstractMessaging
from ubuntuone.status.logger import logger

APPLICATION_NAME = 'Ubuntu One Client'


# pylint: disable=W0613
def open_volumes():
    """Open the control panel to the shares tab."""
    bus = dbus.SessionBus()
    obj = bus.get_object(DBUS_BUS_NAME, DBUS_PATH)
    service = dbus.Interface(obj, dbus_interface=DBUS_IFACE_GUI)

    def error_handler(*args, **kwargs):
        """Log errors when calling D-Bus methods in a async way."""
        logger.error(
            'Dbus call to com.ubuntuone.controlpanel.gui failed: %r %r', args,
            kwargs)

    def reply_handler(*args, **kwargs):
        """Exit when done."""
        pass

    service.switch_to_alert(
        'volumes', True, reply_handler=reply_handler,
        error_handler=error_handler)


def _server_callback(the_indicator, message_time=None):
    """Open the control panel to the shares tab."""
    subprocess.Popen(['ubuntuone-control-panel-gtk'])
# pylint: enable=W0613


class Messaging(AbstractMessaging):
    """Notification of the end user."""

    def __init__(self, server_callback=_server_callback):
        if USE_INDICATE:
            self.indicators = []
            self.server = indicate.indicate_server_ref_default()
            self.server.connect("server-display", server_callback)
            self.server.set_type("message.u1")
            self.server.set_desktop_file(
                "/usr/share/applications/ubuntuone-control-panel-gtk.desktop")
            self.server.show()

    # pylint: disable=R0913
    def show_message(self, sender, callback=None, message_time=None,
                     message_count=None, icon=None):
        """Show a message in the messaging menu."""
        if USE_INDICATE:
            indicator = indicate.Indicator()
            indicator.set_property("subtype", "u1")
            indicator.set_property("name", sender)
            indicator.set_property("sender", sender)

            if callback is None:
                callback = self.create_callback()
            indicator.connect("user-display", callback)

            if icon is not None:
                indicator.set_property_icon("icon", icon)
            if message_count is not None:
                indicator.set_property("count", str(message_count))
            else:
                if message_time is None:
                    message_time = time()
                indicator.set_property_time("time", message_time)
            indicator.set_property("draw-attention", "true")
            indicator.show()
            self.indicators.append(indicator)
            return indicator
    # pylint: enable=R0913

    def create_callback(self):
        """Create the callback to be used."""

        def callback(indicator, message_time=None):  # pylint: disable=W0613
            """Callback to be executed when message is clicked."""
            open_volumes()
            indicator.set_property("draw-attention", "false")
            indicator.hide()
            self.indicators.remove(indicator)
        return callback

    def update_count(self, indicator, add_count):
        """Update the count for an existing indicator."""
        if USE_INDICATE:
            new_count = int(indicator.get_property('count')) + add_count
            indicator.set_property('count', str(new_count))
