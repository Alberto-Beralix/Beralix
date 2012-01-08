# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
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

"""Defines a constant for ubuntuone's log folder based on XDG."""

import os

from ubuntu_sso.xdg_base_directory import xdg_cache_home

ubuntuone_log_dir = os.path.join(xdg_cache_home, 'ubuntuone', 'log')
if not os.path.exists(ubuntuone_log_dir):
    os.makedirs(ubuntuone_log_dir)
