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

"""Small library for OAuth signing of urls."""

import dbus
import httplib2
import logging
import ubuntu_sso
import urlparse

from gettext import gettext as _
from oauth import oauth
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)

import socket
socket.setdefaulttimeout(5)

APP_NAME = "Ubuntu One"
HMAC_SHA1 = oauth.OAuthSignatureMethod_HMAC_SHA1()
PLAINTEXT = oauth.OAuthSignatureMethod_PLAINTEXT()
NO_CREDENTIALS = _('No OAuth credentials passed in or found in Ubuntu SSO.')


class CredentialsNotFound(Exception):
    """Exception for missing data in SSO."""

    def __init__(self, key):            # pylint: disable=W0231
        self.key = key

    def __str__(self):
        return "Credentials Not Found Error: missing key %s" % self.key


def _undbusify(value):
    """Convert dbus types back to native types."""
    for singleton in (None, True, False):
        if value == singleton:
            return singleton
    for val_type in (long, int, float, complex,
                     unicode, str,
                     list, tuple, dict, set):
        if isinstance(value, val_type):
            return val_type(value)
    raise TypeError(value)


def get_oauth_credentials():
    """Get dictionary of OAuth information from the keyring."""

    DBusGMainLoop(set_as_default=True)

    bus = dbus.SessionBus()
    proxy = bus.get_object(
        ubuntu_sso.DBUS_BUS_NAME, ubuntu_sso.DBUS_CRED_PATH,
        follow_name_owner_changes=True)
    logging.info(
        'get_oauth_data: asking for credentials from Ubuntu SSO. App name: %s',
        APP_NAME)
    oauth_data = dict(
        (_undbusify(k), _undbusify(v)) for k, v in
        proxy.find_credentials(APP_NAME).iteritems())
    if len(oauth_data) > 0:
        logging.info(
            'get_oauth_data: Got non emtpy credentials from Ubuntu SSO.')
    credentials = {}
    for key in ('consumer_key', 'consumer_secret', 'token', 'token_secret'):
        try:
            credentials[key] = oauth_data[key]
        except KeyError:
            raise CredentialsNotFound(key)
    return credentials


def get_oauth_token(token, secret):
    """Turn token and secret into a Token."""
    token_string = 'oauth_token=%s&oauth_token_secret=%s' % (token, secret)
    return oauth.OAuthToken.from_string(token_string)


def get_oauth_request_header(consumer, access_token, http_url,
                             http_method='GET', signature_method=HMAC_SHA1,
                             parameters=None):
    """Get an oauth request header given the token and the url."""
    assert http_url.startswith("https")
    oauth_request = oauth.OAuthRequest.from_consumer_and_token(
        http_url=http_url,
        http_method=http_method,
        oauth_consumer=consumer,
        token=access_token,
        parameters=parameters)
    oauth_request.sign_request(signature_method, consumer, access_token)
    return oauth_request.to_header()


def request(url, sigmeth='HMAC_SHA1', http_method='GET', request_body=None,
            consumer_key=None, consumer_secret=None, access_token=None,
            token_secret=None, headers=None):
    """Make an OAuth signed request."""
    # Set the signature method. This should be HMAC unless you have a jolly
    # good reason for it to not be.
    if sigmeth == "PLAINTEXT":
        signature_method = PLAINTEXT
    else:
        signature_method = HMAC_SHA1
    if access_token is None or consumer_key is None:
        try:
            credentials = get_oauth_credentials()
        except CredentialsNotFound, e:
            logging.error('No credentials found in SSO. %s', e)
            return NO_CREDENTIALS
        access_token = credentials['token']
        token_secret = credentials['token_secret']
        consumer_key = credentials['consumer_key']
        consumer_secret = credentials['consumer_secret']
    token = get_oauth_token(access_token, token_secret)
    consumer = oauth.OAuthConsumer(consumer_key, consumer_secret)

    parameters = {}
    query = urlparse.urlparse(url)[4]
    for key, value in urlparse.parse_qs(query).items():
        parameters[key] = value[0]

    request_len = len(request_body) if request_body else 0
    timeout = 10 * (request_len / 1024 / 1024 + 1)  # 10 seconds per megabyte

    oauth_header = get_oauth_request_header(
        consumer, token, url, http_method, signature_method, parameters)
    headers = headers or {}
    headers.update(oauth_header)
    http = httplib2.Http(timeout=timeout,
                         disable_ssl_certificate_validation=True)
    return http.request(
        url, method=http_method, headers=headers, body=request_body)
