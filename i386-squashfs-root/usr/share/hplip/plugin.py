#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# (c) Copyright 2003-2009 Hewlett-Packard Development Company, L.P.
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#
# Author: Don Welch
#

__version__ = '2.1'
__mod__ = 'hp-plugin'
__title__ = 'Plugin Download and Install Utility'
__doc__ = ""

# Std Lib
import sys
import getopt
import time
import os.path
import re
import os
import gzip

# Local
from base.g import *
from base import device, utils, tui, module
from prnt import cups

pm = None

def plugin_download_callback(c, s, t):
    pm.update(int(100*c*s/t),
             utils.format_bytes(c*s))


def plugin_install_callback(s):
    print s



USAGE = [ (__doc__, "", "name", True),
          ("Usage: %s [MODE] [OPTIONS]" % __mod__, "", "summary", True),
          utils.USAGE_MODE,
          utils.USAGE_GUI_MODE,
          utils.USAGE_INTERACTIVE_MODE,
          ("Installation for required printer mode:", "--required (Qt4 only)", "option", False),
          ("Installation for optional printer mode:", "--optional (Qt4 only)", "option", False),
          #("Installation generic mode:", "--generic (default)", "option", False),
          utils.USAGE_LANGUAGE,
          utils.USAGE_OPTIONS,
          ("Specify the path to the plugin file:", "-p <path> or --path=<path> or --plugin=<path>", "option", False),
          utils.USAGE_LOGGING1, utils.USAGE_LOGGING2, utils.USAGE_LOGGING3,
          utils.USAGE_HELP,
          utils.USAGE_SPACE,
          utils.USAGE_SEEALSO,
          ("hp-setup", "", "seealso", False),
          ("hp-firmware", "", "seealso", False),
        ]


mod = module.Module(__mod__, __title__, __version__, __doc__, USAGE,
                    (INTERACTIVE_MODE, GUI_MODE),
                    (UI_TOOLKIT_QT3, UI_TOOLKIT_QT4), True)

opts, device_uri, printer_name, mode, ui_toolkit, loc = \
    mod.parseStdOpts('p:', ['path=', 'plugin=', 'plug-in=', 'reason=',
                            'generic', 'optional', 'required'],
                     handle_device_printer=False)

plugin_path = None
install_mode = PLUGIN_NONE # reuse plugin types for mode (PLUGIN_NONE = generic)
plugin_reason = PLUGIN_REASON_NONE

for o, a in opts:
    if o in ('-p', '--path', '--plugin', '--plug-in'):
        plugin_path = os.path.normpath(os.path.abspath(os.path.expanduser(a)))

    elif o == '--required':
        install_mode = PLUGIN_REQUIRED
        if ui_toolkit == 'qt3':
            log.warn("--required switch ignored.")

    elif o == '--optional':
        install_mode = PLUGIN_OPTIONAL
        if ui_toolkit == 'qt3':
            log.warn("--optional switch ignored.")

    elif o == '--reason':
        plugin_reason = int(a)


version = prop.installed_version
plugin_filename = 'hplip-%s-plugin.run' % version

if plugin_path is not None:
    if not os.path.exists(plugin_path):
        log.error("Plug-in path '%s' not found." % plugin_path)
        sys.exit(1)

    if os.path.isdir(plugin_path):
        plugin_path = os.path.join(plugin_path, 'hplip-%s-plugin.run' % version)

        if not os.path.exists(plugin_path):
            log.error("Plug-in path '%s' not found." % plugin_path)
            sys.exit(1)

    if os.path.basename(plugin_path) != plugin_filename:
        log.error("Plug-in filename must be '%s'." % plugin_filename)
        sys.exit(1)


    size, checksum, timestamp = os.stat(plugin_path)[6], '', 0.0
    plugin_path = 'file://' + plugin_path
    log.debug("Plugin path=%s (%d)" % (plugin_path, size))


if mode == GUI_MODE:
    if ui_toolkit == 'qt3':
        if not utils.canEnterGUIMode():
            log.error("%s requires GUI support (try running with --qt4). Try using interactive (-i) mode." % __mod__)
            sys.exit(1)
    else:
        if not utils.canEnterGUIMode4():
            log.error("%s requires GUI support (try running with --qt3). Try using interactive (-i) mode." % __mod__)
            sys.exit(1)


PKIT = utils.to_bool(sys_conf.get('configure', 'policy-kit'))
if PKIT:
    try:
        from base.pkit import *
        try:
            pkit = PolicyKit()
            pkit_installed = True
        except dbus.DBusException, ex:
            log.error("PolicyKit support requires DBUS or PolicyKit support files missing")
            pkit_installed = False
    except:
        log.error("Unable to load pkit...is HPLIP installed?")
        pkit_installed = False
