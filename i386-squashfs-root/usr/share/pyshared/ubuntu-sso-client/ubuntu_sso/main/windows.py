# -*- coding: utf-8 -*-
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
"""Main implementation on windows."""

import warnings

# pylint: disable=F0401
from _winreg import HKEY_LOCAL_MACHINE, OpenKey, QueryValueEx

from functools import wraps

import win32process
import win32security

from twisted.internet import defer, reactor
from twisted.internet.threads import deferToThread
from twisted.spread.pb import (
    DeadReferenceError,
    PBClientFactory,
    Referenceable,
    Root,
)

from ubuntu_sso import NO_OP
from ubuntu_sso.account import Account
from ubuntu_sso.credentials import ERROR_KEY, ERROR_DETAIL_KEY
from ubuntu_sso.logger import setup_logging
from ubuntu_sso.main import (CredentialsManagementRoot, SSOLoginRoot,
                             SSOCredentialsRoot, except_to_errdict)
from ubuntu_sso.utils.tcpactivation import ActivationConfig, ActivationClient

logger = setup_logging("ubuntu_sso.main.windows")
NAMED_PIPE_URL = '\\\\.\\pipe\\ubuntu_sso\\%s'
U1_REG_PATH = r'Software\Ubuntu One'
SSO_INSTALL_PATH = 'SSOInstallPath'
LOCALHOST = "127.0.0.1"
SSO_BASE_PB_PORT = 50000
SSO_RESERVED_PORTS = 3000
SSO_PORT_ALLOCATION_STEP = 3  # contiguous ports for sso, u1client, and u1cp
SSO_SERVICE_NAME = "ubuntu-sso-client"


def get_user_id():
    """Find the numeric user id."""
    process_handle = win32process.GetCurrentProcess()
    token_handle = win32security.OpenProcessToken(process_handle,
                                              win32security.TOKEN_ALL_ACCESS)
    user_sid = win32security.GetTokenInformation(token_handle,
                                              win32security.TokenUser)[0]
    sid_parts = str(user_sid).split("-")
    uid = int(sid_parts[-1])
    return uid


def get_sso_pb_port():
    """Get the port on which the SSO pb is running."""
    uid = get_user_id()
    uid_modulo = uid % SSO_RESERVED_PORTS
    port = SSO_BASE_PB_PORT + uid_modulo * SSO_PORT_ALLOCATION_STEP
    return port


def remote_handler(handler):
    """Execute a callback in a remote object.

    If the callback takes arguments, it's assumed that the last
    one is a twisted Failure, and it has no keyword arguments.
    """
    if handler:

        def f(*args):
            """Process arguments and call remote."""
            try:
                args = list(args)
                if args:
                    args[-1] = except_to_errdict(args[-1].value)
                return handler.callRemote('execute', *args)
            # Yes, I want to catch everything
            # pylint: disable=W0703
            except Exception:
                logger.exception("Remote handler argument processing error:")
        return f

    logger.warning("Remote handler got an empty handler.")
    return lambda: None


def get_activation_cmdline(service_name):
    """Get the command line to activate an executable."""
    key = OpenKey(HKEY_LOCAL_MACHINE, U1_REG_PATH)
    # pylint: disable=W0612
    value, registry_type = QueryValueEx(key, "path-" + service_name)
    return value


def get_activation_config():
    """Get the configuration to activate the sso service."""
    port = get_sso_pb_port()
    service_name = SSO_SERVICE_NAME
    cmdline = get_activation_cmdline(service_name)
    return ActivationConfig(service_name, cmdline, port)


def blocking(f, app_name, result_cb, error_cb):
    """Run f in a thread; return or throw an exception thru the callbacks."""
    d = deferToThread(f)
    # the calls in twisted will be called with the args in a diff order,
    # in order to follow the linux api, we swap them around with a lambda
    d.addCallback(lambda result, app: result_cb(app, result), app_name)
    d.addErrback(lambda err, app:
                 error_cb(app, except_to_errdict(err.value)), app_name)


