# DistUpgradeViewKDE.py 
#  
#  Copyright (c) 2007 Canonical Ltd
#  
#  Author: Jonathan Riddell <jriddell@ubuntu.com>
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

import sys
import logging
import time
import subprocess
import traceback
import tempfile

import apt
import apt_pkg
import os
import shutil

import pty

from DistUpgradeApport import *

from DistUpgradeView import DistUpgradeView, FuzzyTimeToStr, InstallProgress, FetchProgress

import select
import gettext
from DistUpgradeGettext import gettext as gett

def _(str):
    return unicode(gett(str), 'UTF-8')

def utf8(str):
  if isinstance(str, unicode):
      return str
  return unicode(str, 'UTF-8')

def loadUi(file, parent):
    if os.path.exists(file):
        uic.loadUi(file, parent)
    else:
        #FIXME find file
        print "error, can't find file: " + file

class DumbTerminal(QTextEdit):
    """ A very dumb terminal """
    def __init__(self, installProgress, parent_frame):
        " really dumb terminal with simple editing support "
        QTextEdit.__init__(self, "", parent_frame)
        self.installProgress = installProgress
        self.setFontFamily("Monospace")
        self.setFontPointSize(8)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setUndoRedoEnabled(False)
        self.setOverwriteMode(True)
        self._block = False
        #self.connect(self, SIGNAL("cursorPositionChanged()"), 
        #             self.onCursorPositionChanged)

    def fork(self):
        """pty voodoo"""
        (self.child_pid, self.installProgress.master_fd) = pty.fork()
        if self.child_pid == 0:
            os.environ["TERM"] = "dumb"
        return self.child_pid

    def update_interface(self):
        (rlist, wlist, xlist) = select.select([self.installProgress.master_fd],[],[], 0)
        if len(rlist) > 0:
            line = os.read(self.installProgress.master_fd, 255)
            self.insertWithTermCodes(utf8(line))
        QApplication.processEvents()

    def insertWithTermCodes(self, text):
        """ support basic terminal codes """
        display_text = ""
        for c in text:
            # \b - backspace - this seems to comes as "^H" now ??!
            if ord(c) == 8:
                self.insertPlainText(display_text)
                self.textCursor().deletePreviousChar()
                display_text=""
            # \r - is filtered out
            elif c == chr(13):
                pass
            # \a - bell - ignore for now
            elif c == chr(7):
                pass
            else:
                display_text += c
        self.insertPlainText(display_text)

    def keyPressEvent(self, ev):
        """ send (ascii) key events to the pty """
        # no master_fd yet
        if not hasattr(self.installProgress, "master_fd"):
            return
        # special handling for backspace
        if ev.key() == Qt.Key_Backspace:
            #print "sent backspace"
            os.write(self.installProgress.master_fd, chr(8))
            return
        # do nothing for events like "shift" 
        if not ev.text():
            return
        # now sent the key event to the termianl as utf-8
        os.write(self.installProgress.master_fd, ev.text().toUtf8())

    def onCursorPositionChanged(self):
        """ helper that ensures that the cursor is always at the end """
        if self._block:
            return
        # block signals so that we do not run into a recursion
        self._block = True
        self.moveCursor(QTextCursor.End)
        self._block = False

class KDECdromProgressAdapter(apt.progress.CdromProgress):
    """ Report the cdrom add progress """
    def __init__(self, parent):
        self.status = parent.window_main.label_status
        self.progressbar = parent.window_main.progressbar_cache
        self.parent = parent

    def update(self, text, step):
        """ update is called regularly so that the gui can be redrawn """
        if text:
          self.status.setText(text)
        self.progressbar.setValue(step/float(self.totalSteps))
        QApplication.processEvents()

    def askCdromName(self):
        return (False, "")

    def changeCdrom(self):
        return False

class KDEOpProgress(apt.progress.base.OpProgress):
  """ methods on the progress bar """
  def __init__(self, progressbar, progressbar_label):
      self.progressbar = progressbar
      self.progressbar_label = progressbar_label
      #self.progressbar.set_pulse_step(0.01)
      #self.progressbar.pulse()

  def update(self, percent):
      #if percent > 99:
      #    self.progressbar.set_fraction(1)
      #else:
      #    self.progressbar.pulse()
      #self.progressbar.set_fraction(percent/100.0)
      self.progressbar.setValue(percent)
      QApplication.processEvents()

  def done(self):
      self.progressbar_label.setText("")

