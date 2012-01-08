# -*- coding: utf-8 -*-
#
# Author: Natalia Bidart <natalia.bidart@canonical.com>
# Author: Alejandro J. Cura <alecu@canonical.com>
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
"""Main object implementations."""

import os
import sys
import warnings

from ubuntu_sso import NO_OP
from ubuntu_sso.account import Account
from ubuntu_sso.credentials import (Credentials, HELP_TEXT_KEY, PING_URL_KEY,
    TC_URL_KEY, UI_CLASS_KEY, UI_MODULE_KEY, WINDOW_ID_KEY,
    SUCCESS_CB_KEY, ERROR_CB_KEY, DENIAL_CB_KEY)
from ubuntu_sso.keyring import get_token_name, U1_APP_NAME, Keyring
from ubuntu_sso.logger import setup_logging

logger = setup_logging("ubuntu_sso.main")
U1_PING_URL = "https://one.ubuntu.com/oauth/sso-finished-so-get-tokens/"
TIMEOUT_INTERVAL = 10000  # 10 seconds


class SSOLoginProcessor(Account):
    """Login and register users using the Ubuntu Single Sign On service.

    Alias classname to maintain backwards compatibility. DO NOT USE, use
    ubuntu_sso.account.Account instead.
    """

    def __init__(self, sso_service_class=None):
        """Create a new SSO Account manager."""
        msg = 'Use ubuntu_sso.account.Account instead.'
        warnings.warn(msg, DeprecationWarning)
        super(SSOLoginProcessor, self).__init__(sso_service_class)


def except_to_errdict(e):
    """Turn an exception into a dictionary to return thru DBus."""
    result = {
        "errtype": e.__class__.__name__,
    }
    if len(e.args) == 0:
        result["message"] = e.__class__.__doc__
    elif isinstance(e.args[0], dict):
        result.update(e.args[0])
    elif isinstance(e.args[0], basestring):
        result["message"] = e.args[0]

    return result


class SSOLoginRoot(object):
    """Login thru the Single Sign On service."""

    def __init__(self, sso_login_processor_class=Account,
                 sso_service_class=None):
        """Initiate the Login object."""
        self.sso_login_processor_class = sso_login_processor_class
        self.processor = self.sso_login_processor_class(
                                    sso_service_class=sso_service_class)

    def generate_captcha(self, app_name, filename, result_cb,
                         error_cb):
        """Call the matching method in the processor."""
        def f():
            """Inner function that will be run in a thread."""
            return self.processor.generate_captcha(filename)
        thread_execute(f, app_name, result_cb, error_cb)

    def register_user(self, app_name, email, password, name, captcha_id,
                      captcha_solution, result_cb, error_cb):
        """Call the matching method in the processor."""
        def f():
            """Inner function that will be run in a thread."""
            return self.processor.register_user(email, password, name,
                                                captcha_id, captcha_solution)
        thread_execute(f, app_name, result_cb, error_cb)

    def login(self, app_name, email, password, result_cb,
              error_cb, not_validated_cb):
        """Call the matching method in the processor."""
        def f():
            """Inner function that will be run in a thread."""
            token_name = get_token_name(app_name)
            logger.debug('login: token_name %r, email %r, password <hidden>.',
                         token_name, email)
            credentials = self.processor.login(email, password, token_name)
            logger.debug('login returned not None credentials? %r.',
                         credentials is not None)
            return credentials

        def success_cb(app_name, credentials):
            """Login finished successfull."""
            is_validated = self.processor.is_validated(credentials)
            logger.debug('user is validated? %r.', is_validated)
            if is_validated:
                # pylint: disable=E1101
                d = Keyring().set_credentials(app_name, credentials)
                d.addCallback(lambda _: result_cb(app_name, email))
                d.addErrback(lambda failure: \
                             error_cb(app_name,
                                      except_to_errdict(failure.value)))
            else:
                not_validated_cb(app_name, email)
        thread_execute(f, app_name, success_cb, error_cb)

    def validate_email(self, app_name, email, password, email_token,
                       result_cb, error_cb):
        """Call the matching method in the processor."""

        def f():
            """Inner function that will be run in a thread."""
            token_name = get_token_name(app_name)
            credentials = self.processor.validate_email(email, password,
                                                      email_token, token_name)
            return credentials

        def success_cb(app_name, credentials):
            """Validation finished successfully."""
            # pylint: disable=E1101
            d = Keyring().set_credentials(app_name, credentials)
            d.addCallback(lambda _: result_cb(app_name, email))
            failure_cb = lambda f: error_cb(app_name, f.value)
            d.addErrback(failure_cb)

        thread_execute(f, app_name, success_cb, error_cb)

    def request_password_reset_token(self, app_name, email,
                                     result_cb, error_cb):
        """Call the matching method in the processor."""
        def f():
            """Inner function that will be run in a thread."""
            return self.processor.request_password_reset_token(email)
        thread_execute(f, app_name, result_cb, error_cb)

    def set_new_password(self, app_name, email, token, new_password,
                         result_cb, error_cb):
        """Call the matching method in the processor."""
        def f():
            """Inner function that will be run in a thread."""
            return self.processor.set_new_password(email, token,
                                                   new_password)
        thread_execute(f, app_name, result_cb, error_cb)


