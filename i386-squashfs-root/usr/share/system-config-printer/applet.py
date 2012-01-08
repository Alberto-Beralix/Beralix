#!/usr/bin/python

## Copyright (C) 2007, 2008, 2009, 2010, 2011 Red Hat, Inc.
## Author: Tim Waugh <twaugh@redhat.com>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import cups
cups.require ("1.9.42")
import sys
from debug import *

import dbus
import dbus.glib
import dbus.service
import gobject
import time
import locale
import gettext
import cupshelpers.installdriver
from gettext import gettext as _
DOMAIN="system-config-printer"
gettext.textdomain (DOMAIN)
try:
    locale.setlocale (locale.LC_ALL, "")
except locale.Error, e:
    import os
    os.environ['LC_ALL'] = 'C'
    locale.setlocale (locale.LC_ALL, "")

try:
    import pynotify
except RuntimeError, e:
    print "%s:" % DOMAIN, e
    print "This is a graphical application and requires DISPLAY to be set."
    sys.exit (1)

APPDIR="/usr/share/system-config-printer"
ICON="printer"

# We need to call pynotify.init before we can check the server for caps
pynotify.init('System Config Printer Notification')

# D-Bus APIs of other objects we'll use.
PRINTING_BUS="org.fedoraproject.Config.Printing"
PRINTING_PATH="/org/fedoraproject/Config/Printing"
PRINTING_IFACE="org.fedoraproject.Config.Printing"
NEWPRINTERDIALOG_IFACE=PRINTING_IFACE + ".NewPrinterDialog"
PRINTERPROPERTIESDIALOG_IFACE=PRINTING_IFACE + ".PrinterPropertiesDialog"

