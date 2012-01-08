# -*- coding: utf-8 -*-
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
"""Keyring implementation on Windows."""

from json import loads, dumps

from twisted.internet.threads import deferToThread

USERNAME = 'ubuntu_sso'


class Keyring(object):
    """A Keyring for a given application name."""

    def __init__(self, keyring=None):
        """Create a new instance."""
        if keyring is None:
            import keyring as pykeyring
            keyring = pykeyring
        self.keyring = keyring

    def set_credentials(self, app_name, cred):
        """Set the credentials of the Ubuntu SSO item."""
        # the windows keyring can only store a pair username-password
        # so we store the data using ubuntu_sso as the user name. Then
        # the cred will be stored as the string representation of the dict.
        return deferToThread(self.keyring.set_password, app_name, USERNAME,
                             dumps(cred))

    def _get_credentials_obj(self, app_name):
        """A dict with the credentials."""
        creds = self.keyring.get_password(app_name, USERNAME)
        if creds:
            return loads(creds)

    def get_credentials(self, app_name):
        """A deferred with the secret of the SSO item in a dictionary."""
        return deferToThread(self._get_credentials_obj, app_name)

    def delete_credentials(self, app_name):
        """Delete a set of credentials from the keyring."""
        # this call depends on a patch I sent to pykeyring. The patch has
        # not landed as of version 0.5.1. If you have that version you can
        # clone my patch in the following way:
        # hg clone https://bitbucket.org/mandel/pykeyring-delete-password
        # pylint: disable=E1103
        return deferToThread(self.keyring.delete_password, app_name, USERNAME)
