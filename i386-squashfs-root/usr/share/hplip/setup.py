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


__version__ = '9.0'
__title__ = 'Printer/Fax Setup Utility'
__mod__ = 'hp-setup'
__doc__ = "Installs HPLIP printers and faxes in the CUPS spooler. Tries to automatically determine the correct PPD file to use. Allows the printing of a testpage. Performs basic fax parameter setup."

# Std Lib
import sys
import getopt
import time
import os.path
import re
import os
import gzip

try:
    import readline
except ImportError:
    pass

# Local
from base.g import *
from base import device, utils, tui, models, module
from prnt import cups

pm = None

def plugin_download_callback(c, s, t):
    pm.update(int(100*c*s/t),
             utils.format_bytes(c*s))


nickname_pat = re.compile(r'''\*NickName:\s*\"(.*)"''', re.MULTILINE)

USAGE = [ (__doc__, "", "name", True),
          ("Usage: %s [MODE] [OPTIONS] [SERIAL NO.|USB bus:device|IP|DEVNODE]" % __mod__, "", "summary", True),
          utils.USAGE_MODE,
          utils.USAGE_GUI_MODE,
          utils.USAGE_INTERACTIVE_MODE,
          utils.USAGE_SPACE,
          utils.USAGE_OPTIONS,
          ("Automatic mode:", "-a or --auto (-i mode only)", "option", False),
          ("To specify the port on a multi-port JetDirect:", "--port=<port> (Valid values are 1\*, 2, and 3. \*default)", "option", False),
          ("No testpage in automatic mode:", "-x (-i mode only)", "option", False),
          ("To specify a CUPS printer queue name:", "-p<printer> or --printer=<printer> (-i mode only)", "option", False),
          ("To specify a CUPS fax queue name:", "-f<fax> or --fax=<fax> (-i mode only)", "option", False),
          ("Type of queue(s) to install:", "-t<typelist> or --type=<typelist>. <typelist>: print*, fax\* (\*default) (-i mode only)", "option", False),
          ("To specify the device URI to install:", "-d<device> or --device=<device> (--qt4 mode only)", "option", False),
          ("Remove printers or faxes instead of setting-up:", "-r or --rm or --remove (-u only)", "option", False),
          utils.USAGE_LANGUAGE,
          utils.USAGE_LOGGING1, utils.USAGE_LOGGING2, utils.USAGE_LOGGING3,
          utils.USAGE_HELP,
          ("[SERIAL NO.|USB ID|IP|DEVNODE]", "", "heading", False),
          ("USB bus:device (usb only):", """"xxx:yyy" where 'xxx' is the USB bus and 'yyy' is the USB device. (Note: The ':' and all leading zeros must be present.)""", 'option', False),
          ("", "Use the 'lsusb' command to obtain this information.", "option", False),
          ("IPs (network only):", 'IPv4 address "a.b.c.d" or "hostname"', "option", False),
          ("DEVNODE (parallel only):", '"/dev/parportX", X=0,1,2,...', "option", False),
          ("SERIAL NO. (usb and parallel only):", '"serial no."', "option", True),
          utils.USAGE_EXAMPLES,
          ("Setup using GUI mode:", "$ hp-setup", "example", False),
          ("Setup using GUI mode, specifying usb:", "$ hp-setup -b usb", "example", False),
          ("Setup using GUI mode, specifying an IP:", "$ hp-setup 192.168.0.101", "example", False),
          ("One USB printer attached, automatic:", "$ hp-setup -i -a", "example", False),
          ("USB, IDs specified:", "$ hp-setup -i 001:002", "example", False),
          ("Network:", "$ hp-setup -i 66.35.250.209", "example", False),
          ("Network, Jetdirect port 2:", "$ hp-setup -i --port=2 66.35.250.209", "example", False),
          ("Parallel:", "$ hp-setup -i /dev/parport0", "example", False),
          ("USB or parallel, using serial number:", "$ hp-setup -i US12345678A", "example", False),
          ("USB, automatic:", "$ hp-setup -i --auto 001:002", "example", False),
          ("Parallel, automatic, no testpage:", "$ hp-setup -i -a -x /dev/parport0", "example", False),
          ("Parallel, choose device:", "$ hp-setup -i -b par", "example", False),
          utils.USAGE_SPACE,
          utils.USAGE_NOTES,
          ("1. If no serial number, USB ID, IP, or device node is specified, the USB and parallel busses will be probed for devices.", "", 'note', False),
          ("2. Using 'lsusb' to obtain USB IDs: (example)", "", 'note', False),
          ("   $ lsusb", "", 'note', False),
          ("         Bus 003 Device 011: ID 03f0:c202 Hewlett-Packard", "", 'note', False),
          ("   $ hp-setup --auto 003:011", "", 'note', False),
          ("   (Note: You may have to run 'lsusb' from /sbin or another location. Use '$ locate lsusb' to determine this.)", "", 'note', True),
          ("3. Parameters -a, -f, -p, or -t are not valid in GUI (-u) mode.", "", 'note', True),
          utils.USAGE_SPACE,
          utils.USAGE_SEEALSO,
          ("hp-makeuri", "", "seealso", False),
          ("hp-probe", "", "seealso", False),
        ]


