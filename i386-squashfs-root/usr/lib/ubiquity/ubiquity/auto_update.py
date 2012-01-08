# Copyright (C) 2006, 2009 Canonical Ltd.
# Written by Michael Vogt <michael.vogt@ubuntu.com> and
# Colin Watson <cjwatson@ubuntu.com>.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

# Update the installer from the network.

import sys
import os
import syslog

import apt
import apt_pkg

from ubiquity import misc

MAGIC_MARKER = "/var/run/ubiquity.updated"
# Make sure that ubiquity is last, otherwise apt may try to install another
# frontend.
UBIQUITY_PKGS = ["ubiquity-casper",
                 "ubiquity-frontend-debconf",
                 "ubiquity-frontend-gtk",
                 "ubiquity-frontend-kde",
                 "ubiquity-ubuntu-artwork",
                 "ubiquity"]


class CacheProgressDebconfProgressAdapter(apt.progress.OpProgress):
    def __init__(self, frontend):
        self.frontend = frontend
        self.frontend.debconf_progress_start(
            0, 100, self.frontend.get_string('reading_package_information'))

    def update(self, percent):
        self.frontend.debconf_progress_set(percent)
        self.frontend.refresh()

    def really_done(self):
        # Unfortunately the process of opening a Cache calls done() twice,
        # so we have to take care of this manually.
        self.frontend.debconf_progress_stop()


class FetchProgressDebconfProgressAdapter(apt.progress.FetchProgress):
    def __init__(self, frontend):
        apt.progress.FetchProgress.__init__(self)
        self.frontend = frontend

    def pulse(self):
        apt.progress.FetchProgress.pulse(self)
        if self.currentCPS > 0:
            info = self.frontend.get_string('apt_progress_cps')
            info = info.replace('${SPEED}', apt_pkg.SizeToStr(self.currentCPS))
        else:
            info = self.frontend.get_string('apt_progress')
        info = info.replace('${INDEX}', str(self.currentItems))
        info = info.replace('${TOTAL}', str(self.totalItems))
        self.frontend.debconf_progress_info(info)
        self.frontend.debconf_progress_set(self.percent)
        self.frontend.refresh()
        return True

    def stop(self):
        self.frontend.debconf_progress_stop()

    def start(self):
        self.frontend.debconf_progress_start(
            0, 100, self.frontend.get_string('updating_package_information'))


class InstallProgressDebconfProgressAdapter(apt.progress.InstallProgress):
    def __init__(self, frontend):
        apt.progress.InstallProgress.__init__(self)
        self.frontend = frontend

    def statusChange(self, unused_pkg, percent, unused_status):
        self.frontend.debconf_progress_set(percent)

    def startUpdate(self):
        self.frontend.debconf_progress_start(
            0, 100, self.frontend.get_string('installing_update'))

    def finishUpdate(self):
        self.frontend.debconf_progress_stop()

    def updateInterface(self):
        apt.progress.InstallProgress.updateInterface(self)
        self.frontend.refresh()


@misc.raise_privileges
def update(frontend):
    frontend.debconf_progress_start(
        0, 3, frontend.get_string('checking_for_installer_updates'))
    # check if we have updates
    cache_progress = CacheProgressDebconfProgressAdapter(frontend)
    cache = apt.Cache(cache_progress)
    cache_progress.really_done()

    fetchprogress = FetchProgressDebconfProgressAdapter(frontend)
    try:
        cache.update(fetchprogress)
        cache_progress = CacheProgressDebconfProgressAdapter(frontend)
        cache = apt.Cache(cache_progress)
        cache_progress.really_done()
        updates = filter(
            lambda pkg: pkg in cache and cache[pkg].isUpgradable,
            UBIQUITY_PKGS)
    except IOError, e:
        print "ERROR: cache.update() returned: '%s'" % e
        updates = []

    if not updates:
        frontend.debconf_progress_stop()
        return False

    # We have something to upgrade.  Shut down debconf-communicator for
    # the duration, otherwise we'll have locking problems.
    if frontend.dbfilter is not None and frontend.dbfilter.db is not None:
        frontend.stop_debconf()
        frontend.dbfilter.db = None
        stopped_debconf = True
    else:
        stopped_debconf = False
    try:
        # install the updates
        fixer = apt.ProblemResolver(cache)
        for pkg in updates:
            cache[pkg].markInstall(autoFix=False)
            fixer.clear(cache[pkg])
            fixer.protect(cache[pkg])
        fixer.resolve()
        try:
            # dpkg will talk to stdout. We'd rather have this in the debug
            # log file.
            old_stdout = os.dup(1)
            os.dup2(2, 1)
            cache.commit(FetchProgressDebconfProgressAdapter(frontend),
                         InstallProgressDebconfProgressAdapter(frontend))
        except (SystemError, IOError), e:
            syslog.syslog(syslog.LOG_ERR,
                          "Error installing the update: '%s'" % e)
            title = frontend.get_string('error_updating_installer')
            if frontend.locale is None:
                extended_locale = 'extended:c'
            else:
                extended_locale = 'extended:%s' % frontend.locale
            msg = frontend.get_string('error_updating_installer',
                                      extended_locale)
            msg = msg.replace('${ERROR}', str(e))
            frontend.error_dialog(title, msg)
            frontend.debconf_progress_stop()
            return True
        finally:
            os.dup2(old_stdout, 1)
            os.close(old_stdout)

        # all went well, write marker and restart self
        # FIXME: we probably want some sort of in-between-restart-splash
        #        or at least a dialog here
        open(MAGIC_MARKER, "w").write("1")
        os.execv(sys.argv[0], sys.argv)
        return False
    finally:
        if stopped_debconf:
            frontend.start_debconf()
            frontend.dbfilter.db = frontend.db


def already_updated():
    return os.path.exists(MAGIC_MARKER)
