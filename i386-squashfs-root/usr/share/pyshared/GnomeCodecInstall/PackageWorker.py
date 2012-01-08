# -*- coding: utf-8 -*-
# Copyright (c) 2005-2007 Canonical, GPL

import apt
import subprocess
import gtk
import gtk.gdk
import thread
import time
import os
import tempfile
from gettext import gettext as _

try:
  from aptdaemon import client, errors, enums
  from defer import inline_callbacks
  from aptdaemon.gtkwidgets import AptProgressDialog
except ImportError, e:
  def inline_callbacks(f):
    return f

class GtkOpProgress(apt.progress.base.OpProgress):
  " a simple helper that keeps the GUI alive "

  def update(self, percent):
    while gtk.events_pending():
      gtk.main_iteration()

class PackageWorker(object):
  """ base class """
  def perform_action(self, window_main, to_add=None, to_rm=None):
    raise NotImplemented
  def perform_update(self, window_main):
    raise NotImplemented

class PackageWorkerAptdaemon(PackageWorker):

  def __init__(self):
    self.client = client.AptClient()

  def _wait_for_finishing(self):
    while not self._finished:
      while gtk.events_pending():
        gtk.main_iteration()
      time.sleep(0.01)

  def perform_action(self, parent_window, install, remove):
    self._finished = False
    self._perform_action(parent_window, install, remove)
    self._wait_for_finishing()
    return self._result

  @inline_callbacks
  def _perform_action(self, parent_window, install, remove):
    trans = yield self.client.commit_packages(
      list(install), [], list(remove), [], [], [], defer=True)
    self._run_in_dialog(trans, parent_window)

  def perform_update(self, parent_window):
    self._finished = False
    self._perform_update(parent_window)
    self._wait_for_finishing()
    return self._result

  @inline_callbacks
  def _perform_update(self, parent_window):
    trans = yield self.client.update_cache(defer=True)
    self._run_in_dialog(trans, parent_window)

  def _run_in_dialog(self, trans, parent_window):
    dia = AptProgressDialog(trans, parent=parent_window)
    dia.connect("finished", self._on_finished)
    dia.run()

  def _on_finished(self, dialog):
    dialog.hide()
    self._finished = True
    self._result = (dialog._transaction.exit == enums.EXIT_SUCCESS)


class PackageWorkerSynaptic(PackageWorker):
    """
    A class which does the actual package installing/removing.
    """
    # synaptic actions
    (INSTALL, UPDATE) = range(2)

    def run_synaptic(self, id, lock, to_add=None,to_rm=None, action=INSTALL):
        #print "run_synaptic(%s,%s,%s)" % (id, lock, selections)
        cmd = []
        if os.getuid() != 0:
            cmd = ["/usr/bin/gksu",
                   "--desktop", "/usr/share/applications/synaptic.desktop",
                   "--"]
        cmd += ["/usr/sbin/synaptic",
                "--hide-main-window",
                "--non-interactive",
                "-o", "Synaptic::closeZvt=true",
                "--parent-window-id", "%s" % (id) ]

        # create tempfile for install (here because it must survive
        # durng the synaptic call
        f = tempfile.NamedTemporaryFile()
        if action == self.INSTALL:
            # install the stuff
            for item in to_add:
                f.write("%s\tinstall\n" % item)
                #print item.pkgname
            for item in to_rm:
                f.write("%s\tuninstall\n" % item)
            cmd.append("--set-selections-file")
            cmd.append("%s" % f.name)
            f.flush()
        elif action == self.UPDATE:
            #print "Updating..."
            cmd.append("--update-at-startup")
        self.return_code = subprocess.call(cmd)
        lock.release()
        f.close()

    def perform_update(self, window_main):
        window_main.set_sensitive(False)
        if window_main.window:
          window_main.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        lock = thread.allocate_lock()
        lock.acquire()
        t = thread.start_new_thread(self.run_synaptic,(window_main.window.xid,lock, [], [], self.UPDATE))
        while lock.locked():
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.05)
        window_main.set_sensitive(True)
        if window_main.window:
          window_main.window.set_cursor(None)

    def perform_action(self, window_main, to_add=None, to_rm=None):
        """ 
        install/remove the given set of packages 
        
        return True on success 
               False if any of the actions could not be performed
        """
        window_main.set_sensitive(False)
        if window_main.window:
          window_main.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.WATCH))
        lock = thread.allocate_lock()
        lock.acquire()
        t = thread.start_new_thread(self.run_synaptic,(window_main.window.xid,lock,to_add, to_rm, self.INSTALL))
        while lock.locked():
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.05)

        # check if the requested package really got installed
        # we can not use the exit code here because gksu does
        # not transport the exit code over
        result = True
        cache = apt.Cache(GtkOpProgress())
        for pkgname in to_add:
            if not cache[pkgname].is_installed:
                result = False
                break
        for pkgname in to_rm:
            if cache[pkgname].is_installed:
                result = False
                break
        window_main.set_sensitive(True)
        if window_main.window:
          window_main.window.set_cursor(None)
        return result


def get_worker():
  if (os.path.exists("/usr/sbin/aptd") and
      not "CODEC_INSTALLER_FORCE_BACKEND_SYNAPTIC" in os.environ):
    return PackageWorkerAptdaemon()
  if os.path.exists("/usr/sbin/synaptic"):
    return PackageWorkerSynaptic()

if __name__ == "__main__":
  worker = get_worker()
  print worker
  res = worker.perform_update(None)
  print res
  res = worker.perform_action(None, ["2vcard"], [])
  print res
