# missing_package_cruft.py - install a missing package
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


class MissingPackageCruft(computerjanitor.Cruft):

    """Install a missing package."""
        
    def __init__(self, package, description=None):
        self.package = package
        self.description = description
        
    def get_prefix(self):
        return "install-deb"
        
    def get_prefix_description(self):
        return _("Install missing package.")
        
    def get_shortname(self):
        return self.package.name
        
    def get_description(self):
        if self.description:    
            return self.description
        else:
            return _("Package %s should be installed.") % self.package.name
                
    def cleanup(self):
        self.package.markInstall()
