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

"""XDG multiplatform."""

import sys

# pylint: disable=C0103
if sys.platform == "win32":
    from ubuntu_sso.xdg_base_directory import windows
    load_config_paths = windows.load_config_paths
    save_config_path = windows.save_config_path
    xdg_cache_home = windows.xdg_cache_home
    xdg_data_home = windows.xdg_data_home
    xdg_data_dirs = windows.xdg_data_dirs
else:
    import xdg.BaseDirectory
    load_config_paths = xdg.BaseDirectory.load_config_paths
    save_config_path = xdg.BaseDirectory.save_config_path
    xdg_cache_home = xdg.BaseDirectory.xdg_cache_home
    xdg_data_home = xdg.BaseDirectory.xdg_data_home
    xdg_data_dirs = xdg.BaseDirectory.xdg_data_dirs
