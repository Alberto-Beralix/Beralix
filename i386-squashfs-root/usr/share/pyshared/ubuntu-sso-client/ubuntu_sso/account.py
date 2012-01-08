# -*- coding: utf-8 -*-

# Author: Natalia Bidart <natalia.bidart@canonical.com>
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
"""Single Sign On account management."""

import os
import re
import urllib2

# Unable to import 'lazr.restfulclient.*'
# pylint: disable=F0401
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from lazr.restfulclient.errors import HTTPError
from lazr.restfulclient.resource import ServiceRoot
# pylint: enable=F0401
from oauth import oauth

from ubuntu_sso.logger import setup_logging


logger = setup_logging("ubuntu_sso.account")
SERVICE_URL = "https://login.ubuntu.com/api/1.0"
SSO_STATUS_OK = 'ok'
SSO_STATUS_ERROR = 'error'


class InvalidEmailError(Exception):
    """The email is not valid."""


class InvalidPasswordError(Exception):
    """The password is not valid.

    Must provide at least 8 characters, one upper case, one number.
    """


class RegistrationError(Exception):
    """The registration failed."""


class AuthenticationError(Exception):
    """The authentication failed."""


class EmailTokenError(Exception):
    """The email token is not valid."""


class ResetPasswordTokenError(Exception):
    """The token for password reset could not be generated."""


class NewPasswordError(Exception):
    """The new password could not be set."""