else:
    pkit_installed = False


if mode == GUI_MODE:
    if ui_toolkit == 'qt3':
        try:
            from qt import *
            from ui import pluginform2
        except ImportError:
            log.error("Unable to load Qt3 support. Is it installed?")
            sys.exit(1)

        app = QApplication(sys.argv)
        QObject.connect(app, SIGNAL("lastWindowClosed()"), app, SLOT("quit()"))

        if loc is None:
            loc = user_conf.get('ui', 'loc', 'system')
            if loc.lower() == 'system':
                loc = str(QTextCodec.locale())
                log.debug("Using system locale: %s" % loc)

        if loc.lower() != 'c':
            e = 'utf8'
            try:
                l, x = loc.split('.')
                loc = '.'.join([l, e])
            except ValueError:
                l = loc
                loc = '.'.join([loc, e])

            log.debug("Trying to load .qm file for %s locale." % loc)
            trans = QTranslator(None)

            qm_file = 'hplip_%s.qm' % l
            log.debug("Name of .qm file: %s" % qm_file)
            loaded = trans.load(qm_file, prop.localization_dir)

            if loaded:
                app.installTranslator(trans)
            else:
                loc = 'c'

        if loc == 'c':
            log.debug("Using default 'C' locale")
        else:
            log.debug("Using locale: %s" % loc)
            QLocale.setDefault(QLocale(loc))
            prop.locale = loc
            try:
                locale.setlocale(locale.LC_ALL, locale.normalize(loc))
            except locale.Error:
                pass

        if not pkit_installed and not os.geteuid() == 0:
            log.error("You must be root to run this utility.")

            QMessageBox.critical(None,
                                 "HP Device Manager - Plug-in Installer",
                                 "You must be root to run hp-plugin.",
                                  QMessageBox.Ok,
                                  QMessageBox.NoButton,
                                  QMessageBox.NoButton)

            sys.exit(1)

        w = pluginform2.PluginForm2()
        app.setMainWidget(w)
        w.show()

        app.exec_loop()

    else: # qt4
        try:
            from PyQt4.QtGui import QApplication, QMessageBox
            from ui4.plugindialog import PluginDialog
        except ImportError:
            log.error("Unable to load Qt4 support. Is it installed?")
            sys.exit(1)

        app = QApplication(sys.argv)

        if not pkit_installed and not os.geteuid() == 0:
            log.error("You must be root to run this utility.")

            QMessageBox.critical(None,
                                 "HP Device Manager - Plug-in Installer",
                                 "You must be root to run hp-plugin.",
                                  QMessageBox.Ok,
                                  QMessageBox.NoButton,
                                  QMessageBox.NoButton)

            sys.exit(1)


        dialog = PluginDialog(None, install_mode, plugin_reason)
        dialog.show()
        try:
            log.debug("Starting GUI loop...")
            app.exec_()
        except KeyboardInterrupt:
            log.error("User exit")
            sys.exit(0)


