#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Progress handlers for APT operations"""
# Copyright (C) 2008-2009 Sebastian Heinlein <glatzor@ubuntu.com>
#
# Licensed under the GNU General Public License Version 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

__author__  = "Sebastian Heinlein <devel@glatzor.de>"

__all__ = ("DaemonAcquireProgress", "DaemonOpenProgress",
           "DaemonInstallProgress", "DaemonDpkgInstallProgress",
           "DaemonDpkgRecoverProgress")

import logging
import os
import re
import signal
import sys
import termios
import time
import traceback
import tty

import apt_pkg
import apt.progress.base
import apt.debfile
import gobject

import enums
import lock
from loop import mainloop

# Required to get translatable strings extraced by xgettext
_ = lambda s: s

log = logging.getLogger("AptDaemon.Worker")
log_terminal = logging.getLogger("AptDaemon.Worker.Terminal")

INSTALL_TIMEOUT = 10 * 60

MAP_STAGE = {"install":_("Installing %s"),
             "configure":_("Configuring %s"),
             "remove":_("Removing %s"),
             "trigproc":_("Running post-installation trigger %s"),
             "purge":_("Purging %s"),
             "disappear": "", # nothing for now, this is very rare and not important to the user
             "upgrade":_("Upgrading %s")}

REGEX_ANSI_ESCAPE_CODE = chr(27) + "\[[;?0-9]*[A-Za-z]"

class DaemonOpenProgress(apt.progress.base.OpProgress):

    """Handles the progress of the cache opening."""

    def __init__(self, transaction, begin=0, end=100, quiet=False):
        """Initialize a new DaemonOpenProgress instance.

        Keyword arguments:
        transaction -- corresponding transaction D-Bus object
        begin -- begin of the progress range (defaults to 0)
        end -- end of the progress range (defaults to 100)
        quiet -- do not emit any progress information for the transaction
        """
        apt.progress.base.OpProgress.__init__(self)
        self._transaction = transaction
        self.steps = [begin + (end - begin) * modifier
                      # the final 1.00 will not be used but we still 
                      # need it here for the final pop()
                      for modifier in [0.25, 0.50, 0.75, 1.00, 1.00]]
        self.progress_begin = float(begin)
        self.progress_end = self.steps.pop(0)
        self.progress = 0
        self.quiet = quiet

    def update(self, percent=None):
        """Callback for progress updates.

        Keyword argument:
        percent - current progress in percent
        """
        # python-apt 0.8 does not include "percent" anymore in the call
        percent = percent or self.percent
        if percent < 101:
            progress = int(self.progress_begin + (percent / 100) * \
                           (self.progress_end - self.progress_begin))
            if self.progress == progress:
                return
        else:
            progress = 101
        self.progress = progress
        if not self.quiet:
            self._transaction.progress = progress

    def done(self):
        """Callback after completing a step.

        Sets the progress range to the next interval."""
        # ensure that progress is updated
        self.progress = self.progress_end
        # switch to new progress_{begin, end}
        self.progress_begin = self.progress_end
        try:
            self.progress_end = self.steps.pop(0)
        except:
            log.warning("An additional step to open the cache is required")

