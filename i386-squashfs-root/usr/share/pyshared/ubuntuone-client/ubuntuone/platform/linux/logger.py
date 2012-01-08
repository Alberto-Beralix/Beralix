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
"""Provide platform logging settings."""
import logging
import pyinotify

def get_filesystem_logger():
    """Return the logger used by the filesystem."""
    return getattr(pyinotify, 'log', logging.getLogger('pyinotify'))


def setup_filesystem_logging(filesystem_logger, root_handler):
    """Set the extra logging to be used on linux."""
    # hook pyinotify logger, but remove the console handler first
    for hdlr in filesystem_logger.handlers:
        if isinstance(hdlr, logging.StreamHandler):
            filesystem_logger.removeHandler(hdlr)
    filesystem_logger.addHandler(root_handler)
    filesystem_logger.setLevel(logging.ERROR)
    filesystem_logger.propagate = False
    return filesystem_logger

