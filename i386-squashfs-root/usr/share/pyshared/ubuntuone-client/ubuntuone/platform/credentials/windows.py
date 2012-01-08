# -*- coding: utf-8 -*-
#
# Authors: Manuel de la Pena <manuel@canonical.com>
#          Alejandro J. Cura <alecu@canonical.com>
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
"""Ubuntu One credentials management IPC service."""


from ubuntu_sso.main.windows import UbuntuSSOClient
from twisted.internet import defer

from ubuntu_sso.credentials import (
    HELP_TEXT_KEY,
    PING_URL_KEY,
    TC_URL_KEY,
)
from ubuntuone.platform.credentials import (
    APP_NAME,
    DESCRIPTION,
    logger,
    NO_OP,
    PING_URL,
    TC_URL,
)


class RemovableSignal(object):
    """A signal that can be removed."""

    def __init__(self, proxy, signal_name, callback):
        """Initialize this instance."""
        self.proxy = proxy
        self.signal_name = signal_name
        self.callback = callback
        setattr(self.proxy, signal_name, self)

    def __call__(self, *args, **kwargs):
        """Call this instance."""
        app_name = args[0] if len(args) > 0 else None
        logger.debug('Handling signal_name: %r, app_name: %r.',
                     self.signal_name, app_name)

        if app_name != APP_NAME:
            # This fixed bug #818190: filter signals not related to APP_NAME
            logger.info('Received %r but app_name %r does not match %r, ' \
                        'exiting.', self.signal_name, app_name, APP_NAME)
            return

        if self.callback is not None:
            # drop the app name, callers do not care about it
            args = args[1:]
            logger.debug('Calling %r with %d args and %d kwargs.',
                         self.callback, len(args), len(kwargs))
            return self.callback(*args, **kwargs)

    def remove(self):
        """Remove this signal."""
        if getattr(self.proxy, self.signal_name, False):
            setattr(self.proxy, self.signal_name, None)


class CredentialsManagement(object):
    """Object that manages Ubuntu One credentials."""

    _SIGNAL_TO_CALLBACK_MAPPING = {
        'AuthorizationDenied': 'on_authorization_denied_cb',
        'CredentialsCleared': 'on_credentials_cleared_cb',
        'CredentialsError': 'on_credentials_error_cb',
        'CredentialsFound': 'on_credentials_found_cb',
        'CredentialsNotFound': 'on_credentials_not_found_cb',
        'CredentialsStored': 'on_credentials_stored_cb',
    }

    def __init__(self, proxy, *args, **kwargs):
        super(CredentialsManagement, self).__init__(*args, **kwargs)
        self.sso_proxy = proxy

    def connect_to_signal(self, signal_name, callback):
        """Register 'callback' to be called when 'signal_name' is emitted."""
        cb_name = self._SIGNAL_TO_CALLBACK_MAPPING[signal_name]
        match = RemovableSignal(self.sso_proxy, cb_name, callback)
        return match

    def find_credentials(self, reply_handler=NO_OP, error_handler=NO_OP):
        """Ask the Ubuntu One credentials."""
        d = self.sso_proxy.find_credentials(APP_NAME, {})
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def clear_credentials(self, reply_handler=NO_OP, error_handler=NO_OP):
        """Clear the Ubuntu One credentials."""
        d = self.sso_proxy.clear_credentials(APP_NAME, {})
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def store_credentials(self, credentials,
                          reply_handler=NO_OP, error_handler=NO_OP):
        """Store the token for Ubuntu One application."""
        d = self.sso_proxy.store_credentials(APP_NAME, credentials)
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def register(self, args, reply_handler=NO_OP, error_handler=NO_OP):
        """Get credentials if found else prompt to register to Ubuntu One."""
        params = {HELP_TEXT_KEY: DESCRIPTION, TC_URL_KEY: TC_URL,
                  PING_URL_KEY: PING_URL}
        params.update(args)
        d = self.sso_proxy.register(APP_NAME, params)
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def login(self, args, reply_handler=NO_OP, error_handler=NO_OP):
        """Get credentials if found else prompt to login to Ubuntu One."""
        params = {HELP_TEXT_KEY: DESCRIPTION, TC_URL_KEY: TC_URL,
                  PING_URL_KEY: PING_URL}
        params.update(args)
        d = self.sso_proxy.login(APP_NAME, params)
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def login_email_password(self, args,
                             reply_handler=NO_OP, error_handler=NO_OP):
        """Get credentials if found else login to Ubuntu One."""
        params = {PING_URL_KEY: PING_URL}
        params.update(args)
        d = self.sso_proxy.login_email_password(APP_NAME, params)
        d.addCallbacks(lambda _: reply_handler(), error_handler)

    def register_to_credentials_stored(self, callback):
        """Register to the CredentialsStored dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_credentials_stored_cb",
                               callback)

    def register_to_credentials_cleared(self, callback):
        """Register to the CredentialsCleared dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_credentials_cleared_cb",
                               callback)

    def register_to_credentials_found(self, callback):
        """Register to the CredentialsFound dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_credentials_found_cb",
                               callback)

    def register_to_credentials_not_found(self, callback):
        """Register to the CredentialsFound dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_credentials_not_found_cb",
                               callback)

    def register_to_authorization_denied(self, callback):
        """Register to the AuthorizationDenied dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_authorization_denied_cb",
                               callback)

    def register_to_credentials_error(self, callback):
        """Register to the CredentialsError dbus signal."""
        return RemovableSignal(self.sso_proxy, "on_credentials_error_cb",
                               callback)


@defer.inlineCallbacks
def get_creds_proxy():
    """Get the CredentialsManagement proxy."""
    client = UbuntuSSOClient()
    yield client.connect()
    yield client.cred_management.register_to_signals()
    result = CredentialsManagement(client.cred_management)
    defer.returnValue(result)