class DaemonAcquireProgress(apt.progress.base.AcquireProgress):
    '''
    Handle the package download process
    '''
    def __init__(self, transaction, begin=0, end=100):
        apt.progress.base.AcquireProgress.__init__(self)
        self.transaction = transaction
        self.progress_end = end
        self.progress_begin = begin
        self.progress = 0

    def _emit_acquire_item(self, item, total_size=0, current_size=0):
        if item.owner.status == apt_pkg.AcquireItem.STAT_DONE:
            status = enums.DOWNLOAD_DONE
            # Workaround for a bug in python-apt, see lp: #581886
            current_size = item.owner.filesize
        elif item.owner.status == apt_pkg.AcquireItem.STAT_AUTH_ERROR:
            status = enums.DOWNLOAD_AUTH_ERROR
        elif item.owner.status == apt_pkg.AcquireItem.STAT_FETCHING:
            status = enums.DOWNLOAD_FETCHING
        elif item.owner.status == apt_pkg.AcquireItem.STAT_ERROR:
            status = enums.DOWNLOAD_ERROR
        elif item.owner.status == apt_pkg.AcquireItem.STAT_IDLE:
            status = enums.DOWNLOAD_IDLE
        else:
            # Workaround: The StatTransientNetworkError status isn't mapped
            # by python-apt, see LP #602578
            status = enums.DOWNLOAD_NETWORK_ERROR
        if item.owner.status != apt_pkg.AcquireItem.STAT_DONE and \
           item.owner.error_text:
            msg = item.owner.error_text
        elif item.owner.mode:
            msg = item.owner.mode
        else:
            msg = ""
        self.transaction.progress_download = item.uri, status, item.shortdesc, \
                                             total_size | item.owner.filesize, \
                                             current_size | item.owner.partialsize, \
                                             msg

    def done(self, item):
        """Invoked when an item is successfully and completely fetched."""
        self._emit_acquire_item(item)

    def fail(self, item):
        """Invoked when an item could not be fetched."""
        self._emit_acquire_item(item)

    def fetch(self, item):
        """Invoked when some of the item's data is fetched."""
        self._emit_acquire_item(item)

    def ims_hit(self, item):
        """Invoked when an item is confirmed to be up-to-date.

        Invoked when an item is confirmed to be up-to-date. For instance,
        when an HTTP download is informed that the file on the server was
        not modified.
        """
        self._emit_acquire_item(item)

    def pulse(self, owner):
        """Callback to update progress information"""
        if self.transaction.cancelled:
            return False
        self.transaction.progress_details = (self.current_items,
                                             self.total_items,
                                             self.current_bytes,
                                             self.total_bytes,
                                             self.current_cps,
                                             self.elapsed_time)
        percent = (((self.current_bytes + self.current_items) * 100.0) /
                    float(self.total_bytes + self.total_items))
        progress = int(self.progress_begin + percent/100 * \
                       (self.progress_end - self.progress_begin))
        # If the progress runs backwards emit an illegal progress value
        # e.g. during cache updates.
        if self.progress > progress:
            self.transaction.progress = 101
        else:
            self.transaction.progress = progress
            self.progress = progress
        # Show all currently downloaded files
        items = set()
        for worker in owner.workers:
            if not worker.current_item:
                continue
            self._emit_acquire_item(worker.current_item,
                                    worker.total_size,
                                    worker.current_size)
            if worker.current_item.owner.id:
                items.add(worker.current_item.owner.id)
            else:
                items.add(worker.current_item.shortdesc)
        if items:
            #TRANSLATORS: %s is a list of package names
            msg = self.transaction.ngettext("Downloading %(files)s",
                                            "Downloading %(files)s",
                                            len(items)) % {"files":
                                                           " ".join(items)}
            self.transaction.status_details = msg

        while gobject.main_context_default().pending():
            gobject.main_context_default().iteration()
        return True

    def start(self):
        """Callback at the beginning of the operation"""
        self.transaction.status = enums.STATUS_DOWNLOADING
        self.transaction.cancellable = True

    def stop(self):
        """Callback at the end of the operation"""
        self.transaction.progress_details = (0, 0, 0L, 0L, 0.0, 0L)
        self.transaction.progress = self.progress_end
        self.transaction.cancellable = False

    def media_change(self, medium, drive):
        """Callback for media changes"""
        #FIXME: make use of DeviceKit/hal
        self.transaction.required_medium = medium, drive
        self.transaction.paused = True
        self.transaction.status = enums.STATUS_WAITING_MEDIUM
        while self.transaction.paused:
            gobject.main_context_default().iteration()
        self.transaction.status = enums.STATUS_DOWNLOADING
        if self.transaction.cancelled:
            return False
        return True


