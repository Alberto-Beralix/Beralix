# exc.py - exceptions for computerjanitor
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


import computerjanitor
_ = computerjanitor.setup_gettext()


class ComputerJanitorException(Exception):

    def __str__(self):
        return self._str


class UnimplementedMethod(ComputerJanitorException):

    def __init__(self, method):
        self._str = _("Unimplemented method: %s") % str(method)