class RemoteMeta(type):
    """Append remote_ to the remote methods.

    Remote has to be appended to the remote method to work over pb but this
    names cannot be used since the other platforms do not expect the remote
    prefix. This metaclass creates those prefixes so that the methods can be
    correctly called.
    """

    def __new__(mcs, name, bases, attrs):
        remote_calls = attrs.get('remote_calls', None)
        if remote_calls:
            for current in remote_calls:
                attrs['remote_' + current] = attrs[current]
        return super(RemoteMeta, mcs).__new__(mcs, name, bases, attrs)


class SignalBroadcaster(object):
    """Object that allows to emit signals to clients over the IPC."""

    def __init__(self):
        """Create a new instance."""
        self.clients = []

    def _emit_failure(self, reason):
        """Log the issue when emitting a signal."""
        logger.warn('Could not emit signal due to %s', reason)
        logger.warn('Traceback is:\n%s', reason.printDetailedTraceback())

    def remote_register_to_signals(self, client):
        """Allow a client to register to a signal."""
        if client not in self.clients:
            self.clients.append(client)
        else:
            logger.warn('Client %s tried to register twice.', client)

    def remote_unregister_to_signals(self, client):
        """Allow a client to register to a signal."""
        if client in self.clients:
            self.clients.remove(client)
        else:
            logger.warn('Tried to remove %s when was not registered.', client)

    def emit_signal(self, signal_name, *args, **kwargs):
        """Emit the given signal to the clients."""
        dead_clients = []
        for current_client in self.clients:
            try:
                d = current_client.callRemote(signal_name, *args, **kwargs)
                d.addErrback(self._emit_failure)
            except DeadReferenceError:
                dead_clients.append(current_client)
        for client in dead_clients:
            self.remote_unregister_to_signals(client)


