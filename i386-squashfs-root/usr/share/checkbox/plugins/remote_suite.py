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
from checkbox.plugin import Plugin


class RemoteSuite(Plugin):

    def register(self, manager):
        super(RemoteSuite, self).register(manager)

        for (rt, rh) in [
             ("prompt-remote", self.prompt_remote),
             ("report-remote", self.report_remote)]:
            self._manager.reactor.call_on(rt, rh)

    def prompt_remote(self, interface, suite):
        self._manager.reactor.fire("prompt-suite", interface, suite)

        # Register temporary handler for report-message events
        def report_message(message):
            message["suite"] = suite["name"]
            self._manager.reactor.fire("report-job", message)

        event_id = self._manager.reactor.call_on("report-message", report_message)
        self._manager.reactor.fire("message-exec", suite)
        self._manager.reactor.cancel_call(event_id)

    def report_remote(self, suite):
        self._manager.reactor.fire("report-suite", suite)


factory = RemoteSuite
