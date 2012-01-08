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

"""Miscellaneous logging functions."""

import logging
import os
import sys

from functools import wraps
from logging.handlers import RotatingFileHandler

# pylint: disable=F0401,E0611
from ubuntuone.logger import LOGBACKUP, basic_formatter
from ubuntuone.platform.xdg_base_directory import ubuntuone_log_dir


if os.environ.get('DEBUG'):
    LOG_LEVEL = logging.DEBUG
else:
    # Only log this level and above
    LOG_LEVEL = logging.DEBUG  # before final release, switch to INFO

FILE_NAME = os.path.join(ubuntuone_log_dir, 'controlpanel.log')
MAIN_HANDLER = RotatingFileHandler(FILE_NAME,
                                   maxBytes=1048576,
                                   backupCount=LOGBACKUP)
MAIN_HANDLER.setFormatter(basic_formatter)
MAIN_HANDLER.setLevel(LOG_LEVEL)


def setup_logging(log_domain, prefix=None):
    """Create a logger for 'log_domain'.

    Final domain will be 'ubuntuone.controlpanel.<log_domain>.

    """
    logger = logging.getLogger('ubuntuone.controlpanel.%s' % log_domain)
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(MAIN_HANDLER)
    if os.environ.get('DEBUG'):
        debug_handler = logging.StreamHandler(sys.stderr)
        debug_handler.setFormatter(basic_formatter)
        logger.addHandler(debug_handler)

    return logger


def log_call(log_func, with_args=True):
    """Decorator to add log info using 'log_func'.

    To be replaced soon with the log_call defined in ubuntuone-client.

    """

    def middle(f):
        """Add logging when calling 'f'."""

        @wraps(f)
        def inner(*args, **kwargs):
            """Call f(*args, **kwargs)."""
            if with_args:
                log_func('%s: args %r, kwargs %r.', f.__name__, args, kwargs)
            else:
                log_func('%s.', f.__name__)

            res = f(*args, **kwargs)
            return res

        return inner

    return middle