class SSOLogin(Referenceable, SignalBroadcaster):
    """Login thru the Single Sign On service."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'generate_captcha',
        'register_user',
        'login',
        'validate_email',
        'request_password_reset_token',
        'set_new_password']

    def __init__(self, bus_name, object_path=None,
                 sso_login_processor_class=Account,
                 sso_service_class=None):
        """Initiate the Login object."""
        super(SSOLogin, self).__init__()
        # ignore bus_name and object path so that we do not break the current
        # API. Shall we change this???
        self.root = SSOLoginRoot(sso_login_processor_class, sso_service_class)

    # generate_capcha signals
    def emit_captcha_generated(self, app_name, result):
        """Signal thrown after the captcha is generated."""
        logger.debug('SSOLogin: emitting CaptchaGenerated with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_captcha_generated', app_name, result)

    def emit_captcha_generation_error(self, app_name, raised_error):
        """Signal thrown when there's a problem generating the captcha."""
        logger.debug('SSOLogin: emitting CaptchaGenerationError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_captcha_generation_error', app_name,
                         except_to_errdict(raised_error.value))

    def generate_captcha(self, app_name, filename):
        """Call the matching method in the processor."""
        self.root.generate_captcha(app_name, filename,
                                   self.emit_captcha_generated,
                                   self.emit_captcha_generation_error)

    # register_user signals
    def emit_user_registered(self, app_name, result):
        """Signal thrown when the user is registered."""
        logger.debug('SSOLogin: emitting UserRegistered with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_user_registered', app_name, result)

    def emit_user_registration_error(self, app_name, raised_error):
        """Signal thrown when there's a problem registering the user."""
        logger.debug('SSOLogin: emitting UserRegistrationError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_user_registration_error', app_name,
                         except_to_errdict(raised_error.value))

    def register_user(self, app_name, email, password, displayname,
                      captcha_id, captcha_solution):
        """Call the matching method in the processor."""
        self.root.register_user(app_name, email, password, displayname,
                                captcha_id, captcha_solution,
                                self.emit_user_registered,
                                self.emit_user_registration_error)

    # login signals
    def emit_logged_in(self, app_name, result):
        """Signal thrown when the user is logged in."""
        logger.debug('SSOLogin: emitting LoggedIn with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_logged_in', app_name, result)

    def emit_login_error(self, app_name, raised_error):
        """Signal thrown when there is a problem in the login."""
        logger.debug('SSOLogin: emitting LoginError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_login_error', app_name,
                         except_to_errdict(raised_error.value))

    def emit_user_not_validated(self, app_name, result):
        """Signal thrown when the user is not validated."""
        logger.debug('SSOLogin: emitting UserNotValidated with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_user_not_validated', app_name, result)

    def login(self, app_name, email, password):
        """Call the matching method in the processor."""
        self.root.login(app_name, email, password,
                        self.emit_logged_in, self.emit_login_error,
                        self.emit_user_not_validated)

    # validate_email signals
    def emit_email_validated(self, app_name, result):
        """Signal thrown after the email is validated."""
        logger.debug('SSOLogin: emitting EmailValidated with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_email_validated', app_name, result)

    def emit_email_validation_error(self, app_name, raised_error):
        """Signal thrown when there's a problem validating the email."""
        logger.debug('SSOLogin: emitting EmailValidationError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_email_validation_error', app_name,
                         except_to_errdict(raised_error.value))

    def validate_email(self, app_name, email, password, email_token):
        """Call the matching method in the processor."""
        self.root.validate_email(app_name, email, password, email_token,
                                 self.emit_email_validated,
                                 self.emit_email_validation_error)

    # request_password_reset_token signals
    def emit_password_reset_token_sent(self, app_name, result):
        """Signal thrown when the token is successfully sent."""
        logger.debug('SSOLogin: emitting PasswordResetTokenSent with app_name '
                     '"%s" and result %r', app_name, result)
        self.emit_signal('on_password_reset_token_sent', app_name, result)

    def emit_password_reset_error(self, app_name, raised_error):
        """Signal thrown when there's a problem sending the token."""
        logger.debug('SSOLogin: emitting PasswordResetError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_password_reset_error', app_name,
                         except_to_errdict(raised_error.value))

    def request_password_reset_token(self, app_name, email):
        """Call the matching method in the processor."""
        self.root.request_password_reset_token(app_name, email,
                                        self.emit_password_reset_token_sent,
                                        self.emit_password_reset_error)

    # set_new_password signals
    def emit_password_changed(self, app_name, result):
        """Signal thrown when the token is successfully sent."""
        logger.debug('SSOLogin: emitting PasswordChanged with app_name "%s" '
                     'and result %r', app_name, result)
        self.emit_signal('on_password_changed', app_name, result)

    def emit_password_change_error(self, app_name, raised_error):
        """Signal thrown when there's a problem sending the token."""
        logger.debug('SSOLogin: emitting PasswordChangeError with '
                     'app_name "%s" and error %r', app_name, raised_error)
        self.emit_signal('on_password_change_error', app_name,
                         except_to_errdict(raised_error.value))

    def set_new_password(self, app_name, email, token, new_password):
        """Call the matching method in the processor."""
        self.root.set_new_password(app_name, email, token, new_password,
                                   self.emit_password_changed,
                                   self.emit_password_change_error)


