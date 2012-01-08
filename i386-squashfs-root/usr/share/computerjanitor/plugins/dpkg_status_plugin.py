# dpkg_status.py - compact the dpkg status file
# Copyright (C) 2009  Canonical, Ltd.
#
# Author: Michael Vogt <mvo@ubuntu.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from apt_pkg import TagFile, PkgSystemLock, PkgSystemUnLock
import subprocess
import logging

import computerjanitor
_ = computerjanitor.setup_gettext()


class DpkgStatusCruft(computerjanitor.Cruft):

    def __init__(self, n_items):
        self.n_items = n_items

    def get_prefix(self):
        return "dpkg-status"

    def get_prefix_description(self): # pragma: no cover
        return _("%i obsolete entries in the status file") % self.n_items

    def get_shortname(self):
        return _("Obsolete entries in dpkg status")

    def get_description(self): # pragma: no cover
        return _("Obsolete dpkg status entries")

    def cleanup(self): # pragma: no cover
        logging.debug("calling dpkg --forget-old-unavail")
        res = subprocess.call(["dpkg","--forget-old-unavail"])
        logging.debug("dpkg --forget-old-unavail returned %s" % res)

class DpkgStatusPlugin(computerjanitor.Plugin):

    def __init__(self, fname="/var/lib/dpkg/status"):
        self.status = fname
        self.condition = ["PostCleanup"]
    
    def get_cruft(self):
        n_cruft = 0
        tagf = TagFile(open(self.status))
        while tagf.step():
            statusline = tagf.section.get("Status")
            (want, flag, status) = statusline.split()
            if want == "purge" and flag == "ok" and status == "not-installed":
                n_cruft += 1
        logging.debug("DpkgStatusPlugin found %s cruft items" % n_cruft)
        if n_cruft:
            return [DpkgStatusCruft(n_cruft)]
        return [] # pragma: no cover
