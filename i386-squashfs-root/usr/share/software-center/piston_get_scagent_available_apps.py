#!/usr/bin/python

from gi.repository import GObject

import argparse
import logging
import os
import pickle
import sys

import piston_mini_client.auth

from softwarecenter.enums import (SOFTWARE_CENTER_NAME_KEYRING,
                                  SOFTWARE_CENTER_SSO_DESCRIPTION,
                                  )
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.piston.scaclient import SoftwareCenterAgentAPI
from softwarecenter.backend.login_sso import get_sso_backend
from softwarecenter.backend.restfulclient import UbuntuSSOAPI
from softwarecenter.utils import clear_token_from_ubuntu_sso

from gettext import gettext as _

LOG = logging.getLogger(__name__)

class SSOLoginHelper(object):
    def __init__(self, xid=0):
        self.oauth = None
        self.xid = xid
        self.loop = GObject.MainLoop(GObject.main_context_default())
    
    def _login_successful(self, sso_backend, oauth_result):
        self.oauth = oauth_result
        # FIXME: actually verify the token against ubuntu SSO
        self.loop.quit()

    def verify_token(self, token):
        def _whoami_done(sso, me):
            self._whoami = me
            self.loop.quit()
        self._whoami = None
        sso = UbuntuSSOAPI(token)
        sso.connect("whoami", _whoami_done)
        sso.connect("error", lambda sso, err: self.loop.quit())
        sso.whoami()
        self.loop.run()
        # check if the token is valid
        if self._whoami is None:
            return False
        else:
            return True

    def clear_token(self):
        clear_token_from_ubuntu_sso(SOFTWARE_CENTER_NAME_KEYRING)

    def get_oauth_token_sync(self):
        self.oauth = None
        sso = get_sso_backend(
            self.xid, 
            SOFTWARE_CENTER_NAME_KEYRING,
            _(SOFTWARE_CENTER_SSO_DESCRIPTION))
        sso.connect("login-successful", self._login_successful)
        sso.connect("login-failed", lambda s: self.loop.quit())
        sso.connect("login-canceled", lambda s: self.loop.quit())
        sso.login_or_register()
        self.loop.run()
        return self.oauth

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(description="Helper for software-center-agent")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
    parser.add_argument("--ignore-cache", action="store_true", default=False,
                        help="force ignore cache")
    parser.add_argument("--parent-xid", default=0,
                        help="xid of the parent window")

    subparser = parser.add_subparsers(title="Commands")
    # available_apps
    command = subparser.add_parser("available_apps")
    command.add_argument("lang")
    command.add_argument("series")
    command.add_argument("arch")
    command.set_defaults(command="available_apps")

    # available_apps_qa
    command = subparser.add_parser("available_apps_qa")
    command.add_argument("lang")
    command.add_argument("series")
    command.add_argument("arch")
    command.set_defaults(command="available_apps_qa")
    # subscriptions
    command = subparser.add_parser("subscriptions_for_me")
    command.set_defaults(command="subscriptions_for_me")
    # exhibits
    command = subparser.add_parser("exhibits")
    command.add_argument("lang")
    command.set_defaults(command="exhibits")

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "scaclient")


    # check if auth is required
    if args.command in ("available_apps_qa", "subscriptions_for_me"):
        helper = SSOLoginHelper(args.parent_xid)
        token = helper.get_oauth_token_sync()
        # check if the token is valid and reset it if it is not
        if token and not helper.verify_token(token):
            helper.clear_token()
            # re-trigger login
            token = helper.get_oauth_token_sync()
        # if we don't have a token, error here
        if not token:
            sys.stderr.write("ERROR: can not obtain a oauth token\n")
            sys.exit(1)
        
        auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                       token["token_secret"],
                                                       token["consumer_key"],
                                                       token["consumer_secret"])
        scaclient = SoftwareCenterAgentAPI(cachedir=cachedir, auth=auth)
    else:
        scaclient = SoftwareCenterAgentAPI(cachedir=cachedir)
        
    piston_reply = None

    # common kwargs
    if args.command in ("available_apps", "available_apps_qa"):
        kwargs = {"lang": args.lang,
                  "series": args.series,
                  "arch": args.arch
                  }

    # handle the args
    if args.command == "available_apps":
        try:
            piston_reply = scaclient.available_apps(**kwargs)
        except:
            LOG.exception("available_apps")
            sys.exit(1)

    elif args.command == "available_apps_qa":
        try:
            piston_reply = scaclient.available_apps_qa(**kwargs)
        except:
            LOG.exception("available_apps_qa")
            sys.exit(1)
    elif args.command == "subscriptions_for_me":
        try:
            piston_reply = scaclient.subscriptions_for_me(complete_only=True)
            # the new piston API send the data in a nasty format, most
            # interessting stuff is in the "application" dict, move it
            # back int othe main object here so that the parser understands it
            for item in piston_reply:
                for k, v in item.application.iteritems():
                    setattr(item, k, v)
        except:
            LOG.exception("subscriptions_for_me")
            sys.exit(1)
    if args.command == "exhibits":
        try:
            piston_reply = scaclient.exhibits(lang=args.lang)
        except:
            LOG.exception("exhibits")
            sys.exit(1)

    if args.debug:
        LOG.debug("reply: %s" % piston_reply)
        for item in piston_reply:
            for var in vars(item):
                print "%s: %s" % (var, getattr(item, var))
            print "\n\n"


    # print to stdout where its consumed by the parent
    if piston_reply is not None:
        try:
            print pickle.dumps(piston_reply)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass
