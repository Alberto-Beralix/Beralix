#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 Canonical
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

from gi.repository import GObject
import logging
import os

import softwarecenter.paths
from softwarecenter.paths import PistonHelpers
from spawn_helper import SpawnHelper
from softwarecenter.utils import get_language
from softwarecenter.distro import get_distro, get_current_arch

LOG = logging.getLogger(__name__)

class SoftwareCenterAgent(GObject.GObject):

    __gsignals__ = {
        "available-for-me" : (GObject.SIGNAL_RUN_LAST,
                              GObject.TYPE_NONE, 
                              (GObject.TYPE_PYOBJECT,),
                             ),
        "available" : (GObject.SIGNAL_RUN_LAST,
                              GObject.TYPE_NONE, 
                              (GObject.TYPE_PYOBJECT,),
                             ),
        "exhibits" : (GObject.SIGNAL_RUN_LAST,
                              GObject.TYPE_NONE, 
                              (GObject.TYPE_PYOBJECT,),
                             ),
        "error" : (GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, 
                   (str,),
                  ),
        }
    
    def __init__(self, ignore_cache=False, xid=None):
        GObject.GObject.__init__(self)
        self.distro = get_distro()
        self.ignore_cache = ignore_cache
        binary = os.path.join(
            softwarecenter.paths.datadir, PistonHelpers.SOFTWARE_CENTER_AGENT)
        self.HELPER_CMD = [binary]
        if self.ignore_cache:
            self.HELPER_CMD.append("--ignore-cache")
        if xid:
            self.HELPER_CMD.append("--parent-xid")
            self.HELPER_CMD.append(str(xid))

    def query_available(self, series_name=None, arch_tag=None):
        self._query_available(series_name, arch_tag, for_qa=False)

    def query_available_qa(self, series_name=None, arch_tag=None):
        self._query_available(series_name, arch_tag, for_qa=True)

    def _query_available(self, series_name, arch_tag, for_qa):
        language = get_language()
        if not series_name:
            series_name = self.distro.get_codename()
        if not arch_tag:
            arch_tag = get_current_arch()
        # build the command
        cmd = self.HELPER_CMD[:]
        if for_qa:
            cmd.append("available_apps_qa")
        else:
            cmd.append("available_apps")
        cmd += [language,
                series_name,
                arch_tag,
                ]
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_query_available_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_query_available_data(self, spawner, piston_available):
        self.emit("available", piston_available)

    def query_available_for_me(self, oauth_token, openid_identifier):
        cmd = self.HELPER_CMD[:]
        cmd.append("subscriptions_for_me")
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_query_available_for_me_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_query_available_for_me_data(self, spawner, piston_available_for_me):
        self.emit("available-for-me", piston_available_for_me)

    def query_exhibits(self):
        cmd = self.HELPER_CMD[:]
        cmd.append("exhibits")
        cmd.append(get_language())
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_exhibits_data_available)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_exhibits_data_available(self, spawner, exhibits):
        for exhibit in exhibits:
            # special case, if there is no title provided by the server
            # just extract the title from the first "h1" html
            if not hasattr(exhibit, "title_translated"):
                if exhibit.html:
                    from softwarecenter.utils import get_title_from_html
                    exhibit.title_translated = get_title_from_html(exhibit.html)
                else:
                    exhibit.title_translated = ""
        self.emit("exhibits", exhibits)
        
if __name__ == "__main__":
    def _available(agent, available):
        print ("_available: %s" % available)
    def _available_for_me(agent, available_for_me):
        print ("_availalbe_for_me: %s" % available_for_me)
    def _exhibits(agent, exhibits):
        print ("exhibits: " % exhibits)
    def _error(agent, msg):
        print ("got a error" % msg)
        #gtk.main_quit()

    # test specific stuff
    logging.basicConfig()
    softwarecenter.paths.datadir = "./data"

    scagent = SoftwareCenterAgent()
    scagent.connect("available-for-me", _available_for_me)
    scagent.connect("available", _available)
    scagent.connect("exhibits", _exhibits)
    scagent.connect("error", _error)
    #scagent.query_available("natty", "i386")
    #scagent.query_available_for_me("dummy_oauth", "dummy openid")
    scagent.query_exhibits()

    from gi.repository import Gtk
    Gtk.main()