####
#### NewPrinterNotification DBus server (the 'new' way).
####
PDS_PATH="/com/redhat/NewPrinterNotification"
PDS_IFACE="com.redhat.NewPrinterNotification"
PDS_OBJ="com.redhat.NewPrinterNotification"
class NewPrinterNotification(dbus.service.Object):
    STATUS_SUCCESS = 0
    STATUS_MODEL_MISMATCH = 1
    STATUS_GENERIC_DRIVER = 2
    STATUS_NO_DRIVER = 3

    def __init__ (self, system_bus, session_bus):
        self.system_bus = system_bus
        self.session_bus = session_bus
        self.getting_ready = 0
        bus_name = dbus.service.BusName (PDS_OBJ, bus=system_bus)
        dbus.service.Object.__init__ (self, bus_name, PDS_PATH)
        self.notification = None

    @dbus.service.method(PDS_IFACE, in_signature='', out_signature='')
    def GetReady (self):
        TIMEOUT=1200000
        if self.getting_ready == 0:
            n = pynotify.Notification (_("Configuring new printer"),
                                       _("Please wait..."),
                                       'printer')
            n.set_timeout (TIMEOUT + 5000)
            n.set_data ('closed', False)
            n.connect ('closed', self.on_notification_closed)
            n.show ()
            self.notification = n

        self.getting_ready += 1
        gobject.timeout_add_seconds (TIMEOUT, self.timeout_ready)

    def on_notification_closed (self, notification):
        notification.set_data ('closed', True)

    def timeout_ready (self):
        if self.getting_ready > 0:
            self.getting_ready -= 1
        if (self.getting_ready == 0 and
            self.notification and
            not self.notification.get_data ('closed')):
            self.notification.close ()

        return False

    @dbus.service.method(PDS_IFACE, in_signature='isssss', out_signature='')
    def NewPrinter (self, status, name, mfg, mdl, des, cmd):
        if name.find("/") >= 0:
            # name is a URI, no queue was generated, because no suitable
            # driver was found
            title = _("Missing printer driver")
            devid = "MFG:%s;MDL:%s;DES:%s;CMD:%s;" % (mfg, mdl, des, cmd)
            if (mfg and mdl) or des:
                if (mfg and mdl):
                    device = "%s %s" % (mfg, mdl)
                else:
                    device = des
                text = _("No printer driver for %s.") % device
            else:
                text = _("No driver for this printer.")
            n = pynotify.Notification (title, text, 'printer')
            if "actions" in pynotify.get_server_caps():
                n.set_urgency (pynotify.URGENCY_CRITICAL)
                n.set_timeout (pynotify.EXPIRES_NEVER)
                n.add_action ("setup-printer", _("Search"),
                              lambda x, y:
                                  self.setup_printer (x, y, name, devid))
            else:
                self.setup_printer (None, None, name, devid)

        else:
            # name is the name of the queue which hal_lpadmin has set up
            # automatically.
            c = cups.Connection ()
            try:
                printer = c.getPrinters ()[name]
            except KeyError:
                return

            try:
                filename = c.getPPD (name)
            except cups.IPPError:
                return

            del c

            # Check for missing packages
            cups.ppdSetConformance (cups.PPD_CONFORM_RELAXED)
            ppd = cups.PPD (filename)
            import os
            os.unlink (filename)
            import sys
            sys.path.append (APPDIR)
            import cupshelpers
            (missing_pkgs,
             missing_exes) = cupshelpers.missingPackagesAndExecutables (ppd)

            from cupshelpers.ppds import ppdMakeModelSplit
            (make, model) = ppdMakeModelSplit (printer['printer-make-and-model'])
            driver = make + " " + model
            if status < self.STATUS_GENERIC_DRIVER:
                title = _("Printer added")
            else:
                title = _("Missing printer driver")

            if len (missing_pkgs) > 0:
                pkgs = reduce (lambda x,y: x + ", " + y, missing_pkgs)
                title = _("Install printer driver")
                text = _("`%s' requires driver installation: %s.") % (name, pkgs)
                n = pynotify.Notification (title, text)
                import installpackage
                if "actions" in pynotify.get_server_caps():
                    try:
                        self.packagekit = installpackage.PackageKit ()
                        n.set_timeout (pynotify.EXPIRES_NEVER)
                        n.add_action ("install-driver", _("Install"),
                                      lambda x, y:
                                          self.install_driver (x, y,
                                                               missing_pkgs))
                    except:
                        pass
                else:
                    try:
                        self.packagekit = installpackage.PackageKit ()
                        self.packagekit.InstallPackageName (0, 0,
                                                            missing_pkgs[0])
                    except:
                        pass

            elif status == self.STATUS_SUCCESS:
                devid = "MFG:%s;MDL:%s;DES:%s;CMD:%s;" % (mfg, mdl, des, cmd)
                text = _("`%s' is ready for printing.") % name
                n = pynotify.Notification (title, text)
                if "actions" in pynotify.get_server_caps():
                    n.set_urgency (pynotify.URGENCY_NORMAL)
                    n.add_action ("test-page", _("Print test page"),
                                  lambda x, y:
                                      self.print_test_page (x, y, name))
                    n.add_action ("configure", _("Configure"),
                                  lambda x, y: self.configure (x, y, name))
            else: # Model mismatch
                devid = "MFG:%s;MDL:%s;DES:%s;CMD:%s;" % (mfg, mdl, des, cmd)
                text = (_("`%s' has been added, using the `%s' driver.") %
                        (name, driver))
                n = pynotify.Notification (title, text, 'printer')
                if "actions" in pynotify.get_server_caps():
                    n.set_urgency (pynotify.URGENCY_CRITICAL)
                    n.add_action ("test-page", _("Print test page"),
                                  lambda x, y:
                                      self.print_test_page (x, y, name, devid))
                    n.add_action ("find-driver", _("Find driver"),
                                  lambda x, y: 
                                  self.find_driver (x, y, name, devid))
                    n.set_timeout (pynotify.EXPIRES_NEVER)
                else:
                    self.configure (None, None, name)

        self.timeout_ready ()
        n.show ()
        self.notification = n

    def print_test_page (self, notification, action, name):
        path = self.configure (None, None, name)
        obj = self.session_bus.get_object (PRINTING_BUS, path)
        iface = dbus.Interface (obj, PRINTERPROPERTIESDIALOG_IFACE)
        iface.PrintTestPage ()

    def configure (self, notification, action, name):
        obj = self.session_bus.get_object (PRINTING_BUS, PRINTING_PATH)
        iface = dbus.Interface (obj, PRINTING_IFACE)
        return iface.PrinterPropertiesDialog (dbus.UInt32(0), name)

    def get_newprinterdialog_interface (self):
        obj = self.session_bus.get_object (PRINTING_BUS, PRINTING_PATH)
        iface = dbus.Interface (obj, PRINTING_IFACE)
        path = iface.NewPrinterDialog ()
        obj = self.session_bus.get_object (PRINTING_BUS, path)
        iface = dbus.Interface (obj, NEWPRINTERDIALOG_IFACE)
        return iface

    def ignore_dbus_replies (self, *args):
        pass

    def find_driver (self, notification, action, name, devid = ""):
        try:
            iface = self.get_newprinterdialog_interface ()
            iface.ChangePPD (dbus.UInt32(0), name, devid,
                             reply_handler=self.ignore_dbus_replies,
                             error_handler=self.ignore_dbus_replies)
        except dbus.DBusException:
            pass

    def setup_printer (self, notification, action, uri, devid = ""):
        try:
            iface = self.get_newprinterdialog_interface ()
            iface.NewPrinterFromDevice (dbus.UInt32(0), uri, devid,
                                        reply_handler=self.ignore_dbus_replies,
                                        error_handler=self.ignore_dbus_replies)
        except dbus.DBusException:
            pass

    def install_driver (self, notification, action, missing_pkgs):
        try:
            self.packagekit.InstallPackageName (0, 0, missing_pkgs[0])
        except:
            pass

    def collect_exit_code (self, pid):
        # We do this with timers instead of signals because we already
        # have gobject imported, but don't (yet) import signal;
        # let's try not to inflate the process size.
        import os
        try:
            print "Waiting for child %d" % pid
            (pid, status) = os.waitpid (pid, os.WNOHANG)
            if pid == 0:
                # Run this timer again.
                return True
        except OSError:
            pass

        return False

