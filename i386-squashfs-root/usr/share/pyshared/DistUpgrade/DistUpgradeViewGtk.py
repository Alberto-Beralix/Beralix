# DistUpgradeViewGtk.py 
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

import pygtk
pygtk.require('2.0')
import glib
import gtk
import gtk.gdk
import vte
import gobject
import pango
import sys
import locale
import logging
import time
import subprocess

import apt
import apt_pkg
import os

from DistUpgradeApport import run_apport, apport_crash

from DistUpgradeView import DistUpgradeView, FuzzyTimeToStr, InstallProgress, FetchProgress
from SimpleGtkbuilderApp import SimpleGtkbuilderApp

import gettext
from DistUpgradeGettext import gettext as _

gobject.threads_init()

def utf8(str):
  return unicode(str, 'latin1').encode('utf-8')

class GtkCdromProgressAdapter(apt.progress.CdromProgress):
    """ Report the cdrom add progress
        Subclass this class to implement cdrom add progress reporting
    """
    def __init__(self, parent):
        self.status = parent.label_status
        self.progress = parent.progressbar_cache
        self.parent = parent
    def update(self, text, step):
        """ update is called regularly so that the gui can be redrawn """
        if text:
          self.status.set_text(text)
        self.progress.set_fraction(step/float(self.totalSteps))
        while gtk.events_pending():
          gtk.main_iteration()
    def askCdromName(self):
        return (False, "")
    def changeCdrom(self):
        return False

class GtkOpProgress(apt.progress.base.OpProgress):
  def __init__(self, progressbar):
      self.progressbar = progressbar
      #self.progressbar.set_pulse_step(0.01)
      #self.progressbar.pulse()
      self.fraction = 0.0

  def update(self, percent):
      #if percent > 99:
      #    self.progressbar.set_fraction(1)
      #else:
      #    self.progressbar.pulse()
      new_fraction = percent/100.0
      if abs(self.fraction-new_fraction) > 0.1:
        self.fraction = new_fraction
        self.progressbar.set_fraction(self.fraction)
      while gtk.events_pending():
          gtk.main_iteration()

  def done(self):
      self.progressbar.set_text(" ")


class GtkFetchProgressAdapter(FetchProgress):
    # FIXME: we really should have some sort of "we are at step"
    # xy in the gui
    # FIXME2: we need to thing about mediaCheck here too
    def __init__(self, parent):
        super(GtkFetchProgressAdapter, self).__init__()
        # if this is set to false the download will cancel
        self.status = parent.label_status
        self.progress = parent.progressbar_cache
        self.parent = parent
        self.canceled = False
        self.button_cancel = parent.button_fetch_cancel
        self.button_cancel.connect('clicked', self.cancelClicked)
    def cancelClicked(self, widget):
        logging.debug("cancelClicked")
        self.canceled = True
    def media_change(self, medium, drive):
        #print "mediaChange %s %s" % (medium, drive)
        msg = _("Please insert '%s' into the drive '%s'") % (medium,drive)
        dialog = gtk.MessageDialog(parent=self.parent.window_main,
                                   flags=gtk.DIALOG_MODAL,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_OK_CANCEL)
        dialog.set_markup(msg)
        res = dialog.run()
        dialog.set_title("")
        dialog.destroy()
        if res == gtk.RESPONSE_OK:
            return True
        return False
    def start(self):
        #logging.debug("start")
        super(GtkFetchProgressAdapter, self).start()
        self.progress.set_fraction(0)
        self.status.show()
        self.button_cancel.show()
    def stop(self):
        #logging.debug("stop")
        self.progress.set_text(" ")
        self.status.set_text(_("Fetching is complete"))
        self.button_cancel.hide()
    def pulse(self, owner):
        super(GtkFetchProgressAdapter, self).pulse(owner)
        # only update if there is a noticable change
        if abs(self.percent-self.progress.get_fraction()*100.0) > 0.1:
          self.progress.set_fraction(self.percent/100.0)
          currentItem = self.current_items + 1
          if currentItem > self.total_items:
            currentItem = self.total_items
          if self.current_cps > 0:
            self.status.set_text(_("Fetching file %li of %li at %sB/s") % (
                currentItem, self.total_items, 
                apt_pkg.size_to_str(self.current_cps)))
            self.progress.set_text(_("About %s remaining") % FuzzyTimeToStr(
                self.eta))
          else:
            self.status.set_text(_("Fetching file %li of %li") % (
                currentItem, self.total_items))
            self.progress.set_text("  ")
        while gtk.events_pending():
            gtk.main_iteration()
        return (not self.canceled)