def showPasswordUI(prompt):
    import getpass
    print ""
    print log.bold(prompt)
    username = raw_input("Username: ")
    password = getpass.getpass("Password: ")

    return (username, password)


def restart_cups():
    if os.path.exists('/etc/init.d/cups'):
        return '/etc/init.d/cups restart'

    elif os.path.exists('/etc/init.d/cupsys'):
        return '/etc/init.d/cupsys restart'

    else:
        return 'killall -HUP cupsd'


mod = module.Module(__mod__, __title__, __version__, __doc__, USAGE,
                    (INTERACTIVE_MODE, GUI_MODE),
                    (UI_TOOLKIT_QT3, UI_TOOLKIT_QT4),
                    run_as_root_ok=True)

opts, device_uri, printer_name, mode, ui_toolkit, loc = \
    mod.parseStdOpts('axp:P:f:t:b:d:r',
                     ['ttl=', 'filter=', 'search=', 'find=',
                      'method=', 'time-out=', 'timeout=',
                      'printer=', 'fax=', 'type=', 'port=',
                       'auto', 'device=', 'rm', 'remove'],
                      handle_device_printer=False)

selected_device_name = None
printer_name = None
fax_name = None
bus = None
setup_print = True
setup_fax = True
makeuri = None
auto = False
testpage_in_auto_mode = True
jd_port = 1
remove = False

for o, a in opts:
    if o == '-x':
        testpage_in_auto_mode = False

    elif o in ('-P', '-p', '--printer'):
        printer_name = a

    elif o in ('-f', '--fax'):
        fax_name = a

    elif o in ('-d', '--device'):
        device_uri = a

    elif o in ('-b', '--bus'):
        bus = [x.lower().strip() for x in a.split(',')]
        if not device.validateBusList(bus, False):
            mod.usage(error_msg=['Invalid bus name'])

    elif o in ('-t', '--type'):
        setup_fax, setup_print = False, False
        a = a.strip().lower()
        for aa in a.split(','):
            if aa.strip() not in ('print', 'fax'):
                mod.usage(error_msg=['Invalid type.'])

            if aa.strip() == 'print':
                setup_print = True

            elif aa.strip() == 'fax':
                if not prop.fax_build:
                    log.error("Cannot enable fax setup - HPLIP not built with fax enabled.")
                else:
                    setup_fax = True

    elif o == '--port':
        try:
            jd_port = int(a)
        except ValueError:
            #log.error("Invalid port number. Must be between 1 and 3 inclusive.")
            mod.usage(error_msg=['Invalid port number. Must be between 1 and 3 inclusive.'])

    elif o in ('-a', '--auto'):
        auto = True

    elif o in ('-r', '--rm', '--remove'):
        remove = True


try:
    param = mod.args[0]
except IndexError:
    param = ''

log.debug("param=%s" % param)

if printer_name is not None:
   selected_device_name = printer_name
else:
   if fax_name is not None:
      selected_device_name = fax_name
log.debug("selected_device_name=%s" % selected_device_name)

