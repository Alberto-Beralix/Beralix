# langpack_manual_plugin.py - mark langpacks to be manually installed
# Copyright (C) 2009  Canonical, Ltd.
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


import computerjanitor
_ = computerjanitor.setup_gettext()

import logging

class ManualInstallCruft(computerjanitor.Cruft):

    def __init__(self, pkg):
        self.pkg = pkg

    def get_prefix(self):
        return "mark-manually-installed"
        
    def get_shortname(self):
        return self.pkg.name

    def get_description(self):
        return (_("%s needs to be marked as manually installed.") % 
                self.pkg.name)

    def cleanup(self):
        self.pkg.markKeep()
        self.pkg.markInstall()


class MarkLangpacksManuallyInstalledPlugin(computerjanitor.Plugin):

    """Plugin to mark language packs as manually installed.
    
    This works around quirks in the hardy->intrepid upgrade.

    """

    def __init__(self):
        self.condition = ["from_hardyPostDistUpgradeCache"]

    def get_cruft(self):
        # language-support-* changed its dependencies from "recommends"
        # to "suggests" for language-pack-* - this means that apt will
        # think they are now auto-removalable if they got installed
        # as a dep of language-support-* - we fix this here
        cache = self.app.apt_cache
        for pkg in cache:
            if (pkg.name.startswith("language-pack-") and 
                not pkg.name.endswith("-base") and
                cache._depcache.IsAutoInstalled(pkg._pkg) and
                pkg.is_installed):
                logging.debug("setting '%s' to manual installed" % pkg.name)
                yield ManualInstallCruft(pkg)
