# -*- coding: utf-8 -*-
#
# ubuntu_sso.main - main login handling interface
#
# Author: Natalia Bidart <natalia.bidart@canonical.com>
# Author: Alejandro J. Cura <alecu@canonical.com>
#
# Copyright 2009 Canonical Ltd.
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
"""Single Sign On login handler.

An utility which accepts requests for Ubuntu Single Sign On login over D-Bus.

The OAuth process is handled, including adding the OAuth access token to the
local keyring.

"""

import threading
import warnings

import dbus.service

from ubuntu_sso import (DBUS_ACCOUNT_PATH, DBUS_IFACE_USER_NAME,
    DBUS_IFACE_CRED_NAME, DBUS_CREDENTIALS_IFACE, NO_OP)
from ubuntu_sso.account import Account
from ubuntu_sso.credentials import ERROR_KEY, ERROR_DETAIL_KEY
from ubuntu_sso.logger import setup_logging
from ubuntu_sso.main import (CredentialsManagementRoot, SSOLoginRoot,
                             SSOCredentialsRoot, except_to_errdict)


# Disable the invalid name warning, as we have a lot of DBus style names
# pylint: disable=C0103


logger = setup_logging("ubuntu_sso.main")


def blocking(f, app_name, result_cb, error_cb):
    """Run f in a thread; return or throw an exception thru the callbacks."""
    def _in_thread():
        """The part that runs inside the thread."""
        try:
            result_cb(app_name, f())
        except Exception, e:  # pylint: disable=W0703
            msg = "Exception while running DBus blocking code in a thread:"
            logger.exception(msg)
            error_cb(app_name, except_to_errdict(e))
    threading.Thread(target=_in_thread).start()


