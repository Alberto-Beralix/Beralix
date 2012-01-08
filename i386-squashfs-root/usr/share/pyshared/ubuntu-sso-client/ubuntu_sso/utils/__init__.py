# -*- coding: utf-8 -*-

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

"""Utility modules that may find use outside ubuntu_sso."""

import cgi

from oauth import oauth
from urlparse import urlparse


def oauth_headers(url, credentials, http_method='GET'):
    """Sign 'url' using 'credentials'.

    * 'url' must be a valid unicode url.
    * 'credentials' must be a valid OAuth token.

    Return oauth headers that can be pass to any Request like object.

    """
    assert isinstance(url, unicode)
    url = url.encode('utf-8')
    _, _, _, _, query, _ = urlparse(url)
    parameters = dict(cgi.parse_qsl(query))

    consumer = oauth.OAuthConsumer(credentials['consumer_key'],
                                   credentials['consumer_secret'])
    token = oauth.OAuthToken(credentials['token'],
                             credentials['token_secret'])
    kwargs = dict(oauth_consumer=consumer, token=token,
                  http_method=http_method, http_url=url,
                  parameters=parameters)
    get_request = oauth.OAuthRequest.from_consumer_and_token
    oauth_req = get_request(**kwargs)
    hmac_sha1 = oauth.OAuthSignatureMethod_HMAC_SHA1()
    oauth_req.sign_request(hmac_sha1, consumer, token)
    headers = oauth_req.to_header()

    return headers
