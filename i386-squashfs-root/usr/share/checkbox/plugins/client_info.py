#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
from checkbox.properties import String
from checkbox.plugin import Plugin


class ClientInfo(Plugin):

    # Name of the user agent
    name = String()

    # Version of the user agent
    version = String()

    def register(self, manager):
        super(ClientInfo, self).register(manager)

        self._manager.reactor.call_on("report", self.report)

    def report(self):
        message = {
            "name": self.name,
            "version": self.version}
        self._manager.reactor.fire("report-client", message)


factory = ClientInfo