else: # INTERACTIVE_MODE
    try:
        if not os.geteuid() == 0:
            log.error("You must be root to run this utility.")
            sys.exit(1)

        log.info("(Note: Defaults for each question are maked with a '*'. Press <enter> to accept the default.)")
        log.info("")

        from installer import core_install
        core = core_install.CoreInstall()

        core.set_plugin_version()

        tui.header("PLUG-IN INSTALLATION FOR HPLIP %s" % version)

        if core.check_for_plugin() and plugin_path is None:
            log.info("The driver plugin for HPLIP %s appears to already be installed." % version)

            cont, ans = tui.enter_yes_no("Do you wish to download and re-install the plug-in?")

            if not cont or not ans:
                sys.exit(0)


        if plugin_path is None:
            table = tui.Formatter(header=('Option', 'Description'), min_widths=(10, 50))
            table.add(('d', 'Download plug-in from HP (recomended)'))
            table.add(('p', 'Specify a path to the plug-in (advanced)'))
            table.add(('q', 'Quit hp-plugin (skip installation)'))

            table.output()

            cont, ans = tui.enter_choice("\nEnter option (d=download*, p=specify path, q=quit) ? ",
                ['d', 'p'], 'd')

            if not cont: # q
                sys.exit(0)


            if ans == 'd': # d - download
                # read plugin.conf (local or on sf.net) to get plugin_path (http://)
                plugin_conf_url = core.get_plugin_conf_url()

                if plugin_conf_url.startswith('file://'):
                    tui.header("COPY CONFIGURATION")
                else:
                    tui.header("DOWNLOAD CONFIGURATION")

                    log.info("Checking for network connection...")
                    ok = core.check_network_connection()

                    if not ok:
                        log.error("Network connection not detected.")
                        sys.exit(1)


                log.info("Downloading configuration file from: %s" % plugin_conf_url)
                pm = tui.ProgressMeter("Downloading configuration:")

                plugin_path, size, checksum, timestamp, ok = core.get_plugin_info(plugin_conf_url,
                    plugin_download_callback)

                print

                if not plugin_path.startswith('http://') and not plugin_path.startswith('file://'):
                    plugin_path = 'file://' + plugin_path

            else: # p - specify plugin path

                while True:
                    plugin_path = raw_input(log.bold("Enter the path to the 'hplip-%s-plugin.run' file (q=quit) : " %
                        version)).strip()

                    if plugin_path.strip().lower() == 'q':
                        sys.exit(1)

                    if not plugin_path.startswith('http://'):
                        plugin_path = os.path.normpath(os.path.abspath(os.path.expanduser(plugin_path)))

                        if not os.path.exists(plugin_path):
                            log.error("Plug-in path '%s' not found." % plugin_path)
                            continue

                        if os.path.isdir(plugin_path):
                            plugin_path = os.path.join(plugin_path, plugin_filename)

                            if not os.path.exists(plugin_path):
                                log.error("Plug-in path '%s' not found." % plugin_path)
                                continue

                        if os.path.basename(plugin_path) != plugin_filename:
                            log.error("Plug-in filename must be '%s'." % plugin_filename)
                            continue

                        size, checksum, timestamp = os.stat(plugin_path)[6], '', 0.0
                        plugin_path = 'file://' + plugin_path

                    break


        if plugin_path.startswith('file://'):
            tui.header("COPY PLUGIN")
        else:
            tui.header("DOWNLOAD PLUGIN")

            log.info("Checking for network connection...")
            ok = core.check_network_connection()

            if not ok:
                log.error("Network connection not detected.")
                sys.exit(1)

        log.info("Downloading plug-in from: %s" % plugin_path)
        pm = tui.ProgressMeter("Downloading plug-in:")

        status, ret = core.download_plugin(plugin_path, size, checksum, timestamp, plugin_download_callback)
        print

        if status in (core_install.PLUGIN_INSTALL_ERROR_UNABLE_TO_RECV_KEYS, core_install.PLUGIN_INSTALL_ERROR_DIGITAL_SIG_NOT_FOUND):
            log.error("Digital signature file download failed. Without this file, it is not possible to authenticate and validate the plug-in prior to installation.")
            cont, ans = tui.enter_yes_no("Do you still want to install the plug-in?", 'n')

            if not cont or not ans:
                sys.exit(0)

        elif status != core_install.PLUGIN_INSTALL_ERROR_NONE:

            if status == core_install.PLUGIN_INSTALL_ERROR_PLUGIN_FILE_NOT_FOUND:
                desc = "Plug-in file not found (server returned 404 or similar error). Error code: %s" % str(ret)

            elif status == core_install.PLUGIN_INSTALL_ERROR_DIGITAL_SIG_BAD:
                desc = "Plug-in file does not match its digital signature. File may have been corrupted or altered. Error code: %s" % str(ret)

            elif status == core_install.PLUGIN_INSTALL_ERROR_PLUGIN_FILE_CHECKSUM_ERROR:
                desc = "Plug-in file does not match its checksum. File may have been corrupted or altered."

            elif status == core_install.PLUGIN_INSTALL_ERROR_NO_NETWORK:
                desc = "Unable to connect to network to download the plug-in. Please check your network connection and try again."

            elif status == core_install.PLUGIN_INSTALL_ERROR_DIRECTORY_ERROR:
                desc = "Unable to create the plug-in directory. Please check your permissions and try again."

            core.delete_plugin()
            log.error(desc)
            sys.exit(1)


        tui.header("INSTALLING PLUG-IN")

        core.run_plugin(mode, plugin_install_callback)

        cups_devices = device.getSupportedCUPSDevices(['hp']) #, 'hpfax'])
        #print cups_devices

        title = False

        for dev in cups_devices:
            mq = device.queryModelByURI(dev)

            if mq.get('fw-download', 0):

                if not title:
                    tui.header("DOWNLOADING FIRMWARE")
                    title = True

                # Download firmware if needed
                log.info(log.bold("\nDownloading firmware to device %s..." % dev))
                try:
                    d = device.Device(dev)
                except Error:
                    log.error("Error opening device. Exiting.")
                    sys.exit(1)

                if d.downloadFirmware():
                    log.info("Firmware download successful.\n")

                d.close()


    except KeyboardInterrupt:
        log.error("User exit")

log.info("")
log.info("Done.")