class SSOCredentials(Referenceable, SignalBroadcaster):
    """DBus object that gets credentials, and login/registers if needed."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'find_credentials',
        'login_or_register_to_get_credentials',
        'login_to_get_credentials',
        'clear_token',
    ]

    def __init__(self, *args, **kwargs):
        super(SSOCredentials, self).__init__()
        self.root = SSOCredentialsRoot()

    def _process_error(self, app_name, error_dict):
        """Process the 'error_dict' and emit CredentialsError."""
        msg = error_dict.get(ERROR_KEY, 'No error message given.')
        detail = error_dict.get(ERROR_DETAIL_KEY, 'No detailed error given.')
        self.emit_credentials_error(app_name, msg, detail)

    def emit_authorization_denied(self, app_name):
        """Signal thrown when the user denies the authorization."""
        logger.info('SSOCredentials: emitting AuthorizationDenied with '
                    'app_name "%s"', app_name)
        self.emit_signal('on_authorization_denied', app_name)

    def emit_credentials_found(self, app_name, credentials):
        """Signal thrown when the credentials are found."""
        logger.info('SSOCredentials: emitting CredentialsFound with '
                    'app_name "%s"', app_name)
        self.emit_signal('on_credentials_found', app_name, credentials)

    def emit_credentials_error(self, app_name, error_message, detailed_error):
        """Signal thrown when there is a problem finding the credentials."""
        logger.error('SSOCredentials: emitting CredentialsError with app_name '
                     '"%s" and error_message %r', app_name, error_message)
        self.emit_signal('on_credentials_error', app_name, error_message,
                         detailed_error)

    def find_credentials(self, app_name, callback=NO_OP, errback=NO_OP):
        """Get the credentials from the keyring or {} if not there."""
        self.root.find_credentials(app_name, remote_handler(callback),
                                   remote_handler(errback))

    def login_or_register_to_get_credentials(self, app_name,
                                             terms_and_conditions_url,
                                             help_text, window_id,
                                             ui_module='ubuntu_sso.qt.gui'):
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
                                                self.emit_credentials_found,
                                                self._process_error,
                                                self.emit_authorization_denied,
                                                ui_module=ui_module)

    def login_to_get_credentials(self, app_name, help_text, window_id):
        """Get credentials if found else prompt GUI just to login

        'app_name' will be displayed in the GUI.
        'help_text' is an explanatory text for the end-users, will be shown
         before the login fields.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """
        self.root.login_to_get_credentials(app_name, help_text, window_id,
                                           self.emit_credentials_found,
                                           self._process_error,
                                           self.emit_authorization_denied,
                                           ui_module='ubuntu_sso.qt.gui')

    def clear_token(self, app_name, callback=NO_OP, errback=NO_OP):
        """Clear the token for an application from the keyring.

        'app_name' is the name of the application.
        """
        self.root.clear_token(app_name, remote_handler(callback),
                              remote_handler(errback))


class CredentialsManagement(Referenceable, SignalBroadcaster):
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

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'find_credentials',
        'clear_credentials',
        'store_credentials',
        'register',
        'shutdown',
        'login',
        'login_email_password',
    ]

    def __init__(self, timeout_func, shutdown_func, *args, **kwargs):
        super(CredentialsManagement, self).__init__(*args, **kwargs)
        self.root = CredentialsManagementRoot(timeout_func, shutdown_func,
                                              self.emit_credentials_found,
                                              self.emit_credentials_error,
                                              self.emit_authorization_denied)

    def _process_failure(self, failure, app_name):
        """Process the 'failure' and emit CredentialsError."""
        self.emit_credentials_error(app_name, except_to_errdict(failure.value))

    def shutdown(self):
        """If no ongoing requests, call self.shutdown_func."""
        logger.debug('shutdown!, ref_count is %r.', self.root.ref_count)
        self.root.shutdown()

    def emit_authorization_denied(self, app_name):
        """Signal thrown when the user denies the authorization."""
        self.root.ref_count -= 1
        logger.info('%s: emitting AuthorizationDenied with app_name "%s".',
                    self.__class__.__name__, app_name)
        self.emit_signal('on_authorization_denied', app_name)

    def emit_credentials_found(self, app_name, credentials):
        """Signal thrown when the credentials are found."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsFound with app_name "%s".',
                    self.__class__.__name__, app_name)
        self.emit_signal('on_credentials_found', app_name, credentials)

    def emit_credentials_not_found(self, app_name):
        """Signal thrown when the credentials are not found."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsNotFound with app_name "%s".',
                    self.__class__.__name__, app_name)
        self.emit_signal('on_credentials_not_found', app_name)

    def emit_credentials_cleared(self, app_name):
        """Signal thrown when the credentials were cleared."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsCleared with app_name "%s".',
                    self.__class__.__name__, app_name)
        self.emit_signal('on_credentials_cleared', app_name)

    def emit_credentials_stored(self, app_name):
        """Signal thrown when the credentials were cleared."""
        self.root.ref_count -= 1
        logger.info('%s: emitting CredentialsStored with app_name "%s".',
                    self.__class__.__name__, app_name)
        self.emit_signal('on_credentials_stored', app_name)

    def emit_credentials_error(self, app_name, error_dict):
        """Signal thrown when there is a problem getting the credentials."""
        self.root.ref_count -= 1
        logger.error('%s: emitting CredentialsError with app_name "%s" and '
                     'error_dict %r.', self.__class__.__name__, app_name,
                     error_dict)
        self.emit_signal('on_credentials_error', app_name, error_dict)

    def find_credentials(self, app_name, args):
        """Look for the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """

        def success_cb(credentials):
            """Find credentials and notify using signals."""
            if credentials is not None and len(credentials) > 0:
                self.emit_credentials_found(app_name, credentials)
            else:
                self.emit_credentials_not_found(app_name)

        self.root.find_credentials(app_name, args, success_cb,
                                   self._process_failure)

    def clear_credentials(self, app_name, args):
        """Clear the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """
        self.root.clear_credentials(app_name, args,
                            lambda _: self.emit_credentials_cleared(app_name),
                            self._process_failure)

    def store_credentials(self, app_name, args):
        """Store the token for an application.

        - 'app_name': the name of the application which credentials are
        going to be stored.

        - 'args' is the dictionary holding the credentials. Needs to provide
        the following mandatory keys: 'token', 'token_key', 'consumer_key',
        'consumer_secret'.

        """
        self.root.store_credentials(app_name, args,
                            lambda _: self.emit_credentials_stored(app_name),
                            self._process_failure)

    def register(self, app_name, args):
        """Get credentials if found else prompt GUI to register."""
        self.root.register(app_name, args)

    def login(self, app_name, args):
        """Get credentials if found else prompt GUI to login."""
        self.root.login(app_name, args)

    def login_email_password(self, app_name, args):
        """Get credentials if found, else login."""
        self.root.login_email_password(app_name, args)


