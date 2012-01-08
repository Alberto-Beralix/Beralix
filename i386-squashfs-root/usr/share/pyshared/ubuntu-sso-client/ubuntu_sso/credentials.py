# -*- coding: utf-8 -*-

# Author: Natalia Bidart <natalia.bidart@canonical.com>
# Author: Alejandro J. Cura <alecu@canonical.com>
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
"""Credential management utilities.

'Credentials' provides the following fault-tolerant methods:

 * find_credentials
 * clear_credentials
 * store_credentials
 * register
 * login

The first three return a Deferred that will be fired when the operation was
completed.

The second two use the 'success_cb', 'error_cb' and 'denial_cb' to signal the
caller when the credentials were retrieved successfully, when there was an
error or when the user denied the access to the application, respectively.

For details, please read the Credentials class documentation.

"""

import sys
import traceback
import urllib2

from functools import wraps

from twisted.internet.defer import inlineCallbacks, returnValue

from ubuntu_sso import NO_OP, utils
from ubuntu_sso.keyring import Keyring
from ubuntu_sso.logger import setup_logging

logger = setup_logging('ubuntu_sso.credentials')


APP_NAME_KEY = 'app_name'
TC_URL_KEY = 'tc_url'
HELP_TEXT_KEY = 'help_text'
WINDOW_ID_KEY = 'window_id'
PING_URL_KEY = 'ping_url'
UI_MODULE_KEY = 'ui_module'
UI_CLASS_KEY = 'ui_class'
SUCCESS_CB_KEY = 'success_cb'
ERROR_CB_KEY = 'error_cb'
DENIAL_CB_KEY = 'denial_cb'
ERROR_KEY = 'error_message'
ERROR_DETAIL_KEY = 'detailed_error'


def handle_exceptions(msg):
    """Handle exceptions using 'msg' as error message."""

    def middle(f):
        """Decorate 'f' to catch all errors."""

        @wraps(f)
        def inner(self, *a, **kw):
            """Call 'f' within a try-except block.

            If any exception occurs, self.error_cb is called and the exception
            is logged.
            """
            result = None
            try:
                result = f(self, *a, **kw)
            except:  # pylint: disable=W0702
                logger.exception('%s (app_name: %s): %s.',
                                 f.__name__, self.app_name, msg)
                logger.error('%s (app_name: %s): Calling error_cb at %r.',
                                 f.__name__, self.app_name, self.error_cb)
                error_dict = {ERROR_KEY: msg,
                              ERROR_DETAIL_KEY: traceback.format_exc()}
                self.error_cb(error_dict)
            return result

        return inner

    return middle


def handle_failures(msg):
    """Handle failures using 'msg' as error message."""

    def middle(f):
        """Decorate 'f' to catch all errors."""

        @wraps(f)
        @inlineCallbacks
        def inner(self, *a, **kw):
            """Call 'f' within a try-except block.

            If any exception occurs, self.error_cb is called and the exception
            is logged.
            """
            result = None
            try:
                result = yield f(self, *a, **kw)
            except Exception:  # pylint: disable=W0703
                logger.exception('%s (app_name: %s): %s.',
                                 f.__name__, self.app_name, msg)
                logger.error('%s (app_name: %s): Calling error_cb at %r.',
                                 f.__name__, self.app_name, self.error_cb)
                error_dict = {ERROR_KEY: msg,
                              ERROR_DETAIL_KEY: traceback.format_exc()}
                self.error_cb(error_dict)
            returnValue(result)

        return inner

    return middle


