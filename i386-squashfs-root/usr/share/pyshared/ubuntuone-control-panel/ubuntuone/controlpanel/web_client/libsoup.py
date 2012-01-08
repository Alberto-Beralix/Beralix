# -*- coding: utf-8 -*-

# Authors: Alejandro J. Cura <alecu@canonical.com>
# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""The control panel backend webservice client."""

import simplejson

# pylint: disable=E0611
from gi.repository import Soup, SoupGNOME
from twisted.internet import defer

from ubuntuone.controlpanel import WEBSERVICE_BASE_URL
from ubuntuone.controlpanel.web_client import (add_oauth_headers,
                                               WebClientError,
                                               UnauthorizedError)

from ubuntuone.controlpanel.logger import setup_logging

logger = setup_logging('webclient')


# full list of status codes
# http://library.gnome.org/devel/libsoup/stable/libsoup-2.4-soup-status.html


class WebClient(object):
    """A client for the u1 webservice."""

    def __init__(self, get_credentials, base_url=WEBSERVICE_BASE_URL):
        """Initialize the webclient."""
        self.base_url = base_url
        self.session = Soup.SessionAsync()
        self.session.add_feature_by_type(SoupGNOME.ProxyResolverGNOME)
        self.get_credentials = get_credentials

    def _handler(self, session, msg, d):
        """Handle the result of an http message."""
        logger.debug("got http response %d for uri %r",
                     msg.status_code, msg.get_uri().to_string(False))
        data = msg.response_body.data
        if msg.status_code == 200:
            result = simplejson.loads(data)
            d.callback(result)
        else:
            if msg.status_code in (401,):
                e = UnauthorizedError(msg.status_code, data)
            else:
                e = WebClientError(msg.status_code, data)
            d.errback(e)

    def _call_api_with_creds(self, credentials, api_name):
        """Get a given url from the webservice with credentials."""
        url = (self.base_url + api_name).encode('utf-8')
        method = "GET"
        logger.debug("getting url: %s, %s", method, url)
        msg = Soup.Message.new(method, url)
        add_oauth_headers(msg.request_headers.append, method, url, credentials)
        d = defer.Deferred()
        self.session.queue_message(msg, self._handler, d)
        return d

    def call_api(self, api_name):
        """Get a given url from the webservice."""
        # this may log device ID's, but only for removals, which is OK
        logger.debug("calling api: %s", api_name)
        d = self.get_credentials()
        d.addCallback(self._call_api_with_creds, api_name)
        return d

    def shutdown(self):
        """End the soup session for this webclient."""
        self.session.abort()