class UbuntuSSORoot(object, Root):
    """Root object that exposes the diff referenceable objects."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'get_sso_login',
        'get_sso_credentials',
        'get_cred_manager']

    def __init__(self, sso_login, sso_credentials, cred_manager):
        """Create a new instance that will expose the objects."""
        super(UbuntuSSORoot, self).__init__()
        self._sso_login = sso_login
        self._sso_credentials = sso_credentials
        self._cred_manager = cred_manager

    def get_sso_login(self):
        """Return the sso_login."""
        return self._sso_login

    def get_sso_credentials(self):
        """Return the sso credentials."""
        return self._sso_credentials

    def get_cred_manager(self):
        """Return the credentials manager."""
        return self._cred_manager


def remote(function):
    """Decorate the function to make the remote call."""

    @wraps(function)
    def remote_wrapper(instance, *args, **kwargs):
        """Return the deferred for the remote call."""
        fname = function.__name__
        logger.info('Performing %s as a remote call.', fname)
        result = instance.remote.callRemote(fname, *args, **kwargs)
        return result

    return remote_wrapper


def signal(function):
    """Decorate a function to perform the signal callback."""

    @wraps(function)
    def callback_wrapper(instance, *args, **kwargs):
        """Return the result of the callback if present."""
        fname = function.__name__
        callback = getattr(instance, fname + '_cb', None)
        if callback is not None:
            logger.info('Emitting remote signal for %s with callback %r.',
                        fname, callback)
            return callback(*args, **kwargs)

    return callback_wrapper


class RemoteClient(object):
    """Represent a client for remote calls."""

    def __init__(self, remote_object):
        """Create instance."""
        self.remote = remote_object

    def register_to_signals(self):
        """Register to the signals."""
        return self.remote.callRemote('register_to_signals', self)

    def unregister_to_signals(self):
        """Register to the signals."""
        return self.remote.callRemote('unregister_to_signals', self)


class RemoteHandler(object, Referenceable):
    """Represents a handler that can be called so that is called remotely."""

    def __init__(self, cb):
        """Create a new instance."""
        self.cb = cb

    def remote_execute(self, *args, **kwargs):
        """Execute the callback."""
        if self.cb:
            self.cb(*args, **kwargs)


def callbacks(callbacks_indexes=None, callbacks_names=None):
    """Ensure that the callbacks can be remotely called."""
    def decorator(function):
        """Decorate the function to make sure the callbacks can be executed."""
        @wraps(function)
        def callbacks_wrapper(*args, **kwargs):
            """Set the paths to be absolute."""
            fixed_args = list(args)
            if callbacks_indexes:
                for current_cb in callbacks_indexes:
                    fixed_args[current_cb] = RemoteHandler(args[current_cb])
                fixed_args = tuple(fixed_args)
            if callbacks_names:
                for current_key, current_index in callbacks_names:
                    try:
                        kwargs[current_key] = RemoteHandler(
                                                        kwargs[current_key])
                    except KeyError:
                        fixed_args[current_index] = RemoteHandler(
                                                        args[current_index])
            fixed_args = tuple(fixed_args)
            return function(*fixed_args, **kwargs)
        return callbacks_wrapper
    return decorator


class SSOLoginClient(RemoteClient, Referenceable):
    """Client that can perform calls to the remote SSOLogin object."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'on_captcha_generated',
        'on_captcha_generation_error',
        'on_user_registered',
        'on_user_registration_error',
        'on_logged_in',
        'on_login_error',
        'on_user_not_validated',
        'on_email_validated',
        'on_email_validation_error',
        'on_password_reset_token_sent',
        'on_password_reset_error',
        'on_password_changed',
        'on_password_change_error',
    ]

    def __init__(self, remote_login):
        """Create a client for the login API."""
        super(SSOLoginClient, self).__init__(remote_login)

    @signal
    def on_captcha_generated(self, app_name, result):
        """Signal thrown after the captcha is generated."""

    @signal
    def on_captcha_generation_error(self, app_name, raised_error):
        """Signal thrown when there's a problem generating the captcha."""

    @remote
    def generate_captcha(self, app_name, filename):
        """Call the matching method in the processor."""

    @signal
    def on_user_registered(self, app_name, result):
        """Signal thrown when the user is registered."""

    @signal
    def on_user_registration_error(self, app_name, raised_error):
        """Signal thrown when there's a problem registering the user."""

    @remote
    def register_user(self, app_name, email, password, displayname,
                      captcha_id, captcha_solution):
        """Call the matching method in the processor."""

    @signal
    def on_logged_in(self, app_name, result):
        """Signal thrown when the user is logged in."""

    @signal
    def on_login_error(self, app_name, raised_error):
        """Signal thrown when there is a problem in the login."""

    @signal
    def on_user_not_validated(self, app_name, result):
        """Signal thrown when the user is not validated."""

    @remote
    def login(self, app_name, email, password):
        """Call the matching method in the processor."""

    @signal
    def on_email_validated(self, app_name, result):
        """Signal thrown after the email is validated."""

    @signal
    def on_email_validation_error(self, app_name, raised_error):
        """Signal thrown when there's a problem validating the email."""

    @remote
    def validate_email(self, app_name, email, password, email_token):
        """Call the matching method in the processor."""

    @signal
    def on_password_reset_token_sent(self, app_name, result):
        """Signal thrown when the token is successfully sent."""

    @signal
    def on_password_reset_error(self, app_name, raised_error):
        """Signal thrown when there's a problem sending the token."""

    @remote
    def request_password_reset_token(self, app_name, email):
        """Call the matching method in the processor."""

    @signal
    def on_password_changed(self, app_name, result):
        """Signal thrown when the token is successfully sent."""

    @signal
    def on_password_change_error(self, app_name, raised_error):
        """Signal thrown when there's a problem sending the token."""

    @remote
    def set_new_password(self, app_name, email, token, new_password):
        """Call the matching method in the processor."""


