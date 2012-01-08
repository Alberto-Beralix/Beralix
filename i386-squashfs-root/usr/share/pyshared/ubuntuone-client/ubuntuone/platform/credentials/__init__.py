# -*- coding: utf-8 -*-
#
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
# Author: Manuel de la Pena<manuel@canonical.com>
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
"""Common code for the credentials management."""

import gettext
import logging
import os
import platform
import urllib
import sys

from functools import partial

from twisted.internet import defer

from ubuntuone import clientdefs
from ubuntuone.logger import (
    basic_formatter,
    CustomRotatingFileHandler,
    log_call,
)
from ubuntuone.platform.xdg_base_directory import ubuntuone_log_dir

LOG_LEVEL = logging.DEBUG
path = os.path.join(ubuntuone_log_dir, 'credentials.log')
MAIN_HANDLER = CustomRotatingFileHandler(path)
MAIN_HANDLER.setFormatter(basic_formatter)
MAIN_HANDLER.setLevel(LOG_LEVEL)

logger = logging.getLogger("ubuntuone.credentials")
logger.setLevel(LOG_LEVEL)
logger.addHandler(MAIN_HANDLER)

NO_OP = lambda *args, **kwargs: None
Q_ = lambda string: gettext.dgettext(clientdefs.GETTEXT_PACKAGE, string)
APP_NAME = u"Ubuntu One"
TC_URL = u"https://one.ubuntu.com/terms/"


def platform_data():
    result = {'platform': platform.system(),
              'platform_version': platform.release(),
              'platform_arch': platform.machine(),
              'client_version': clientdefs.VERSION}
    # urlencode will not encode unicode, only bytes
    result = urllib.urlencode(result)
    return result

BASE_PING_URL = \
    u"https://one.ubuntu.com/oauth/sso-finished-so-get-tokens/{email}"
# the result of platform_data is given by urlencode, encoded with ascii
PING_URL = BASE_PING_URL + u"?" + platform_data().decode('ascii')
DESCRIPTION = Q_('Ubuntu One requires an Ubuntu Single Sign On (SSO) account. '
                 'This process will allow you to create a new account, '
                 'if you do not yet have one.')


class CredentialsError(Exception):
    """A general exception when hadling credentilas."""