class KDEFetchProgressAdapter(FetchProgress):
    """ methods for updating the progress bar while fetching packages """
    # FIXME: we really should have some sort of "we are at step"
    # xy in the gui
    # FIXME2: we need to thing about mediaCheck here too
    def __init__(self, parent):
        FetchProgress.__init__(self)
        # if this is set to false the download will cancel
        self.status = parent.window_main.label_status
        self.progress = parent.window_main.progressbar_cache
        self.parent = parent

    def media_change(self, medium, drive):
      msg = _("Please insert '%s' into the drive '%s'") % (medium,drive)
      change = QMessageBox.question(self.parent.window_main, _("Media Change"), msg, QMessageBox.Ok, QMessageBox.Cancel)
      if change == QMessageBox.Ok:
        return True
      return False

    def start(self):
        FetchProgress.start(self)
        #self.progress.show()
        self.progress.setValue(0)
        self.status.show()

    def stop(self):
        self.parent.window_main.progress_text.setText("  ")
        self.status.setText(_("Fetching is complete"))

    def pulse(self, owner):
        """ we don't have a mainloop in this application, we just call processEvents here and elsewhere"""
        # FIXME: move the status_str and progress_str into python-apt
        # (python-apt need i18n first for this)
        FetchProgress.pulse(self, owner)
        self.progress.setValue(self.percent)
        current_item = self.current_items + 1
        if current_item > self.total_items:
            current_item = self.total_items

        if self.current_cps > 0:
            self.status.setText(_("Fetching file %li of %li at %sB/s") % (current_item, self.total_items, apt_pkg.size_to_str(self.current_cps)))
            self.parent.window_main.progress_text.setText("<i>" + _("About %s remaining") % unicode(FuzzyTimeToStr(self.eta), 'utf-8') + "</i>")
        else:
            self.status.setText(_("Fetching file %li of %li") % (current_item, self.total_items))
            self.parent.window_main.progress_text.setText("  ")

        QApplication.processEvents()
        return True