if mode == GUI_MODE:
    if selected_device_name is not None: 
        log.warning("-p or -f option is not supported")
    if ui_toolkit == 'qt3':
        if not utils.canEnterGUIMode():
            log.error("%s requires GUI support (try running with --qt4). Also, try using interactive (-i) mode." % __mod__)
            sys.exit(1)
    else:
        if not utils.canEnterGUIMode4():
            log.error("%s requires GUI support (try running with --qt3). Also, try using interactive (-i) mode." % __mod__)
            sys.exit(1)

if mode == GUI_MODE:
    if ui_toolkit == 'qt3':
        try:
            from qt import *
            from ui import setupform
        except ImportError:
            log.error("Unable to load Qt3 support. Is it installed?")
            sys.exit(1)

        if remove:
            log.warn("-r/--rm/--remove not supported in qt3 mode.")

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

        try:
            w = setupform.SetupForm(bus, param, jd_port)
        except Error:
            log.error("Unable to connect to HPLIP I/O. Please (re)start HPLIP and try again.")
            sys.exit(1)

        app.setMainWidget(w)
        w.show()

        app.exec_loop()

    else: # qt4
        try:
            from PyQt4.QtGui import QApplication, QMessageBox
            from ui4.setupdialog import SetupDialog
        except ImportError:
            log.error("Unable to load Qt4 support. Is it installed?")
            sys.exit(1)

        app = QApplication(sys.argv)
        log.debug("Sys.argv=%s printer_name=%s param=%s jd_port=%s device_uri=%s remove=%s" % (sys.argv, printer_name, param, jd_port, device_uri, remove))
        dlg = SetupDialog(None, param, jd_port, device_uri, remove)
        dlg.show()
        try:
            log.debug("Starting GUI loop...")
            app.exec_()
        except KeyboardInterrupt:
            sys.exit(0)


