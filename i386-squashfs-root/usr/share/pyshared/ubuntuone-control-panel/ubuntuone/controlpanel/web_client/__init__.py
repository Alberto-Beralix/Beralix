# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
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

"""The web client."""

from oauth import oauth


# pylint: disable=W0401, W0614


class WebClientError(Exception):
    """An http error happened while calling the webservice."""


class UnauthorizedError(WebClientError):
    """The request ended with bad_request, unauthorized or forbidden."""


def build_oauth_headers(method, url, credentials):
    """Build an oauth request given some credentials."""
    consumer = oauth.OAuthConsumer(credentials["consumer_key"],
                                   credentials["consumer_secret"])
    token = oauth.OAuthToken(credentials["token"],
                             credentials["token_secret"])
    request = oauth.OAuthRequest.from_consumer_and_token(
                                        http_url=url,
                                        http_method=method,
                                        oauth_consumer=consumer,
                                        token=token)
    sig_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
    request.sign_request(sig_method, consumer, token)
    return request.to_header()


def add_oauth_headers(append_method, method, url, credentials):
    """Sign a libsoup message with oauth headers."""
    headers = build_oauth_headers(method, url, credentials)
    for key, value in headers.items():
        append_method(key, value)


def web_client_factory(*args, **kwargs):
    """Choose the type of the web client dynamically."""
    # the reactor can only be imported after Qt is initialized
    # pylint: disable=W0404
    from twisted.internet import reactor
    if getattr(reactor, "qApp", None):
        from ubuntuone.controlpanel.web_client.txwebclient import WebClient
    else:
        from ubuntuone.controlpanel.web_client.libsoup import WebClient
    return WebClient(*args, **kwargs)
