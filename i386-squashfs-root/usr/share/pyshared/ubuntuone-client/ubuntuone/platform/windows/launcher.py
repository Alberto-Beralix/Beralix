# ubuntuone.platform.linux.unity
#
# Author: Alejandro J. Cura <alecu@canonical.com>
#
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
"""Use libunity to show a progressbar and emblems on the launcher icon."""

U1_DOTDESKTOP = "ubuntuone-control-panel-gtk.desktop"


class UbuntuOneLauncher(object):
    """The Ubuntu One launcher icon."""

    def __init__(self):
        """Initialize this instance."""

    def show_progressbar(self):
        """The progressbar is shown."""

    def hide_progressbar(self):
        """The progressbar is hidden."""

    def set_progress(self, value):
        """The progressbar value is changed."""

    def set_urgent(self, value=True):
        """Set the launcher to urgent."""


# linux needs a dummy launcher in case Unity is not running, of course this
# makes no bloody sense on windows, lets adapt to it and discuss about it
# later
DummyLauncher = UbuntuOneLauncher
