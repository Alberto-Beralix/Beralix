#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import os

from gi.repository import GObject
GObject.threads_init()

import logging
import threading

from softwarecenter.enums import BUY_SOMETHING_HOST

# possible workaround for bug #599332 is to try to import lazr.restful
# import lazr.restful
# import lazr.restfulclient

from lazr.restfulclient.resource import ServiceRoot
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthToken

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue

# mostly for testing
from fake_review_settings import FakeReviewSettings, network_delay

from login import LoginBackend

LOG = logging.getLogger(__name__)

UBUNTU_SSO_SERVICE = os.environ.get(
    "USSOC_SERVICE_URL", "https://login.ubuntu.com/api/1.0")
UBUNTU_SOFTWARE_CENTER_AGENT_SERVICE = BUY_SOMETHING_HOST+"/api/1.0"

class AttributesObject(object):
    """ convinient object to hold attributes """
    MAX_REPR_STRING_SIZE = 30

    def __repr__(self):
        s = "<'%s': " % self.__class__.__name__
        for key in vars(self):
            value = str(getattr(self, key))
            if len(value) > self.MAX_REPR_STRING_SIZE:
                value = "%s..." % value[:self.MAX_REPR_STRING_SIZE]
            s += "%s='%s';" % (key, value)
        s += ">"
        return s


def restful_collection_to_real_python(restful_list):
    """ take a restful and convert it to a python list with real python
        objects
    """
    l = []
    for entry in restful_list:
        o = AttributesObject()
        for attr in entry.lp_attributes:
            setattr(o, attr, getattr(entry, attr))
        l.append(o)
    return l

class RestfulClientWorker(threading.Thread):
    """ a generic worker thread for a lazr.restfulclient """

    def __init__(self, authorizer, service_root):
        """ init the thread """
        threading.Thread.__init__(self)
        self._service_root_url = service_root
        self._authorizer = authorizer
        self._pending_requests = Queue()
        self._shutdown = False
        self.daemon = True
        self.error = None
        self._cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                      "restfulclient")

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        LOG.debug("lp worker thread run")
        try:
            self.service = ServiceRoot(self._authorizer, 
                                       self._service_root_url,
                                       self._cachedir)
        except:
            logging.exception("worker thread can not connect to service root")
            self.error = "ERROR_SERVICE_ROOT"
            self._shutdown = True
            return
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def queue_request(self, func, args, kwargs, result_callback, error_callback):
        """
        queue a (remote) command for execution, the result_callback will
        call with the result_list when done (that function will be
        called async)
        """
        self._pending_requests.put((func, args, kwargs, result_callback, error_callback))

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            while not self._pending_requests.empty():
                LOG.debug("found pending request")
                (func_str, args, kwargs, result_callback, error_callback) = self._pending_requests.get()
                # run func async
                try:
                    func = self.service
                    for part in func_str.split("."):
                        func = getattr(func, part)
                    res = func(*args, **kwargs)
                except Exception ,e:
                    error_callback(e)
                else:
                    result_callback(res)
                self._pending_requests.task_done()
            # wait a bit
            import time
            time.sleep(0.1)
            if (self._shutdown and
                self._pending_requests.empty()):
                return

class UbuntuSSOAPI(GObject.GObject):

    __gsignals__ = {
        "whoami" : (GObject.SIGNAL_RUN_LAST,
                    GObject.TYPE_NONE, 
                    (GObject.TYPE_PYOBJECT,),
                    ),
        "error" : (GObject.SIGNAL_RUN_LAST,
                    GObject.TYPE_NONE, 
                    (GObject.TYPE_PYOBJECT,),
                    ),

        }
       
    def __init__(self, token):
        GObject.GObject.__init__(self)
        self._whoami = None
        self._error = None
        self.service = UBUNTU_SSO_SERVICE
        self.token = token
        token = OAuthToken(self.token["token"], self.token["token_secret"])
        authorizer = OAuthAuthorizer(self.token["consumer_key"],
                                     self.token["consumer_secret"],
                                     access_token=token)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        GObject.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self._whoami is not None:
            self.emit("whoami", self._whoami)
            self._whoami = None
        if self._error is not None:
            self.emit("error", self._error)
            self._error = None
        return True

    def _thread_whoami_done(self, result):
        self._whoami = result

    def _thread_whoami_error(self, e):
        self._error = e

    def whoami(self):
        self.worker_thread.queue_request("accounts.me", (), {},
                                         self._thread_whoami_done,
                                         self._thread_whoami_error)


