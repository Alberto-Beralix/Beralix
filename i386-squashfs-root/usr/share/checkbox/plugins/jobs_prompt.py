#
# This file is part of Checkbox.
#
# Copyright 2010 Canonical Ltd.
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
from checkbox.contrib.persist import Persist, MemoryBackend

from checkbox.job import JobStore, UNINITIATED, UNTESTED
from checkbox.properties import Int, Path
from checkbox.plugin import Plugin
from checkbox.user_interface import NEXT, PREV


class JobsPrompt(Plugin):

    # Directory where messages are stored
    store_directory = Path(default="%(checkbox_data)s/store")

    # Maximum number of messages per directory
    store_directory_size = Int(default=1000)

    @property
    def persist(self):
        if self._persist is None:
            self._persist = Persist(backend=MemoryBackend())

        return self._persist.root_at("jobs_prompt")

    @property
    def store(self):
        if self._store is None:
            self._store = JobStore(self.persist, self.store_directory,
                self.store_directory_size)

        return self._store

    def register(self, manager):
        super(JobsPrompt, self).register(manager)

        self._ignore = []
        self._persist = None
        self._store = None

        for (rt, rh) in [
             ("expose-msgstore", self.expose_msgstore),
             ("begin-persist", self.begin_persist),
             ("begin-recover", self.begin_recover),
             ("ignore-jobs", self.ignore_jobs),
             ("prompt-job", self.prompt_job),
             ("prompt-jobs", self.prompt_jobs),
             ("prompt-finish", self.prompt_finish),
             ("report", self.report),
             ("report-job", self.report_job)]:
            self._manager.reactor.call_on(rt, rh)

    def expose_msgstore(self):
        self._manager.reactor.fire("store-access", self.store)

    def begin_persist(self, persist):
        self._persist = persist

    def begin_recover(self, recover):
        if not recover:
            self.store.delete_all_messages()

    def ignore_jobs(self, jobs):
        self._ignore = jobs

    def report_job(self, job):
        # Update job
        job.setdefault("status", UNINITIATED)
        self._manager.reactor.fire("report-%s" % job["plugin"], job)

        self.store.add(job)

    def prompt_job(self, interface, job):
        attribute = "description" if job.get("type") == "suite" else "name"
        if job[attribute] in self._ignore:
            job["status"] = UNTESTED
        else:
            self._manager.reactor.fire("prompt-%s" % job["plugin"], interface, job)

    def prompt_jobs(self, interface):
        while True:
            if interface.direction == PREV:
                if not self.store.remove_pending_offset():
                    break

            messages = self.store.get_pending_messages(1)
            if not messages:
                break

            job = messages[0]
            self._manager.reactor.fire("prompt-job", interface, job)
            self.store.update(job)

            if interface.direction == NEXT:
                self.store.add_pending_offset()

    def prompt_finish(self, interface):
        if interface.direction == NEXT:
            self.store.delete_all_messages()

    def report(self):
        self.store.set_pending_offset(0)
        messages = self.store.get_pending_messages()
        self.store.add_pending_offset(len(messages))

        tests = [m for m in messages if m.get("type") in ("test", "metric")]
        self._manager.reactor.fire("report-tests", tests)

        attachments = [m for m in messages if m.get("type") == "attachment" and "data" in m]
        self._manager.reactor.fire("report-attachments", attachments)


factory = JobsPrompt