class SSOLogin(dbus.service.Object):
    """Login thru the Single Sign On service."""

    # Operator not preceded by a space (fails with dbus decorators)
    # pylint: disable=C0322

    def __init__(self, bus_name, object_path=DBUS_ACCOUNT_PATH,
                 sso_login_processor_class=Account,
                 sso_service_class=None):
        """Initiate the Login object."""
        dbus.service.Object.__init__(self, object_path=object_path,
                                     bus_name=bus_name)
        self.root = SSOLoginRoot(sso_login_processor_class, sso_service_class)
        msg = 'Use ubuntu_sso.main.CredentialsManagement instead.'
        warnings.warn(msg, DeprecationWarning)

    # generate_capcha signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def CaptchaGenerated(self, app_name, result):
        """Signal thrown after the captcha is generated."""
        logger.debug('SSOLogin: emitting CaptchaGenerated with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def CaptchaGenerationError(self, app_name, error):
        """Signal thrown when there's a problem generating the captcha."""
        logger.debug('SSOLogin: emitting CaptchaGenerationError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='ss')
    def generate_captcha(self, app_name, filename):
        """Call the matching method in the processor."""
        self.root.generate_captcha(app_name, filename,
                                   self.CaptchaGenerated,
                                   self.CaptchaGenerationError)

    # register_user signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def UserRegistered(self, app_name, result):
        """Signal thrown when the user is registered."""
        logger.debug('SSOLogin: emitting UserRegistered with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def UserRegistrationError(self, app_name, error):
        """Signal thrown when there's a problem registering the user."""
        logger.debug('SSOLogin: emitting UserRegistrationError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='ssssss')
    def register_user(self, app_name, email, password, name,
                      captcha_id, captcha_solution):
        """Call the matching method in the processor."""
        self.root.register_user(app_name, email, password, name, captcha_id,
                                captcha_solution,
                                self.UserRegistered,
                                self.UserRegistrationError)

    # login signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def LoggedIn(self, app_name, result):
        """Signal thrown when the user is logged in."""
        logger.debug('SSOLogin: emitting LoggedIn with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def LoginError(self, app_name, error):
        """Signal thrown when there is a problem in the login."""
        logger.debug('SSOLogin: emitting LoginError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def UserNotValidated(self, app_name, result):
        """Signal thrown when the user is not validated."""
        logger.debug('SSOLogin: emitting UserNotValidated with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='sss')
    def login(self, app_name, email, password):
        """Call the matching method in the processor."""
        self.root.login(app_name, email, password, self.LoggedIn,
                        self.LoginError, self.UserNotValidated)

    # validate_email signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def EmailValidated(self, app_name, result):
        """Signal thrown after the email is validated."""
        logger.debug('SSOLogin: emitting EmailValidated with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def EmailValidationError(self, app_name, error):
        """Signal thrown when there's a problem validating the email."""
        logger.debug('SSOLogin: emitting EmailValidationError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='ssss')
    def validate_email(self, app_name, email, password, email_token):
        """Call the matching method in the processor."""
        self.root.validate_email(app_name, email, password, email_token,
                                 self.EmailValidated,
                                 self.EmailValidationError)

    # request_password_reset_token signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def PasswordResetTokenSent(self, app_name, result):
        """Signal thrown when the token is succesfully sent."""
        logger.debug('SSOLogin: emitting PasswordResetTokenSent with app_name '
                     '"%s" and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def PasswordResetError(self, app_name, error):
        """Signal thrown when there's a problem sending the token."""
        logger.debug('SSOLogin: emitting PasswordResetError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='ss')
    def request_password_reset_token(self, app_name, email):
        """Call the matching method in the processor."""
        self.root.request_password_reset_token(app_name, email,
                                               self.PasswordResetTokenSent,
                                               self.PasswordResetError)

    # set_new_password signals
    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="ss")
    def PasswordChanged(self, app_name, result):
        """Signal thrown when the token is succesfully sent."""
        logger.debug('SSOLogin: emitting PasswordChanged with app_name "%s" '
                     'and result %r', app_name, result)

    @dbus.service.signal(DBUS_IFACE_USER_NAME, signature="sa{ss}")
    def PasswordChangeError(self, app_name, error):
        """Signal thrown when there's a problem sending the token."""
        logger.debug('SSOLogin: emitting PasswordChangeError with '
                     'app_name "%s" and error %r', app_name, error)

    @dbus.service.method(dbus_interface=DBUS_IFACE_USER_NAME,
                         in_signature='ssss')
    def set_new_password(self, app_name, email, token, new_password):
        """Call the matching method in the processor."""
        self.root.set_new_password(app_name, email, token, new_password,
                                   self.PasswordChanged,
                                   self.PasswordChangeError)


class SSOCredentials(dbus.service.Object):
    """DBus object that gets credentials, and login/registers if needed.

    This class is Deprecated. DO NOT USE, use CredentialsManagement instead.

    """

    # Operator not preceded by a space (fails with dbus decorators)
    # pylint: disable=C0322

    def __init__(self, *args, **kwargs):
        dbus.service.Object.__init__(self, *args, **kwargs)
        self.root = SSOCredentialsRoot()
        warnings.warn('%r DBus object is deprecated, please use %r instead.' %
                      (DBUS_IFACE_CRED_NAME, DBUS_CREDENTIALS_IFACE),
                      DeprecationWarning)

    def _process_error(self, app_name, error_dict):
        """Process the 'error_dict' and emit CredentialsError."""
        msg = error_dict.get(ERROR_KEY, 'No error message given.')
        detail = error_dict.get(ERROR_DETAIL_KEY, 'No detailed error given.')
        self.CredentialsError(app_name, msg, detail)

    @dbus.service.signal(DBUS_IFACE_CRED_NAME, signature="s")
    def AuthorizationDenied(self, app_name):
        """Signal thrown when the user denies the authorization."""
        logger.info('SSOCredentials: emitting AuthorizationDenied with '
                    'app_name "%s"', app_name)

    @dbus.service.signal(DBUS_IFACE_CRED_NAME, signature="sa{ss}")
    def CredentialsFound(self, app_name, credentials):
        """Signal thrown when the credentials are found."""
        logger.info('SSOCredentials: emitting CredentialsFound with '
                    'app_name "%s"', app_name)

    @dbus.service.signal(DBUS_IFACE_CRED_NAME, signature="sss")
    def CredentialsError(self, app_name, error_message, detailed_error):
        """Signal thrown when there is a problem finding the credentials."""
        logger.error('SSOCredentials: emitting CredentialsError with app_name '
                     '"%s" and error_message %r', app_name, error_message)

    @dbus.service.method(dbus_interface=DBUS_IFACE_CRED_NAME,
                         in_signature="s", out_signature="a{ss}",
                         async_callbacks=("callback", "errback"))
    def find_credentials(self, app_name, callback=NO_OP, errback=NO_OP):
        """Get the credentials from the keyring or {} if not there."""
        self.root.find_credentials(app_name, callback, errback)

    @dbus.service.method(dbus_interface=DBUS_IFACE_CRED_NAME,
                         in_signature="sssx", out_signature="")
    def login_or_register_to_get_credentials(self, app_name,
                                             terms_and_conditions_url,
                                             help_text, window_id):
        """Get credentials if found else prompt GUI to login or register.

        'app_name' will be displayed in the GUI.
        'terms_and_conditions_url' will be the URL pointing to T&C.
        'help_text' is an explanatory text for the end-users, will be shown
         below the headers.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """
        self.root.login_or_register_to_get_credentials(app_name,
                                               terms_and_conditions_url,
                                               help_text, window_id,
                                               self.CredentialsFound,
                                               self._process_error,
                                               self.AuthorizationDenied,
                                               ui_module='ubuntu_sso.gtk.gui')

    @dbus.service.method(dbus_interface=DBUS_IFACE_CRED_NAME,
                         in_signature="ssx", out_signature="")
    def login_to_get_credentials(self, app_name, help_text, window_id):
        """Get credentials if found else prompt GUI just to login

        'app_name' will be displayed in the GUI.
        'help_text' is an explanatory text for the end-users, will be shown
         before the login fields.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """
        self.root.login_to_get_credentials(app_name, help_text, window_id,
                                           self.CredentialsFound,
                                           self._process_error,
                                           self.AuthorizationDenied,
                                           ui_module='ubuntu_sso.gtk.gui')

    @dbus.service.method(dbus_interface=DBUS_IFACE_CRED_NAME,
                         in_signature='s', out_signature='',
                         async_callbacks=("callback", "errback"))
    def clear_token(self, app_name, callback=NO_OP, errback=NO_OP):
        """Clear the token for an application from the keyring.

        'app_name' is the name of the application.
        """
        self.root.clear_token(app_name, callback, errback)


class CredentialsManagement(dbus.service.Object):
    """DBus object that manages credentials.

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

    def __init__(self, timeout_func, shutdown_func, *args, **kwargs):
        super(CredentialsManagement, self).__init__(*args, **kwargs)
        self.root = CredentialsManagementRoot(timeout_func, shutdown_func,
                                              self.CredentialsFound,
                                              self.CredentialsError,
                                              self.AuthorizationDenied)

    # Operator not preceded by a space (fails with dbus decorators)
    # pylint: disable=C0322

    def _process_failure(self, failure, app_name):
        """Process the 'failure' and emit CredentialsError."""
        self.CredentialsError(app_name, except_to_errdict(failure.value))

    def shutdown(self):
        """If no ongoing requests, call self.shutdown_func."""
        logger.debug('shutdown!, ref_count is %r.', self.root.ref_count)
        self.root.shutdown()

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='s')
    def AuthorizationDenied(self, app_name):
        """Signal thrown when the user denies the authorization."""
        self.root.ref_count -= 1
        logger.info('%s: emitting AuthorizationDenied with app_name "%s".',
                    self.__class__.__name__, app_name)

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='sa{ss}')
    def CredentialsFound(self, app_name, credentials):
        """Signal thrown when the credentials are found."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsFound with app_name "%s".',
                    self.__class__.__name__, app_name)

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='s')
    def CredentialsNotFound(self, app_name):
        """Signal thrown when the credentials are not found."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsNotFound with app_name "%s".',
                    self.__class__.__name__, app_name)

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='s')
    def CredentialsCleared(self, app_name):
        """Signal thrown when the credentials were cleared."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsCleared with app_name "%s".',
                    self.__class__.__name__, app_name)

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='s')
    def CredentialsStored(self, app_name):
        """Signal thrown when the credentials were cleared."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsStored with app_name "%s".',
                    self.__class__.__name__, app_name)

    @dbus.service.signal(DBUS_CREDENTIALS_IFACE, signature='sa{ss}')
    def CredentialsError(self, app_name, error_dict):
        """Signal thrown when there is a problem getting the credentials."""
        self.root.ref_count -= 1
        logger.error('%s: emitting CredentialsError with app_name "%s" and '
                     'error_dict %r.', self.__class__.__name__, app_name,
                     error_dict)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def find_credentials(self, app_name, args):
        """Look for the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """

        def success_cb(credentials):
            """Find credentials and notify using signals."""
            if credentials is not None and len(credentials) > 0:
                self.CredentialsFound(app_name, credentials)
            else:
                self.CredentialsNotFound(app_name)

        self.root.find_credentials(app_name, args, success_cb,
                                   self._process_failure)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def clear_credentials(self, app_name, args):
        """Clear the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """
        self.root.clear_credentials(app_name, args,
                                lambda _: self.CredentialsCleared(app_name),
                                self._process_failure)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def store_credentials(self, app_name, args):
        """Store the token for an application.

        - 'app_name': the name of the application which credentials are
        going to be stored.

        - 'args' is the dictionary holding the credentials. Needs to provide
        the following mandatory keys: 'token', 'token_key', 'consumer_key',
        'consumer_secret'.

        """
        self.root.store_credentials(app_name, args,
                                lambda _: self.CredentialsStored(app_name),
                                self._process_failure)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def register(self, app_name, args):
        """Get credentials if found else prompt GUI to register."""
        self.root.register(app_name, args)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def login(self, app_name, args):
        """Get credentials if found else prompt GUI to login."""
        self.root.login(app_name, args)

    @dbus.service.method(dbus_interface=DBUS_CREDENTIALS_IFACE,
                         in_signature='sa{ss}', out_signature='')
    def login_email_password(self, app_name, args):
        """Get credentials if found, else login using email and password.

        - 'args' should contain at least the follwing keys: 'email' and
        'password'. Those will be used to issue a new SSO token, which will be
        returned trough the CredentialsFound signal.

        """
        self.root.login_email_password(app_name, args)
