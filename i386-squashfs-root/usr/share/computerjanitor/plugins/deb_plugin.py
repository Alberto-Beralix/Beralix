# deb_plugin.py - common package for post_cleanup for apt/.deb packages
# Copyright (C) 2008  Canonical, Ltd.
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


import os

import computerjanitor
import apt


class DebPlugin(computerjanitor.Plugin):

    """Plugin for post_cleanup processing with apt.
    
    This plugin does not find any cruft of its own. Instead it
    centralizes the post_cleanup handling for all packages that remove
    .deb packages.
    
    """

    def get_cruft(self):
        return []

    def post_cleanup(self):
        try:
            self.app.apt_cache.commit(apt.progress.text.AcquireProgress(),
                                      apt.progress.base.InstallProgress())
        except Exception, e: # pragma: no cover
            raise
        finally:
            self.app.refresh_apt_cache()
