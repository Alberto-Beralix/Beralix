# -*- coding: utf-8 -*-

# Authors: Alejandro J. Cura <alecu@canonical.com>
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

"""The control panel backend webservice client using twisted.web."""

import simplejson

from twisted.internet import defer, reactor
from twisted.web import client, error, http

from ubuntuone.controlpanel import WEBSERVICE_BASE_URL
from ubuntuone.controlpanel.web_client import (add_oauth_headers,
                                               WebClientError,
                                               UnauthorizedError)

from ubuntuone.controlpanel.logger import setup_logging

logger = setup_logging('webclient')


class WebClient(object):
    """A client for the u1 webservice."""

    def __init__(self, get_credentials, base_url=WEBSERVICE_BASE_URL):
        """Initialize the webclient."""
        self.base_url = base_url
        self.get_credentials = get_credentials
        self.running = True
        # pylint: disable=E1101
        self.trigger_id = reactor.addSystemEventTrigger("before", "shutdown",
                                                        self.shutdown)

    def _handle_response(self, result):
        """Handle the response of the webservice call."""
        return simplejson.loads(result)

    def _handle_error(self, failure):
        """Handle an error while calling the webservice."""
        if failure.type == error.Error:
            exception = failure.value
            if exception.status == str(http.UNAUTHORIZED):
                raise UnauthorizedError(exception.status, exception.response)
            else:
                raise WebClientError(exception.status, exception.response)
        else:
            raise WebClientError(-1, failure)

    def _call_api_with_creds(self, credentials, api_name):
        """Get a given url from the webservice with credentials."""
        url = (self.base_url + api_name).encode('utf-8')
        method = "GET"
        logger.debug("getting url: %s, %s", method, url)
        headers = {}
        add_oauth_headers(headers.__setitem__, method, url, credentials)
        d = client.getPage(url, headers=headers)
        d.addCallback(self._handle_response)
        d.addErrback(self._handle_error)
        return d

    def call_api(self, api_name):
        """Get a given url from the webservice."""
        # this may log device ID's, but only for removals, which is OK
        logger.debug("calling api: %s", api_name)
        d = self.get_credentials()
        d.addErrback(self._handle_error)
        d.addCallback(self._call_api_with_creds, api_name)
        d2 = defer.Deferred()
        d.addCallback(d2.callback)

        def mask_errors_on_shutdown(failure):
            """Do not fire the errbacks if we are shutting down."""
            if self.running:
                d2.errback(failure)

        d.addErrback(mask_errors_on_shutdown)
        return d2

    def shutdown(self):
        """End the pending webclient calls."""
        self.running = False
        # pylint: disable=E1101
        reactor.removeSystemEventTrigger(self.trigger_id)
