# -*- coding: utf-8 -*-
# Authors:
#  Andrew Higginson
#  Alejandro J. Cura <alecu@canonical.com>
#  Manuel de la Pena <manuel@canonical.com>
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
"""Implementations of different keyrings."""

import socket
import sys
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue

from ubuntu_sso.logger import setup_logging

logger = setup_logging("ubuntu_sso.keyring")

TOKEN_SEPARATOR = ' @ '
SEPARATOR_REPLACEMENT = ' AT '

U1_APP_NAME = "Ubuntu One"
U1_KEY_NAME = "UbuntuOne token for https://ubuntuone.com"
U1_KEY_ATTR = {
    "oauth-consumer-key": "ubuntuone",
    "ubuntuone-realm": "https://ubuntuone.com",
}


def get_old_token_name(app_name):
    """Build the token name (old style)."""
    quoted_app_name = urllib.quote(app_name)
    computer_name = socket.gethostname()
    quoted_computer_name = urllib.quote(computer_name)
    return "%s - %s" % (quoted_app_name, quoted_computer_name)


def get_token_name(app_name):
    """Build the token name."""
    computer_name = socket.gethostname()
    computer_name = computer_name.replace(TOKEN_SEPARATOR,
                                          SEPARATOR_REPLACEMENT)
    return TOKEN_SEPARATOR.join((app_name, computer_name)).encode('utf-8')


@inlineCallbacks
def try_old_credentials(app_name):
    """Try to get old U1 credentials and format them as new."""
    logger.debug('trying to get old credentials.')
    old_creds = yield UbuntuOneOAuthKeyring().get_credentials(U1_KEY_NAME)
    if old_creds is not None:
        # Old creds found, build a new credentials dict with them
        creds = {
            'consumer_key': "ubuntuone",
            'consumer_secret': "hammertime",
            'name': U1_KEY_NAME,
            'token': old_creds["oauth_token"],
            'token_secret': old_creds["oauth_token_secret"],
        }
        logger.debug('found old credentials')
        returnValue(creds)
    logger.debug('try_old_credentials: No old credentials for this app.')
    returnValue(None)


if sys.platform == 'win32':
    from ubuntu_sso.keyring.windows import Keyring
else:
    from ubuntu_sso.keyring.linux import Keyring


class UbuntuOneOAuthKeyring(Keyring):
    """A particular Keyring for Ubuntu One."""

    def _get_keyring_attr(self, app_name):
        """Build the keyring attributes for this credentials."""
        return U1_KEY_ATTR