class CredentialsManagementTool(object):
    """Wrapper to CredentialsManagement.

    The goal of this class is to abstract the caller from calling the IPC
    service implemented in the class CredentialsManagement.

    """

    def __init__(self):
        self._cleanup_signals = []
        self._proxy = None

    def callback(self, result, deferred):
        """Fire 'deferred' with success, sending 'result' as result."""
        deferred.callback(result)

    def errback(self, error, deferred):
        """Fire 'deferred' with error sending a CredentialsError."""
        deferred.errback(CredentialsError(error))

    def cleanup(self, _):
        """Disconnect all the DBus signals."""
        for sig in self._cleanup_signals:
            logger.debug('cleanup: removing signal match %r', sig)
            remove = getattr(sig, "remove", None)
            if remove: remove()

        return _

    def get_platform_source(self):
        """Platform-specific source."""
        if sys.platform == 'win32':
            from ubuntuone.platform.credentials import windows
            source = windows
        else:
            from ubuntuone.platform.credentials import linux
            source = linux
        return source

    @defer.inlineCallbacks
    def get_creds_proxy(self):
        """Call the platform-dependent get_creds_proxy caching the result."""
        if self._proxy is None:
            source = self.get_platform_source()
            self._proxy = yield source.get_creds_proxy()
        defer.returnValue(self._proxy)

    # do not log returned credentials
    @log_call(logger.debug, with_result=False)
    @defer.inlineCallbacks
    def find_credentials(self):
        """Find credentials for Ubuntu One.

        Return a deferred that, when fired, will return the credentials for
        Ubuntu One for the current logged in user.

        The credentials is a dictionary with both string keys and values. The
        dictionary may be either empty if there are no credentials for the
        user, or will hold five items as follow:

        - "name"
        - "token"
        - "token_secret"
        - "consumer_key"
        - "consumer_secret"

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsFound', d.callback)
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsNotFound',
                    partial(self.callback, result={}, deferred=d))
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.find_credentials(
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        result = yield d
        defer.returnValue(result)

    @log_call(logger.debug)
    @defer.inlineCallbacks
    def clear_credentials(self):
        """Clear credentials for Ubuntu One.

        Return a deferred that, when fired, will return no result but will
        indicate that the Ubuntu One credentials for the current user were
        removed from the local keyring.

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsCleared',
                    partial(self.callback, result=None, deferred=d))
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.clear_credentials(
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        yield d

    # do not log token
    @log_call(logger.debug, with_args=False)
    @defer.inlineCallbacks
    def store_credentials(self, token):
        """Store credentials for Ubuntu One.

        The parameter 'token' should be a dictionary that matches the
        description of the result of 'find_credentials'.

        Return a deferred that, when fired, will return no result but will
        indicate that 'token' was stored in the local keyring as the new Ubuntu
        One credentials for the current user.

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsStored',
                    partial(self.callback, result=None, deferred=d))
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.store_credentials(token,
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        yield d

    # do not log returned credentials
    @log_call(logger.debug, with_result=False)
    @defer.inlineCallbacks
    def register(self, window_id=0):
        """Register to Ubuntu One.

        Return a deferred that, when fired, will return the credentials for
        Ubuntu One for the current logged in user.

        If there are no credentials for the current user, a GTK UI will be
        opened to invite the user to register to Ubuntu One. This UI provides
        options to either register (main screen) or login (secondary screen).

        You can pass an optional 'window_id' parameter that will be used by the
        GTK UI to be set transient for it.

        The returned credentials will be either a non-empty dictionary like the
        one described in 'find_credentials', or None. The latter indicates that
        there were no credentials for the user in the local keyring and that
        the user refused to register to Ubuntu One.

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsFound', d.callback)
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('AuthorizationDenied',
                    partial(self.callback, result=None, deferred=d))
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.register({'window_id': str(window_id)},
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        result = yield d
        defer.returnValue(result)

    # do not log returned credentials
    @log_call(logger.debug, with_result=False)
    @defer.inlineCallbacks
    def login(self, window_id=0):
        """Login to Ubuntu One.

        Return a deferred that, when fired, will return the credentials for
        Ubuntu One for the current logged in user.

        If there are no credentials for the current user, a GTK UI will be
        opened to invite the user to login to Ubuntu One. This UI provides
        options to either login (main screen) or retrieve password (secondary
        screen).

        You can pass an optional 'window_id' parameter that will be used by the
        GTK UI to be set transient for it.

        The returned credentials will be either a non-empty dictionary like the
        one described in 'find_credentials', or None. The latter indicates that
        there were no credentials for the user in the local keyring and that
        the user refused to login to Ubuntu One.

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsFound', d.callback)
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('AuthorizationDenied',
                    partial(self.callback, result=None, deferred=d))
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.login({'window_id': str(window_id)},
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        result = yield d
        defer.returnValue(result)

    # do not log password nor returned credentials
    @log_call(logger.debug, with_args=False, with_result=False)
    @defer.inlineCallbacks
    def login_email_password(self, email, password):
        """Login to Ubuntu One.

        Return a deferred that, when fired, will return the credentials for
        Ubuntu One for the given email and password.

        The returned credentials will be either a non-empty dictionary like the
        one described in 'find_credentials', or None. The latter indicates
        invalid or wrong user/password.

        """
        d = defer.Deferred()
        d.addBoth(self.cleanup)

        proxy = yield self.get_creds_proxy()

        sig = proxy.connect_to_signal('CredentialsFound', d.callback)
        self._cleanup_signals.append(sig)

        sig = proxy.connect_to_signal('CredentialsError',
                    partial(self.errback, deferred=d))
        self._cleanup_signals.append(sig)

        done = defer.Deferred()
        proxy.login_email_password({'email': email, 'password': password},
            reply_handler=partial(self.callback, result=None, deferred=done),
            error_handler=partial(self.errback, deferred=done))

        yield done

        result = yield d
        defer.returnValue(result)
