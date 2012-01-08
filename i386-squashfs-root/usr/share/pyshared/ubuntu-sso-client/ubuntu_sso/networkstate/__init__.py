# -*- coding: utf-8 -*-
# Author: Manuel de la Pena <manuel@canonical.com>
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
"""Platform specific network status."""

import sys

# ignore global naming issues.
# pylint: disable=C0103

NetworkManagerState = None
ONLINE = None
OFFLINE = None
UNKNOWN = None

if sys.platform == 'win32':
    from ubuntu_sso.networkstate import windows
    NetworkManagerState = windows.NetworkManagerState
    ONLINE = windows.ONLINE
    OFFLINE = windows.OFFLINE
    UNKNOWN = windows.UNKNOWN
else:
    from ubuntu_sso.networkstate import linux
    NetworkManagerState = linux.NetworkManagerState
    ONLINE = linux.ONLINE
    OFFLINE = linux.OFFLINE
    UNKNOWN = linux.UNKNOWN
