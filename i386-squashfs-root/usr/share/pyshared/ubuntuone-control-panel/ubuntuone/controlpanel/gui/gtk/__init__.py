# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
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

"""The GTK graphical interface for the control panel for Ubuntu One."""

DBUS_BUS_NAME = 'com.ubuntuone.controlpanel.gui'
DBUS_PATH = '/gui'
DBUS_IFACE_GUI = 'com.ubuntuone.controlpanel.gui'

# Unused import main
# pylint: disable=W0611

from ubuntuone.controlpanel.gui.gtk.gui import main
