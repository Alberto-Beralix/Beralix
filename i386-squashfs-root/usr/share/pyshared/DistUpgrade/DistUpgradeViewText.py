# DistUpgradeViewText.py 
#  
#  Copyright (c) 2004-2006 Canonical
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

import sys
import logging
import subprocess

import apt
import os

from DistUpgradeView import DistUpgradeView, InstallProgress, FetchProgress
import apt.progress

import gettext
from DistUpgradeGettext import gettext as _
from utils import  twrap

class TextFetchProgress(FetchProgress, apt.progress.text.AcquireProgress):
    def __init__(self):
        apt.progress.text.AcquireProgress.__init__(self)
        FetchProgress.__init__(self)
    def pulse(self, owner):
        apt.progress.text.AcquireProgress.pulse(self, owner)
        FetchProgress.pulse(self, owner)
        return True

class TextCdromProgressAdapter(apt.progress.base.CdromProgress):
    """ Report the cdrom add progress  """
    def update(self, text, step):
        """ update is called regularly so that the gui can be redrawn """
        if text:
          print "%s (%f)" % (text, step/float(self.totalSteps)*100)
    def askCdromName(self):
        return (False, "")
    def changeCdrom(self):
        return False


class DistUpgradeViewText(DistUpgradeView):
    " text frontend of the distUpgrade tool "
    def __init__(self, datadir=None, logdir=None):
        # indicate that we benefit from using gnu screen
        self.needs_screen = True
        # its important to have a debconf frontend for
        # packages like "quagga"
        if not os.environ.has_key("DEBIAN_FRONTEND"):
            os.environ["DEBIAN_FRONTEND"] = "dialog"
        if not datadir:
          localedir=os.path.join(os.getcwd(),"mo")
        else:
          localedir="/usr/share/locale/update-manager"

        try:
          gettext.bindtextdomain("update-manager", localedir)
          gettext.textdomain("update-manager")
        except Exception, e:
          logging.warning("Error setting locales (%s)" % e)
        
        self.last_step = 0 # keep a record of the latest step
        self._opCacheProgress = apt.progress.text.OpProgress()
        self._fetchProgress = TextFetchProgress()
        self._cdromProgress = TextCdromProgressAdapter()
        self._installProgress = InstallProgress()
        sys.excepthook = self._handleException
        #self._process_events_tick = 0

    def _handleException(self, type, value, tb):
        import traceback
        print
        lines = traceback.format_exception(type, value, tb)
        logging.error("not handled exception:\n%s" % "\n".join(lines))
        self.error(_("A fatal error occurred"),
                   _("Please report this as a bug and include the "
                     "files /var/log/dist-upgrade/main.log and "
                     "/var/log/dist-upgrade/apt.log "
                     "in your report. The upgrade has aborted.\n"
                     "Your original sources.list was saved in "
                     "/etc/apt/sources.list.distUpgrade."),
                   "\n".join(lines))
        sys.exit(1)

    def getFetchProgress(self):
        return self._fetchProgress
    def getInstallProgress(self, cache):
        self._installProgress._cache = cache
        return self._installProgress
    def getOpCacheProgress(self):
        return self._opCacheProgress
    def getCdromProgress(self):
        return self._cdromProgress
    def updateStatus(self, msg):
      print
      print msg
      sys.stdout.flush()
    def abort(self):
      print
      print _("Aborting")
    def setStep(self, step):
      self.last_step = step
    def showDemotions(self, summary, msg, demotions):
        self.information(summary, msg, 
                         _("Demoted:\n")+twrap(", ".join(demotions)))
    def information(self, summary, msg, extended_msg=None):
      print
      print twrap(summary)
      print twrap(msg)
      if extended_msg:
        print twrap(extended_msg)
      print _("To continue please press [ENTER]")
      sys.stdin.readline()
    def error(self, summary, msg, extended_msg=None):
      print
      print twrap(summary)
      print twrap(msg)
      if extended_msg:
        print twrap(extended_msg)
      return False
    def showInPager(self, output):
      " helper to show output in a pager"
      for pager in ["/usr/bin/sensible-pager", "/bin/more"]:
          if os.path.exists(pager):
              p = subprocess.Popen([pager,"-"],stdin=subprocess.PIPE)
              p.stdin.write(output)
              p.stdin.close()
              p.wait()
              return
      # if we don't have a pager, just print
      print output

    def confirmChanges(self, summary, changes, demotions, downloadSize,
                       actions=None, removal_bold=True):
      DistUpgradeView.confirmChanges(self, summary, changes, demotions, 
                                     downloadSize, actions)
      print
      print twrap(summary)
      print twrap(self.confirmChangesMessage)
      print " %s %s" % (_("Continue [yN] "), _("Details [d]")),
      while True:
        res = sys.stdin.readline()
        # TRANSLATORS: the "y" is "yes"
        if res.strip().lower().startswith(_("y")):
          return True
        # TRANSLATORS: the "n" is "no"
        elif res.strip().lower().startswith(_("n")):
          return False
        # TRANSLATORS: the "d" is "details"
        elif res.strip().lower().startswith(_("d")):
          output = ""
          if len(self.demotions) > 0:
              output += "\n"  
              output += twrap(
                  _("No longer supported: %s\n") % " ".join([p.name for p in self.demotions]),
                  subsequent_indent='  ')
          if len(self.toRemove) > 0:
              output += "\n"  
              output += twrap(
                  _("Remove: %s\n") % " ".join([p.name for p in self.toRemove]),
                  subsequent_indent='  ')
          if len(self.toRemoveAuto) > 0:
              output += twrap(
                  _("Remove (was auto installed) %s") % " ".join([p.name for p in self.toRemoveAuto]), 
                  subsequent_indent='  ')
              output += "\n"
          if len(self.toInstall) > 0:
              output += "\n"
              output += twrap(
                  _("Install: %s\n") % " ".join([p.name for p in self.toInstall]),
                  subsequent_indent='  ')
          if len(self.toUpgrade) > 0:
              output += "\n"  
              output += twrap(
                  _("Upgrade: %s\n") % " ".join([p.name for p in self.toUpgrade]),
                  subsequent_indent='  ')
          self.showInPager(output)
        print "%s %s" % (_("Continue [yN] "), _("Details [d]")),

    def askYesNoQuestion(self, summary, msg, default='No'):
      print
      print twrap(summary)
      print twrap(msg)
      if default == 'No':
          print _("Continue [yN] "),
          res = sys.stdin.readline()
          # TRANSLATORS: first letter of a positive (yes) answer
          if res.strip().lower().startswith(_("y")):
              return True
          return False
      else:
          print _("Continue [Yn] "),
          res = sys.stdin.readline()
          # TRANSLATORS: first letter of a negative (no) answer
          if res.strip().lower().startswith(_("n")):
              return False
          return True

