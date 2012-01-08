# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Canonical
#
# Authors:
#  Andrew Higginson
#  Alejandro J. Cura <alecu@canonical.com>
#  Natalia B. Bidart <natalia.bidart@canonical.com>
#  Manuel de la Pena <manuel@canonical.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Handle keys in the local kerying."""

import urllib
import urlparse

from twisted.internet.defer import inlineCallbacks, returnValue

from ubuntu_sso.logger import setup_logging
from ubuntu_sso.utils.txsecrets import SecretService
from ubuntu_sso.keyring import (
    get_token_name,
    get_old_token_name,
    U1_APP_NAME,
    try_old_credentials)


logger = setup_logging("ubuntu_sso.keyring")


class Keyring(object):
    """A Keyring for a given application name."""

    def __init__(self):
        """Initialize this instance."""
        self.service = SecretService()

    @inlineCallbacks
    def _find_keyring_item(self, app_name, attr=None):
        """Return the keyring item or None if not found."""
        if attr is None:
            logger.debug("getting attr")
            attr = self._get_keyring_attr(app_name)
        logger.debug("finding all items")
        items = yield self.service.search_items(attr)
        if len(items) == 0:
            # if no items found, return None
            logger.debug("No items found")
            returnValue(None)

        logger.debug("Returning first item found")
        returnValue(items[0])

    def _get_keyring_attr(self, app_name):
        """Build the keyring attributes for this credentials."""
        attr = {"key-type": "Ubuntu SSO credentials",
                "token-name": get_token_name(app_name)}
        return attr

    @inlineCallbacks
    def set_credentials(self, app_name, cred):
        """Set the credentials of the Ubuntu SSO item."""
        # Creates the secret from the credentials
        secret = urllib.urlencode(cred)

        attr = self._get_keyring_attr(app_name)
        # Add our SSO credentials to the keyring
        yield self.service.open_session()
        collection = yield self.service.get_default_collection()
        yield collection.create_item(app_name, attr, secret, True)

    @inlineCallbacks
    def _migrate_old_token_name(self, app_name):
        """Migrate credentials with old name, store them with new name."""
        logger.debug("getting keyring attr")
        attr = self._get_keyring_attr(app_name)
        logger.debug("getting old token name")
        attr['token-name'] = get_old_token_name(app_name)
        logger.debug("finding keyring item")
        item = yield self._find_keyring_item(app_name, attr=attr)
        if item is not None:
            logger.debug("setting credentials")
            yield self.set_credentials(app_name,
                                       dict(urlparse.parse_qsl(item.secret)))
            logger.debug("deleting old item")
            yield item.delete()

        logger.debug("finding keyring item")
        result = yield self._find_keyring_item(app_name)
        logger.debug("returning result value")
        returnValue(result)

    @inlineCallbacks
    def get_credentials(self, app_name):
        """A deferred with the secret of the SSO item in a dictionary."""
        # If we have no attributes, return None
        logger.debug("getting credentials")
        yield self.service.open_session()
        logger.debug("calling find item")
        item = yield self._find_keyring_item(app_name)
        if item is None:
            logger.debug("migrating token")
            item = yield self._migrate_old_token_name(app_name)

        if item is not None:
            logger.debug("parsing secret")
            secret = yield item.get_value()
            returnValue(dict(urlparse.parse_qsl(secret)))
        else:
            # if no item found, try getting the old credentials
            if app_name == U1_APP_NAME:
                logger.debug("trying old credentials")
                old_creds = yield try_old_credentials(app_name)
                returnValue(old_creds)
        # nothing was found
        returnValue(None)

    @inlineCallbacks
    def delete_credentials(self, app_name):
        """Delete a set of credentials from the keyring."""
        attr = self._get_keyring_attr(app_name)
        # Add our SSO credentials to the keyring
        yield self.service.open_session()
        collection = yield self.service.get_default_collection()
        yield collection.create_item(app_name, attr, "secret!", True)

        item = yield self._find_keyring_item(app_name)
        if item is not None:
            yield item.delete()
