# -*- coding: utf-8 -*-

# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""Client to manage packages."""

import apt
import aptdaemon.client
# pylint: disable=W0404
import aptdaemon.enums

try:
    # Unable to import 'defer', pylint: disable=F0401,E0611,W0404
    from aptdaemon.defer import inline_callbacks, return_value
except ImportError:
    # Unable to import 'defer', pylint: disable=F0401,E0611,W0404
    from defer import inline_callbacks, return_value
from aptdaemon.gtkwidgets import AptProgressBar

from ubuntuone.controlpanel.logger import setup_logging


logger = setup_logging('package_manager')


class PackageManagerProgressBar(AptProgressBar):
    """A progress bar for a transaction."""


class PackageManager(object):
    """Manage packages (check if is installed, install)."""

    def is_installed(self, package_name):
        """Return whether 'package_name' is installed in this system."""
        cache = apt.Cache()
        result = package_name in cache and cache[package_name].is_installed
        logger.debug('is %r installed? %r', package_name, result)
        return result

    @inline_callbacks
    def install(self, package_name):
        """Install 'package_name' if is not installed in this system."""
        if self.is_installed(package_name):
            return_value(aptdaemon.enums.EXIT_SUCCESS)

        client = aptdaemon.client.AptClient()
        transaction = yield client.install_packages([package_name])
        return_value(transaction)
