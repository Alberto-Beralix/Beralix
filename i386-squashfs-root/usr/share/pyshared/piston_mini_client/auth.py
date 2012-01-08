# -*- coding: utf-8 -*-
# Copyright 2010-2011 Canonical Ltd.  This software is licensed under the
# GNU Lesser General Public License version 3 (see the file LICENSE).

"""Classes for adding authentication headers to your API requests.

You usually want to pass in an instance of one of these classes when you
instantiate a ``PistonAPI`` object.
"""

from functools import wraps


class OAuthAuthorizer(object):
    """Authenticate to OAuth protected APIs."""
    def __init__(self, token_key, token_secret, consumer_key, consumer_secret,
                 oauth_realm="OAuth"):
        """Initialize a ``OAuthAuthorizer``.

        ``token_key``, ``token_secret``, ``consumer_key`` and
        ``consumer_secret`` are required for signing OAuth requests.  The
        ``oauth_realm`` to use is optional.
        """
        self.token_key = token_key
        self.token_secret = token_secret
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.oauth_realm = oauth_realm

    def sign_request(self, url, method, body, headers):
        """Sign a request with OAuth credentials."""
        # Import oauth here so that you don't need it if you're not going
        # to use it.  Plan B: move this out into a separate oauth module.
        from oauth.oauth import (OAuthRequest, OAuthConsumer, OAuthToken,
            OAuthSignatureMethod_PLAINTEXT)
        consumer = OAuthConsumer(self.consumer_key, self.consumer_secret)
        token = OAuthToken(self.token_key, self.token_secret)
        oauth_request = OAuthRequest.from_consumer_and_token(
            consumer, token, http_url=url)
        oauth_request.sign_request(OAuthSignatureMethod_PLAINTEXT(),
            consumer, token)
        headers.update(oauth_request.to_header(self.oauth_realm))

class BasicAuthorizer(object):
    """Authenticate to Basic protected APIs."""
    def __init__(self, username, password):
        """Initialize a ``BasicAuthorizer``.

        You'll need to provide the ``username`` and ``password`` that will
        be used to authenticate with the server.
        """
        self.username = username
        self.password = password
    
    def sign_request(self, url, method, body, headers):
        """Sign a request with Basic credentials."""
        headers['Authorization'] = self.auth_header()

    def auth_header(self):
        encoded = ('%s:%s' % (self.username, self.password)).encode('base64')
        return 'Basic ' + encoded
