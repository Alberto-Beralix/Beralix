# DistUpgradeQuirks.py 
#  
#  Copyright (c) 2004-2010 Canonical
#  
#  Author: Michael Vogt <michael.vogt@ubuntu.com>
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU General Public License as 
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

import apt
import glob
import logging
import os
import os.path
import re
import hashlib
import shutil
import string
import sys
import subprocess
from subprocess import PIPE, Popen
from hashlib import md5
from utils import lsmod, get_arch

from DistUpgradeGettext import gettext as _
from computerjanitor.plugin import PluginManager

class DistUpgradeQuirks(object):
    """
    This class collects the various quirks handlers that can
    be hooked into to fix/work around issues that the individual
    releases have
    """
    
    def __init__(self, controller, config):
        self.controller = controller
        self._view = controller._view
        self.config = config
        self.uname = Popen(["uname","-r"],stdout=PIPE).communicate()[0].strip()
        self.arch = get_arch()
        self.plugin_manager = PluginManager(self.controller, ["./plugins"])

    # the quirk function have the name:
    #  $Name (e.g. PostUpgrade)
    #  $todist$Name (e.g. intrepidPostUpgrade)
    #  $from_$fromdist$Name (e.g. from_dapperPostUpgrade)
    def run(self, quirksName):
        """
        Run the specific quirks handler, the follow handlers are supported:
        - PreCacheOpen: run *before* the apt cache is opened the first time
                        to set options that affect the cache
        - PostInitialUpdate: run *before* the sources.list is rewritten but
                             after a initial apt-get update
        - PostDistUpgradeCache: run *after* the dist-upgrade was calculated
                                in the cache
        - StartUpgrade: before the first package gets installed (but the
                        download is finished)
        - PostUpgrade: run *after* the upgrade is finished successfully and 
                       packages got installed
        - PostCleanup: run *after* the cleanup (orphaned etc) is finished
        """
        # we do not run any quirks in partialUpgrade mode
        if self.controller._partialUpgrade:
            logging.info("not running quirks in partialUpgrade mode")
            return
        # first check for matching plugins
        for condition in [
            quirksName,
            "%s%s" %  (self.config.get("Sources","To"), quirksName),
            "from_%s%s" % (self.config.get("Sources","From"), quirksName)
            ]:
            for plugin in self.plugin_manager.get_plugins(condition):
                logging.debug("running quirks plugin %s" % plugin)
                plugin.do_cleanup_cruft()
        
        # run the handler that is common to all dists
        funcname = "%s" % quirksName
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

        # run the quirksHandler to-dist
        funcname = "%s%s" % (self.config.get("Sources","To"), quirksName)
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

        # now run the quirksHandler from_${FROM-DIST}Quirks
        funcname = "from_%s%s" % (self.config.get("Sources","From"), quirksName)
        func = getattr(self, funcname, None)
        if func is not None:
            logging.debug("quirks: running %s" % funcname)
            func()

    # individual quirks handler that run *before* the cache is opened
    def PreCacheOpen(self):
        """ run before the apt cache is opened the first time """
        logging.debug("running Quirks.PreCacheOpen")

    def oneiricPreCacheOpen(self):
        logging.debug("running Quirks.oneiricPreCacheOpen")
        # enable i386 multiach temporarely during the upgrade if on amd64
        # this needs to be done very early as libapt caches the result
        # of the "getArchitectures()" call in aptconfig and its not possible
        # currently to invalidate this cache
        if apt.apt_pkg.config.find("Apt::Architecture") == "amd64":
            logging.debug("multiarch: enabling i386 as a additional architecture")
            apt.apt_pkg.config.set("Apt::Architectures::", "i386")
            # increase case size to workaround bug in natty apt that
            # may cause segfault on cache grow
            apt.apt_pkg.config.set("APT::Cache-Start", str(48*1024*1024))


    # individual quirks handler when the dpkg run is finished ---------
    def PostCleanup(self):
        " run after cleanup " 
        logging.debug("running Quirks.PostCleanup")

    def from_dapperPostUpgrade(self):
        " this works around quirks for dapper->hardy upgrades "
        logging.debug("running Controller.from_dapperQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()
        
    def intrepidPostUpgrade(self):
        " this applies rules for the hardy->intrepid upgrade "
	logging.debug("running Controller.intrepidQuirks handler")
        self._addRelatimeToFstab()

    def gutsyPostUpgrade(self):
        """ this function works around quirks in the feisty->gutsy upgrade """
        logging.debug("running Controller.gutsyQuirks handler")

    def feistyPostUpgrade(self):
        """ this function works around quirks in the edgy->feisty upgrade """
        logging.debug("running Controller.feistyQuirks handler")
        self._rewriteFstab()
        self._checkAdminGroup()

    def karmicPostUpgrade(self):
        """ this function works around quirks in the jaunty->karmic upgrade """
        logging.debug("running Controller.karmicPostUpgrade handler")
        self._ntfsFstabFixup()
        self._checkLanguageSupport()

    # quirks when run when the initial apt-get update was run ----------------
    def from_lucidPostInitialUpdate(self):
        """ Quirks that are run before the sources.list is updated to the
            new distribution when upgrading from a lucid system (either
            to maverick or the new LTS)
        """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # systems < i686 will not upgrade
        self._test_and_fail_on_non_i686()
        self._test_and_warn_on_i8xx()

    def oneiricPostInitialUpdate(self):
        self._test_and_warn_on_i8xx()

    def lucidPostInitialUpdate(self):
        """ quirks that are run before the sources.list is updated to lucid """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # upgrades on systems with < arvm6 CPUs will break
        self._test_and_fail_on_non_arm_v6()
        # vserver+upstart are problematic
        self._test_and_warn_if_vserver()
        # fglrx dropped support for some cards
        self._test_and_warn_on_dropped_fglrx_support()

    # quirks when the cache upgrade calculation is finished -------------------
    def from_dapperPostDistUpgradeCache(self):
        self.hardyPostDistUpgradeCache()
        self.gutsyPostDistUpgradeCache()
        self.feistyPostDistUpgradeCache()
        self.edgyPostDistUpgradeCache()

    def from_hardyPostDistUpgradeCache(self):
        """ this function works around quirks in upgrades from hardy """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # ensure 386 -> generic transition happens
        self._kernel386TransitionCheck()
        # ensure kubuntu-kde4-desktop transition
        self._kubuntuDesktopTransition()
        # evms got removed after hardy, warn and abort
        if self._usesEvmsInMounts():
            logging.error("evms in use in /etc/fstab")
            self._view.error(_("evms in use"),
                             _("Your system uses the 'evms' volume manager "
                               "in /proc/mounts. "
                               "The 'evms' software is no longer supported, "
                               "please switch it off and run the upgrade "
                               "again when this is done."))
            self.controller.abort()
        # check if "wl" module is loaded and if so, install bcmwl-kernel-source
        self._checkAndInstallBroadcom()
        # langpacks got re-organized in 9.10
        self._dealWithLanguageSupportTransition()
        # nvidia-71, nvidia-96 got dropped
        self._test_and_warn_on_old_nvidia()
        # new nvidia needs a CPU with sse support
        self._test_and_warn_on_nvidia_and_no_sse()

    def nattyPostDistUpgradeCache(self):
        """
        this function works around quirks in the 
        maverick -> natty cache upgrade calculation
        """
        self._add_kdegames_card_extra_if_installed()

    def maverickPostDistUpgradeCache(self):
        """
        this function works around quirks in the 
        lucid->maverick upgrade calculation
        """
        self._add_extras_repository()
        self._gutenprint_fixup()

    def karmicPostDistUpgradeCache(self):
        """ 
        this function works around quirks in the 
        jaunty->karmic upgrade calculation
        """
        # check if "wl" module is loaded and if so, install
        # bcmwl-kernel-source (this is needed for lts->lts as well)
        self._checkAndInstallBroadcom()
        self._dealWithLanguageSupportTransition()
        self._kernel386TransitionCheck()
        self._mysqlClusterCheck()

    def jauntyPostDistUpgradeCache(self):
        """ 
        this function works around quirks in the 
        intrepid->jaunty upgrade calculation
        """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # bug 332328 - make sure pidgin-libnotify is upgraded
        for pkg in ["pidgin-libnotify"]:
            if (self.controller.cache.has_key(pkg) and
                self.controller.cache[pkg].is_installed and
                not self.controller.cache[pkg].marked_upgrade):
                logging.debug("forcing '%s' upgrade" % pkg)
                self.controller.cache[pkg].mark_upgrade()
        # deal with kipi/gwenview/kphotoalbum
        for pkg in ["gwenview","digikam"]:
            if (self.controller.cache.has_key(pkg) and
                self.controller.cache[pkg].is_installed and
                not self.controller.cache[pkg].marked_upgrade):
                logging.debug("forcing libkipi '%s' upgrade" % pkg)
                if self.controller.cache.has_key("libkipi0"):
                    logging.debug("removing  libkipi0)")
                    self.controller.cache["libkipi0"].mark_delete()
                self.controller.cache[pkg].mark_upgrade()
        
    def intrepidPostDistUpgradeCache(self):
        """ 
        this function works around quirks in the 
        hardy->intrepid upgrade 
        """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # kdelibs4-dev is unhappy (#279621)
        fromp = "kdelibs4-dev"
        to = "kdelibs5-dev"
        if (self.controller.cache.has_key(fromp) and 
            self.controller.cache[fromp].is_installed and
            self.controller.cache.has_key(to)):
            self.controller.cache.mark_install(to, "kdelibs4-dev -> kdelibs5-dev transition")

    def hardyPostDistUpgradeCache(self):
        """ 
        this function works around quirks in the 
        {dapper,gutsy}->hardy upgrade 
        """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # deal with gnome-translator and help apt with the breaks
        if (self.controller.cache.has_key("nautilus") and
            self.controller.cache["nautilus"].is_installed and
            not self.controller.cache["nautilus"].marked_upgrade):
            # uninstallable and gutsy apt is unhappy about this
            # breaks because it wants to upgrade it and gives up
            # if it can't
            for broken in ("link-monitor-applet"):
                if self.controller.cache.has_key(broken) and self.controller.cache[broken].is_installed:
                    self.controller.cache[broken].mark_delete()
            self.controller.cache["nautilus"].mark_install()
        # evms gives problems, remove it if it is not in use
        self._checkAndRemoveEvms()
        # give the language-support-* packages a extra kick
        # (if we have network, otherwise this will not work)
        if self.config.get("Options","withNetwork") == "True":
            for pkg in self.controller.cache:
                if (pkg.name.startswith("language-support-") and
                    pkg.is_installed and
                    not pkg.marked_upgrade):
                    self.controller.cache.mark_install(pkg.name,"extra language-support- kick")

    def gutsyPostDistUpgradeCache(self):
        """ this function works around quirks in the feisty->gutsy upgrade """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # lowlatency kernel flavour vanished from feisty->gutsy
        try:
            (version, build, flavour) = self.uname.split("-")
            if (flavour == 'lowlatency' or 
                flavour == '686' or
                flavour == 'k7'):
                kernel = "linux-image-generic"
                if not (self.controller.cache[kernel].is_installed or self.controller.cache[kernel].marked_install):
                    logging.debug("Selecting new kernel '%s'" % kernel)
                    self.controller.cache[kernel].mark_install()
        except Exception, e:
            logging.warning("problem while transitioning lowlatency kernel (%s)" % e)
        # fix feisty->gutsy utils-linux -> nfs-common transition (LP: #141559)
        try:
            for line in map(string.strip, open("/proc/mounts")):
                if line == '' or line.startswith("#"):
                    continue
                try:
                    (device, mount_point, fstype, options, a, b) = line.split()
                except Exception, e:
                    logging.error("can't parse line '%s'" % line)
                    continue
                if "nfs" in fstype:
                    logging.debug("found nfs mount in line '%s', marking nfs-common for install " % line)
                    self.controller.cache["nfs-common"].mark_install()
                    break
        except Exception, e:
            logging.warning("problem while transitioning util-linux -> nfs-common (%s)" % e)

    def feistyPostDistUpgradeCache(self):
        """ this function works around quirks in the edgy->feisty upgrade """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        # ndiswrapper changed again *sigh*
        for (fr, to) in [("ndiswrapper-utils-1.8","ndiswrapper-utils-1.9")]:
            if self.controller.cache.has_key(fr) and self.controller.cache.has_key(to):
                if self.controller.cache[fr].is_installed and not self.controller.cache[to].marked_install:
                    try:
                        self.controller.cache.mark_install(to,"%s->%s quirk upgrade rule" % (fr, to))
                    except SystemError, e:
                        logging.warning("Failed to apply %s->%s install (%s)" % (fr, to, e))
            

    def edgyPostDistUpgradeCache(self):
        """ this function works around quirks in the dapper->edgy upgrade """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        for pkg in self.controller.cache:
            # deal with the python2.4-$foo -> python-$foo transition
            if (pkg.name.startswith("python2.4-") and
                pkg.is_installed and
                not pkg.marked_upgrade):
                basepkg = "python-"+pkg.name[len("python2.4-"):]
                if (self.controller.cache.has_key(basepkg) and 
                    self.controller.cache[basepkg].candidateDownloadable and
                    not self.controller.cache[basepkg].marked_install):
                    try:
                        self.controller.cache.mark_install(basepkg,
                                         "python2.4->python upgrade rule")
                    except SystemError, e:
                        logging.debug("Failed to apply python2.4->python install: %s (%s)" % (basepkg, e))
            # xserver-xorg-input-$foo gives us trouble during the upgrade too
            if (pkg.name.startswith("xserver-xorg-input-") and
                pkg.is_installed and
                not pkg.marked_upgrade):
                try:
                    self.controller.cache.mark_install(pkg.name, "xserver-xorg-input fixup rule")
                except SystemError, e:
                    logging.debug("Failed to apply fixup: %s (%s)" % (pkg.name, e))
            
        # deal with held-backs that are unneeded
        for pkgname in ["hpijs", "bzr", "tomboy"]:
            if (self.controller.cache.has_key(pkgname) and self.controller.cache[pkgname].is_installed and
                self.controller.cache[pkgname].isUpgradable and not self.controller.cache[pkgname].marked_upgrade):
                try:
                    self.controller.cache.mark_install(pkgname,"%s quirk upgrade rule" % pkgname)
                except SystemError, e:
                    logging.debug("Failed to apply %s install (%s)" % (pkgname,e))
        # libgl1-mesa-dri from xgl.compiz.info (and friends) breaks the
	# upgrade, work around this here by downgrading the package
        if self.controller.cache.has_key("libgl1-mesa-dri"):
            pkg = self.controller.cache["libgl1-mesa-dri"]
            # the version from the compiz repo has a "6.5.1+cvs20060824" ver
            if (pkg.candidateVersion == pkg.installedVersion and
                "+cvs2006" in pkg.candidateVersion):
                for ver in pkg._pkg.VersionList:
                    # the "official" edgy version has "6.5.1~20060817-0ubuntu3"
                    if "~2006" in ver.VerStr:
			# ensure that it is from a trusted repo
			for (VerFileIter, index) in ver.FileList:
				indexfile = self.controller.cache._list.FindIndex(VerFileIter)
				if indexfile and indexfile.IsTrusted:
					logging.info("Forcing downgrade of libgl1-mesa-dri for xgl.compz.info installs")
		                        self.controller.cache._depcache.SetCandidateVer(pkg._pkg, ver)
					break
                                    
        # deal with general if $foo is installed, install $bar
        for (fr, to) in [("xserver-xorg-driver-all","xserver-xorg-video-all")]:
            if self.controller.cache.has_key(fr) and self.controller.cache.has_key(to):
                if self.controller.cache[fr].is_installed and not self.controller.cache[to].marked_install:
                    try:
                        self.controller.cache.mark_install(to,"%s->%s quirk upgrade rule" % (fr, to))
                    except SystemError, e:
                        logging.debug("Failed to apply %s->%s install (%s)" % (fr, to, e))
                    
    def dapperPostDistUpgradeCache(self):
        """ this function works around quirks in the breezy->dapper upgrade """
        logging.debug("running %s" %  sys._getframe().f_code.co_name)
        if (self.controller.cache.has_key("nvidia-glx") and self.controller.cache["nvidia-glx"].is_installed and
            self.controller.cache.has_key("nvidia-settings") and self.controller.cache["nvidia-settings"].is_installed):
            logging.debug("nvidia-settings and nvidia-glx is installed")
            self.controller.cache.mark_remove("nvidia-settings")
            self.controller.cache.mark_install("nvidia-glx")

    # run right before the first packages get installed
    def StartUpgrade(self):
        self._applyPatches()
        self._removeOldApportCrashes()
        self._removeBadMaintainerScripts()
        self._killUpdateNotifier()
        self._killKBluetooth()
        self._killScreensaver()
        self._stopDocvertConverter()
    def oneiricStartUpgrade(self):
        logging.debug("oneiric StartUpgrade quirks")
        # fix grub issue
        cache = self.controller.cache
        if (os.path.exists("/usr/sbin/update-grub") and
            not os.path.exists("/etc/kernel/postinst.d/zz-update-grub")):
            # create a version of zz-update-grub to avoid depending on
            # the upgrade order. if that file is missing, we may end
            # up generating a broken grub.cfg
            targetdir = "/etc/kernel/postinst.d"
            if not os.path.exists(targetdir):
                os.makedirs(targetdir)
            logging.debug("copying zz-update-grub into %s" % targetdir)
            shutil.copy("zz-update-grub", targetdir)
            os.chmod(os.path.join(targetdir, "zz-update-grub"), 0755)
        # enable multiarch permanently
        if apt.apt_pkg.config.find("Apt::Architecture") == "amd64":
            self._enable_multiarch(foreign_arch="i386")
            
    def from_hardyStartUpgrade(self):
        logging.debug("from_hardyStartUpgrade quirks")
        self._stopApparmor()
    def jauntyStartUpgrade(self):
        self._createPycentralPkgRemove()
        # hal/NM triggers problem, if the old (intrepid) hal gets
        # triggered for a restart this causes NM to drop all connections
        # because (old) hal thinks it has no devices anymore (LP: #327053)
        ap = "/var/lib/dpkg/info/hal.postinst"
        if os.path.exists(ap):
            # intrepid md5 of hal.postinst (jaunty one is different)
            # md5 jaunty 22c146857d751181cfe299a171fc11c9
            md5sum = "146145275900af343d990a4dea968d7c"
            if md5(open(ap).read()).hexdigest() == md5sum:
                logging.debug("removing bad script '%s'" % ap)
                os.unlink(ap)
    def dapperStartUpgrade(self):
        # check theme, crux is known to fail badly when upgraded 
        # from dapper
        if "DISPLAY" in os.environ and "SUDO_USER" in os.environ:
            out = subprocess.Popen(["sudo","-u", os.environ["SUDO_USER"],
                                    "./theme-switch-helper.py", "-g"],
                                    stdout=subprocess.PIPE).communicate()[0]
            if "Crux" in out:
                subprocess.call(["sudo","-u", os.environ["SUDO_USER"],
                                    "./theme-switch-helper.py", "--defaults"])
        return True

    # helpers
    def _get_pci_ids(self):
        """ return a set of pci ids of the system (using lspci -n) """
        lspci = set()
        try:
            p = subprocess.Popen(["lspci","-n"],stdout=subprocess.PIPE)
        except OSError:
            return lspci
        for line in p.communicate()[0].split("\n"):
            if line:
                lspci.add(line.split()[2])
        return lspci

    def _test_and_warn_on_i8xx(self):
        I8XX_PCI_IDS = ["8086:7121", # i810
                        "8086:7125", # i810e
                        "8086:1132", # i815
                        "8086:3577", # i830
                        "8086:2562", # i845
                        "8086:3582", # i855
                        "8086:2572", # i865
                        ]
        lspci = self._get_pci_ids()
        if set(I8XX_PCI_IDS).intersection(lspci):
            res = self._view.askYesNoQuestion(
                _("Your graphics hardware may not be fully supported in "
                  "Ubuntu 11.04."),
                _("The support in Ubuntu 11.04 for your intel graphics "
                  "hardware is limited "
                  "and you may encounter problems after the upgrade. "
                  "Do you want to continue with the upgrade?")
                )
            if res == False:
                self.controller.abort()

    def _test_and_warn_on_nvidia_and_no_sse(self):
        """ The current 
        """
        # check if we have sse
        cache = self.controller.cache
        for pkgname in ["nvidia-glx-180", "nvidia-glx-185", "nvidia-glx-195"]:
            if (cache.has_key(pkgname) and 
                cache[pkgname].marked_install and
                self._checkVideoDriver("nvidia")):
                logging.debug("found %s video driver" % pkgname)
                if not self._cpuHasSSESupport():
                    logging.warning("nvidia driver that needs SSE but cpu has no SSE support")
                    res = self._view.askYesNoQuestion(_("Upgrading may reduce desktop "
                                        "effects, and performance in games "
                                        "and other graphically intensive "
                                        "programs."),
                                      _("This computer is currently using "
                                        "the NVIDIA 'nvidia' "
                                        "graphics driver. "
                                        "No version of this driver is "
                                        "available that works with your "
                                        "video card in Ubuntu "
                                        "10.04 LTS.\n\nDo you want to continue?"))
                    if res == False:
                        self.controller.abort()
                    # if the user continue, do not install the broken driver
                    # so that we can transiton him to the free "nv" one after
                    # the upgrade
                    self.controller.cache[pkgname].mark_keep()
        

    def _test_and_warn_on_old_nvidia(self):
        """ nvidia-glx-71 and -96 are no longer in the archive since 8.10 """
        # now check for nvidia and show a warning if needed
        cache = self.controller.cache
        for pkgname in ["nvidia-glx-71","nvidia-glx-96"]:
            if (cache.has_key(pkgname) and 
                cache[pkgname].marked_install and
                self._checkVideoDriver("nvidia")):
                logging.debug("found %s video driver" % pkgname)
                res = self._view.askYesNoQuestion(_("Upgrading may reduce desktop "
                                        "effects, and performance in games "
                                        "and other graphically intensive "
                                        "programs."),
                                      _("This computer is currently using "
                                        "the NVIDIA 'nvidia' "
                                        "graphics driver. "
                                        "No version of this driver is "
                                        "available that works with your "
                                        "video card in Ubuntu "
                                        "10.04 LTS.\n\nDo you want to continue?"))
                if res == False:
                    self.controller.abort()
                # if the user continue, do not install the broken driver
                # so that we can transiton him to the free "nv" one after
                # the upgrade
                self.controller.cache[pkgname].mark_keep()

    def _test_and_warn_on_dropped_fglrx_support(self):
        """
        Some cards are no longer supported by fglrx. Check if that
        is the case and warn
        """
        # this is to deal with the fact that support for some of the cards
        # that fglrx used to support got dropped
        if (self._checkVideoDriver("fglrx") and 
            not self._supportInModaliases("fglrx")):
             res = self._view.askYesNoQuestion(_("Upgrading may reduce desktop "
                                         "effects, and performance in games "
                                         "and other graphically intensive "
                                         "programs."),
                                       _("This computer is currently using "
                                         "the AMD 'fglrx' graphics driver. "
                                         "No version of this driver is "
                                         "available that works with your "
                                         "hardware in Ubuntu "
                                         "10.04 LTS.\n\nDo you want to continue?"))
             if res == False:
                 self.controller.abort()
             # if the user wants to continue we remove the fglrx driver
             # here because its no use (no support for this card)
             logging.debug("remove xorg-driver-fglrx,xorg-driver-fglrx-envy,fglrx-kernel-source")
             l=self.controller.config.getlist("Distro","PostUpgradePurge")
             l.append("xorg-driver-fglrx")
             l.append("xorg-driver-fglrx-envy")
             l.append("fglrx-kernel-source")
             l.append("fglrx-amdcccle")
             l.append("xorg-driver-fglrx-dev")
             l.append("libamdxvba1")
             self.controller.config.set("Distro","PostUpgradePurge",",".join(l))

    def _test_and_fail_on_non_i686(self):
        """
        Test and fail if the cpu is not i686 or more or if its a newer
        CPU but does not have the cmov feature (LP: #587186)
        """
        # check on i386 only
        if self.arch == "i386":
            logging.debug("checking for i586 CPU")
            if not self._cpu_is_i686_and_has_cmov():
                logging.error("not a i686 or no cmov")
                summary = _("No i686 CPU")
                msg = _("Your system uses an i586 CPU or a CPU that does "
                        "not have the 'cmov' extension. "
                        "All packages were built with "
                        "optimizations requiring i686 as the "
                        "minimal architecture. It is not possible to "
                        "upgrade your system to a new Ubuntu release "
                        "with this hardware.")
                self._view.error(summary, msg)
                self.controller.abort()

    def _cpu_is_i686_and_has_cmov(self, cpuinfo_path="/proc/cpuinfo"):
        if not os.path.exists(cpuinfo_path):
            logging.error("cannot open %s ?!?" % cpuinfo_path)
            return True
        cpuinfo = open(cpuinfo_path).read()
        # check family
        if re.search("^cpu family\s*:\s*[345]\s*", cpuinfo, re.MULTILINE):
            logging.debug("found cpu family [345], no i686+")
            return False
        # check flags for cmov
        match = re.search("^flags\s*:\s*(.*)", cpuinfo, re.MULTILINE)
        if match:
            if not "cmov" in match.group(1).split():
                logging.debug("found flags '%s'" % match.group(1))
                logging.debug("can not find cmov in flags")
                return False
        return True


    def _test_and_fail_on_non_arm_v6(self):
        """ 
        Test and fail if the cpu is not a arm v6 or greater,
        from 9.10 on we do no longer support those CPUs
        """
        if self.arch == "armel":
            if not self._checkArmCPU():
                res = self._view.error(_("No ARMv6 CPU"),
                    _("Your system uses an ARM CPU that is older "
                      "than the ARMv6 architecture. "
                      "All packages in karmic were built with "
                      "optimizations requiring ARMv6 as the "
                      "minimal architecture. It is not possible to "
                      "upgrade your system to a new Ubuntu release "
                      "with this hardware."))
                self.controller.abort()

    def _test_and_warn_if_vserver(self):
        """
        upstart and vserver environments are not a good match, warn
        if we find one
        """
        # verver test (LP: #454783), see if there is a init around
        try:
            os.kill(1, 0)
        except:
            logging.warn("no init found")
            res = self._view.askYesNoQuestion(
                _("No init available"),
                _("Your system appears to be a virtualised environment "
                  "without an init daemon, e.g. Linux-VServer. "
                  "Ubuntu 10.04 LTS cannot function within this type of "
                  "environment, requiring an update to your virtual "
                  "machine configuration first.\n\n"
                  "Are you sure you want to continue?"))
            if res == False:
                self.controller.abort()
            self._view.processEvents()

    def _kubuntuDesktopTransition(self):
        """
        check if a key depends of kubuntu-kde4-desktop is installed
        and transition in this case as well
        """
        deps_found = False
        frompkg = "kubuntu-kde4-desktop"
        topkg = "kubuntu-desktop"
        if self.config.getlist(frompkg,"KeyDependencies"):
            deps_found = True
            for pkg in self.config.getlist(frompkg,"KeyDependencies"):
                deps_found &= (self.controller.cache.has_key(pkg) and
                               self.controller.cache[pkg].is_installed)
        if deps_found:
            logging.debug("transitioning %s to %s (via key depends)" % (frompkg, topkg))
            self.controller.cache[topkg].mark_install()

    def _mysqlClusterCheck(self):
        """
        check if ndb clustering is used and do not upgrade mysql
        if it is (LP: #450837)
        """
        logging.debug("_mysqlClusterCheck")
        if (self.controller.cache.has_key("mysql-server") and
            self.controller.cache["mysql-server"].is_installed):
            # taken from the mysql-server-5.1.preinst
            ret = subprocess.call([
                    "egrep", "-q", "-i", "-r",
                    "^[^#]*ndb.connectstring|^[:space:]*\[[:space:]*ndb_mgmd", 
                    "/etc/mysql/"])
            logging.debug("egrep returned %s" % ret)
            # if clustering is used, do not upgrade to 5.1 and 
            # remove mysql-{server,client}
            # metapackage and upgrade the 5.0 packages
            if ret == 0:
                logging.debug("mysql clustering in use, do not upgrade to 5.1")
                for pkg in ("mysql-server", "mysql-client"):
                    self.controller.cache.mark_remove(pkg, "clustering in use")
                    # mark mysql-{server,client}-5.0 as manual install (#453513)
                    depcache = self.controller.cache._depcache
                    for pkg in ["mysql-server-5.0", "mysql-client-5.0"]:
                        if pkg.is_installed and depcache.IsAutoInstalled(pkg._pkg):
                            logging.debug("marking '%s' manual installed" % pkg.name)
                            autoInstDeps = False
                            fromUser = True
                            depcache.Mark_install(pkg._pkg, autoInstDeps, fromUser)
            else:
                self.controller.cache.mark_upgrade("mysql-server", "no clustering in use")

    def _checkArmCPU(self):
        """
        parse /proc/cpuinfo and search for ARMv6 or greater
        """
        logging.debug("checking for ARM CPU version")
        if not os.path.exists("/proc/cpuinfo"):
            logging.error("cannot open /proc/cpuinfo ?!?")
            return False
        cpuinfo = open("/proc/cpuinfo")
        if re.search("^Processor\s*:\s*ARMv[45]", cpuinfo.read(), re.MULTILINE):
            return False
        return True

    def _dealWithLanguageSupportTransition(self):
        """
        In karmic the language-support-translations-* metapackages
        are gone and the direct dependencies will get marked for
        auto removal - mark them as manual instead
        """
        logging.debug("language-support-translations-* transition")
        for pkg in self.controller.cache:
            depcache = self.controller.cache._depcache
            if (pkg.name.startswith("language-support-translations") and
                pkg.is_installed):
                for dp_or in pkg.installedDependencies:
                    for dpname in dp_or.or_dependencies:
                        dp = self.controller.cache[dpname.name]
                        if dp.is_installed and depcache.IsAutoInstalled(dp._pkg):
                            logging.debug("marking '%s' manual installed" % dp.name)
                            autoInstDeps = False
                            fromUser = True
                            depcache.mark_install(dp._pkg, autoInstDeps, fromUser)
                            
    def _checkLanguageSupport(self):
        """
        check if the language support is fully installed and if
        not generate a update-notifier note on next login
        """
        if not os.path.exists("/usr/bin/check-language-support"):
            logging.debug("no check-language-support available")
            return
        p = subprocess.Popen(["check-language-support"],stdout=subprocess.PIPE)
        for pkgname in p.communicate()[0].split():
            if (self.controller.cache.has_key(pkgname) and
                not self.controller.cache[pkgname].is_installed):
                logging.debug("language support package '%s' missing" % pkgname)
                # check if kde/gnome and copy language-selector note
                base = "/usr/share/language-support/"
                target = "/var/lib/update-notifier/user.d"
                for p in ("incomplete-language-support-gnome.note",
                          "incomplete-language-support-qt.note"):
                    if os.path.exists(os.path.join(base,p)):
                        shutil.copy(os.path.join(base,p), target)
                        return

    def _checkAndInstallBroadcom(self):
        """
        check for the 'wl' kernel module and install bcmwl-kernel-source
        if the module is loaded
        """
        logging.debug("checking for 'wl' module")
        if "wl" in lsmod():
            self.controller.cache.mark_install("bcmwl-kernel-source",
                                              "'wl' module found in lsmod")

    def _stopApparmor(self):
        """ /etc/init.d/apparmor stop (see bug #559433)"""
        if os.path.exists("/etc/init.d/apparmor"):
            logging.debug("/etc/init.d/apparmor stop")
            subprocess.call(["/etc/init.d/apparmor","stop"])
    def _stopDocvertConverter(self):
        " /etc/init.d/docvert-converter stop (see bug #450569)"
        if os.path.exists("/etc/init.d/docvert-converter"):
            logging.debug("/etc/init.d/docvert-converter stop")
            subprocess.call(["/etc/init.d/docvert-converter","stop"])
    def _killUpdateNotifier(self):
        "kill update-notifier"
        # kill update-notifier now to suppress reboot required
        if os.path.exists("/usr/bin/killall"):
            logging.debug("killing update-notifier")
            subprocess.call(["killall","-q","update-notifier"])
    def _killKBluetooth(self):
        """killall kblueplugd kbluetooth (riddel requested it)"""
        if os.path.exists("/usr/bin/killall"):
            logging.debug("killing kblueplugd kbluetooth4")
            subprocess.call(["killall", "-q", "kblueplugd", "kbluetooth4"])
    def _killScreensaver(self):
        """killall gnome-screensaver """
        if os.path.exists("/usr/bin/killall"):
            logging.debug("killing gnome-screensaver")
            subprocess.call(["killall", "-q", "gnome-screensaver"])
    def _removeBadMaintainerScripts(self):
        " remove bad/broken maintainer scripts (last resort) "
        # apache: workaround #95325 (edgy->feisty)
        # pango-libthai #103384 (edgy->feisty)
        bad_scripts = ["/var/lib/dpkg/info/apache2-common.prerm",
                       "/var/lib/dpkg/info/pango-libthai.postrm",
                       ]
        for ap in bad_scripts:
            if os.path.exists(ap):
                logging.debug("removing bad script '%s'" % ap)
                os.unlink(ap)

    def _createPycentralPkgRemove(self):
        """
        intrepid->jaunty, create /var/lib/pycentral/pkgremove flag file
        to help python-central so that it removes all preinst links
        on upgrade
        """
        logging.debug("adding pkgremove file")
        if not os.path.exists("/var/lib/pycentral/"):
            os.makedirs("/var/lib/pycentral")
        open("/var/lib/pycentral/pkgremove","w")

    def _removeOldApportCrashes(self):
        " remove old apport crash files "
        try:
            for f in glob.glob("/var/crash/*.crash"):
                logging.debug("removing old crash file '%s'" % f)
                os.unlink(f)
        except Exception, e:
            logging.warning("error during unlink of old crash files (%s)" % e)

    def _cpuHasSSESupport(self, cpuinfo="/proc/cpuinfo"):
        " helper that checks if the given cpu has sse support "
        if not os.path.exists(cpuinfo):
            return False
        for line in open(cpuinfo):
            if line.startswith("flags") and not " sse" in line:
                return False
        return True

    def _usesEvmsInMounts(self):
        " check if evms is used in /proc/mounts "
        logging.debug("running _usesEvmsInMounts")
        for line in open("/proc/mounts"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception:
                logging.error("can't parse line '%s'" % line)
                continue
            if "evms" in device:
                logging.debug("found evms device in line '%s', skipping " % line)
                return True
        return False

    def _checkAndRemoveEvms(self):
        " check if evms is in use and if not, remove it "
        logging.debug("running _checkAndRemoveEvms")
        if self._usesEvmsInMounts():
            return False
        # if not in use, nuke it
        for pkg in ["evms","libevms-2.5","libevms-dev",
                    "evms-ncurses", "evms-ha",
                    "evms-bootdebug",
                    "evms-gui", "evms-cli",
                    "linux-patch-evms"]:
            if self.controller.cache.has_key(pkg) and self.controller.cache[pkg].is_installed:
                self.controller.cache[pkg].mark_delete()
        return True

    def _addRelatimeToFstab(self):
        " add the relatime option to ext2/ext3 filesystems on upgrade "
        logging.debug("_addRelatime")
        replaced = False
        lines = []
        for line in open("/etc/fstab"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            if (("ext2" in fstype or
                 "ext3" in fstype) and 
                (not "noatime" in options) and
                (not "relatime" in options) ):
                logging.debug("adding 'relatime' to line '%s' " % line)
                line = line.replace(options,"%s,relatime" % options)
                logging.debug("replaced line is '%s' " % line)
                replaced=True
            lines.append(line)
        # we have converted a line
        if replaced:
            logging.debug("writing new /etc/fstab")
            f=open("/etc/fstab.intrepid","w")
            f.write("\n".join(lines))
            # add final newline (see LP: #279093)
            f.write("\n")
            f.close()
            os.rename("/etc/fstab.intrepid","/etc/fstab")
        return True
        
    def _ntfsFstabFixup(self, fstab="/etc/fstab"):
        """change PASS 1 to 0 for ntfs entries (#441242)"""
        logging.debug("_ntfsFstabFixup")
        replaced = False
        lines = []
        for line in open(fstab):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, fdump, fpass) = line.split()
            except Exception:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            if ("ntfs" in fstype and fpass == "1"):
                logging.debug("changing PASS for ntfs to 0 for '%s' " % line)
                if line[-1] == "1":
                    line = line[:-1] + "0"
                else:
                    logging.error("unexpected value in line")
                logging.debug("replaced line is '%s' " % line)
                replaced=True
            lines.append(line)
        # we have converted a line
        if replaced:
            suffix = ".jaunty"
            logging.debug("writing new /etc/fstab")
            f=open(fstab + suffix, "w")
            f.write("\n".join(lines))
            # add final newline (see LP: #279093)
            f.write("\n")
            f.close()
            os.rename(fstab+suffix, fstab)
        return True
        

    def _rewriteFstab(self):
        " convert /dev/{hd?,scd0} to /dev/cdrom for the feisty upgrade "
        logging.debug("_rewriteFstab()")
        replaced = 0
        lines = []
        # we have one cdrom to convert
        for line in open("/etc/fstab"):
            line = line.strip()
            if line == '' or line.startswith("#"):
                lines.append(line)
                continue
            try:
                (device, mount_point, fstype, options, a, b) = line.split()
            except Exception:
                logging.error("can't parse line '%s'" % line)
                lines.append(line)
                continue
            # edgy kernel has /dev/cdrom -> /dev/hd?
            # feisty kernel (for a lot of chipsets) /dev/cdrom -> /dev/scd0
            # this breaks static mounting (LP#86424)
            #
            # we convert here to /dev/cdrom only if current /dev/cdrom
            # points to the device in /etc/fstab already. this ensures
            # that we don't break anything or that we get it wrong
            # for systems with two (or more) cdroms. this is ok, because
            # we convert under the old kernel
            if ("iso9660" in fstype and
                device != "/dev/cdrom" and
                os.path.exists("/dev/cdrom") and
                os.path.realpath("/dev/cdrom") == device
                ):
                logging.debug("replacing '%s' " % line)
                line = line.replace(device,"/dev/cdrom")
                logging.debug("replaced line is '%s' " % line)
                replaced += 1
            lines.append(line)
        # we have converted a line (otherwise we would have exited already)
        if replaced > 0:
            logging.debug("writing new /etc/fstab")
            shutil.copy("/etc/fstab","/etc/fstab.edgy")
            f=open("/etc/fstab","w")
            f.write("\n".join(lines))
            # add final newline (see LP: #279093)
            f.write("\n")
            f.close()
        return True

    def _checkAdminGroup(self):
        " check if the current sudo user is in the admin group "
        logging.debug("_checkAdminGroup")
        import grp
        try:
            admin_group = grp.getgrnam("admin").gr_mem
        except KeyError, e:
            logging.warning("System has no admin group (%s)" % e)
            subprocess.call(["addgroup","--system","admin"])
        # double paranoia
        try:
            admin_group = grp.getgrnam("admin").gr_mem
        except KeyError, e:
            logging.warning("adding the admin group failed (%s)" % e)
            return
        # if the current SUDO_USER is not in the admin group
        # we add him - this is no security issue because
        # the user is already root so adding him to the admin group
        # does not change anything
        if (os.environ.has_key("SUDO_USER") and
            not os.environ["SUDO_USER"] in admin_group):
            admin_user = os.environ["SUDO_USER"]
            logging.info("SUDO_USER=%s is not in admin group" % admin_user)
            cmd = ["usermod","-a","-G","admin",admin_user]
            res = subprocess.call(cmd)
            logging.debug("cmd: %s returned %i" % (cmd, res))

    def _checkVideoDriver(self, name):
        " check if the given driver is in use in xorg.conf "
        XORG="/etc/X11/xorg.conf"
        if not os.path.exists(XORG):
            return False
        for line in open(XORG):
            s=line.split("#")[0].strip()
            # check for fglrx driver entry
            if (s.lower().startswith("driver") and
                s.endswith('"%s"' % name)):
                return True
        return False

    def _applyPatches(self, patchdir="./patches"):
        """
        helper that applies the patches in patchdir. the format is
        _path_to_file.md5sum
        
        and it will apply the diff to that file if the md5sum
        matches
        """
        if not os.path.exists(patchdir):
            logging.debug("no patchdir")
            return
        for f in os.listdir(patchdir):
            # skip, not a patch file, they all end with .$md5sum
            if not "." in f:
                logging.debug("skipping '%s' (no '.')" % f)
                continue
            logging.debug("check if patch '%s' needs to be applied" % f)
            (encoded_path, md5sum, result_md5sum) = string.rsplit(f, ".", 2)
            # FIXME: this is not clever and needs quoting support for
            #        filenames with "_" in the name
            path = encoded_path.replace("_","/")
            logging.debug("target for '%s' is '%s' -> '%s'" % (
                    f, encoded_path, path))
            # target does not exist
            if not os.path.exists(path):
                logging.debug("target '%s' does not exist" % path)
                continue
            # check the input md5sum, this is not strictly needed as patch()
            # will verify the result md5sum and discard the result if that
            # does not match but this will remove a misleading error in the 
            # logs
            md5 = hashlib.md5()
            md5.update(open(path).read())
            if md5.hexdigest() == result_md5sum:
                logging.debug("already at target hash, skipping '%s'" % path)
                continue
            elif md5.hexdigest() != md5sum:
                logging.warn("unexpected target md5sum, skipping: '%s'" % path)
                continue
            # patchable, do it
            from DistUpgradePatcher import patch
            try:
                patch(path, os.path.join(patchdir, f), result_md5sum)
                logging.info("applied '%s' successfully" % f)
            except Exception:
                logging.exception("ed failed for '%s'" % f)
                    
    def _supportInModaliases(self, pkgname, lspci=None):
        """ 
        Check if pkgname will work on this hardware

        This helper will check with the modaliasesdir if the given 
        pkg will work on this hardware (or the hardware given
        via the lspci argument)
        """
        # get lspci info (if needed)
        if not lspci:
            lspci = self._get_pci_ids()
        # get pkg
        if (not pkgname in self.controller.cache or
            not self.controller.cache[pkgname].candidate):
            logging.warn("can not find '%s' in cache")
            return False
        pkg = self.controller.cache[pkgname]
        for (module, pciid_list) in self._parse_modaliases_from_pkg_header(pkg.candidate.record):
            for pciid in pciid_list:
                m = re.match("pci:v0000(.+)d0000(.+)sv.*", pciid)
                if m:
                    matchid = "%s:%s" % (m.group(1), m.group(2))
                    if matchid.lower() in lspci:
                        logging.debug("found system pciid '%s' in modaliases" % matchid)
                        return True
        logging.debug("checking for %s support in modaliases but none found" % pkgname)
        return False
                    
    def _parse_modaliases_from_pkg_header(self, pkgrecord):
        """ return a list of (module1, (pciid, ...), (module2, (pciid, ...)))"""
        if not "Modaliases" in pkgrecord:
            return []
        # split the string
        modules = []
        for m in pkgrecord["Modaliases"].split(")"):
            m = m.strip(", ")
            if not m:
                continue
            (module, pciids) = m.split("(")
            modules.append ((module, [x.strip() for x in pciids.split(",")]))
        return modules

    def _kernel386TransitionCheck(self):
        """ test if the current kernel is 386 and if the system is 
            capable of using a generic one instead (#353534)
        """
        logging.debug("_kernel386TransitionCheck")
        # we test first if one of 386 is installed
        # if so, check if the system could also work with -generic
        # (we get that from base-installer) and try to installed
        #  that)
        for pkgname in ["linux-386", "linux-image-386"]:
            if (self.controller.cache.has_key(pkgname) and
                self.controller.cache[pkgname].is_installed):
                working_kernels = self.controller.cache.getKernelsFromBaseInstaller()
                upgrade_to = ["linux-generic", "linux-image-generic"]
                for pkgname in upgrade_to:
                    if pkgname in working_kernels:
                        logging.debug("386 kernel installed, but generic kernel  will work on this machine")
                        if self.controller.cache.mark_install(pkgname, "386 -> generic transition"):
                            return
        

    def _add_extras_repository(self):
        logging.debug("_add_extras_repository")
        cache = self.controller.cache
        if not "ubuntu-extras-keyring" in cache:
            logging.debug("no ubuntu-extras-keyring, no need to add repo")
            return
        if not (cache["ubuntu-extras-keyring"].marked_install or
                cache["ubuntu-extras-keyring"].installed):
            logging.debug("ubuntu-extras-keyring not installed/marked_install")
            return
        try:
            import aptsources.sourceslist
            sources = aptsources.sourceslist.SourcesList()
            for entry in sources:
                if "extras.ubuntu.com" in entry.uri:
                    logging.debug("found extras.ubuntu.com, no need to add it")
                    break
            else:
                logging.info("no extras.ubuntu.com, adding it to sources.list")
                sources.add("deb","http://extras.ubuntu.com/ubuntu",
                            self.controller.toDist, ["main"],
                            "Third party developers repository")
                sources.save()
        except:
            logging.exception("error adding extras.ubuntu.com")

    def _gutenprint_fixup(self):
        """ foomatic-db-gutenprint get removed during the upgrade,
            replace it with the compressed ijsgutenprint-ppds
            (context is foomatic-db vs foomatic-db-compressed-ppds)
        """
        try:
            cache = self.controller.cache
            if ("foomatic-db-gutenprint" in cache and
                cache["foomatic-db-gutenprint"].marked_delete and
                "ijsgutenprint-ppds" in cache):
                logging.info("installing ijsgutenprint-ppds")
                cache.mark_install(
                    "ijsgutenprint-ppds",
                    "foomatic-db-gutenprint -> ijsgutenprint-ppds rule")
        except:
            logging.exception("_gutenprint_fixup failed")

    def _enable_multiarch(self, foreign_arch="i386"):
        """ enable multiarch via /etc/dpkg/dpkg.cfg.d/multiarch """
        cfg = "/etc/dpkg/dpkg.cfg.d/multiarch"
        if not os.path.exists(cfg):
            try:
                os.makedirs("/etc/dpkg/dpkg.cfg.d/")
            except OSError:
                pass
            open(cfg, "w").write("foreign-architecture %s\n" % foreign_arch)

    def _add_kdegames_card_extra_if_installed(self):
        """ test if kdegames-card-data is installed and if so,
            add kdegames-card-data-extra so that users do not 
            loose functionality (LP: #745396)
        """
        try:
            cache = self.controller.cache
            if not ("kdegames-card-data" in cache or
                    "kdegames-card-data-extra" in cache):
                return
            if (cache["kdegames-card-data"].is_installed or
                cache["kdegames-card-data"].marked_install):
                cache.mark_install(
                    "kdegames-card-data-extra",
                    "kdegames-card-data -> k-c-d-extra transition")
        except:
            logging.exception("_add_kdegames_card_extra_if_installed failed")
        
    def ensure_recommends_are_installed_on_desktops(self):
        """ ensure that on a desktop install recommends are installed 
            (LP: #759262)
        """
        import apt
        if not self.controller.serverMode:
            if not apt.apt_pkg.config.find_b("Apt::Install-Recommends"):
                logging.warn("Apt::Install-Recommends was disabled, enabling it just for the upgrade")
                apt.apt_pkg.config.set("Apt::Install-Recommends", "1")