class SSOCredentialsClient(RemoteClient, Referenceable):
    """Deprecated client for the remote SSOCredentials object.

    This class is deprecated!
    """

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'on_authorization_denied',
        'on_credentials_found',
        'on_credentials_error',
    ]

    def __init__(self, remote_login):
        """Create a client for the cred API."""
        warnings.warn("SSOCredentialsClient is deprecated.",
            DeprecationWarning)
        super(SSOCredentialsClient, self).__init__(remote_login)

    @signal
    def on_authorization_denied(self, app_name):
        """Signal thrown when the user denies the authorization."""

    @signal
    def on_credentials_found(self, app_name, credentials):
        """Signal thrown when the credentials are found."""

    @signal
    def on_credentials_error(self, app_name, error_message, detailed_error):
        """Signal thrown when there is a problem finding the credentials."""

    @callbacks(callbacks_names=[('callback', 2), ('errback', 3)])
    @remote
    def find_credentials(self, app_name, callback=NO_OP, errback=NO_OP):
        """Get the credentials from the keyring or {} if not there."""

    @remote
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

    @remote
    def login_to_get_credentials(self, app_name, help_text, window_id):
        """Get credentials if found else prompt GUI just to login

        'app_name' will be displayed in the GUI.
        'help_text' is an explanatory text for the end-users, will be shown
         before the login fields.
        'window_id' is the id of the window which will be set as a parent of
         the GUI. If 0, no parent will be set.

        """

    @callbacks(callbacks_names=[('callback', 2), ('errback', 3)])
    @remote
    def clear_token(self, app_name, callback=NO_OP, errback=NO_OP):
        """Clear the token for an application from the keyring.

        'app_name' is the name of the application.
        """