else: # INTERACTIVE_MODE
    try:

        cups.setPasswordCallback(showPasswordUI)

        if remove:
            log.error("-r/--rm/--remove not supported in -i mode.")
            sys.exit(1)

        if not auto:
            log.info("(Note: Defaults for each question are maked with a '*'. Press <enter> to accept the default.)")
            log.info("")

        # ******************************* MAKEURI
        if param:
            device_uri, sane_uri, fax_uri = device.makeURI(param, jd_port)

        # ******************************* CONNECTION TYPE CHOOSER
        if not device_uri and bus is None:
            bus = tui.connection_table()

            if bus is None:
                sys.exit(0)

            log.info("\nUsing connection type: %s" % bus[0])

            log.info("")

        # ******************************* DEVICE CHOOSER

        if not device_uri:
            log.debug("\nDEVICE CHOOSER setup_fax=%s, setup_print=%s" % (setup_fax, setup_print))
            device_uri = mod.getDeviceUri(device_uri, selected_device_name, devices = device.probeDevices(bus))


        # ******************************* QUERY MODEL AND COLLECT PPDS
        log.info(log.bold("\nSetting up device: %s\n" % device_uri))

        log.info("")
        print_uri = device_uri.replace("hpfax:", "hp:")
        fax_uri = device_uri.replace("hp:", "hpfax:")

        back_end, is_hp, bus, model, \
            serial, dev_file, host, zc, port = \
            device.parseDeviceURI(device_uri)

        log.debug("Model=%s" % model)
        mq = device.queryModelByURI(device_uri)

        if not mq or mq.get('support-type', SUPPORT_TYPE_NONE) == SUPPORT_TYPE_NONE:
            log.error("Unsupported printer model.")
            sys.exit(1)

        if mq.get('fax-type', FAX_TYPE_NONE) in (FAX_TYPE_NONE, FAX_TYPE_NOT_SUPPORTED) and setup_fax:
            #log.warning("Cannot setup fax - device does not have fax feature.")
            setup_fax = False

        # ******************************* PLUGIN

        norm_model = models.normalizeModelName(model).lower()
        plugin = mq.get('plugin', PLUGIN_NONE)

        plugin_installed = utils.to_bool(sys_state.get('plugin', 'installed', '0'))
        if plugin > PLUGIN_NONE and not plugin_installed:
            tui.header("PLUG-IN INSTALLATION")

            hp_plugin = utils.which('hp-plugin')

            if hp_plugin:
                if prop.gui_build:
                    os.system("hp-plugin -i")
                else:
                    os.system("hp-plugin")

        ppds = cups.getSystemPPDs()

        default_model = utils.xstrip(model.replace('series', '').replace('Series', ''), '_')
        stripped_model = cups.stripModel2(default_model)

        installed_print_devices = device.getSupportedCUPSDevices(['hp'])
        for d in installed_print_devices.keys():
            for p in installed_print_devices[d]:
                log.debug("found print queue '%s'" % p)

        installed_fax_devices = device.getSupportedCUPSDevices(['hpfax'])
        for d in installed_fax_devices.keys():
            for f in installed_fax_devices[d]:
                log.debug("found fax queue '%s'" % f)

        # ******************************* PRINT QUEUE SETUP
        if setup_print:

            tui.header("PRINT QUEUE SETUP")

            if not auto and print_uri in installed_print_devices:
                log.warning("One or more print queues already exist for this device: %s." %
                    ', '.join(installed_print_devices[print_uri]))

                ok, setup_print = tui.enter_yes_no("\nWould you like to install another print queue for this device", 'n')
                if not ok: sys.exit(0)

        if setup_print:
            if auto:
                printer_name = default_model

            printer_default_model = default_model

            # Check for duplicate names
            if device_uri in installed_print_devices and \
                printer_default_model in installed_print_devices[device_uri]:
                    i = 2
                    while True:
                        t = printer_default_model + "_%d" % i
                        if t not in installed_print_devices[device_uri]:
                            printer_default_model += "_%d" % i
                            break
                        i += 1

            if not auto:
                if printer_name is None:
                    while True:
                        printer_name = raw_input(log.bold("\nPlease enter a name for this print queue (m=use model name:'%s'*, q=quit) ?" % printer_default_model))

                        if printer_name.lower().strip() == 'q':
                            log.info("OK, done.")
                            sys.exit(0)

                        if not printer_name or printer_name.lower().strip() == 'm':
                            printer_name = printer_default_model

                        name_ok = True

                        for d in installed_print_devices.keys():
                            for p in installed_print_devices[d]:
                                if printer_name == p:
                                    log.error("A print queue with that name already exists. Please enter a different name.")
                                    name_ok = False
                                    break

                        for d in installed_fax_devices.keys():
                            for f in installed_fax_devices[d]:
                                if printer_name == f:
                                    log.error("A fax queue with that name already exists. Please enter a different name.")
                                    name_ok = False
                                    break

                        for c in printer_name:
                            if c in cups.INVALID_PRINTER_NAME_CHARS:
                                log.error("Invalid character '%s' in printer name. Please enter a name that does not contain this character." % c)
                                name_ok = False

                        if name_ok:
                            break
            else:
                printer_name = printer_default_model

            log.info("Using queue name: %s" % printer_name)

            default_model = utils.xstrip(model.replace('series', '').replace('Series', ''), '_')
            stripped_model = default_model.lower().replace('hp-', '').replace('hp_', '')

            log.info("Locating PPD file... Please wait.")
            print_ppd = cups.getPPDFile2(stripped_model, ppds)
            enter_ppd = False

            if print_ppd is None:
                enter_ppd = True
                log.error("Unable to find an appropriate PPD file.")

            else:
                print_ppd, desc = print_ppd
                log.info("\nFound PPD file: %s" % print_ppd)

                log.info("Description: %s" % desc)
