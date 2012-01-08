#  software-properties PPA support
#
#  Copyright (c) 2004-2009 Canonical Ltd.
#
#  Author: Michael Vogt <mvo@debian.org>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

import apt_pkg
import json
import re
import subprocess
from threading import Thread
import urllib
from urllib2 import urlopen, Request, URLError
from urlparse import urlparse

DEFAULT_KEYSERVER = "hkp://keyserver.ubuntu.com:80/"
# maintained until 2015
LAUNCHPAD_PPA_API = 'https://launchpad.net/api/1.0/~%s/+archive/%s'

def encode(s):
    return re.sub("[^a-zA-Z0-9_-]","_", s)

def expand_ppa_line(abrev, distro_codename):
    """ Convert an abbreviated ppa name of the form 'ppa:$name' to a
        proper sources.list line of the form 'deb ...' """
    # leave non-ppa: lines unchanged
    if not abrev.startswith("ppa:"):
        return (abrev, None)
    # FIXME: add support for dependency PPAs too (once we can get them
    #        via some sort of API, see LP #385129)
    abrev = abrev.split(":")[1]
    ppa_owner = abrev.split("/")[0]
    try:
        ppa_name = abrev.split("/")[1]
    except IndexError, e:
        ppa_name = "ppa"
    sourceslistd = apt_pkg.Config.find_dir("Dir::Etc::sourceparts")
    line = "deb http://ppa.launchpad.net/%s/%s/ubuntu %s main" % (
        ppa_owner, ppa_name, distro_codename)
    filename = "%s/%s-%s-%s.list" % (
        sourceslistd, encode(ppa_owner), encode(ppa_name), distro_codename)
    return (line, filename)

def get_ppa_info_from_lp(owner_name, ppa_name):
    lp_url = LAUNCHPAD_PPA_API % (owner_name, ppa_name)
    # we ask for a JSON structure from lp_page, we could use
    # simplejson, but the format is simple enough for the regexp
    req =  Request(lp_url)
    req.add_header("Accept","application/json")
    lp_page = urlopen(req).read()
    return json.loads(lp_page)

class AddPPASigningKeyThread(Thread):
    " thread class for adding the signing key in the background "

    def __init__(self, ppa_path, keyserver=None):
        Thread.__init__(self)
        self.ppa_path = ppa_path
        self.keyserver = (keyserver if keyserver is not None
                          else DEFAULT_KEYSERVER)
        
    def run(self):
        self.add_ppa_signing_key(self.ppa_path)
        
    def add_ppa_signing_key(self, ppa_path):
        """Query and add the corresponding PPA signing key.
        
        The signing key fingerprint is obtained from the Launchpad PPA page,
        via a secure channel, so it can be trusted.
        """
        owner_name, ppa_name, distro = ppa_path[1:].split('/')
        try:
            ppa_info = get_ppa_info_from_lp(owner_name, ppa_name)
        except URLError as e:
            print "Error reading %s: %s" % (lp_url, e)
            return False
        try:
            signing_key_fingerprint = ppa_info["signing_key_fingerprint"]
        except IndexError as e:
            print "Error: can't find signing_key_fingerprint at %s" % lp_url
            return False
        res = subprocess.call(
            ["apt-key", "adv", 
             "--keyserver", self.keyserver,
             "--recv", signing_key_fingerprint])
        return (res == 0)


if __name__ == "__main__":
    import sys
    owner_name, ppa_name = sys.argv[1].split(":")[1].split("/")
    print get_ppa_info_from_lp(owner_name, ppa_name)