class Credentials(object):
    """Credentials management gateway."""

    def __init__(self, app_name, tc_url=None, help_text='',
                 window_id=0, ping_url=None,
                 ui_module='ubuntu_sso.gtk.gui', ui_class='UbuntuSSOClientGUI',
                 success_cb=NO_OP, error_cb=NO_OP, denial_cb=NO_OP):
        """Return a Credentials management object.

        'app_name' is the application name to be displayed in the GUI.

        'tc_url' is the URL pointing to Terms & Conditions. If None, no
        TOS agreement will be displayed.

        'help_text' is an explanatory text for the end-users, will be shown
         below the headers.

        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        'ping_url' is the url that will be pinged when a user registers/logins
        successfully. The user email will be attached to 'ping_url'.

        'success_cb' will be called when the credentials were retrieved
        successfully. Two params will be passed: the app_name and the
        credentials per se. The credentials is a dictionary of the form:

            {'token': <value>,
             'token_secret': <value>,
             'consumer_key': <value>,
             'consumer_secret': <value>,
             'name': <the token name, matches "[app_name] @ [host name]">}

        'error_cb' will be called when the credentials retrieval failed. Two
        params will be passed: the app_name, and an error dict with 2 keys:
        the error message (user friendly, not translatable so far), and
        the detailed error (usually the traceback).

        'denial_cb' will be called when the user denied the credentials to the
        caller. A single param is passed: the app_name.

        """
        self.app_name = app_name
        self.help_text = help_text
        self.window_id = window_id
        self.ping_url = ping_url
        self.tc_url = tc_url
        self.ui_module = ui_module
        self.ui_class = ui_class
        self._success_cb = success_cb
        self._error_cb = error_cb
        self.denial_cb = denial_cb
        self.inner = None  # will hold the GUI or SSOLoginRoot instance

    @handle_failures(msg='Problem while retrieving credentials')
    @inlineCallbacks
    def _login_success_cb(self, app_name, email):
        """Store credentials when the login/registration succeeded.

        Also, open self.ping_url/email to notify about this new token. If any
        error occur, self.error_cb is called. Otherwise, self.success_cb is
        called.

        Return 0 on success, and a non-zero value (or None) on error.

        """
        logger.info('Login/registration was successful for app %r, email %r',
                    app_name, email)
        creds = yield self.find_credentials()
        if creds is not None:
            assert len(creds) > 0, 'Creds are empty! This should not happen'
            # ping a server with the credentials if we were requested to
            if self.ping_url is not None:
                status = yield self._ping_url(app_name, email, creds)
                if status is None:
                    yield self.clear_credentials()
                    return

            self.success_cb(creds)
            returnValue(0)

    def _auth_denial_cb(self, app_name):
        """The user decided not to allow the registration or login."""
        logger.warning('Login/registration was denied to app %r', app_name)
        self.denial_cb(app_name)

    @handle_failures(msg='Problem opening the ping_url')
    @inlineCallbacks
    def _ping_url(self, app_name, email, credentials):
        """Ping the self.ping_url with the email attached.

        Sign the request with the user credentials. The self.ping_url must be
        defined if this method is being called.

        """
        logger.info('Pinging server for app_name %r, ping_url: %r, '
                    'email %r.', app_name, self.ping_url, email)
        try:
            url = self.ping_url.format(email=email)
        except IndexError:  # tuple index out of range
            url = self.ping_url.format(email)  # format the first substitution

        if url == self.ping_url:
            logger.debug('Original url (%r) could not be formatted, '
                         'appending email (%r).', self.ping_url, email)
            url = self.ping_url + email

        headers = utils.oauth_headers(url, credentials)
        request = urllib2.Request(url, headers=headers)
        logger.debug('Opening the url %r with urllib2.urlopen.',
                     request.get_full_url())
        # This code is blocking, we should change this.
        # I've tried with deferToThread an twisted.web.client.getPage
        # but the returned deferred will never be fired (nataliabidart).
        response = urllib2.urlopen(request)
        logger.debug('Url opened. Response: %s.', response.code)
        returnValue(response)

    @handle_exceptions(msg='Problem opening the Ubuntu SSO user interface')
    def _show_ui(self, login_only):
        """Shows the UI, connect outcome signals."""

        __import__(self.ui_module)
        gui = sys.modules[self.ui_module]

        self.inner = getattr(gui, self.ui_class)(app_name=self.app_name,
                        tc_url=self.tc_url, help_text=self.help_text,
                        window_id=self.window_id, login_only=login_only)

        self.inner.login_success_callback = self._login_success_cb
        self.inner.registration_success_callback = self._login_success_cb
        self.inner.user_cancellation_callback = self._auth_denial_cb

    @handle_exceptions(msg='Problem logging with email and password.')
    def _do_login(self, email, password):
        """Login using email/password, connect outcome signals."""
        from ubuntu_sso.main import SSOLoginRoot
        self.inner = SSOLoginRoot()
        self.inner.login(app_name=self.app_name, email=email,
                         password=password,
                         result_cb=self._login_success_cb,
                         error_cb=self._error_cb,
                         not_validated_cb=self._error_cb)

    @handle_failures(msg='Problem while retrieving credentials')
    @inlineCallbacks
    def _login_or_register(self, login_only, email=None, password=None):
        """Get credentials if found else prompt the GUI."""
        logger.info("_login_or_register: login_only=%r email=%r.",
            login_only, email)
        token = yield self.find_credentials()
        if token is not None and len(token) > 0:
            self.success_cb(token)
        elif token == {}:
            if email and password:
                self._do_login(email, password)
            else:
                self._show_ui(login_only)
        else:
            # something went wrong with find_credentials, already handled.
            logger.info('_login_or_register: call to "find_credentials" went '
                        'wrong, and was already handled.')

    def error_cb(self, error_dict):
        """Handle error and notify the caller."""
        logger.error('Calling error callback at %r (error is %r).',
                     self._error_cb, error_dict)
        self._error_cb(self.app_name, error_dict)

    def success_cb(self, creds):
        """Handle success and notify the caller."""
        logger.debug('Calling success callback at %r.', self._success_cb)
        self._success_cb(self.app_name, creds)

    @inlineCallbacks
    def find_credentials(self):
        """Get the credentials for 'self.app_name'. Return {} if not there."""
        creds = yield Keyring().get_credentials(self.app_name)
        logger.info('find_credentials: self.app_name %r, '
                    'result is {}? %s', self.app_name, creds is None)
        returnValue(creds if creds is not None else {})

    @inlineCallbacks
    def clear_credentials(self):
        """Clear the credentials for 'self.app_name'."""
        yield Keyring().delete_credentials(self.app_name)

    @inlineCallbacks
    def store_credentials(self, token):
        """Store the credentials for 'self.app_name'."""
        yield Keyring().set_credentials(self.app_name, token)

    def register(self):
        """Get credentials if found else prompt the GUI to register."""
        return self._login_or_register(login_only=False)

    def login(self):
        """Get credentials if found else prompt the GUI to login."""
        return self._login_or_register(login_only=True)

    def login_email_password(self, email, password):
        """Get credentials if found else login using email and password."""
        return self._login_or_register(login_only=True,
                                       email=email, password=password)
