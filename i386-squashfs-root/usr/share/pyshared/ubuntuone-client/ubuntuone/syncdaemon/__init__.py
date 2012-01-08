# ubuntuone.syncdaemon - Ubuntu One sync daemon modules
#
# Copyright 2009 Canonical Ltd.
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
"""Client module."""

# required capabilities
REQUIRED_CAPS = frozenset(["no-content",
                           "account-info",
                           "resumable-uploads",
                           "fix462230",
                           "volumes",
                           "generations",
                          ])
