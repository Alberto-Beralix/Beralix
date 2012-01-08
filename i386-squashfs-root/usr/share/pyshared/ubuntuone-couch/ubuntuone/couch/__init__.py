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

"""Small library for talking to Ubuntu One CouchDBs."""

import cgi
import httplib2
import json
import urllib
import urlparse
from oauth import oauth
from ubuntuone.couch.auth import (
    get_oauth_credentials, get_oauth_token,
    HMAC_SHA1, PLAINTEXT, request as oauth_request, get_oauth_request_header)

APP_NAME = "Ubuntu One"
INFO_URL = "https://one.ubuntu.com/api/account/"


class OAuthAuthenticationError(Exception):
    """Exception when OAuth Authentication fails."""


class UnknownError(Exception):
    """Exception when OAuth Authentication fails."""


def get_user_info(info_url, consumer_key=None, consumer_secret=None,
                  access_token=None, token_secret=None):
    """Look up the user's user id and prefix."""
    resp, content = oauth_request(
        info_url, consumer_key=consumer_key, consumer_secret=consumer_secret,
        access_token=access_token, token_secret=token_secret)
    if resp['status'] not in ("200", "201"):
        raise UnknownError(
            "Error retrieving user data (%s, %s)" % (resp, content))
    document = json.loads(content)
    return (document["id"], document["couchdb_root"])


def request(urlpath, sig_meth='HMAC_SHA1', http_method='GET',
            request_body=None, server_override=None, access_token=None,
            token_secret=None, consumer_key=None, consumer_secret=None,
            extra_headers=None):
    """Make a request to couchdb.one.ubuntu.com for the user's data.

    The user supplies a urlpath (for example, dbname). We need to actually
    request https://couchdb.one.ubuntu.com/PREFIX/dbname, and sign it with
    the user's OAuth token.

    We find the prefix by querying https://one.ubuntu.com/api/account/
    (see desktopcouch.replication_services.ubuntuone, which does this).

    """
    if access_token is None or consumer_key is None:
        credentials = get_oauth_credentials()
        access_token = credentials['token']
        token_secret = credentials['token_secret']
        consumer_key = credentials['consumer_key']
        consumer_secret = credentials['consumer_secret']
    token = get_oauth_token(access_token, token_secret)
    consumer = oauth.OAuthConsumer(consumer_key, consumer_secret)

    # Set the signature method. This should be HMAC unless you have a jolly
    # good reason for it to not be.
    if sig_meth == "PLAINTEXT":
        signature_method = PLAINTEXT
    else:
        signature_method = HMAC_SHA1
    userid, couch_root = get_user_info(
        INFO_URL, consumer_key=consumer_key, consumer_secret=consumer_secret,
        access_token=access_token, token_secret=token_secret)
    schema, netloc, path, params, query, fragment = urlparse.urlparse(
        couch_root)
    if server_override:
        netloc = server_override
    # Don't escape the first /
    path = "/" + urllib.quote(path[1:], safe="")
    couch_root = urlparse.urlunparse((
        schema, netloc, path, params, query, fragment))

    # Now use COUCH_ROOT and the specified user urlpath to get data
    if urlpath == "_all_dbs":
        couch_url = urlparse.urlunparse((
            schema, netloc, "_all_dbs", None, "user_id=%s" % userid, None))
    else:
        couch_url = "%s%%2F%s" % (couch_root, urlpath)
    schema, netloc, path, params, query, fragment = urlparse.urlparse(
        couch_url)
    querystr_as_dict = dict(cgi.parse_qsl(query))

    oauth_header = get_oauth_request_header(
        consumer, token, couch_url, http_method=http_method,
        signature_method=signature_method, parameters=querystr_as_dict)
    if extra_headers:
        oauth_header.update(dict(
            [(x.split(':', 1)[0].strip(), x.split(':', 1)[1].strip())
            for x in extra_headers]))

    http = httplib2.Http()
    resp, content = http.request(
        couch_url, method=http_method, headers=oauth_header, body=request_body)
    if resp['status'] in ("200", "201"):
        return json.loads(content)
    elif resp['status'] == "400":
        raise OAuthAuthenticationError(
            "The server could not parse the oauth token:\n%s" % content)
    elif resp['status'] == "401":
        raise OAuthAuthenticationError(
            "Access Denied. Content: %r" % content)
    else:
        raise UnknownError(
            "There was a problem processing the request:\nstatus:%s, response:"
            " %r" % (resp['status'], content))