class GtkInstallProgressAdapter(InstallProgress):
    # timeout with no status change when the terminal is expanded
    # automatically
    TIMEOUT_TERMINAL_ACTIVITY = 240
    
    def __init__(self,parent):
        InstallProgress.__init__(self)
        self._cache = None
        self.label_status = parent.label_status
        self.progress = parent.progressbar_cache
        self.expander = parent.expander_terminal
        self.term = parent._term
        self.term.connect("child-exited", self.child_exited)
        self.parent = parent
        # setup the child waiting
        # some options for dpkg to make it die less easily
        apt_pkg.Config.set("DPkg::StopOnError","False")

    def start_update(self):
        InstallProgress.start_update(self)
        self.finished = False
        # FIXME: add support for the timeout
        # of the terminal (to display something useful then)
        # -> longer term, move this code into python-apt 
        self.label_status.set_text(_("Applying changes"))
        self.progress.set_fraction(0.0)
        self.progress.set_text(" ")
        self.expander.set_sensitive(True)
        self.term.show()
        # if no libgtk22-perl is installed show the terminal
        frontend= os.environ.get("DEBIAN_FRONTEND") or "gnome"
        if frontend == "gnome" and self._cache:
          if (not "libgtk2-perl" in self._cache or 
              not self._cache["libgtk2-perl"].is_installed):
            frontend = "dialog"
            self.expander.set_expanded(True)
        self.env = ["VTE_PTY_KEEP_FD=%s"% self.writefd,
                    "APT_LISTCHANGES_FRONTEND=none"]
        if not os.environ.has_key("DEBIAN_FRONTEND"):
          self.env.append("DEBIAN_FRONTEND=%s" % frontend)
        # do a bit of time-keeping
        self.start_time = 0.0
        self.time_ui = 0.0
        self.last_activity = 0.0
        
    def error(self, pkg, errormsg):
        InstallProgress.error(self, pkg, errormsg)
        logging.error("got an error from dpkg for pkg: '%s': '%s'" % (pkg, errormsg))
	# we do not report followup errors from earlier failures
        if gettext.dgettext('dpkg', "dependency problems - leaving unconfigured") in errormsg:
	  return False

        #self.expander_terminal.set_expanded(True)
        self.parent.dialog_error.set_transient_for(self.parent.window_main)
        summary = _("Could not install '%s'") % pkg
        msg = _("The upgrade will continue but the '%s' package may not "
                "be in a working state. Please consider submitting a "
                "bug report about it.") % pkg
        markup="<big><b>%s</b></big>\n\n%s" % (summary, msg)
        self.parent.dialog_error.realize()
        self.parent.dialog_error.set_title("")
        self.parent.dialog_error.window.set_functions(gtk.gdk.FUNC_MOVE)
        self.parent.label_error.set_markup(markup)
        self.parent.textview_error.get_buffer().set_text(utf8(errormsg))
        self.parent.scroll_error.show()
        self.parent.dialog_error.run()
        self.parent.dialog_error.hide()

    def conffile(self, current, new):
        logging.debug("got a conffile-prompt from dpkg for file: '%s'" % current)
        start = time.time()
        #self.expander.set_expanded(True)
        prim = _("Replace the customized configuration file\n'%s'?") % current
        sec = _("You will lose any changes you have made to this "
                "configuration file if you choose to replace it with "
                "a newer version.")
        markup = "<span weight=\"bold\" size=\"larger\">%s </span> \n\n%s" % (prim, sec)
        self.parent.label_conffile.set_markup(markup)
        self.parent.dialog_conffile.set_title("")
        self.parent.dialog_conffile.set_transient_for(self.parent.window_main)

        # workaround silly dpkg 
        if not os.path.exists(current):
          current = current+".dpkg-dist"

        # now get the diff
        if os.path.exists("/usr/bin/diff"):
          cmd = ["/usr/bin/diff", "-u", current, new]
          diff = utf8(subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0])
          self.parent.textview_conffile.get_buffer().set_text(diff)
        else:
          self.parent.textview_conffile.get_buffer().set_text(_("The 'diff' command was not found"))
        res = self.parent.dialog_conffile.run()
        self.parent.dialog_conffile.hide()
        self.time_ui += time.time() - start
        # if replace, send this to the terminal
        if res == gtk.RESPONSE_YES:
          self.term.feed_child("y\n", -1)
        else:
          self.term.feed_child("n\n", -1)
        
    def fork(self):
        pid = self.term.forkpty(envv=self.env)
        if pid == 0:
          # WORKAROUND for broken feisty vte where envv does not work)
          for env in self.env:
            (key, value) = env.split("=")
            os.environ[key] = value
            # force dpkg terminal messages untranslated for better bug
            # duplication detection
            os.environ["DPKG_UNTRANSLATED_MESSAGES"] = "1"
          # HACK to work around bug in python/vte and unregister the logging
          #      atexit func in the child
          sys.exitfunc = lambda: True
        return pid

    def status_change(self, pkg, percent, status):
        # start the timer when the first package changes its status
        if self.start_time == 0.0:
          #print "setting start time to %s" % self.start_time
          self.start_time = time.time()
        # only update if there is a noticable change
        if abs(percent-self.progress.get_fraction()*100.0) > 0.1:
          self.progress.set_fraction(float(percent)/100.0)
          self.label_status.set_text(status.strip())
        # start showing when we gathered some data
        if percent > 1.0:
          self.last_activity = time.time()
          self.activity_timeout_reported = False
          delta = self.last_activity - self.start_time
          # time wasted in conffile questions (or other ui activity)
          delta -= self.time_ui
          time_per_percent = (float(delta)/percent)
          eta = (100.0 - percent) * time_per_percent
          # only show if we have some sensible data (60sec < eta < 2days)
          if eta > 61.0 and eta < (60*60*24*2):
            self.progress.set_text(_("About %s remaining") % FuzzyTimeToStr(eta))
          else:
            self.progress.set_text(" ")
          # 2 == WEBKIT_LOAD_FINISHED - the enums is not exposed via python
          if (self.parent._webkit_view and
              self.parent._webkit_view.get_property("load-status") == 2):
            self.parent._webkit_view.execute_script('progress("%s")' % percent)

    def child_exited(self, term):
        # we need to capture the full status here (not only the WEXITSTATUS)
        self.apt_status = term.get_child_exit_status()
        self.finished = True

    def wait_child(self):
        while not self.finished:
            self.update_interface()
        return self.apt_status

    def finish_update(self):
        self.label_status.set_text("")
    
    def update_interface(self):
        InstallProgress.update_interface(self)
        # check if we haven't started yet with packages, pulse then
        if self.start_time == 0.0:
          self.progress.pulse()
          time.sleep(0.2)
        # check about terminal activity
        if self.last_activity > 0 and \
           (self.last_activity + self.TIMEOUT_TERMINAL_ACTIVITY) < time.time():
          if not self.activity_timeout_reported:
            logging.warning("no activity on terminal for %s seconds (%s)" % (self.TIMEOUT_TERMINAL_ACTIVITY, self.label_status.get_text()))
            self.activity_timeout_reported = True
          self.parent.expander_terminal.set_expanded(True)
        # process events
        while gtk.events_pending():
            gtk.main_iteration()
	time.sleep(0.01)