class UbuntuSSOAPIFake(UbuntuSSOAPI):

    def __init__(self, token):
        GObject.GObject.__init__(self)
        self._fake_settings = FakeReviewSettings()

    @network_delay
    def whoami(self):
        if self._fake_settings.get_setting('whoami_response') == "whoami":
            self.emit("whoami", self._create_whoami_response())
        elif self._fake_settings.get_setting('whoami_response') == "error": 
            self.emit("error", self._make_error())
    
    def _create_whoami_response(self):
        username = self._fake_settings.get_setting('whoami_username') or "anyuser"
        response = {
                    u'username': username.decode('utf-8'), 
                    u'preferred_email': u'user@email.com', 
                    u'displayname': u'Fake User', 
                    u'unverified_emails': [], 
                    u'verified_emails': [], 
                    u'openid_identifier': u'fnerkWt'
                   }
        return response
    
    def _make_error():
        return 'HTTP Error 401: Unauthorized'

def get_ubuntu_sso_backend(token):
    """ 
    factory that returns an ubuntu sso loader singelton
    """
    if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
        ubuntu_sso_class = UbuntuSSOAPIFake(token)
        LOG.warn('Using fake Ubuntu SSO API. Only meant for testing purposes')
    else:
        ubuntu_sso_class = UbuntuSSOAPI(token)
    return ubuntu_sso_class


class UbuntuSSOlogin(LoginBackend):

    NEW_ACCOUNT_URL = "https://login.launchpad.net/+standalone-login"
    FORGOT_PASSWORD_URL = "https://login.ubuntu.com/+forgot_password"

    SSO_AUTHENTICATE_FUNC = "authentications.authenticate"

    def __init__(self):
        LoginBackend.__init__(self)
        self.service = UBUNTU_SSO_SERVICE
        # we get a dict here with the following keys:
        #  token
        #  consumer_key (also the openid identifier)
        #  consumer_secret
        #  token_secret
        #  name (that is just 'software-center')
        self.oauth_credentials = None
        self._oauth_credentials = None
        self._login_failure = None
        self.worker_thread = None

    def shutdown(self):
        self.worker_thread.shutdown()

    def login(self, username=None, password=None):
        if not username or not password:
            self.emit("need-username-password")
            return
        authorizer = BasicHttpAuthorizer(username, password)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        kwargs = { "token_name" : "software-center", 
                 }
        self.worker_thread.queue_request(self.SSO_AUTHENTICATE_FUNC, (), kwargs,
                                         self._thread_authentication_done,
                                         self._thread_authentication_error)
        GObject.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self._oauth_credentials:
            self.emit("login-successful", self._oauth_credentials)
            self.oauth_credentials = self._oauth_credentials
            self._oauth_credentials = None
        if self._login_failure:
            self.emit("login-failed")
            self._login_failure = None
        return True

    def _thread_authentication_done(self, result):
        # runs in the thread context, can not touch gui or glib
        #print "_authentication_done", result
        self._oauth_credentials = result

    def _thread_authentication_error(self, e):
        # runs in the thread context, can not touch gui or glib
        #print "_authentication_error", type(e)
        self._login_failure = e

    def __del__(self):
        #print "del"
        if self.worker_thread:
            self.worker_thread.shutdown()


# test code
def _login_success(lp, token):
    print "success", lp, token
def _login_failed(lp):
    print "fail", lp
def _login_need_user_and_password(sso):
    import sys
    sys.stdout.write("user: ")
    sys.stdout.flush()
    user = sys.stdin.readline().strip()
    sys.stdout.write("pass: ")
    sys.stdout.flush()
    password = sys.stdin.readline().strip()
    sso.login(user, password)

def _error(scaagent, errormsg):
    print "_error:", errormsg
def _whoami(sso, whoami):
    print "whoami: ", whoami

# interactive test code
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print "need an argument, one of: 'sso', 'ssologin'"
        sys.exit(1)

    elif sys.argv[1] == "sso":
        def _dbus_maybe_login_successful(ssologin, oauth_result):
            sso = UbuntuSSOAPI(oauth_result)
            sso.connect("whoami", _whoami)
            sso.connect("error", _error)
            sso.whoami()
        from login_sso import get_sso_backend
        backend = get_sso_backend("", "appname", "help_text")
        backend.connect("login-successful", _dbus_maybe_login_successful)
        backend.login_or_register()

    elif sys.argv[1] == "ssologin":
        ssologin = UbuntuSSOlogin()
        ssologin.connect("login-successful", _login_success)
        ssologin.connect("login-failed", _login_failed)
        ssologin.connect("need-username-password", _login_need_user_and_password)
        ssologin.login()
        
    else:
        print "unknown option"
        sys.exit(1)