class SSOCredentialsRoot(object):
    """Object that gets credentials, and login/registers if needed.

    This class is DEPRECATED, use CredentialsManagementRoot instead.

    """

    def __init__(self):
        self.ping_url = os.environ.get('USSOC_PING_URL', U1_PING_URL)
        msg = 'Use ubuntu_sso.main.CredentialsManagementRoot instead.'
        warnings.warn(msg, DeprecationWarning)

    def find_credentials(self, app_name, callback=NO_OP, errback=NO_OP):
        """Get the credentials from the keyring or {} if not there."""

        def log_result(result):
            """Log the result and continue."""
            logger.info('find_credentials: app_name "%s", result is {}? %s',
                        app_name, result == {})
            return result

        d = Credentials(app_name=app_name).find_credentials()
        # pylint: disable=E1101
        d.addCallback(log_result)
        d.addCallbacks(callback, errback)

    def login_or_register_to_get_credentials(self, app_name,
                                             terms_and_conditions_url,
                                             help_text, window_id,
                                             success_cb, error_cb, denial_cb,
                                             ui_module='ubuntu_sso.gtk.gui'):
        """Get credentials if found else prompt GUI to login or register.

        'app_name' will be displayed in the GUI.
        'terms_and_conditions_url' will be the URL pointing to T&C.
        'help_text' is an explanatory text for the end-users, will be shown
         below the headers.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """
        ping_url = self.ping_url if app_name == U1_APP_NAME else None
        obj = Credentials(app_name=app_name, ping_url=ping_url,
                          tc_url=terms_and_conditions_url,
                          help_text=help_text, window_id=window_id,
                          success_cb=success_cb, error_cb=error_cb,
                          denial_cb=denial_cb, ui_module=ui_module)
        obj.register()

    def login_to_get_credentials(self, app_name, help_text, window_id,
                                 success_cb, error_cb, denial_cb,
                                 ui_module='ubuntu_sso.gtk.gui'):
        """Get credentials if found else prompt GUI just to login

        'app_name' will be displayed in the GUI.
        'help_text' is an explanatory text for the end-users, will be shown
         before the login fields.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """
        ping_url = self.ping_url if app_name == U1_APP_NAME else None
        obj = Credentials(app_name=app_name, ping_url=ping_url, tc_url=None,
                          help_text=help_text, window_id=window_id,
                          success_cb=success_cb, error_cb=error_cb,
                          denial_cb=denial_cb, ui_module=ui_module)
        obj.login()

    def clear_token(self, app_name, callback=NO_OP, errback=NO_OP):
        """Clear the token for an application from the keyring.

        'app_name' is the name of the application.
        """
        d = Credentials(app_name=app_name).clear_credentials()
        # pylint: disable=E1101
        d.addCallbacks(lambda _: callback(), errback)