class KDEInstallProgressAdapter(InstallProgress):
    """methods for updating the progress bar while installing packages"""
    # timeout with no status change when the terminal is expanded
    # automatically
    TIMEOUT_TERMINAL_ACTIVITY = 240

    def __init__(self,parent):
        InstallProgress.__init__(self)
        self._cache = None
        self.label_status = parent.window_main.label_status
        self.progress = parent.window_main.progressbar_cache
        self.progress_text = parent.window_main.progress_text
        self.parent = parent
        try:
            self._terminal_log = open("/var/log/dist-upgrade/term.log","w")
        except Exception, e:
            # if something goes wrong (permission denied etc), use stdout
            logging.error("Can not open terminal log: '%s'" % e)
            self._terminal_log = sys.stdout
        # some options for dpkg to make it die less easily
        apt_pkg.config.set("DPkg::StopOnError","False")

    def start_update(self):
        InstallProgress.start_update(self)
        self.finished = False
        # FIXME: add support for the timeout
        # of the terminal (to display something useful then)
        # -> longer term, move this code into python-apt 
        self.label_status.setText(_("Applying changes"))
        self.progress.setValue(0)
        self.progress_text.setText(" ")
        # do a bit of time-keeping
        self.start_time = 0.0
        self.time_ui = 0.0
        self.last_activity = 0.0
        self.parent.window_main.showTerminalButton.setEnabled(True)

    def error(self, pkg, errormsg):
        InstallProgress.error(self, pkg, errormsg)
        logging.error("got an error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
        # we do not report followup errors from earlier failures
        if gettext.dgettext('dpkg', "dependency problems - leaving unconfigured") in errormsg:
          return False
        summary = _("Could not install '%s'") % pkg
        msg = _("The upgrade will continue but the '%s' package may not "
                "be in a working state. Please consider submitting a "
                "bug report about it.") % pkg
        msg = "<big><b>%s</b></big><br />%s" % (summary, msg)

        dialogue = QDialog(self.parent.window_main)
        loadUi("dialog_error.ui", dialogue)
        self.parent.translate_widget_children(dialogue)
        dialogue.label_error.setText(utf8(msg))
        if errormsg != None:
            dialogue.textview_error.setText(utf8(errormsg))
            dialogue.textview_error.show()
        else:
            dialogue.textview_error.hide()
        dialogue.connect(dialogue.button_bugreport, SIGNAL("clicked()"), self.parent.reportBug)
        dialogue.exec_()

    def conffile(self, current, new):
        """ask question in case conffile has been changed by user"""
        logging.debug("got a conffile-prompt from dpkg for file: '%s'" % current)
        start = time.time()
        prim = _("Replace the customized configuration file\n'%s'?") % current
        sec = _("You will lose any changes you have made to this "
                "configuration file if you choose to replace it with "
                "a newer version.")
        markup = "<span weight=\"bold\" size=\"larger\">%s </span> \n\n%s" % (prim, sec)
        self.confDialogue = QDialog(self.parent.window_main)
        loadUi("dialog_conffile.ui", self.confDialogue)
        self.confDialogue.label_conffile.setText(markup)
        self.confDialogue.textview_conffile.hide()
        #FIXME, below to be tested
        #self.confDialogue.resize(self.confDialogue.minimumSizeHint())
        self.confDialogue.connect(self.confDialogue.show_difference_button, SIGNAL("clicked()"), self.showConffile)

        # workaround silly dpkg 
        if not os.path.exists(current):
          current = current+".dpkg-dist"

        # now get the diff
        if os.path.exists("/usr/bin/diff"):
          cmd = ["/usr/bin/diff", "-u", current, new]
          diff = utf8(subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0])
          self.confDialogue.textview_conffile.setText(diff)
        else:
          self.confDialogue.textview_conffile.setText(_("The 'diff' command was not found"))
        result = self.confDialogue.exec_()
        self.time_ui += time.time() - start
        # if replace, send this to the terminal
        if result == QDialog.Accepted:
            os.write(self.master_fd, "y\n")
        else:
            os.write(self.master_fd, "n\n")

    def showConffile(self):
        if self.confDialogue.textview_conffile.isVisible():
            self.confDialogue.textview_conffile.hide()
            self.confDialogue.show_difference_button.setText(_("Show Difference >>>"))
        else:
            self.confDialogue.textview_conffile.show()
            self.confDialogue.show_difference_button.setText(_("<<< Hide Difference"))

    def fork(self):
        """pty voodoo"""
        (self.child_pid, self.master_fd) = pty.fork()
        if self.child_pid == 0:
            os.environ["TERM"] = "dumb"
            if (not os.environ.has_key("DEBIAN_FRONTEND") or
                os.environ["DEBIAN_FRONTEND"] == "kde"):
                os.environ["DEBIAN_FRONTEND"] = "noninteractive"
            os.environ["APT_LISTCHANGES_FRONTEND"] = "none"
        logging.debug(" fork pid is: %s" % self.child_pid)
        return self.child_pid

    def status_change(self, pkg, percent, status):
        """update progress bar and label"""
        # start the timer when the first package changes its status
        if self.start_time == 0.0:
          #print "setting start time to %s" % self.start_time
          self.start_time = time.time()
        self.progress.setValue(self.percent)
        self.label_status.setText(unicode(status.strip(), 'UTF-8'))
        # start showing when we gathered some data
        if percent > 1.0:
          self.last_activity = time.time()
          self.activity_timeout_reported = False
          delta = self.last_activity - self.start_time
          # time wasted in conffile questions (or other ui activity)
          delta -= self.time_ui
          time_per_percent = (float(delta)/percent)
          eta = (100.0 - self.percent) * time_per_percent
          # only show if we have some sensible data (60sec < eta < 2days)
          if eta > 61.0 and eta < (60*60*24*2):
            self.progress_text.setText(_("About %s remaining") % FuzzyTimeToStr(eta))
          else:
            self.progress_text.setText(" ")

    def finish_update(self):
        self.label_status.setText("")

    def update_interface(self):
        """
        no mainloop in this application, just call processEvents lots here
        it's also important to sleep for a minimum amount of time
        """
        # log the output of dpkg (on the master_fd) to the terminal log
        while True:
            try:
                (rlist, wlist, xlist) = select.select([self.master_fd],[],[], 0)
                if len(rlist) > 0:
                    line = os.read(self.master_fd, 255)
                    self._terminal_log.write(line)
                    self.parent.terminal_text.insertWithTermCodes(utf8(line))
                else:
                    break
            except Exception, e:
                print e
                logging.debug("error reading from self.master_fd '%s'" % e)
                break

        # now update the GUI
        try:
          InstallProgress.update_interface(self)
        except ValueError, e:
          logging.error("got ValueError from InstallProgress.update_interface. Line was '%s' (%s)" % (self.read, e))
          # reset self.read so that it can continue reading and does not loop
          self.read = ""
        # check about terminal activity
        if self.last_activity > 0 and \
           (self.last_activity + self.TIMEOUT_TERMINAL_ACTIVITY) < time.time():
          if not self.activity_timeout_reported:
            #FIXME bug 95465, I can't recreate this, so here's a hacky fix
            try:
                logging.warning("no activity on terminal for %s seconds (%s)" % (self.TIMEOUT_TERMINAL_ACTIVITY, self.label_status.text()))
            except UnicodeEncodeError:
                logging.warning("no activity on terminal for %s seconds" % (self.TIMEOUT_TERMINAL_ACTIVITY))
            self.activity_timeout_reported = True
          self.parent.window_main.konsole_frame.show()
        QApplication.processEvents()
        time.sleep(0.02)

    def wait_child(self):
        while True:
            self.update_interface()
            (pid, res) = os.waitpid(self.child_pid,os.WNOHANG)
            if pid == self.child_pid:
                break
        # we need the full status here (not just WEXITSTATUS)
        return res