class CredentialsManagementClient(RemoteClient, Referenceable):
    """Client that can perform calls to the remote CredManagement object."""

    __metaclass__ = RemoteMeta

    # calls that will be accessible remotely
    remote_calls = [
        'on_authorization_denied',
        'on_credentials_found',
        'on_credentials_not_found',
        'on_credentials_cleared',
        'on_credentials_stored',
        'on_credentials_error',
    ]

    def __init__(self, remote_login):
        """Create a client for the cred API."""
        super(CredentialsManagementClient, self).__init__(remote_login)

    @remote
    def shutdown(self):
        """If no ongoing requests, call self.shutdown_func."""

    @signal
    def on_authorization_denied(self, app_name):
        """Signal thrown when the user denies the authorization."""

    @signal
    def on_credentials_found(self, app_name, credentials):
        """Signal thrown when the credentials are found."""

    @signal
    def on_credentials_not_found(self, app_name):
        """Signal thrown when the credentials are not found."""

    @signal
    def on_credentials_cleared(self, app_name):
        """Signal thrown when the credentials were cleared."""

    @signal
    def on_credentials_stored(self, app_name):
        """Signal thrown when the credentials were cleared."""

    @signal
    def on_credentials_error(self, app_name, error_dict):
        """Signal thrown when there is a problem getting the credentials."""

    @remote
    def find_credentials(self, app_name, args):
        """Look for the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """

    @remote
    def clear_credentials(self, app_name, args):
        """Clear the credentials for an application.

        - 'app_name': the name of the application which credentials are
        going to be removed.

        - 'args' is a dictionary, currently not used.

        """

    @remote
    def store_credentials(self, app_name, args):
        """Store the token for an application.

        - 'app_name': the name of the application which credentials are
        going to be stored.

        - 'args' is the dictionary holding the credentials. Needs to provide
        the following mandatory keys: 'token', 'token_key', 'consumer_key',
        'consumer_secret'.

        """

    @remote
    def register(self, app_name, args):
        """Get credentials if found else prompt GUI to register."""

    @remote
    def login(self, app_name, args):
        """Get credentials if found else prompt GUI to login."""

    @remote
    def login_email_password(self, app_name, args):
        """Get credentials if found else login."""


class UbuntuSSOClientException(Exception):
    """Raised when there are issues connecting to the process."""


class UbuntuSSOClient(object):
    """Root client that provides access to the sso API."""

    def __init__(self):
        self.sso_login = None
        self.cred_management = None
        self.factory = None
        self.client = None

    @defer.inlineCallbacks
    def _request_remote_objects(self, root):
        """Get the status remote object."""
        sso_login = yield root.callRemote('get_sso_login')
        logger.debug('SSOLogin is %s', sso_login)
        self.sso_login = SSOLoginClient(sso_login)
        cred_management = yield root.callRemote('get_cred_manager')
        self.cred_management = CredentialsManagementClient(cred_management)
        defer.returnValue(self)

    @defer.inlineCallbacks
    def connect(self):
        """Connect to the sso service."""
        ac = ActivationClient(get_activation_config())
        port = yield ac.get_active_port()
        # got the port, lets try and connect to it and get the diff
        # remote objects for the wrappers
        self.factory = PBClientFactory()
        # the reactor does have a connectTCP method
        # pylint: disable=E1101
        self.client = reactor.connectTCP(LOCALHOST, port, self.factory)
        # pylint: enable=E1101
        root = yield self.factory.getRootObject()
        client = yield self._request_remote_objects(root)
        defer.returnValue(client)

    def disconnect(self):
        """Disconnect from the process."""
        if self.client:
            self.client.disconnect()
