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

"""Miscellaneous utilities."""

import os

from ubuntuone.controlpanel.logger import setup_logging


logger = setup_logging('utils')

DATA_SUFFIX = 'data'

ERROR_TYPE = 'error_type'
ERROR_MESSAGE = 'error_msg'


def get_project_dir():
    """Return the absolute path to this project's data/ dir.

    Support symlinks, and priorize local (relative) data/ dir.
    """
    module = os.path.dirname(__file__)
    result = os.path.abspath(os.path.join(module, os.path.pardir,
                                          os.path.pardir, DATA_SUFFIX))
    logger.debug('get_project_dir: trying use data dir at %r (exists? %s)',
                  result, os.path.exists(result))
    if os.path.exists(result):
        logger.info('get_project_dir: returning dir located at %r.', result)
        return result

    # otherwise, try to load PROJECT_DIR from installation path
    try:
        # pylint: disable=F0401, E0611, W0404
        from ubuntuone.controlpanel.constants import PROJECT_DIR
        return PROJECT_DIR
    except ImportError:
        msg = 'get_project_dir: can not build a valid path. Giving up. ' \
              '__file__ is %r, constants module not available.'
        logger.error(msg, __file__)


def get_data_file(filename):
    """Return the absolute path to 'filename' within data/ dir."""
    return os.path.join(get_project_dir(), filename)


def exception_to_error_dict(exc):
    """Transform a regular Exception into a dictionary."""
    result = {ERROR_TYPE: exc.__class__.__name__, ERROR_MESSAGE: unicode(exc)}

    return result


def failure_to_error_dict(failure):
    """Transform a twisted Failure into a dictionary."""
    return exception_to_error_dict(failure.value)