# FIXME: when we need this most the resolver is writing debug logs
#        and we redirect stdout/stderr    
#    def processEvents(self):
#      #time.sleep(0.2)
#      anim = [".","o","O","o"]
#      anim = ["\\","|","/","-","\\","|","/","-"]
#      self._process_events_tick += 1
#      if self._process_events_tick >= len(anim):
#          self._process_events_tick = 0
#      sys.stdout.write("[%s]" % anim[self._process_events_tick])
#      sys.stdout.flush()

    def confirmRestart(self):
      return self.askYesNoQuestion(_("Restart required"),
                                   _("To finish the upgrade, a restart is "
                                     "required.\n"
                                     "If you select 'y' the system "
                                     "will be restarted."), default='No')


if __name__ == "__main__":
  view = DistUpgradeViewText()

  #while True:
  #    view.processEvents()
  
  print twrap("89 packages are going to be upgraded.\nYou have to download a total of 82.7M.\nThis download will take about 10 minutes with a 1Mbit DSL connection and about 3 hours 12 minutes with a 56k modem.", subsequent_indent=" ")
  #sys.exit(1)

  view = DistUpgradeViewText()
  print view.askYesNoQuestion("hello", "Icecream?", "No")
  print view.askYesNoQuestion("hello", "Icecream?", "Yes")
  

  #view.confirmChangesMessage = "89 packages are going to be upgraded.\n You have to download a total of 82.7M.\n This download will take about 10 minutes with a 1Mbit DSL connection and about 3 hours 12 minutes with a 56k modem."
  #view.confirmChanges("xx",[], 100)
  sys.exit(0)

  view.confirmRestart()

  cache = apt.Cache()
  fp = view.getFetchProgress()
  ip = view.getInstallProgress(cache)


  for pkg in sys.argv[1:]:
    cache[pkg].mark_install()
  cache.commit(fp,ip)
  
  sys.exit(0)
  view.getTerminal().call(["dpkg","--configure","-a"])
  #view.getTerminal().call(["ls","-R","/usr"])
  view.error("short","long",
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             "asfds afsdj af asdf asdf asf dsa fadsf asdf as fasf sextended\n"
             )
  view.confirmChanges("xx",[], 100)
  print view.askYesNoQuestion("hello", "Icecream?")