class Account(object):
    """Login and register users using the Ubuntu Single Sign On service."""

    def __init__(self, sso_service_class=None):
        """Create a new SSO Account manager."""
        if sso_service_class is None:
            self.sso_service_class = ServiceRoot
        else:
            self.sso_service_class = sso_service_class

        self.service_url = os.environ.get('USSOC_SERVICE_URL', SERVICE_URL)

        logger.info('Created a new SSO access layer for service url %r',
                     self.service_url)

    def _valid_email(self, email):
        """Validate the given email."""
        return email is not None and '@' in email

    def _valid_password(self, password):
        """Validate the given password."""
        res = (len(password) > 7 and  # at least 8 characters
               re.search('[A-Z]', password) and  # one upper case
               re.search('\d+', password))  # one number
        return res

    def _format_webservice_errors(self, errdict):
        """Turn each list of strings in the errdict into a LF separated str."""
        result = {}
        for key, val in errdict.iteritems():
            # workaround until bug #624955 is solved
            if isinstance(val, basestring):
                result[key] = val
            else:
                result[key] = "\n".join(val)
        return result

    def generate_captcha(self, filename):
        """Generate a captcha using the SSO service."""
        logger.debug('generate_captcha: requesting captcha, filename: %r',
                     filename)
        sso_service = self.sso_service_class(None, self.service_url)
        captcha = sso_service.captchas.new()

        # download captcha and save to 'filename'
        logger.debug('generate_captcha: server answered: %r', captcha)
        try:
            res = urllib2.urlopen(captcha['image_url'])
            with open(filename, 'wb') as f:
                f.write(res.read())
        except:
            msg = 'generate_captcha crashed while downloading the image.'
            logger.exception(msg)
            raise

        return captcha['captcha_id']

    def register_user(self, email, password, displayname,
                      captcha_id, captcha_solution):
        """Register a new user with 'email' and 'password'."""
        logger.debug('register_user: email: %r password: <hidden>, '
                     'displayname: %r, captcha_id: %r, captcha_solution: %r',
                     email, displayname, captcha_id, captcha_solution)
        sso_service = self.sso_service_class(None, self.service_url)
        if not self._valid_email(email):
            logger.error('register_user: InvalidEmailError for email: %r',
                         email)
            raise InvalidEmailError()
        if not self._valid_password(password):
            logger.error('register_user: InvalidPasswordError')
            raise InvalidPasswordError()

        result = sso_service.registrations.register(
                    email=email, password=password,
                    displayname=displayname,
                    captcha_id=captcha_id,
                    captcha_solution=captcha_solution)
        logger.info('register_user: email: %r result: %r', email, result)

        if result['status'].lower() == SSO_STATUS_ERROR:
            errorsdict = self._format_webservice_errors(result['errors'])
            raise RegistrationError(errorsdict)
        elif result['status'].lower() != SSO_STATUS_OK:
            raise RegistrationError('Received unknown status: %s' % result)
        else:
            return email

    def login(self, email, password, token_name):
        """Login a user with 'email' and 'password'."""
        logger.debug('login: email: %r password: <hidden>, token_name: %r',
                     email, token_name)
        basic = BasicHttpAuthorizer(email, password)
        sso_service = self.sso_service_class(basic, self.service_url)
        service = sso_service.authentications.authenticate

        try:
            credentials = service(token_name=token_name)
        except HTTPError:
            logger.exception('login failed with:')
            raise AuthenticationError()

        logger.debug('login: authentication successful! consumer_key: %r, ' \
                     'token_name: %r', credentials['consumer_key'], token_name)
        return credentials

    def is_validated(self, token, sso_service=None):
        """Return if user with 'email' and 'password' is validated."""
        logger.debug('is_validated: requesting accounts.me() info.')
        if sso_service is None:
            oauth_token = oauth.OAuthToken(token['token'],
                                           token['token_secret'])
            authorizer = OAuthAuthorizer(token['consumer_key'],
                                         token['consumer_secret'],
                                         oauth_token)
            sso_service = self.sso_service_class(authorizer, self.service_url)

        me_info = sso_service.accounts.me()
        key = 'preferred_email'
        result = key in me_info and me_info[key] != None

        logger.info('is_validated: consumer_key: %r, result: %r.',
                    token['consumer_key'], result)
        return result

    def validate_email(self, email, password, email_token, token_name):
        """Validate an email token for user with 'email' and 'password'."""
        logger.debug('validate_email: email: %r password: <hidden>, '
                     'email_token: %r, token_name: %r.',
                     email, email_token, token_name)
        token = self.login(email=email, password=password,
                           token_name=token_name)

        oauth_token = oauth.OAuthToken(token['token'], token['token_secret'])
        authorizer = OAuthAuthorizer(token['consumer_key'],
                                     token['consumer_secret'],
                                     oauth_token)
        sso_service = self.sso_service_class(authorizer, self.service_url)
        result = sso_service.accounts.validate_email(email_token=email_token)
        logger.info('validate_email: email: %r result: %r', email, result)
        if 'errors' in result:
            errorsdict = self._format_webservice_errors(result['errors'])
            raise EmailTokenError(errorsdict)
        elif 'email' in result:
            return token
        else:
            raise EmailTokenError('Received invalid reply: %s' % result)

    def request_password_reset_token(self, email):
        """Request a token to reset the password for the account 'email'."""
        sso_service = self.sso_service_class(None, self.service_url)
        service = sso_service.registrations.request_password_reset_token
        try:
            result = service(email=email)
        except HTTPError, e:
            logger.exception('request_password_reset_token failed with:')
            raise ResetPasswordTokenError(e.content.split('\n')[0])

        if result['status'].lower() == SSO_STATUS_OK:
            return email
        else:
            raise ResetPasswordTokenError('Received invalid reply: %s' %
                                          result)

    def set_new_password(self, email, token, new_password):
        """Set a new password for the account 'email' to be 'new_password'.

        The 'token' has to be the one resulting from a call to
        'request_password_reset_token'.

        """
        sso_service = self.sso_service_class(None, self.service_url)
        service = sso_service.registrations.set_new_password
        try:
            result = service(email=email, token=token,
                             new_password=new_password)
        except HTTPError, e:
            logger.exception('set_new_password failed with:')
            raise NewPasswordError(e.content.split('\n')[0])

        if result['status'].lower() == SSO_STATUS_OK:
            return email
        else:
            raise NewPasswordError('Received invalid reply: %s' % result)
