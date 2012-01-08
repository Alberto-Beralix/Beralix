# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
# Authors: Alejandro J. Cura <alecu@canonical.com>
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

"""The control panel for Ubuntu One.

The control panel is a graphical user interface that allows the users to manage
their Ubuntu One subscription and preferences.

"""

# constants
DBUS_BUS_NAME = "com.ubuntuone.controlpanel"
DBUS_PREFERENCES_PATH = "/preferences"
DBUS_PREFERENCES_IFACE = "com.ubuntuone.controlpanel.Preferences"

WEBSERVICE_BASE_URL = u"https://one.ubuntu.com/api/"
TRANSLATION_DOMAIN = 'ubuntuone-control-panel'
