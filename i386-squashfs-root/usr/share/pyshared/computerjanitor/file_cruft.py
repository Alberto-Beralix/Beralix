# file_cruft.py - implementation of file cruft 
# Copyright (C) 2008, 2009  Canonical, Ltd.
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
_ = computerjanitor.setup_gettext()


class FileCruft(computerjanitor.Cruft):

    """Cruft that is individual files.
    
    This type of cruft consists of individual files that should be
    removed. Various plugins may decide that various files are cruft;
    they can all use objects of FileCruft type to mark such files,
    regardless of the reason the files are considered cruft.
    
    When FileCruft instantiated, the file is identified by a pathname.
    
    """

    def __init__(self, pathname, description):
        self.pathname = pathname
        st = os.stat(pathname)
        self.disk_usage = st.st_blocks * 512
        self.description = description

    def get_prefix(self):
        return "file"

    def get_prefix_description(self):
        return _("A file on disk")

    def get_shortname(self):
        return self.pathname

    def get_description(self):
        return "%s\n" % self.description

    def get_disk_usage(self):
        return self.disk_usage

    def cleanup(self):
        os.remove(self.pathname)
