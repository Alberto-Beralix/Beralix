# -*- coding: utf-8 -*-

# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""Client to access Ubuntu One credentials."""

# pylint: disable=E0611, F0401
from ubuntuone.platform.credentials import CredentialsManagementTool
# pylint: enable=E0611, F0401


def get_sso_proxy():
    """Return a login client."""
    result = CredentialsManagementTool()
    return result


def get_credentials():
    """Get the credentials for Ubuntu One."""
    proxy = get_sso_proxy()
    return proxy.find_credentials()


def clear_credentials():
    """Clear the credentials for Ubuntu One."""
    proxy = get_sso_proxy()
    return proxy.clear_credentials()


def login(*args, **kwargs):
    """Get the credentials for Ubuntu One offering the user to login."""
    proxy = get_sso_proxy()
    return proxy.login(*args, **kwargs)


def register(*args, **kwargs):
    """Get the credentials for Ubuntu One offering the user to register."""
    proxy = get_sso_proxy()
    return proxy.register(*args, **kwargs)