class DaemonInstallProgress(object):

    def __init__(self, transaction, begin=50, end=100):
        self.transaction = transaction
        self.status = ""
        self.progress = 0
        self.progress_begin = begin
        self.progress_end = end
        self._child_exit = -1
        self.last_activity = 0
        self.child_pid = 0
        self.status_parent_fd, self.status_child_fd = os.pipe()
        self.output = ""
        self._line_buffer = ""

    def start_update(self):
        log.debug("Start update")
        lock.status_lock.release()
        self.transaction.status = enums.STATUS_COMMITTING
        self.transaction.term_attached = True
        self.last_activity = time.time()
        self.start_time = time.time()

    def finish_update(self):
        """Callback at the end of the operation"""
        self.transaction.term_attached = False
        lock.wait_for_lock(self.transaction, lock.status_lock)

    def _child(self, pm):
        # force terminal messages in dpkg to be untranslated, the
        # status-fd or debconf prompts will not be affected
        os.environ["DPKG_UNTRANSLATED_MESSAGES"] = "1"
        try:
            res = pm.do_install(self.status_child_fd)
        except:
            os._exit(apt_pkg.PackageManager.RESULT_FAILED)
        else:
            os._exit(res)

    def run(self, *args, **kwargs):
        log.debug("Run")
        terminal_fd = None
        if self.transaction.terminal:
            try:
                # Save the settings of the transaction terminal and set to
                # raw mode
                terminal_fd = os.open(self.transaction.terminal,
                                      os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
                terminal_attr = termios.tcgetattr(terminal_fd)
                tty.setraw(terminal_fd, termios.TCSANOW)
            except (OSError, termios.error):
                # Switch to non-interactive
                self.transaction.terminal = ""
        pid = self._fork()
        if pid == 0:
            os.close(self.status_parent_fd)
            try:
                self._setup_child()
                self._child(*args, **kwargs)
            except Exception, error:
                traceback.print_exc()
            finally:
                # Give the parent process enough time to catch the output
                time.sleep(1)
                # Abort the subprocess immediatelly on any unhandled
                # failure - otherwise the atexit methods would
                # be called, e.g. the frozen status decorator
                os._exit(apt_pkg.PackageManager.RESULT_FAILED)
        else:
            self.child_pid = pid
            os.close(self.status_child_fd)
        log.debug("Child pid: %s", pid)
        watchers = []
        flags = gobject.IO_IN | gobject.IO_ERR | gobject.IO_HUP
        if self.transaction.terminal:
            # Setup copying of i/o between the controlling terminals
            watchers.append(gobject.io_add_watch(terminal_fd, flags,
                                                 self._copy_io))
        watchers.append(gobject.io_add_watch(self.master_fd, flags,
                                             self._copy_io_master, terminal_fd))
        # Monitor the child process
        watchers.append(gobject.child_watch_add(pid, self._on_child_exit))
        # Watch for status updates
        watchers.append(gobject.io_add_watch(self.status_parent_fd,
                                             gobject.IO_IN,
                                             self._on_status_update))
        while self._child_exit == -1:
            gobject.main_context_default().iteration()
        for id in watchers:
            gobject.source_remove(id)
        # Restore the settings of the transaction terminal
        if terminal_fd:
            try:
                termios.tcsetattr(terminal_fd, termios.TCSADRAIN, terminal_attr)
            except termios.error:
                pass
        # Make sure all file descriptors are closed
        for fd in [self.master_fd, self.status_parent_fd, terminal_fd]:
            try:
                os.close(fd)
            except (OSError, TypeError):
                pass
        return os.WEXITSTATUS(self._child_exit)

    def _on_child_exit(self, pid, condition):
        log.debug("Child exited: %s", condition)
        self._child_exit = condition
        return False

    def _on_status_update(self, source, condition):
        log.debug("UpdateInterface")
        status_msg = ""
        try:
            while not status_msg.endswith("\n"):
                self.last_activity = time.time()
                status_msg += os.read(source, 1)
        except:
            return False
        try:
            (status, pkg, percent, message_raw) = status_msg.split(":", 3)
        except ValueError:
            # silently ignore lines that can't be parsed
            return True
        message = message_raw.strip()
        #print "percent: %s %s" % (pkg, float(percent)/100.0)
        if status == "pmerror":
            self._error(pkg, message)
        elif status == "pmconffile":
            # we get a string like this:
            # 'current-conffile' 'new-conffile' useredited distedited
            match = re.match("\s*\'(.*)\'\s*\'(.*)\'.*", message_raw)
            if match:
                new, old = match.group(1), match.group(2)
                self._conffile(new, old)
        elif status == "pmstatus":
            self._status_changed(pkg, float(percent), message)
        # catch a time out by sending crtl+c
        if self.last_activity + INSTALL_TIMEOUT < time.time() and \
           self.child_pid:
            log.critical("Killing child since timeout of %s s", INSTALL_TIMEOUT)
            os.kill(self.child_pid, 15)
        return True

    def _fork(self):
        """Fork and create a master/slave pty pair by which the forked process
        can be controlled.
        """
        pid, self.master_fd = os.forkpty()
        return pid

    def _setup_child(self):
        """Setup the environemnt of the child process."""
        def interrupt_handler(signum, frame):
            # Exit the child immediately if we receive the interrupt
            # signal or a Ctrl+C - otherwise the atexit methods would
            # be called, e.g. the frozen status decorator
            os._exit(apt_pkg.PackageManager.RESULT_FAILED)
        signal.signal(signal.SIGINT, interrupt_handler)
        # Make sure that exceptions of the child are not catched by apport
        sys.excepthook = sys.__excepthook__

        mainloop.quit()
        # Switch to the language of the user
        if self.transaction.locale:
            os.putenv("LANG", self.transaction.locale)
        # Either connect to the controllong terminal or switch to
        # non-interactive mode
        if not self.transaction.terminal:
            # FIXME: we should check for "mail" or "gnome" here
            #        and not unset in this case
            os.putenv("APT_LISTCHANGES_FRONTEND", "none")
            os.putenv("APT_LISTBUGS_FRONTEND", "none")
        else:
            #FIXME: Should this be a setting?
            os.putenv("TERM", "linux")
        # Run debconf through a proxy if available
        if self.transaction.debconf:
            os.putenv("DEBCONF_PIPE", self.transaction.debconf)
            os.putenv("DEBIAN_FRONTEND", "passthrough")
            if log.level == logging.DEBUG:
                os.putenv("DEBCONF_DEBUG",".")
        elif not self.transaction.terminal:
            os.putenv("DEBIAN_FRONTEND", "noninteractive")
        # Proxy configuration
        if self.transaction.http_proxy:
            apt_pkg.config.set("Acquire::http::Proxy",
                               self.transaction.http_proxy)
        # Mark changes as being make by aptdaemon
        cmd = "aptdaemon role='%s' sender='%s'" % (self.transaction.role,
                                                   self.transaction.sender)
        apt_pkg.config.set("CommandLine::AsString", cmd)

    def _copy_io_master(self, source, condition, target):
        if condition == gobject.IO_IN:
            self.last_activity = time.time()
            try:
                char = os.read(source, 1)
            except OSError:
                log.debug("Faild to read from master")
                return True
            # Write all the output from dpkg to a log
            if char == "\n":
                # Skip ANSI characters from the console output
                line = re.sub(REGEX_ANSI_ESCAPE_CODE, "", self._line_buffer)
                if line:
                    log_terminal.debug(line)
                    self.output += line + "\n"
                self._line_buffer = ""
            else:
                self._line_buffer += char
            if target:
                try:
                    os.write(target, char)
                except OSError:
                    log.debug("Failed to write to controlling terminal")
            return True
        try:
            os.close(source)
        except OSError:
            # Could already be closed by the clean up in run()
            pass
        return False
 
    def _copy_io(self, source, condition):
        if condition == gobject.IO_IN:
            char = os.read(source, 1)
            # Detect config file prompt answers on the console
            # FIXME: Perhaps should only set the
            # self.transaction.config_file_prompt_answer and not write
            if self.transaction.paused and \
               self.transaction.config_file_conflict:
                self.transaction.config_file_conflict_resolution = None
                self.transaction.paused = False
            try:
                os.write(self.master_fd, char)
            except:
                pass
            else:
                return True
        os.close(source)
        return False

    def _status_changed(self, pkg, percent, status):
        """Callback to update status information"""
        log.debug("APT status: %s" % status)
        progress = self.progress_begin + percent / 100 * \
                   (self.progress_end - self.progress_begin)
        if self.progress < progress:
            self.transaction.progress = int(progress)
            self.progress = progress
        fs_enc = sys.getfilesystemencoding()
        self.transaction.status_details = status.decode(fs_enc, "ignore")

    def _conffile(self, current, new):
        """Callback for a config file conflict"""
        log.warning("Config file prompt: '%s' (%s)" % (current, new))
        self.transaction.config_file_conflict = (current, new)
        self.transaction.paused = True
        self.transaction.status = enums.STATUS_WAITING_CONFIG_FILE_PROMPT
        while self.transaction.paused:
            gobject.main_context_default().iteration()
        log.debug("Sending config file answer: %s",
                  self.transaction.config_file_conflict_resolution)
        if self.transaction.config_file_conflict_resolution == "replace":
            os.write(self.master_fd, "y\n")
        elif self.transaction.config_file_conflict_resolution == "keep":
            os.write(self.master_fd, "n\n")
        self.transaction.config_file_conflict_resolution = None
        self.transaction.config_file_conflict = None
        self.transaction.status = enums.STATUS_COMMITTING
        return True

    def _error(self, pkg, msg):
        """Callback for an error"""
        log.critical("%s: %s" % (pkg, msg))


class DaemonDpkgInstallProgress(DaemonInstallProgress):

    """Progress handler for a local Debian package installation."""

    def __init__(self, transaction, begin=101, end=101):
        DaemonInstallProgress.__init__(self, transaction, begin, end)

    def _child(self, debfile):
        args = [apt_pkg.config["Dir::Bin::DPkg"], "--status-fd",
                str(self.status_child_fd)]
        args.extend(apt_pkg.config.value_list("DPkg::Options"))
        if not self.transaction.terminal:
            args.extend(["--force-confdef", "--force-confold"])
        args.extend(["-i", debfile])
        os.execlp(apt_pkg.config["Dir::Bin::DPkg"], *args)

    def _on_status_update(self, source, condition):
        log.debug("UpdateInterface")
        status_raw = ""
        try:
            while not status_raw.endswith("\n"):
                status_raw += os.read(source, 1)
        except:
            return False
        try:
            status = [s.strip() for s in status_raw.split(":", 3)]
        except ValueError:
            # silently ignore lines that can't be parsed
            return True
        # Parse the status message. It can be of the following types:
        #  - "status: PACKAGE: STATUS"
        #  - "status: PACKAGE: error: MESSAGE"
        #  - "status: FILE: conffile: 'OLD' 'NEW' useredited distedited"
        #  - "processing: STAGE: PACKAGE" with STAGE is one of upgrade,
        #    install, configure, trigproc, remove, purge
        if status[0] == "status":
            if status[2] == "error":
                self._error(status[1], status[3])
            elif status[2] == "conffile":
                match = re.match("\s*\'(.*)\'\s*\'(.*)\'.*", status[3])
                if match:
                    new, old = match.group(1), match.group(2)
                    self._conffile(new, old)
            elif status == "status":

                self._status_changed(pkg=status[1], percent=101,
                                     status=status[2])
        elif status[0] == "processing":
            try:
                msg = self.transaction.gettext(MAP_STAGE[status[1]]) % status[2]
            except ValueError, IndexError:
                msg = self.transaction.gettext(status[1])
            self._status_changed(pkg=status[2], percent=101, status=msg)
        return True


class DaemonDpkgRecoverProgress(DaemonDpkgInstallProgress):

    """Progress handler for dpkg --confiure -a call."""

    def _child(self):
        args = [apt_pkg.config["Dir::Bin::Dpkg"], "--status-fd",
                str(self.status_child_fd), "--configure", "-a"]
        args.extend(apt_pkg.config.value_list("Dpkg::Options"))
        if not self.transaction.terminal:
            args.extend(["--force-confdef", "--force-confold"])
        os.execlp(apt_pkg.config["Dir::Bin::DPkg"], *args)


class DaemonDpkgReconfigureProgress(DaemonDpkgInstallProgress):

    """Progress handler for dpkg-reconfigure call."""

    def _child(self, packages, priority, ):
        args = ["/usr/sbin/dpkg-reconfigure"]
        if priority != "default":
            args.extend(["--priority", priority])
        args.extend(packages)
        os.execlp("/usr/sbin/dpkg-reconfigure", *args)


# vim:ts=4:sw=4:et