#
                if not auto:
                    log.info("\nNote: The model number may vary slightly from the actual model number on the device.")
                    ok, ans = tui.enter_yes_no("\nDoes this PPD file appear to be the correct one")
                    if not ok: sys.exit(0)
                    if not ans: enter_ppd = True


            if enter_ppd:
                enter_ppd = False

                ok, enter_ppd = tui.enter_yes_no("\nWould you like to specify the path to the correct PPD file to use", 'n')
                if not ok: sys.exit(0)

                if enter_ppd:
                    ok = False

                    while True:
                        user_input = raw_input(log.bold("\nPlease enter the full filesystem path to the PPD file to use (q=quit) :"))

                        if user_input.lower().strip() == 'q':
                            log.info("OK, done.")
                            sys.exit(0)

                        file_path = user_input

                        if os.path.exists(file_path) and os.path.isfile(file_path):

                            if file_path.endswith('.gz'):
                                nickname = gzip.GzipFile(file_path, 'r').read(4096)
                            else:
                                nickname = file(file_path, 'r').read(4096)

                            try:
                                desc = nickname_pat.search(nickname).group(1)
                            except AttributeError:
                                desc = ''

                            if desc:
                                log.info("Description for the file: %s" % desc)
                            else:
                                log.error("No PPD 'NickName' found. This file may not be a valid PPD file.")

                            ok, ans = tui.enter_yes_no("\nUse this file")
                            if not ok: sys.exit(0)
                            if ans: print_ppd = file_path

                        else:
                            log.error("File not found or not an appropriate (PPD) file.")

                        if ok:
                            break
                else:
                    log.error("PPD file required. Setup cannot continue. Exiting.")
                    sys.exit(1)

            if auto:
                location, info = '', 'Automatically setup by HPLIP'
            else:
                while True:
                    location = raw_input(log.bold("Enter a location description for this printer (q=quit) ?"))

                    if location.strip().lower() == 'q':
                        log.info("OK, done.")
                        sys.exit(0)

                    # TODO: Validate chars
                    break

                while True:
                    info = raw_input(log.bold("Enter additonal information or notes for this printer (q=quit) ?"))

                    if info.strip().lower() == 'q':
                        log.info("OK, done.")
                        sys.exit(0)

                    # TODO: Validate chars
                    break

            log.info(log.bold("\nAdding print queue to CUPS:"))
            log.info("Device URI: %s" % print_uri)
            log.info("Queue name: %s" % printer_name)
            log.info("PPD file: %s" % print_ppd)
            log.info("Location: %s" % location)
            log.info("Information: %s" % info)

            log.debug("Restarting CUPS...")
            status, output = utils.run(restart_cups())
            log.debug("Restart CUPS returned: exit=%d output=%s" % (status, output))

            cups.setPasswordPrompt("You do not have permission to add a printer.")
            if not os.path.exists(print_ppd): # assume foomatic: or some such
                status, status_str = cups.addPrinter(printer_name.encode('utf8'), print_uri,
                    location, '', print_ppd, info)
            else:
                status, status_str = cups.addPrinter(printer_name.encode('utf8'), print_uri,
                    location, print_ppd, '', info)

            log.debug("addPrinter() returned (%d, %s)" % (status, status_str))

            installed_print_devices = device.getSupportedCUPSDevices(['hp'])

            if print_uri not in installed_print_devices or \
                printer_name not in installed_print_devices[print_uri]:

                log.error("Printer queue setup failed. Please restart CUPS and try again.")
                sys.exit(1)
            else:
                pass
                # TODO:
                #service.sendEvent(hpssd_sock, EVENT_CUPS_QUEUES_CHANGED, device_uri=print_uri)


        # ******************************* FAX QUEUE SETUP
        if setup_fax and not prop.fax_build:
            log.error("Cannot setup fax - HPLIP not built with fax enabled.")
            setup_fax = False

        if setup_fax:

            try:
                from fax import fax
            except ImportError:
                # This can fail on Python < 2.3 due to the datetime module
                setup_fax = False
                log.warning("Fax setup disabled - Python 2.3+ required.")

        log.info("")

        if setup_fax:

            tui.header("FAX QUEUE SETUP")

            if not auto and fax_uri in installed_fax_devices:
                log.warning("One or more fax queues already exist for this device: %s." % ', '.join(installed_fax_devices[fax_uri]))
                ok, setup_fax = tui.enter_yes_no("\nWould you like to install another fax queue for this device", 'n')
                if not ok: sys.exit(0)

        if setup_fax:
            if auto: # or fax_name is None:
                fax_name = default_model + '_fax'

            fax_default_model = default_model + '_fax'

            # Check for duplicate names
            if fax_uri in installed_fax_devices and \
                fax_default_model in installed_fax_devices[fax_uri]:
                    i = 2
                    while True:
                        t = fax_default_model + "_%d" % i
                        if t not in installed_fax_devices[fax_uri]:
                            fax_default_model += "_%d" % i
                            break
                        i += 1

            if not auto:
                if fax_name is None:
                    while True:
                        fax_name = raw_input(log.bold("\nPlease enter a name for this fax queue (m=use model name:'%s'*, q=quit) ?" % fax_default_model))

                        if fax_name.lower().strip() == 'q':
                            log.info("OK, done.")
                            sys.exit(0)

                        if not fax_name or fax_name.lower().strip() == 'm':
                            fax_name = fax_default_model

                        name_ok = True

                        for d in installed_print_devices.keys():
                            for p in installed_print_devices[d]:
                                if fax_name == p:
                                    log.error("A print queue with that name already exists. Please enter a different name.")
                                    name_ok = False
                                    break

                        for d in installed_fax_devices.keys():
                            for f in installed_fax_devices[d]:
                                if fax_name == f:
                                    log.error("A fax queue with that name already exists. Please enter a different name.")
                                    name_ok = False
                                    break

                        for c in fax_name:
                            if c in (' ', '#', '/', '%'):
                                log.error("Invalid character '%s' in fax name. Please enter a name that does not contain this character." % c)
                                name_ok = False

                        if name_ok:
                            break

            else:
                fax_name = fax_default_model

            log.info("Using queue name: %s" % fax_name)

            fax_type = mq.get('fax-type', FAX_TYPE_NONE)

            if prop.hpcups_build:
                if fax_type == FAX_TYPE_SOAP or fax_type == FAX_TYPE_LEDMSOAP:
                    fax_ppd_name = 'HP-Fax2-hpcups'
                else:
                    fax_ppd_name = 'HP-Fax-hpcups'
            else: # hpijs
                if fax_type == FAX_TYPE_SOAP or fax_type == FAX_TYPE_LEDMSOAP:
                    fax_ppd_name = 'HP-Fax2-hpijs'
                else:
                    fax_ppd_name = 'HP-Fax-hpijs'

            for f in ppds:
                if f.find(fax_ppd_name) >= 0:
                    fax_ppd = f
                    log.debug("Found PDD file: %s" % fax_ppd)
                    break
            else:
                log.error("Unable to find HP fax PPD file! Please check you HPLIP installation and try again.")
                sys.exit(1)

            if auto:
                location, info = '', 'Automatically setup by HPLIP'
            else:
                while True:
                    location = raw_input(log.bold("Enter a location description for this printer (q=quit) ?"))

                    if location.strip().lower() == 'q':
                        log.info("OK, done.")
                        sys.exit(0)

                    # TODO: Validate chars
                    break

                while True:
                    info = raw_input(log.bold("Enter additonal information or notes for this printer (q=quit) ?"))

                    if info.strip().lower() == 'q':
                        log.info("OK, done.")
                        sys.exit(0)

                    # TODO: Validate chars
                    break

            log.info(log.bold("\nAdding fax queue to CUPS:"))
            log.info("Device URI: %s" % fax_uri)
            log.info("Queue name: %s" % fax_name)
            log.info("PPD file: %s" % fax_ppd)
            log.info("Location: %s" % location)
            log.info("Information: %s" % info)

            cups.setPasswordPrompt("You do not have permission to add a fax device.")
            if not os.path.exists(fax_ppd): # assume foomatic: or some such
                status, status_str = cups.addPrinter(fax_name.encode('utf8'), fax_uri,
                    location, '', fax_ppd, info)
            else:
                status, status_str = cups.addPrinter(fax_name.encode('utf8'), fax_uri,
                    location, fax_ppd, '', info)

            log.debug("addPrinter() returned (%d, %s)" % (status, status_str))

            installed_fax_devices = device.getSupportedCUPSDevices(['hpfax'])

            log.debug(installed_fax_devices)

            if fax_uri not in installed_fax_devices or \
                fax_name not in installed_fax_devices[fax_uri]:

                log.error("Fax queue setup failed. Please restart CUPS and try again.")
                sys.exit(1)
            else:
                pass
                # TODO:
                #service.sendEvent(hpssd_sock, EVENT_CUPS_QUEUES_CHANGED, device_uri=fax_uri)


        # ******************************* FAX HEADER SETUP
            tui.header("FAX HEADER SETUP")

            if auto:
                setup_fax = False
            else:
                while True:
                    user_input = raw_input(log.bold("\nWould you like to perform fax header setup (y=yes*, n=no, q=quit) ?")).strip().lower()

                    if user_input == 'q':
                        log.info("OK, done.")
                        sys.exit(0)

                    if not user_input:
                        user_input = 'y'

                    setup_fax = (user_input == 'y')

                    if user_input in ('y', 'n', 'q'):
                        break

                    log.error("Please enter 'y' or 'n'")

            if setup_fax:
                d = fax.getFaxDevice(fax_uri, disable_dbus=True)

                try:
                    d.open()
                except Error:
                    log.error("Unable to communicate with the device. Please check the device and try again.")
                else:
                    try:
                        tries = 0
                        ok = True

                        while True:
                            tries += 1

                            try:
                                current_phone_num = str(d.getPhoneNum())
                                current_station_name = str(d.getStationName())
                            except Error:
                                log.error("Could not communicate with device. Device may be busy. Please wait for retry...")
                                time.sleep(5)
                                ok = False

                                if tries > 12:
                                    break

                            else:
                                ok = True
                                break

                        if ok:
                            while True:
                                if current_phone_num:
                                    phone_num = raw_input(log.bold("\nEnter the fax phone number for this device (c=use current:'%s'*, q=quit) ?" % current_phone_num))
                                else:
                                    phone_num = raw_input(log.bold("\nEnter the fax phone number for this device (q=quit) ?"))
                                if phone_num.strip().lower() == 'q':
                                    log.info("OK, done.")
                                    sys.exit(0)

                                if current_phone_num and (not phone_num or phone_num.strip().lower() == 'c'):
                                    phone_num = current_phone_num

                                if len(phone_num) > 50:
                                    log.error("Phone number length is too long (>50 characters). Please enter a shorter number.")
                                    continue

                                ok = True
                                for x in phone_num:
                                    if x not in '0123456789-(+) ':
                                        log.error("Invalid characters in phone number. Please only use 0-9, -, (, +, and )")
                                        ok = False
                                        break

                                if not ok:
                                    continue

                                break

                            while True:
                                if current_station_name:
                                    station_name = raw_input(log.bold("\nEnter the name and/or company for this device (c=use current:'%s'*, q=quit) ?" % current_station_name))
                                else:
                                    station_name = raw_input(log.bold("\nEnter the name and/or company for this device (q=quit) ?"))
                                if station_name.strip().lower() == 'q':
                                    log.info("OK, done.")
                                    sys.exit(0)

                                if current_station_name and (not station_name or station_name.strip().lower() == 'c'):
                                    station_name = current_station_name


                                if len(station_name) > 50:
                                    log.error("Name/company length is too long (>50 characters). Please enter a shorter name/company.")
                                    continue
                                break

                            try:
                                d.setStationName(station_name)
                                d.setPhoneNum(phone_num)
                            except Error:
                                log.error("Could not communicate with device. Device may be busy.")
                            else:
                                log.info("\nParameters sent to device.")

                    finally:
                        d.close()

        # ******************************* TEST PAGE
        if setup_print:
            print_test_page = False

            tui.header("PRINTER TEST PAGE")

            if auto:
                if testpage_in_auto_mode:
                    print_test_page = True
            else:
                ok, print_test_page = tui.enter_yes_no("\nWould you like to print a test page")
                if not ok: sys.exit(0)

            if print_test_page:
                path = utils.which('hp-testpage')

                if printer_name:
                    param = "-p%s" % printer_name
                else:
                    param = "-d%s" % print_uri

                if len(path) > 0:
                    cmd = 'hp-testpage %s' % param
                else:
                    cmd = 'python ./testpage.py %s' % param

                log.debug(cmd)

                os.system(cmd)

    except KeyboardInterrupt:
        log.error("User exit")

log.info("")
log.info("Done.")