PROGRAM_NAME="system-config-printer-applet"
def show_help ():
    print "usage: %s [--help|--version|--debug]" % PROGRAM_NAME

def show_version ():
    import config
    print "%s %s" % (PROGRAM_NAME, config.VERSION)
    
####
#### Main program entry
####

def monitor_session (*args):
    pass

def any_jobs ():
    try:
        c = cups.Connection ()
        jobs = c.getJobs (my_jobs=True, limit=1)
        if len (jobs):
            return True
    except:
        pass

    return False

class RunLoop:
    DBUS_PATH="/com/redhat/PrinterSpooler"
    DBUS_IFACE="com.redhat.PrinterSpooler"

    def __init__ (self, session_bus, system_bus, loop):
        self.system_bus = system_bus
        self.session_bus = session_bus
        self.loop = loop
        self.timer = None
        system_bus.add_signal_receiver (self.handle_dbus_signal,
                                        path=self.DBUS_PATH,
                                        dbus_interface=self.DBUS_IFACE)
        self.check_for_jobs ()

    def remove_signal_receiver (self):
        self.system_bus.remove_signal_receiver (self.handle_dbus_signal,
                                                path=self.DBUS_PATH,
                                                dbus_interface=self.DBUS_IFACE)

    def run (self):
        self.loop.run ()

    def __del__ (self):
        self.remove_signal_receiver ()
        if self.timer:
            gobject.source_remove (self.timer)

    def handle_dbus_signal (self, *args):
        if self.timer:
            gobject.source_remove (self.timer)
        self.timer = gobject.timeout_add (200, self.check_for_jobs)

    def check_for_jobs (self, *args):
        debugprint ("checking for jobs")
        if any_jobs ():
            if self.timer != None:
                gobject.source_remove (self.timer)

            self.remove_signal_receiver ()

            # Start the job applet.
            debugprint ("Starting job applet")
            try:
                obj = self.session_bus.get_object (PRINTING_BUS, PRINTING_PATH)
                iface = dbus.Interface (obj, PRINTING_IFACE)
                path = iface.JobApplet ()
                debugprint ("Job applet is %s" % path)
            except dbus.DBusException, e:
                try:
                    print e
                except:
                    pass

        # Don't run this timer again.
        return False

if __name__ == '__main__':
    import sys, getopt
    try:
        opts, args = getopt.gnu_getopt (sys.argv[1:], '',
                                        ['debug',
                                         'help',
                                         'version'])
    except getopt.GetoptError:
        show_help ()
        sys.exit (1)

    for opt, optarg in opts:
        if opt == "--help":
            show_help ()
            sys.exit (0)
        if opt == "--version":
            show_version ()
            sys.exit (0)
        elif opt == "--debug":
            set_debugging (True)

    # Must be done before connecting to D-Bus (for some reason).
    if not pynotify.init (PROGRAM_NAME):
        try:
            print >> sys.stderr, ("%s: unable to initialize pynotify" %
                                  PROGRAM_NAME)
        except:
            pass

    system_bus = session_bus = None
    try:
        system_bus = dbus.SystemBus()
    except:
        try:
            print >> sys.stderr, ("%s: failed to connect to system D-Bus" %
                                  PROGRAM_NAME)
        finally:
            sys.exit (1)

    try:
        session_bus = dbus.SessionBus()
        # Stop running when the session ends.
        session_bus.add_signal_receiver (monitor_session)
    except:
        try:
            print >> sys.stderr, ("%s: failed to connect to "
                                  "session D-Bus" % PROGRAM_NAME)
        finally:
            sys.exit (1)

    try:
        NewPrinterNotification(system_bus, session_bus)
    except:
        try:
            print >> sys.stderr, ("%s: failed to start "
                                  "NewPrinterNotification service" %
                                  PROGRAM_NAME)
        except:
            pass

    try:
        cupshelpers.installdriver.set_debugprint_fn (debugprint)
        cupshelpers.installdriver.PrinterDriversInstaller(system_bus)
    except Exception, e:
        try:
            print >> sys.stderr, ("%s: failed to start "
                                  "PrinterDriversInstaller service: "
                                  "%s" % (PROGRAM_NAME, e))
        except:
            pass

    loop = gobject.MainLoop ()
    runloop = RunLoop (session_bus, system_bus, loop)
    try:
        runloop.run ()
    except KeyboardInterrupt:
        pass
