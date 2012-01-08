# ubuntuone.syncdaemon.logger - logging utilities
#
# Author: Guillermo Gonzalez <guillermo.gonzalez@canonical.com>
#         Eric Casteleijn <eric.casteleijn@canonical.com>
#
# Copyright 2009-2011 Canonical Ltd.
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

"""SyncDaemon logging utilities and config."""

import logging
import os

from ubuntuone.logger import (
    _DEBUG_LOG_LEVEL,
    basic_formatter,
    CustomRotatingFileHandler,
)

from ubuntuone.platform.xdg_base_directory import ubuntuone_log_dir


LOGFILENAME = os.path.join(ubuntuone_log_dir, 'status.log')
logger = logging.getLogger("ubuntuone.status")
logger.setLevel(_DEBUG_LOG_LEVEL)
handler = CustomRotatingFileHandler(filename=LOGFILENAME)
handler.setFormatter(basic_formatter)
handler.setLevel(_DEBUG_LOG_LEVEL)
logger.addHandler(handler)
