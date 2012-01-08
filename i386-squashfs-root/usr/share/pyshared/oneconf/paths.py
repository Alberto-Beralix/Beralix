# -*- coding: utf-8 -*-
# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche <didrocks@ubuntu.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUTa
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import os
from xdg import BaseDirectory as xdg

ONECONF_DATADIR = '/usr/share/oneconf/data'
ONECONF_CACHE_DIR = os.path.join(xdg.xdg_cache_home, "oneconf")
PACKAGE_LIST_PREFIX = "package_list"
OTHER_HOST_FILENAME = "other_hosts"
PENDING_UPLOAD_FILENAME = "pending_upload"
HOST_DATA_FILENAME = "host"
LOGO_PREFIX = "logo"
LAST_SYNC_DATE_FILENAME = "last_sync"

_datadir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
if not os.path.exists(_datadir):
    _datadir = ONECONF_DATADIR
LOGO_BASE_FILENAME = os.path.join(_datadir, 'images', 'computer.png')
TEST_SETTINGS_DIR = "/home/didrocks/fake/"

