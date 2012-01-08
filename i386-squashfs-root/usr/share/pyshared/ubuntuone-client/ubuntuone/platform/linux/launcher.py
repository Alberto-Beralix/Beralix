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

try:
    from gi.repository import Unity
    use_libunity = True
except ImportError:
    use_libunity = False

U1_DOTDESKTOP = "ubuntuone-installer.desktop"


class UbuntuOneLauncherUnity(object):
    """The Ubuntu One launcher icon."""

    def __init__(self):
        self.entry = Unity.LauncherEntry.get_for_desktop_id(U1_DOTDESKTOP)

    def show_progressbar(self):
        """Show the progress bar."""
        self.entry.set_property('progress_visible', True)

    def hide_progressbar(self):
        """Hide the progress bar."""
        self.entry.set_property('progress_visible', False)

    def set_progress(self, value):
        """Change progressbar value."""
        self.entry.set_property('progress', value)

    def set_urgent(self, value=True):
        """Set the launcher to urgent."""
        self.entry.set_property('urgent', value)

    def set_count(self, value):
        """Set the count value."""
        self.entry.set_property('count', value)

    def show_count(self):
        """Show the count."""
        self.entry.set_property('count_visible', True)

    def hide_count(self):
        """Show the count."""
        self.entry.set_property('count_visible', False)


class DummyLauncher(object):
    """A dummy launcher icon."""

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

    def set_count(self, value):
        """Set the count value."""

    def show_count(self):
        """Show the count."""

    def hide_count(self):
        """Show the count."""


UbuntuOneLauncher = UbuntuOneLauncherUnity if use_libunity else DummyLauncher