class CredentialsManagementRoot(object):
    """Object that manages credentials.

    Every exposed method in this class requires one mandatory argument:

        - 'app_name': the name of the application. Will be displayed in the
        GUI header, plus it will be used to find/build/clear tokens.

    And accepts another parameter named 'args', which is a dictionary that
    can contain the following:

        - 'help_text': an explanatory text for the end-users, will be
        shown below the header. This is an optional free text field.

        - 'ping_url': the url to open after successful token retrieval. If
        defined, the email will be attached to the url and will be pinged
        with a OAuth-signed request.

        - 'tc_url': the link to the Terms and Conditions page. If defined,
        the checkbox to agree to the terms will link to it.

        - 'window_id': the id of the window which will be set as a parent
        of the GUI. If not defined, no parent will be set.

    """

    def __init__(self, timeout_func, shutdown_func, found_cb, error_cb,
                 denied_cb, *args, **kwargs):
        """Create a new instance.

        - 'found_cb' is a callback that will be executed when the credentials
        were found.

        - 'error_cb' is a callback that will be executed when there was an
        error getting the credentials.

        - 'denied_cb' is a callback that will be executed when the user denied
        the use of the crendetials.

        """
        super(CredentialsManagementRoot, self).__init__(*args, **kwargs)
        self._ref_count = 0
        self.timeout_func = timeout_func
        self.shutdown_func = shutdown_func
        self.found_cb = found_cb
        self.error_cb = error_cb
        self.denied_cb = denied_cb

    def _get_ref_count(self):
        """Get value of ref_count."""
        return self._ref_count

    def _set_ref_count(self, new_value):
        """Set a new value to ref_count."""
        logger.debug('ref_count is %r, changing value to %r.',
                     self._ref_count, new_value)
        if new_value < 0:
            self._ref_count = 0
            msg = 'Attempting to decrease ref_count to a negative value (%r).'
            logger.warning(msg, new_value)
        else:
            self._ref_count = new_value

        if self._ref_count == 0:
            logger.debug('Setting up timer with %r (%r, %r).',
                         self.timeout_func, TIMEOUT_INTERVAL, self.shutdown)
            self.timeout_func(TIMEOUT_INTERVAL, self.shutdown)

    ref_count = property(fget=_get_ref_count, fset=_set_ref_count)

    def shutdown(self):
        """If no ongoing requests, call self.shutdown_func."""
        logger.debug('shutdown!, ref_count is %r.', self._ref_count)
        if self._ref_count == 0:
            logger.info('Shutting down, calling %r.', self.shutdown_func)
            self.shutdown_func()

    valid_keys = (HELP_TEXT_KEY, PING_URL_KEY, TC_URL_KEY,
                  UI_CLASS_KEY, UI_MODULE_KEY, WINDOW_ID_KEY)

    def _parse_args(self, args):
        """Retrieve values from the generic param 'args'."""
        result = dict(i for i in args.iteritems() if i[0] in self.valid_keys)
        result[WINDOW_ID_KEY] = int(args.get(WINDOW_ID_KEY, 0))
        result[SUCCESS_CB_KEY] = self.found_cb
        result[ERROR_CB_KEY] = self.error_cb
        result[DENIAL_CB_KEY] = self.denied_cb
        return result

    def find_credentials(self, app_name, args, success_cb, error_cb):
        """Look for the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        - 'success_cb' is a callback that will be execute if the operation was
        a success.

        - 'error_cb' is a callback that will be executed if the operation had
        an error.

        """
        self.ref_count += 1
        obj = Credentials(app_name)
        d = obj.find_credentials()
        # pylint: disable=E1101
        d.addCallback(success_cb)
        d.addErrback(error_cb, app_name)

    def clear_credentials(self, app_name, args, success_cb, error_cb):
        """Clear the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        - 'success_cb' is a callback that will be execute if the operation was
        a success.

        - 'error_cb' is a callback that will be executed if the operation had
        an error.

        """
        self.ref_count += 1
        obj = Credentials(app_name)
        d = obj.clear_credentials()
        # pylint: disable=E1101
        d.addCallback(success_cb)
        d.addErrback(error_cb, app_name)

    def store_credentials(self, app_name, args, success_cb, error_cb):
        """Store the token for an application.

        - 'app_name': the name of the application which credentials are
        going to be stored.

        - 'args' is the dictionary holding the credentials. Needs to provide
        the following mandatory keys: 'token', 'token_key', 'consumer_key',
        'consumer_secret'.

        - 'success_cb' is a callback that will be execute if the operation was
        a success.

        - 'error_cb' is a callback that will be executed if the operation had
        an error.
        """
        self.ref_count += 1
        obj = Credentials(app_name)
        d = obj.store_credentials(args)
        # pylint: disable=E1101
        d.addCallback(success_cb)
        d.addErrback(error_cb, app_name)

    def register(self, app_name, args):
        """Get credentials if found else prompt GUI to register."""
        self.ref_count += 1
        obj = Credentials(app_name, **self._parse_args(args))
        obj.register()

    def login(self, app_name, args):
        """Get credentials if found else prompt GUI to login."""
        self.ref_count += 1
        obj = Credentials(app_name, **self._parse_args(args))
        obj.login()

    def login_email_password(self, app_name, args):
        """Get credentials if found else try to login.

        Login will be done by inspecting 'args' and expecting to find two keys:
        'email' and 'password'.

        """
        self.ref_count += 1
        email = args.pop('email')
        password = args.pop('password')
        obj = Credentials(app_name, **self._parse_args(args))
        obj.login_email_password(email=email, password=password)


# pylint: disable=C0103
SSOLogin = None
SSOCredentials = None
CredentialsManagement = None

if sys.platform == 'win32':
    from ubuntu_sso.main import windows
    SSOLogin = windows.SSOLogin
    SSOCredentials = windows.SSOCredentials
    CredentialsManagement = windows.CredentialsManagement
    TIMEOUT_INTERVAL = 10000000000  # forever
    thread_execute = windows.blocking
else:
    from ubuntu_sso.main import linux
    SSOLogin = linux.SSOLogin
    SSOCredentials = linux.SSOCredentials
    CredentialsManagement = linux.CredentialsManagement
    thread_execute = linux.blocking