# inherit from the class created in window_main.ui
# to add the handler for closing the window
class UpgraderMainWindow(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        #uic.loadUi("window_main.ui", self)
        loadUi("window_main.ui", self)

    def setParent(self, parentRef):
        self.parent = parentRef

    def closeEvent(self, event):
        close = self.parent.on_window_main_delete_event()
        if close:
            event.accept()
        else:
            event.ignore()

class DistUpgradeViewKDE(DistUpgradeView):
    """KDE frontend of the distUpgrade tool"""
    def __init__(self, datadir=None, logdir=None):
        DistUpgradeView.__init__(self)
        # silence the PyQt4 logger
        logger = logging.getLogger("PyQt4")
        logger.setLevel(logging.INFO)
        if not datadir:
          localedir=os.path.join(os.getcwd(),"mo")
        else:
          localedir="/usr/share/locale/update-manager"

        # FIXME: i18n must be somewhere relative do this dir
        try:
          gettext.bindtextdomain("update-manager", localedir)
          gettext.textdomain("update-manager")
        except Exception, e:
          logging.warning("Error setting locales (%s)" % e)

        #about = KAboutData("adept_manager","Upgrader","0.1","Dist Upgrade Tool for Kubuntu",KAboutData.License_GPL,"(c) 2007 Canonical Ltd",
        #"http://wiki.kubuntu.org/KubuntuUpdateManager", "jriddell@ubuntu.com")
        #about.addAuthor("Jonathan Riddell", None,"jriddell@ubuntu.com")
        #about.addAuthor("Michael Vogt", None,"michael.vogt@ubuntu.com")
        #KCmdLineArgs.init(["./dist-upgrade.py"],about)

        # we test for DISPLAY here, QApplication does not throw a 
        # exception when run without DISPLAY but dies instead
        if not "DISPLAY" in os.environ:
            raise Exception, "No DISPLAY in os.environ found"
        self.app = QApplication(["update-manager"])

        if os.path.exists("/usr/share/icons/oxygen/48x48/apps/system-software-update.png"):
            messageIcon = QPixmap("/usr/share/icons/oxygen/48x48/apps/system-software-update.png")
        else:
            messageIcon = QPixmap("/usr/share/icons/hicolor/48x48/apps/adept_manager.png")
        self.app.setWindowIcon(QIcon(messageIcon))

        self.window_main = UpgraderMainWindow()
        self.window_main.setParent(self)
        self.window_main.show()

        self.prev_step = 0 # keep a record of the latest step

        self._opCacheProgress = KDEOpProgress(self.window_main.progressbar_cache, self.window_main.progress_text)
        self._fetchProgress = KDEFetchProgressAdapter(self)
        self._cdromProgress = KDECdromProgressAdapter(self)

        self._installProgress = KDEInstallProgressAdapter(self)

        # reasonable fault handler
        sys.excepthook = self._handleException

        self.window_main.showTerminalButton.setEnabled(False)
        self.app.connect(self.window_main.showTerminalButton, SIGNAL("clicked()"), self.showTerminal)

        #kdesu requires us to copy the xauthority file before it removes it when Adept is killed
        copyXauth = tempfile.mktemp("", "adept")
        if 'XAUTHORITY' in os.environ and os.environ['XAUTHORITY'] != copyXauth:
            shutil.copy(os.environ['XAUTHORITY'], copyXauth)
            os.environ["XAUTHORITY"] = copyXauth

        # Note that with kdesudo this needs --nonewdcop
        ## create a new DCOP-Client:
        #client = DCOPClient()
        ## connect the client to the local DCOP-server:
        #client.attach()

        #for qcstring_app in client.registeredApplications():
        #    app = str(qcstring_app)
        #    if app.startswith("adept"): 
        #        adept = DCOPApp(qcstring_app, client)
        #        adeptInterface = adept.object("MainApplication-Interface")
        #        adeptInterface.quit()

        # This works just as well
        subprocess.call(["killall", "adept_manager"])
        subprocess.call(["killall", "adept_updater"])

        # init gettext
        gettext.bindtextdomain("update-manager",localedir)
        gettext.textdomain("update-manager")
        self.translate_widget_children()
        self.window_main.label_title.setText(self.window_main.label_title.text().replace("Ubuntu", "Kubuntu"))

        # setup terminal text in hidden by default spot
        self.window_main.konsole_frame.hide()
        self.konsole_frame_layout = QHBoxLayout(self.window_main.konsole_frame)
        self.window_main.konsole_frame.setMinimumSize(600, 400)
        self.terminal_text = DumbTerminal(self._installProgress, self.window_main.konsole_frame)
        self.konsole_frame_layout.addWidget(self.terminal_text)
        self.terminal_text.show()

        # for some reason we need to start the main loop to get everything displayed
        # this app mostly works with processEvents but run main loop briefly to keep it happily displaying all widgets
        QTimer.singleShot(10, self.exitMainLoop)
        self.app.exec_()

    def exitMainLoop(self):
        print "exitMainLoop"
        self.app.exit()

    def translate_widget_children(self, parentWidget=None):
        if parentWidget == None:
            parentWidget = self.window_main
        if isinstance(parentWidget, QDialog) or isinstance(parentWidget, QWidget):
            if str(parentWidget.windowTitle()) == "Error":
                parentWidget.setWindowTitle( gettext.dgettext("kdelibs", "Error"))
            else:
                parentWidget.setWindowTitle(_( str(parentWidget.windowTitle()) ))

        if parentWidget.children() != None:
            for widget in parentWidget.children():
                self.translate_widget(widget)
                self.translate_widget_children(widget)

    def translate_widget(self, widget):
        if isinstance(widget, QLabel) or isinstance(widget, QPushButton):
            if str(widget.text()) == "&Cancel":
                widget.setText(unicode(gettext.dgettext("kdelibs", "&Cancel"), 'UTF-8'))
            elif str(widget.text()) == "&Close":
                widget.setText(unicode(gettext.dgettext("kdelibs", "&Close"), 'UTF-8'))
            elif str(widget.text()) != "":
                widget.setText( _(str(widget.text())).replace("_", "&") )

    def _handleException(self, exctype, excvalue, exctb):
        """Crash handler."""

        if (issubclass(exctype, KeyboardInterrupt) or
            issubclass(exctype, SystemExit)):
            return

        # we handle the exception here, hand it to apport and run the
        # apport gui manually after it because we kill u-m during the upgrade
        # to prevent it from popping up for reboot notifications or FF restart
        # notifications or somesuch
        lines = traceback.format_exception(exctype, excvalue, exctb)
        logging.error("not handled exception in KDE frontend:\n%s" % "\n".join(lines))
        # we can't be sure that apport will run in the middle of a upgrade
        # so we still show a error message here
        apport_crash(exctype, excvalue, exctb)
        if not run_apport():
            tbtext = ''.join(traceback.format_exception(exctype, excvalue, exctb))
            dialog = QDialog(self.window_main)
            loadUi("dialog_error.ui", dialog)
            self.translate_widget_children(self.dialog)
            #FIXME make URL work
            #dialog.connect(dialog.beastie_url, SIGNAL("leftClickedURL(const QString&)"), self.openURL)
            dialog.crash_detail.setText(tbtext)
            dialog.exec_()
        sys.exit(1)

    def openURL(self, url):
        """start konqueror"""
        #need to run this else kdesu can't run Konqueror
        #subprocess.call(['su', 'ubuntu', 'xhost', '+localhost'])
        QDesktopServices.openUrl(QUrl(url))

    def reportBug(self):
        """start konqueror"""
        #need to run this else kdesu can't run Konqueror
        #subprocess.call(['su', 'ubuntu', 'xhost', '+localhost'])
        QDesktopServices.openUrl(QUrl("https://launchpad.net/ubuntu/+source/update-manager/+filebug"))

    def showTerminal(self):
        if self.window_main.konsole_frame.isVisible():
            self.window_main.konsole_frame.hide()
            self.window_main.showTerminalButton.setText(_("Show Terminal >>>"))
        else:
            self.window_main.konsole_frame.show()
            self.window_main.showTerminalButton.setText(_("<<< Hide Terminal"))
        self.window_main.resize(self.window_main.sizeHint())

    def getFetchProgress(self):
        return self._fetchProgress

    def getInstallProgress(self, cache):
        self._installProgress._cache = cache
        return self._installProgress

    def getOpCacheProgress(self):
        return self._opCacheProgress

    def getCdromProgress(self):
        return self._cdromProgress

    def update_status(self, msg):
        self.window_main.label_status.setText(utf8(msg))

    def hideStep(self, step):
        image = getattr(self.window_main,"image_step%i" % step)
        label = getattr(self.window_main,"label_step%i" % step)
        image.hide()
        label.hide()

    def abort(self):
        step = self.prev_step
        if step > 0:
            image = getattr(self.window_main,"image_step%i" % step)
            if os.path.exists("/usr/share/icons/oxygen/16x16/actions/dialog-cancel.png"):
                cancelIcon = QPixmap("/usr/share/icons/oxygen/16x16/actions/dialog-cancel.png")
            elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/16x16/actions/dialog-cancel.png"):
                cancelIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/16x16/actions/dialog-cancel.png")
            else:
                cancelIcon = QPixmap("/usr/share/icons/crystalsvg/16x16/actions/cancel.png")
            image.setPixmap(cancelIcon)
            image.show()

    def setStep(self, step):
        if os.path.exists("/usr/share/icons/oxygen/16x16/actions/dialog-ok.png"):
            okIcon = QPixmap("/usr/share/icons/oxygen/16x16/actions/dialog-ok.png")
        elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/16x16/actions/dialog-ok.png"):
            okIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/16x16/actions/dialog-ok.png")
        else:
            okIcon = QPixmap("/usr/share/icons/crystalsvg/16x16/actions/ok.png")

        if os.path.exists("/usr/share/icons/oxygen/16x16/actions/arrow-right.png"):
            arrowIcon = QPixmap("/usr/share/icons/oxygen/16x16/actions/arrow-right.png")
        elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/16x16/actions/arrow-right.png"):
            arrowIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/16x16/actions/arrow-right.png")
        else:
            arrowIcon = QPixmap("/usr/share/icons/crystalsvg/16x16/actions/1rightarrow.png")

        if self.prev_step:
            image = getattr(self.window_main,"image_step%i" % self.prev_step)
            label = getattr(self.window_main,"label_step%i" % self.prev_step)
            image.setPixmap(okIcon)
            image.show()
            ##arrow.hide()
        self.prev_step = step
        # show the an arrow for the current step and make the label bold
        image = getattr(self.window_main,"image_step%i" % step)
        label = getattr(self.window_main,"label_step%i" % step)
        image.setPixmap(arrowIcon)
        image.show()
        label.setText("<b>" + label.text() + "</b>")

    def information(self, summary, msg, extended_msg=None):
        msg = "<big><b>%s</b></big><br />%s" % (summary,msg)

        dialogue = QDialog(self.window_main)
        loadUi("dialog_error.ui", dialogue)
        self.translate_widget_children(dialogue)
        dialogue.label_error.setText(utf8(msg))
        if extended_msg != None:
            dialogue.textview_error.setText(utf8(extended_msg))
            dialogue.textview_error.show()
        else:
            dialogue.textview_error.hide()
        dialogue.button_bugreport.hide()
        dialogue.setWindowTitle(_("Information"))

        if os.path.exists("/usr/share/icons/oxygen/48x48/status/dialog-information.png"):
            messageIcon = QPixmap("/usr/share/icons/oxygen/48x48/status/dialog-information.png")
        elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-information.png"):
            messageIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-information.png")
        else:
            messageIcon = QPixmap("/usr/share/icons/crystalsvg/32x32/actions/messagebox_info.png")
        dialogue.image.setPixmap(messageIcon)
        dialogue.exec_()

    def error(self, summary, msg, extended_msg=None):
        msg="<big><b>%s</b></big><br />%s" % (summary, msg)

        dialogue = QDialog(self.window_main)
        loadUi("dialog_error.ui", dialogue)
        self.translate_widget_children(dialogue)
        dialogue.label_error.setText(utf8(msg))
        if extended_msg != None:
            dialogue.textview_error.setText(utf8(extended_msg))
            dialogue.textview_error.show()
        else:
            dialogue.textview_error.hide()
        dialogue.button_close.show()
        self.app.connect(dialogue.button_bugreport, SIGNAL("clicked()"), self.reportBug)

        if os.path.exists("/usr/share/icons/oxygen/48x48/status/dialog-error.png"):
            messageIcon = QPixmap("/usr/share/icons/oxygen/48x48/status/dialog-error.png")
        elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-error.png"):
            messageIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-error.png")
        else:
            messageIcon = QPixmap("/usr/share/icons/crystalsvg/32x32/actions/messagebox_critical.png")
        dialogue.image.setPixmap(messageIcon)
        dialogue.exec_()

        return False

    def confirmChanges(self, summary, changes, demotions, downloadSize, 
                       actions=None, removal_bold=True):
        """show the changes dialogue"""
        # FIXME: add a whitelist here for packages that we expect to be
        # removed (how to calc this automatically?)
        DistUpgradeView.confirmChanges(self, summary, changes, demotions, 
                                       downloadSize)
        msg = unicode(self.confirmChangesMessage, 'UTF-8')
        self.changesDialogue = QDialog(self.window_main)
        loadUi("dialog_changes.ui", self.changesDialogue)

        self.changesDialogue.treeview_details.hide()
        self.changesDialogue.connect(self.changesDialogue.show_details_button, SIGNAL("clicked()"), self.showChangesDialogueDetails)
        self.translate_widget_children(self.changesDialogue)
        self.changesDialogue.show_details_button.setText(_("Details") + " >>>")
        self.changesDialogue.resize(self.changesDialogue.sizeHint())

        if os.path.exists("/usr/share/icons/oxygen/48x48/status/dialog-warning.png"):
            warningIcon = QPixmap("/usr/share/icons/oxygen/48x48/status/dialog-warning.png")
        elif os.path.exists("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-warning.png"):
            warningIcon = QPixmap("/usr/lib/kde4/share/icons/oxygen/48x48/status/dialog-warning.png")
        else:
            warningIcon = QPixmap("/usr/share/icons/crystalsvg/32x32/actions/messagebox_warning.png")

        self.changesDialogue.question_pixmap.setPixmap(warningIcon)

        if actions != None:
            cancel = actions[0].replace("_", "")
            self.changesDialogue.button_cancel_changes.setText(cancel)
            confirm = actions[1].replace("_", "")
            self.changesDialogue.button_confirm_changes.setText(confirm)

        summaryText = unicode("<big><b>%s</b></big>" % summary, 'UTF-8')
        self.changesDialogue.label_summary.setText(summaryText)
        self.changesDialogue.label_changes.setText(msg)
        # fill in the details
        self.changesDialogue.treeview_details.clear()
        self.changesDialogue.treeview_details.setHeaderLabels(["Packages"])
        self.changesDialogue.treeview_details.header().hide()
        for demoted in self.demotions:
            self.changesDialogue.treeview_details.insertTopLevelItem(0, QTreeWidgetItem(self.changesDialogue.treeview_details, [_("No longer supported %s") % demoted.name]) )
        for rm in self.toRemove:
            self.changesDialogue.treeview_details.insertTopLevelItem(0, QTreeWidgetItem(self.changesDialogue.treeview_details, [_("Remove %s") % rm.name]) )
        for rm in self.toRemoveAuto:
            self.changesDialogue.treeview_details.insertTopLevelItem(0, QTreeWidgetItem(self.changesDialogue.treeview_details, [_("Remove (was auto installed) %s") % rm.name]) )
        for inst in self.toInstall:
            self.changesDialogue.treeview_details.insertTopLevelItem(0, QTreeWidgetItem(self.changesDialogue.treeview_details, [_("Install %s") % inst.name]) )
        for up in self.toUpgrade:
            self.changesDialogue.treeview_details.insertTopLevelItem(0, QTreeWidgetItem(self.changesDialogue.treeview_details, [_("Upgrade %s") % up.name]) )

        #FIXME resize label, stop it being shrinkable
        res = self.changesDialogue.exec_()
        if res == QDialog.Accepted:
            return True
        return False

    def showChangesDialogueDetails(self):
        if self.changesDialogue.treeview_details.isVisible():
            self.changesDialogue.treeview_details.hide()
            self.changesDialogue.show_details_button.setText(_("Details") + " >>>")
        else:
            self.changesDialogue.treeview_details.show()
            self.changesDialogue.show_details_button.setText("<<< " + _("Details"))
        self.changesDialogue.resize(self.changesDialogue.sizeHint())

    def askYesNoQuestion(self, summary, msg, default='No'):
        answer = QMessageBox.question(self.window_main, unicode(summary, 'UTF-8'), unicode("<font>") + unicode(msg, 'UTF-8'), QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            return True
        return False

    def confirmRestart(self):
        messageBox = QMessageBox(QMessageBox.Question, _("Restart required"), _("<b><big>Restart the system to complete the upgrade</big></b>"), QMessageBox.NoButton, self.window_main)
        yesButton = messageBox.addButton(QMessageBox.Yes)
        noButton = messageBox.addButton(QMessageBox.No)
        yesButton.setText(_("_Restart Now").replace("_", "&"))
        noButton.setText(gettext.dgettext("kdelibs", "&Close"))
        answer = messageBox.exec_()
        if answer == QMessageBox.Yes:
            return True
        return False

    def processEvents(self):
        QApplication.processEvents()

    def pulseProgress(self, finished=False):
        # FIXME: currently we do nothing here because this is
        # run in a different python thread and QT explodes if the UI is
        # touched from a non QThread
        pass

    def on_window_main_delete_event(self):
        #FIXME make this user friendly
        text = _("""<b><big>Cancel the running upgrade?</big></b>

The system could be in an unusable state if you cancel the upgrade. You are strongly advised to resume the upgrade.""")
        text = text.replace("\n", "<br />")
        cancel = QMessageBox.warning(self.window_main, _("Cancel Upgrade?"), text, QMessageBox.Yes, QMessageBox.No)
        if cancel == QMessageBox.Yes:
            return True
        return False

if __name__ == "__main__":
  
  view = DistUpgradeViewKDE()
  view.askYesNoQuestion("input box test","bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar bar ")

  if sys.argv[1] == "--test-term":
      pid = view.terminal_text.fork()
      if pid == 0:
          subprocess.call(["bash"])
          sys.exit()
      while True:
          view.terminal_text.update_interface()
          QApplication.processEvents()
          time.sleep(0.01)

  if sys.argv[1] == "--show-in-terminal":
      for c in open(sys.argv[2]).read():
          view.terminal_text.insertWithTermCodes( c )
          #print c, ord(c)
          QApplication.processEvents()
          time.sleep(0.05)
      while True:
          QApplication.processEvents()

  cache = apt.Cache()
  for pkg in sys.argv[1:]:
    if cache[pkg].is_installed and not cache[pkg].isUpgradable: 
      cache[pkg].mark_delete(purge=True)
    else:
      cache[pkg].mark_install()
  cache.commit(view._fetchProgress,view._installProgress)

  # keep the window open
  while True:
      QApplication.processEvents()