class DistUpgradeVteTerminal(object):
  def __init__(self, parent, term):
    self.term = term
    self.parent = parent
  def call(self, cmd, hidden=False):
    def wait_for_child(widget):
      #print "wait for child finished"
      self.finished=True
    self.term.show()
    self.term.connect("child-exited", wait_for_child)
    self.parent.expander_terminal.set_sensitive(True)
    if hidden==False:
      self.parent.expander_terminal.set_expanded(True)
    self.finished = False
    pid = self.term.fork_command(command=cmd[0],argv=cmd)
    if pid < 0:
      # error
      return 
    while not self.finished:
      while gtk.events_pending():
        gtk.main_iteration()
      time.sleep(0.1)
    del self.finished

class HtmlView(object):
  def __init__(self, webkit_view):
    self._webkit_view = webkit_view
  def open(self, url):
    if not self._webkit_view:
      return
    self._webkit_view.open(url)
    self._webkit_view.connect("load-finished", self._on_load_finished)
  def show(self):
    self._webkit_view.show()
  def hide(self):
    self._webkit_view.hide()
  def _on_load_finished(self, view, frame):
    view.show()

class DistUpgradeViewGtk(DistUpgradeView,SimpleGtkbuilderApp):
    " gtk frontend of the distUpgrade tool "
    def __init__(self, datadir=None, logdir=None):
        DistUpgradeView.__init__(self)
        self.logdir = logdir
        if not datadir:
          localedir=os.path.join(os.getcwd(),"mo")
          gladedir=os.getcwd()
        else:
          localedir="/usr/share/locale/"
          gladedir=os.path.join(datadir, "gtkbuilder")

	# check if we have a display etc
	gtk.init_check()

        try:
          locale.bindtextdomain("update-manager",localedir)
          gettext.textdomain("update-manager")
        except Exception, e:
          logging.warning("Error setting locales (%s)" % e)
        
        icons = gtk.icon_theme_get_default()
        try:
          gtk.window_set_default_icon(icons.load_icon("update-manager", 32, 0))
        except gobject.GError, e:
          logging.debug("error setting default icon, ignoring (%s)" % e)
          pass
        SimpleGtkbuilderApp.__init__(self, 
                                     gladedir+"/DistUpgrade.ui", 
                                     "update-manager")
        # terminal stuff
        self.create_terminal()

        self.prev_step = 0 # keep a record of the latest step
        # we don't use this currently
        #self.window_main.set_keep_above(True)
        self.icontheme = gtk.icon_theme_get_default()
        # we keep a reference pngloader around so that its in memory
        # -> this avoid the issue that during the dapper->edgy upgrade
        #    the loaders move from /usr/lib/gtk/2.4.0/loaders to 2.10.0
        self.pngloader = gtk.gdk.PixbufLoader("png")
        try:
          self.svgloader = gtk.gdk.PixbufLoader("svg")
          self.svgloader.close()
        except gobject.GError, e:
          logging.debug("svg pixbuf loader failed (%s)" % e)
          pass
        try:
          import webkit
          self._webkit_view = webkit.WebView()
          self.vbox_main.pack_end(self._webkit_view)
        except:
          logging.exception("html widget")
          self._webkit_view = None
        self.window_main.realize()
        self.window_main.window.set_functions(gtk.gdk.FUNC_MOVE)
        self._opCacheProgress = GtkOpProgress(self.progressbar_cache)
        self._fetchProgress = GtkFetchProgressAdapter(self)
        self._cdromProgress = GtkCdromProgressAdapter(self)
        self._installProgress = GtkInstallProgressAdapter(self)
        # details dialog
        self.details_list = gtk.TreeStore(gobject.TYPE_STRING)
        column = gtk.TreeViewColumn("")
        render = gtk.CellRendererText()
        column.pack_start(render, True)
        column.add_attribute(render, "markup", 0)
        self.treeview_details.append_column(column)
        self.details_list.set_sort_column_id(0, gtk.SORT_ASCENDING)
        self.treeview_details.set_model(self.details_list)
        # Use italic style in the status labels
        attrlist=pango.AttrList()
        #attr = pango.AttrStyle(pango.STYLE_ITALIC, 0, -1)
        attr = pango.AttrScale(pango.SCALE_SMALL, 0, -1)
        attrlist.insert(attr)
        self.label_status.set_property("attributes", attrlist)
        # reasonable fault handler
        sys.excepthook = self._handleException

    def _handleException(self, type, value, tb):
      # we handle the exception here, hand it to apport and run the
      # apport gui manually after it because we kill u-m during the upgrade
      # to prevent it from poping up for reboot notifications or FF restart
      # notifications or somesuch
      import traceback
      lines = traceback.format_exception(type, value, tb)
      logging.error("not handled expection:\n%s" % "\n".join(lines))
      # we can't be sure that apport will run in the middle of a upgrade
      # so we still show a error message here
      apport_crash(type, value, tb)
      if not run_apport():
        self.error(_("A fatal error occurred"),
                   _("Please report this as a bug (if you haven't already) and include the "
                     "files /var/log/dist-upgrade/main.log and "
                     "/var/log/dist-upgrade/apt.log "
                     "in your report. The upgrade has aborted.\n"
                     "Your original sources.list was saved in "
                     "/etc/apt/sources.list.distUpgrade."),
                   "\n".join(lines))
      sys.exit(1)

    def getTerminal(self):
        return DistUpgradeVteTerminal(self, self._term)
    def getHtmlView(self):
        return HtmlView(self._webkit_view)

    def _key_press_handler(self, widget, keyev):
      # user pressed ctrl-c
      if len(keyev.string) == 1 and ord(keyev.string) == 3:
        summary = _("Ctrl-c pressed")
        msg = _("This will abort the operation and may leave the system "
                "in a broken state. Are you sure you want to do that?")
        res = self.askYesNoQuestion(summary, msg)
        logging.warning("ctrl-c press detected, user decided to pass it "
                        "on: %s", res)        
        return not res
      return False

    def create_terminal(self):
        " helper to create a vte terminal "
        self._term = vte.Terminal()
        self._term.connect("key-press-event", self._key_press_handler)
        self._term.set_font_from_string("monospace 10")
        self._term.connect("contents-changed", self._term_content_changed)
        self._terminal_lines = []
        self.hbox_custom.pack_start(self._term)
        self._term.realize()
        self.vscrollbar_terminal = gtk.VScrollbar()
        self.vscrollbar_terminal.show()
        self.hbox_custom.pack_start(self.vscrollbar_terminal)
        self.vscrollbar_terminal.set_adjustment(self._term.get_adjustment())
        try:
          self._terminal_log = open(os.path.join(self.logdir,"term.log"),"w")
        except Exception:
          # if something goes wrong (permission denied etc), use stdout
          self._terminal_log = sys.stdout
        return self._term

    def _term_content_changed(self, term):
        " called when the *visible* part of the terminal changes "
        # get the current visible text, 
        current_text = self._term.get_text(lambda a,b,c,d: True)
        # see what we have currently and only print stuff that wasn't
        # visible last time
        new_lines = []
        for line in current_text.split("\n"):
          new_lines.append(line)
          if not line in self._terminal_lines:
            self._terminal_log.write(line+"\n")
            try:
              self._terminal_log.flush()
            except IOError:
              logging.exception("flush()")
        self._terminal_lines = new_lines
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
        self.label_status.set_text("%s" % msg)
    def hideStep(self, step):
        image = getattr(self,"image_step%i" % step)
        label = getattr(self,"label_step%i" % step)
        #arrow = getattr(self,"arrow_step%i" % step)
        image.hide()
        label.hide()
    def showStep(self, step):
        image = getattr(self,"image_step%i" % step)
        label = getattr(self,"label_step%i" % step)
        image.show()
        label.show()
    def abort(self):
        size = gtk.ICON_SIZE_MENU
        step = self.prev_step
        if step > 0:
            image = getattr(self,"image_step%i" % step)
            arrow = getattr(self,"arrow_step%i" % step)
            image.set_from_stock(gtk.STOCK_CANCEL, size)
            image.show()
            arrow.hide()
    def setStep(self, step):
        if self.icontheme.rescan_if_needed():
          logging.debug("icon theme changed, re-reading")
        # first update the "previous" step as completed
        size = gtk.ICON_SIZE_MENU
        attrlist=pango.AttrList()
        if self.prev_step:
            image = getattr(self,"image_step%i" % self.prev_step)
            label = getattr(self,"label_step%i" % self.prev_step)
            arrow = getattr(self,"arrow_step%i" % self.prev_step)
            label.set_property("attributes",attrlist)
            image.set_from_stock(gtk.STOCK_APPLY, size)
            image.show()
            arrow.hide()
        self.prev_step = step
        # show the an arrow for the current step and make the label bold
        image = getattr(self,"image_step%i" % step)
        label = getattr(self,"label_step%i" % step)
        arrow = getattr(self,"arrow_step%i" % step)
        # check if that step was not hidden with hideStep()
        if not label.get_property("visible"):
          return
        arrow.show()
        image.hide()
        attr = pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1)
        attrlist.insert(attr)
        label.set_property("attributes",attrlist)

    def information(self, summary, msg, extended_msg=None):
      self.dialog_information.set_title("")
      self.dialog_information.set_transient_for(self.window_main)
      msg = "<big><b>%s</b></big>\n\n%s" % (summary,msg)
      self.label_information.set_markup(msg)
      if extended_msg != None:
        buffer = self.textview_information.get_buffer()
        buffer.set_text(extended_msg)
        self.scroll_information.show()
      else:
        self.scroll_information.hide()
      self.dialog_information.realize()
      self.dialog_information.window.set_functions(gtk.gdk.FUNC_MOVE)
      self.dialog_information.run()
      self.dialog_information.hide()
      while gtk.events_pending():
        gtk.main_iteration()

    def error(self, summary, msg, extended_msg=None):
        self.dialog_error.set_title("")
        self.dialog_error.set_transient_for(self.window_main)
        #self.expander_terminal.set_expanded(True)
        msg="<big><b>%s</b></big>\n\n%s" % (summary, msg)
        self.label_error.set_markup(msg)
        if extended_msg != None:
            buffer = self.textview_error.get_buffer()
            buffer.set_text(extended_msg)
            self.scroll_error.show()
        else:
            self.scroll_error.hide()
        self.dialog_error.realize()
        self.dialog_error.window.set_functions(gtk.gdk.FUNC_MOVE)
        self.dialog_error.run()
        self.dialog_error.hide()
        return False

    def confirmChanges(self, summary, changes, demotions, downloadSize, 
                       actions=None, removal_bold=True):
        # FIXME: add a whitelist here for packages that we expect to be
        # removed (how to calc this automatically?)
        if not DistUpgradeView.confirmChanges(self, summary, changes, 
                                              demotions, downloadSize):
          return False
        # append warning
        self.confirmChangesMessage +=  "\n\n<b>%s</b>" %  \
            _("To prevent data loss close all open "
              "applications and documents.")

        if actions != None:
            self.button_cancel_changes.set_use_stock(False)
            self.button_cancel_changes.set_use_underline(True)
            self.button_cancel_changes.set_label(actions[0])
            self.button_confirm_changes.set_label(actions[1])

        self.label_summary.set_markup("<big><b>%s</b></big>" % summary)
        self.label_changes.set_markup(self.confirmChangesMessage)
        # fill in the details
        self.details_list.clear()
        for (parent_text, details_list) in ( 
            ( _("No longer supported by Canonical (%s)"), self.demotions),
            ( _("<b>Downgrade (%s)</b>"), self.toDowngrade),
            ( _("Remove (%s)"), self.toRemove),
            ( _("No longer needed (%s)"), self.toRemoveAuto),
            ( _("Install (%s)"), self.toInstall),
            ( _("Upgrade (%s)"), self.toUpgrade),
          ):
          if details_list:
            node = self.details_list.append(None, 
                                            [parent_text % len(details_list)])
            for pkg in details_list:
              self.details_list.append(node, ["<b>%s</b> - %s" % (
                    pkg.name, glib.markup_escape_text(pkg.summary))])
        # prepare dialog
        self.dialog_changes.realize()
        self.dialog_changes.set_transient_for(self.window_main)
        self.dialog_changes.set_title("")
        self.dialog_changes.window.set_functions(gtk.gdk.FUNC_MOVE|
                                                 gtk.gdk.FUNC_RESIZE)
        res = self.dialog_changes.run()
        self.dialog_changes.hide()
        if res == gtk.RESPONSE_YES:
            return True
        return False

    def askYesNoQuestion(self, summary, msg, default='No'):
        msg = "<big><b>%s</b></big>\n\n%s" % (summary,msg)
        dialog = gtk.MessageDialog(parent=self.window_main,
                                   flags=gtk.DIALOG_MODAL,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_YES_NO)
        dialog.set_title("")
        if default == 'No':
          dialog.set_default_response(gtk.RESPONSE_NO)
        else:
          dialog.set_default_response(gtk.RESPONSE_YES)
        dialog.set_markup(msg)
        res = dialog.run()
        dialog.destroy()
        if res == gtk.RESPONSE_YES:
            return True
        return False
    
    def confirmRestart(self):
        self.dialog_restart.set_transient_for(self.window_main)
        self.dialog_restart.set_title("")
        self.dialog_restart.realize()
        self.dialog_restart.window.set_functions(gtk.gdk.FUNC_MOVE)
        res = self.dialog_restart.run()
        self.dialog_restart.hide()
        if res == gtk.RESPONSE_YES:
            return True
        return False

    def processEvents(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def pulseProgress(self, finished=False):
      self.progressbar_cache.pulse()
      if finished:
        self.progressbar_cache.set_fraction(1.0)

    def on_window_main_delete_event(self, widget, event):
        self.dialog_cancel.set_transient_for(self.window_main)
        self.dialog_cancel.set_title("")
        self.dialog_cancel.realize()
        self.dialog_cancel.window.set_functions(gtk.gdk.FUNC_MOVE)
        res = self.dialog_cancel.run()
        self.dialog_cancel.hide()
        if res == gtk.RESPONSE_CANCEL:
            sys.exit(1)
        return True

if __name__ == "__main__":
  
  view = DistUpgradeViewGtk()
  fp = GtkFetchProgressAdapter(view)
  ip = GtkInstallProgressAdapter(view)

  cache = apt.Cache()
  for pkg in sys.argv[1:]:
    if cache[pkg].is_installed:
      cache[pkg].mark_delete()
    else:
      cache[pkg].mark_install()
  cache.commit(fp,ip)
  gtk.main()
  sys.exit(0)
  
  #sys.exit(0)
  ip.conffile("TODO","TODO~")
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
  
