# -*- coding: utf-8 -*-
#
# ubuntu_sso.logger - logging miscellany
#
# Author: Stuart Langridge <stuart.langridge@canonical.com>
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
#
# Copyright 2009 Canonical Ltd.
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

"""Miscellaneous logging functions."""

import logging
import os
import sys

from logging.handlers import RotatingFileHandler

from ubuntu_sso import xdg_base_directory

LOGFOLDER = os.path.join(xdg_base_directory.xdg_cache_home, 'sso')
# create log folder if it doesn't exists
if not os.path.exists(LOGFOLDER):
    os.makedirs(LOGFOLDER)

if os.environ.get('DEBUG'):
    LOG_LEVEL = logging.DEBUG
else:
    # Only log this level and above
    LOG_LEVEL = logging.INFO

MAIN_HANDLER = RotatingFileHandler(os.path.join(LOGFOLDER, 'sso-client.log'),
                                   maxBytes=1048576,
                                   backupCount=5)
MAIN_HANDLER.setLevel(LOG_LEVEL)
FMT = "%(asctime)s:%(msecs)s - %(name)s - %(levelname)s - %(message)s"
MAIN_HANDLER.setFormatter(logging.Formatter(fmt=FMT))


def setup_logging(log_domain):
    """Create basic logger to set filename."""
    logger = logging.getLogger(log_domain)
    logger.propagate = False
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(MAIN_HANDLER)
    if os.environ.get('DEBUG'):
        debug_handler = logging.StreamHandler(sys.stderr)
        debug_handler.setFormatter(logging.Formatter(fmt=FMT))
        logger.addHandler(debug_handler)

    return logger
