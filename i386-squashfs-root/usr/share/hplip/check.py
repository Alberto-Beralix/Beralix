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

__version__ = '14.3'
__title__ = 'Dependency/Version Check Utility'
__mod__ = 'hp-check'
__doc__ = """Check the existence and versions of HPLIP dependencies. (Run as 'python ./check.py' from the HPLIP tarball before installation.)"""

# Std Lib
import sys
import os
import getopt
import commands
import re

# Local
from base.g import *
from base import utils, tui, models
from installer import dcheck
from installer.core_install import *

device_avail = False
try:
    from base import device, pml
    # This can fail due to hpmudext not being present
except ImportError:
    log.debug("Device library is not avail.")
else:
    device_avail = True


USAGE = [(__doc__, "", "name", True),
         ("Usage: %s [OPTIONS]" % __mod__, "", "summary", True),
         utils.USAGE_OPTIONS,
         ("Compile-time check:", "-c or --compile", "option", False),
         ("Run-time check:", "-r or --run", "option", False),
         ("Compile and run-time checks:", "-b or --both (default)", "option", False),
         utils.USAGE_LOGGING1, utils.USAGE_LOGGING2, utils.USAGE_LOGGING3,
         utils.USAGE_LOGGING_PLAIN,
         utils.USAGE_HELP,
         utils.USAGE_NOTES,
         ("1. For checking for the proper build environment for the HPLIP supplied tarball (.tar.gz or .run),", "", "note", False),
         ("use the --compile or --both switches.", "", "note", False),
         ("2. For checking for the proper runtime environment for a distro supplied package (.deb, .rpm, etc),", "", "note", False),
         ("use the --runtime switch.", "", "note", False),
        ]

def usage(typ='text'):
    if typ == 'text':
        utils.log_title(__title__, __version__)

    utils.format_text(USAGE, typ, __title__, __mod__, __version__)
    sys.exit(0)


build_str = "HPLIP will not build, install, and/or function properly without this dependency."

pat_deviceuri = re.compile(r"""(.*):/(.*?)/(\S*?)\?(?:serial=(\S*)|device=(\S*)|ip=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[^&]*)|zc=(\S+))(?:&port=(\d))?""", re.I)
#pat_deviceuri = re.compile(r"""(.*):/(.*?)/(\S*?)\?(?:serial=(\S*)|device=(\S*)|ip=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[^&]*))(?:&port=(\d))?""", re.I)

pat_cups_error_log = re.compile("""^loglevel\s?(debug|debug2|warn|info|error|none)""", re.I)


def parseDeviceURI(device_uri):
    m = pat_deviceuri.match(device_uri)

    if m is None:
        raise Error(ERROR_INVALID_DEVICE_URI)

    back_end = m.group(1).lower() or ''
    is_hp = (back_end in ('hp', 'hpfax', 'hpaio'))
    bus = m.group(2).lower() or ''

    if bus not in ('usb', 'net', 'bt', 'fw', 'par'):
        raise Error(ERROR_INVALID_DEVICE_URI)

    model = m.group(3) or ''
    serial = m.group(4) or ''
    dev_file = m.group(5) or ''
    host = m.group(6) or ''
    zc = ''
    if not host:
        zc = host = m.group(7) or ''
    port = m.group(8) or 1

    if bus == 'net':
        try:
            port = int(port)
        except (ValueError, TypeError):
            port = 1

        if port == 0:
            port = 1

#   log.debug("%s: back_end '%s' is_hp '%s' bus '%s' model '%s' serial '%s' dev_file '%s' host '%s' zc '%s' port '%s' " %
#       (device_uri, back_end, is_hp, bus, model, serial, dev_file, host, zc, port))

    return back_end, is_hp, bus, model, serial, dev_file, host, zc, port

num_errors = 0
fmt = True
overall_commands_to_run = []
time_flag = DEPENDENCY_RUN_AND_COMPILE_TIME

try:
    log.set_module(__mod__)

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hl:gtcrb',
            ['help', 'help-rest', 'help-man', 'help-desc', 'logging=',
             'run', 'runtime', 'compile', 'both'])

    except getopt.GetoptError, e:
        log.error(e.msg)
        usage()
        sys.exit(1)

    if os.getenv("HPLIP_DEBUG"):
        log.set_level('debug')

    log_level = 'info'

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()

        elif o == '--help-rest':
            usage('rest')

        elif o == '--help-man':
            usage('man')

        elif o == '--help-desc':
            print __doc__,
            sys.exit(0)

        elif o in ('-l', '--logging'):
            log_level = a.lower().strip()

        elif o == '-g':
            log_level = 'debug'

        elif o == '-t':
            fmt = False

        elif o in ('-c', '--compile'):
            time_flag = DEPENDENCY_COMPILE_TIME

        elif o in ('-r', '--runtime', '--run'):
            time_flag = DEPENDENCY_RUN_TIME

        elif o in ('-b', '--both'):
            time_flag = DEPENDENCY_RUN_AND_COMPILE_TIME

    if not log.set_level(log_level):
        usage()

    if not fmt:
        log.no_formatting()

    utils.log_title(__title__, __version__)

    log.info(log.bold("Note: hp-check can be run in three modes:"))

    for l in tui.format_paragraph("1. Compile-time check mode (-c or --compile): Use this mode before compiling the HPLIP supplied tarball (.tar.gz or .run) to determine if the proper dependencies are installed to successfully compile HPLIP."):
        log.info(l)

    for l in tui.format_paragraph("2. Run-time check mode (-r or --run): Use this mode to determine if a distro supplied package (.deb, .rpm, etc) or an already built HPLIP supplied tarball has the proper dependencies installed to successfully run."):
        log.info(l)

    for l in tui.format_paragraph("3. Both compile- and run-time check mode (-b or --both) (Default): This mode will check both of the above cases (both compile- and run-time dependencies)."):
        log.info(l)

    log.info()

    log_file = os.path.normpath('./hp-check.log')
    log.info(log.bold("Saving output in log file: %s" % log_file))
    log.debug("Log file=%s" % log_file)
    if os.path.exists(log_file):
        os.remove(log_file)

    log.set_logfile(log_file)
    log.set_where(log.LOG_TO_CONSOLE_AND_FILE)

    log.info("\nInitializing. Please wait...")
    core =  CoreInstall(MODE_CHECK)
    core.init()
    core.set_plugin_version()

    tui.header("SYSTEM INFO")

    log.info(log.bold("Basic system information:"))
    log.info(core.sys_uname_info)

    log.info()
    log.info(log.bold("Distribution:"))
    log.info("%s %s" % (core.distro_name, core.distro_version))

    #log.info(log.bold("\nHPOJ running?"))

    #if core.hpoj_present:
        #log.error("Yes, HPOJ is running. HPLIP is not compatible with HPOJ. To run HPLIP, please remove HPOJ.")
        #num_errors += 1
    #else:
        #log.info("No, HPOJ is not running (OK).")


    log.info()
    log.info(log.bold("Checking Python version..."))
    ver = sys.version_info
    log.debug("sys.version_info = %s" % repr(ver))
    ver_maj = ver[0]
    ver_min = ver[1]
    ver_pat = ver[2]

    if ver_maj == 2:
        if ver_min >= 1:
            log.info("OK, version %d.%d.%d installed" % ver[:3])
        else:
            log.error("Version %d.%d.%d installed. Please update to Python >= 2.1" % ver[:3])
            sys.exit(1)

    ui_toolkit = sys_conf.get('ui_toolkit', 'qt4')
    if  ui_toolkit == 'qt3':
        log.info()
        log.info(log.bold("Checking PyQt 3.x version..."))

        # PyQt 3
        try:
            import qt
        except ImportError:
            num_errors += 1
            log.error("NOT FOUND OR FAILED TO LOAD!")
        else:
            # check version of Qt
            qtMajor = int(qt.qVersion().split('.')[0])

            if qtMajor < MINIMUM_QT_MAJOR_VER:
                log.error("Incorrect version of Qt installed. Ver. 3.0.0 or greater required.")
            else:
                #check version of PyQt
                try:
                    pyqtVersion = qt.PYQT_VERSION_STR
                except AttributeError:
                    pyqtVersion = qt.PYQT_VERSION

                while pyqtVersion.count('.') < 2:
                    pyqtVersion += '.0'

                (maj_ver, min_ver, pat_ver) = pyqtVersion.split('.')

                if pyqtVersion.find('snapshot') >= 0:
                    log.error("A non-stable snapshot version of PyQt is installed (%s)." % pyqtVersion)
                    num_errors += 1
                else:
                    try:
                        maj_ver = int(maj_ver)
                        min_ver = int(min_ver)
                        pat_ver = int(pat_ver)
                    except ValueError:
                        maj_ver, min_ver, pat_ver = 0, 0, 0

                    if maj_ver < MINIMUM_PYQT_MAJOR_VER or \
                        (maj_ver == MINIMUM_PYQT_MAJOR_VER and min_ver < MINIMUM_PYQT_MINOR_VER):
                        num_errors += 1
                        log.error("HPLIP may not function properly with the version of PyQt that is installed (%d.%d.%d)." % (maj_ver, min_ver, pat_ver))
                        log.error("Ver. %d.%d or greater required." % (MINIMUM_PYQT_MAJOR_VER, MINIMUM_PYQT_MINOR_VER))
                    else:
                        log.info("OK, version %d.%d installed." % (maj_ver, min_ver))
            del qt


    else:

        log.info()
        log.info(log.bold("Checking PyQt 4.x version..."))

        # PyQt 4
        try:
            import PyQt4
        except ImportError:
            num_errors += 1
            log.error("NOT FOUND OR FAILED TO LOAD!")
        else:
            from PyQt4 import QtCore
            log.info("OK, version %s installed." % QtCore.PYQT_VERSION_STR)


#    log.info()
#    log.info(log.bold("Checking SIP version..."))
#
#    sip_ver = None
#    try:
#        import pyqtconfig
#    except ImportError:
#        pass
#    else:
#        sip_ver = pyqtconfig.Configuration().sip_version_str
#
#    if sip_ver is not None:
#        log.info("OK, Version %s installed" % sip_ver)
#    else:
#        num_errors += 1
#        log.error("SIP not installed or version not found.")

    log.info()
    log.info(log.bold("Checking for CUPS..."))
    cups_ok = True

    status, output = utils.run('lpstat -r')
    if status == 0:
        log.info("Status: %s" % output.strip())
    else:
        log.error("Status: (Not available. CUPS may not be installed or not running.)")
        cups_ok = False
        num_errors += 1

    if cups_ok:
        status, output = utils.run('cups-config --version')
        if status == 0:
            log.info("Version: %s" % output.strip())
        else:
            log.warn("Version: (cups-config) Not available. Unable to determine installed version of CUPS.)")

    if cups_ok:
        cups_conf = '/etc/cups/cupsd.conf'

        try:
            f = file(cups_conf, 'r')
        except (IOError, OSError):
            log.warn("%s file not found or not accessible." % cups_conf)
        else:
            for l in f:
                m = pat_cups_error_log.match(l)
                if m is not None:
                    level = m.group(1).lower()
                    log.info("error_log is set to level: %s" % level)

                    #if level not in ('debug', 'debug2'):
                        #log.note("For troubleshooting printing issues, it is best to have the CUPS 'LogLevel'")
                        #log.note("set to 'debug'. To set the LogLevel to debug, edit the file %s (as root)," % cups_conf)
                        #log.note("and change the line near the top of the file that begins with 'LogLevel' to read:")
                        #log.note("LogLevel debug")
                        #log.note("Save the file and then restart CUPS (see your OS/distro docs on how to restart CUPS).")
                        #log.note("Now, when you print, helpful debug information will be saved to the file:")
                        #log.note("/var/log/cups/error_log")
                        #log.note("You can monitor this file by running this command in a console/shell:")
                        #log.note("tail -f /var/log/cups/error_log")

                    break


    log.info()

    log.info(log.bold("Checking for dbus/python-dbus..."))

    if dcheck.check_ps(['dbus-daemon']):
        log.info("dbus daemon is running.")
    else:
        log.warn("dbus daemon is not running.")

    try:
        import dbus
        try:
            log.info("python-dbus version: %s" % dbus.__version__)
        except AttributeError:
            try:
                log.info("python-dbus version: %s" % '.'.join([str(x) for x in dbus.version]))
            except AttributeError:
                log.warn("python-dbus imported OK, but unknown version.")
    except ImportError:
        log.warn("python-dbus not installed.")

    log.info()


    if time_flag == DEPENDENCY_RUN_AND_COMPILE_TIME:
        tui.header("COMPILE AND RUNTIME DEPENDENCIES")
        log.note("To check for compile-time only dependencies, re-run hp-check with the -c parameter (ie, hp-check -c).")
        log.note("To check for run-time only dependencies, re-run hp-check with the -r parameter (ie, hp-check -r).")

    elif time_flag == DEPENDENCY_COMPILE_TIME:
        tui.header("COMPILE TIME DEPENDENCIES")

    elif time_flag == DEPENDENCY_RUN_TIME:
        tui.header("RUNTIME DEPENDENCIES")

    log.info()

    dd = core.dependencies.keys()

    status, output = utils.run('cups-config --version')
    import string
    if status == 0 and (string.count(output, '.') == 1 or string.count(output, '.') == 2):
        if string.count(output, '.') == 1:
            major, minor = string.split(output, '.', 2)
        if string.count(output, '.') == 2:
            major, minor, release = string.split(output, '.', 3)
        if len(minor) > 1 and minor[1] >= '0' and minor[1] <= '9':
            minor = ((ord(minor[0]) - ord('0')) * 10) + (ord(minor[1]) - ord('0'))
        else:
            minor = ord(minor[0]) - ord('0')
        if major > '1' or (major == '1' and minor >= 4):
            dd.remove('cups-ddk')

    dd.sort()
    for d in dd:
        if (d == 'pyqt' and ui_toolkit != 'qt3') or \
           (d == 'pyqt4' and ui_toolkit != 'qt4'):
            continue

        log.debug("***")

        if time_flag == DEPENDENCY_RUN_AND_COMPILE_TIME or time_flag == core.dependencies[d][4]:

            log.info(log.bold("Checking for dependency: %s..." % core.dependencies[d][2]))

            if core.have_dependencies[d]:
                log.info("OK, found.")
            else:
                num_errors += 1

                if core.dependencies[d][4] == DEPENDENCY_RUN_AND_COMPILE_TIME:
                    s = ''
                elif core.dependencies[d][4] == DEPENDENCY_COMPILE_TIME:
                    s = '/COMPILE TIME ONLY'

                elif core.dependencies[d][4] == DEPENDENCY_RUN_TIME:
                    s = '/RUNTIME ONLY'

                if core.dependencies[d][0]:
                    log.error("NOT FOUND! This is a REQUIRED%s dependency. Please make sure that this dependency is installed before installing or running HPLIP." % s)
                else:
                    log.warn("NOT FOUND! This is an OPTIONAL%s dependency. Some HPLIP functionality may not function properly." %s)

                if core.distro_supported():
                    packages_to_install, commands = core.get_dependency_data(d)

                    commands_to_run = []

                    if packages_to_install:
                        package_mgr_cmd = core.get_distro_data('package_mgr_cmd')

                        if package_mgr_cmd:
                            packages_to_install = ' '.join(packages_to_install)
                            commands_to_run.append(utils.cat(package_mgr_cmd))

                    if commands:
                        commands_to_run.extend(commands)

                    overall_commands_to_run.extend(commands_to_run)

                    if len(commands_to_run) == 1:
                        log.info("To install this dependency, execute this command:")
                        log.info(commands_to_run[0])

                    elif len(commands_to_run) > 1:
                        log.info("To install this dependency, execute these commands:")
                        for c in commands_to_run:
                            log.info(c)


            log.info()

    if time_flag in (DEPENDENCY_RUN_TIME, DEPENDENCY_RUN_AND_COMPILE_TIME):
        tui.header("HPLIP INSTALLATION")

        scanning_enabled = utils.to_bool(sys_conf.get('configure', 'scanner-build', '0'))

        log.info()
        log.info(log.bold("Currently installed HPLIP version..."))
        v = sys_conf.get('hplip', 'version')
        home = sys_conf.get('dirs', 'home')

        if v:
            log.info("HPLIP %s currently installed in '%s'." % (v, home))

            log.info()
            log.info(log.bold("Current contents of '/etc/hp/hplip.conf' file:"))
            try:
                output = file('/etc/hp/hplip.conf', 'r').read()
            except (IOError, OSError), e:
                log.error("Could not access file: %s" % e.strerror)
            else:
                log.info(output)

            log.info()
            log.info(log.bold("Current contents of '/var/lib/hp/hplip.state' file:"))
            try:
                output = file(os.path.expanduser('/var/lib/hp/hplip.state'), 'r').read()
            except (IOError, OSError), e:
                log.error("Could not access file: %s" % e.strerror)
            else:
                log.info(output)

            log.info()
            log.info(log.bold("Current contents of '~/.hplip/hplip.conf' file:"))
            try:
                output = file(os.path.expanduser('~/.hplip/hplip.conf'), 'r').read()
            except (IOError, OSError), e:
                log.error("Could not access file: %s" % e.strerror)
            else:
                log.info(output)

        else:
            log.info("Not found.")


        if device_avail:
            #if prop.par_build:
                #tui.header("DISCOVERED PARALLEL DEVICES")

                #devices = device.probeDevices(['par'])

                #if devices:
                    #f = tui.Formatter()
                    #f.header = ("Device URI", "Model")

                    #for d, dd in devices.items():
                        #f.add((d, dd[0]))

                    #f.output()

                #else:
                    #log.info("No devices found.")

                    #if not core.have_dependencies['ppdev']:
                        #log.error("'ppdev' kernel module not loaded.")

            if prop.usb_build:
                tui.header("DISCOVERED USB DEVICES")

                devices = device.probeDevices(['usb'])

                if devices:
                    f = tui.Formatter()
                    f.header = ("Device URI", "Model")

                    for d, dd in devices.items():
                        f.add((d, dd[0]))

                    f.output()

                else:
                    log.info("No devices found.")


        tui.header("INSTALLED CUPS PRINTER QUEUES")

        lpstat_pat = re.compile(r"""(\S*): (.*)""", re.IGNORECASE)
        status, output = utils.run('lpstat -v')
        log.info()

        cups_printers = []
        for p in output.splitlines():
            try:
                match = lpstat_pat.search(p)
                printer_name = match.group(1)
                device_uri = match.group(2)
                cups_printers.append((printer_name, device_uri))
            except AttributeError:
                pass

        log.debug(cups_printers)

        if cups_printers:
            #non_hp = False
            for p in cups_printers:
                printer_name, device_uri = p

                if device_uri.startswith("cups-pdf:/") or \
                    device_uri.startswith('ipp://'):
                    continue

                try:
                    back_end, is_hp, bus, model, serial, dev_file, host, zc, port = \
                        parseDeviceURI(device_uri)
                except Error:
                    back_end, is_hp, bus, model, serial, dev_file, host, zc, port = \
                        '', False, '', '', '', '', '', '', 1

                #print back_end, is_hp, bus, model, serial, dev_file, host, zc, port

                log.info(log.bold(printer_name))
                log.info(log.bold('-'*len(printer_name)))

                x = "Unknown"
                if back_end == 'hpfax':
                    x = "Fax"
                elif back_end == 'hp':
                    x = "Printer"

                log.info("Type: %s" % x)

                #if is_hp:
                #    x = 'Yes, using the %s: CUPS backend.' % back_end
                #else:
                #    x = 'No, not using the hp: or hpfax: CUPS backend.'
                #    non_hp = True

                #log.info("Installed in HPLIP?: %s" % x)
                log.info("Device URI: %s" % device_uri)

                ppd = os.path.join('/etc/cups/ppd', printer_name + '.ppd')

                if os.path.exists(ppd):
                    log.info("PPD: %s" % ppd)
                    nickname_pat = re.compile(r'''\*NickName:\s*\"(.*)"''', re.MULTILINE)

                    f = file(ppd, 'r').read(4096)

                    try:
                        desc = nickname_pat.search(f).group(1)
                    except AttributeError:
                        desc = ''

                    log.info("PPD Description: %s" % desc)

                    status, output = utils.run('lpstat -p%s' % printer_name)
                    log.info("Printer status: %s" % output.replace("\n", ""))

                    if back_end == 'hpfax' and not 'HP Fax' in desc:
                        num_errors += 1
                        log.error("Incorrect PPD file for fax queue '%s'. Fax queues must use 'HP-Fax-hplip.ppd'." % printer_name)

                    elif back_end == 'hp' and 'HP Fax' in desc:
                        num_errors += 1
                        log.error("Incorrect PPD file for a print queue '%s'. Print queues must not use 'HP-Fax-hplip.ppd'." % printer_name)

                    elif back_end not in ('hp', 'hpfax'):
                        log.warn("Printer is not HPLIP installed. Printers must use the hp: or hpfax: CUPS backend to function in HPLIP.")
                        num_errors += 1

                if device_avail and is_hp:
                    d = None
                    try:
                        try:
                            d = device.Device(device_uri)
                        except Error:
                            log.error("Device initialization failed.")
                            continue

                        plugin = d.mq.get('plugin', PLUGIN_NONE)
                        if plugin in (PLUGIN_REQUIRED, PLUGIN_OPTIONAL):

                            if core.check_for_plugin():
                                if plugin == PLUGIN_REQUIRED:
                                    log.info("Required plug-in status: Installed")
                                else:
                                    log.info("Optional plug-in status: Installed")
                            else:
                                num_errors += 1

                                if plugin == PLUGIN_REQUIRED:
                                    log.error("Required plug-in status: Not installed")
                                else:
                                    log.warn("Optional plug-in status: Not installed")


                        if bus in ('par', 'usb'):
                            try:
                                d.open()
                            except Error, e:
                                log.error(e.msg)
                                deviceid = ''
                            else:
                                deviceid = d.getDeviceID()
                                log.debug(deviceid)

                            #print deviceid
                            if not deviceid:
                                log.error("Communication status: Failed")
                                #error_code = pml.ERROR_COMMAND_EXECUTION
                                num_errors += 1
                            else:
                                log.info("Communication status: Good")

                        elif bus == 'net':
                            try:
                                error_code, deviceid = d.getPML(pml.OID_DEVICE_ID)
                            except Error:
                                #log.error("Communication with device failed.")
                                #error_code = pml.ERROR_COMMAND_EXECUTION
                                pass

                            #print error_code
                            if not deviceid:
                                log.error("Communication status: Failed")
                                num_errors += 1
                            else:
                                log.info("Communication status: Good")

                    finally:
                        if d is not None:
                            d.close()

                log.info()



        else:
            log.warn("No queues found.")

        if scanning_enabled:
            tui.header("SANE CONFIGURATION")
            log.info(log.bold("'hpaio' in '/etc/sane.d/dll.conf'..."))
            try:
                f = file('/etc/sane.d/dll.conf', 'r')
            except IOError:
                log.error("'/etc/sane.d/dll.conf' not found. Is SANE installed?")
                num_errors += 1
            else:
                found = False
                for line in f:
                    if 'hpaio' in line:
                        found = True

		# Debian/ Ubuntu place hpaio in /etc/sane.d/dll.d/hplip, so lets check there too

		if not found:
		    log.info(log.bold("'hpaio' in '/etc/sane.d/dll.d/hplip'..."))
		    try:
                       f = file('/etc/sane.d/dll.d/hplip', 'r')
                    except IOError:
                       log.error("'/etc/sane.d/dll.d/hplip' not found.")
                       num_errors += 1
                    else:
                        found = False
                        for line in f:
                            if 'hpaio' in line:
                                found = True

                if found:
                    log.info("OK, found. SANE backend 'hpaio' is properly set up.")
                else:
                    num_errors += 1
                    log.error("Not found. SANE backend 'hpaio' NOT properly setup (needs to be added to /etc/sane.d/dll.conf).")

                log.info()
                log.info(log.bold("Checking output of 'scanimage -L'..."))
                if utils.which('scanimage'):
                    status, output = utils.run("scanimage -L")
                    log.info(output)
                else:
                    log.error("scanimage not found.")

        tui.header("PYTHON EXTENSIONS")

        log.info(log.bold("Checking 'cupsext' CUPS extension..."))
        try:
            import cupsext
        except ImportError:
            num_errors += 1
            log.error("NOT FOUND OR FAILED TO LOAD! Please reinstall HPLIP and check for the proper installation of cupsext.")
        else:
            log.info("OK, found.")

        log.info()
        log.info(log.bold("Checking 'pcardext' Photocard extension..."))
        try:
            import pcardext
        except ImportError:
            num_errors += 1
            log.error("NOT FOUND OR FAILED TO LOAD! Please reinstall HPLIP and check for the proper installation of pcardext.")
        else:
            log.info("OK, found.")

        log.info()
        log.info(log.bold("Checking 'hpmudext' I/O extension..."))
        try:
            import hpmudext
            hpmudext_avail = True
        except ImportError:
            hpmudext_avail = False
            num_errors += 1
            log.error("NOT FOUND OR FAILED TO LOAD! Please reinstall HPLIP and check for the proper installation of hpmudext.")
        else:
            log.info("OK, found.")

        if scanning_enabled:
            log.info()
            log.info(log.bold("Checking 'scanext' SANE scanning extension..."))
            try:
                import scanext
            except ImportError:
                num_errors += 1
                log.error("NOT FOUND OR FAILED TO LOAD! Please reinstall HPLIP and check for the proper installation of scanext.")
            else:
                log.info("OK, found.")

                log.info()


        if hpmudext_avail:
            lsusb = utils.which('lsusb')
            if lsusb:
                log.info()

                lsusb = os.path.join(lsusb, 'lsusb')
                status, output = utils.run("%s -d03f0:" % lsusb)

                if output:
                    tui.header("USB I/O SETUP")
                    log.info(log.bold("Checking for permissions of USB attached printers..."))

                    lsusb_pat = re.compile("""^Bus\s([0-9a-fA-F]{3,3})\sDevice\s([0-9a-fA-F]{3,3}):\sID\s([0-9a-fA-F]{4,4}):([0-9a-fA-F]{4,4})(.*)""", re.IGNORECASE)
                    log.debug(output)

                    for o in output.splitlines():
                        ok = True
                        match = lsusb_pat.search(o)

                        if match is not None:
                            bus, dev, vid, pid, mfg = match.groups()
                            log.info("\nHP Device 0x%x at %s:%s: " % (int(pid, 16), bus, dev))
                            result_code, deviceuri = hpmudext.make_usb_uri(bus, dev)

                            if result_code == hpmudext.HPMUD_R_OK:
                                log.info("    Device URI: %s" %  deviceuri)
                                d = None
                                try:
                                    d = device.Device(deviceuri)
                                except Error:
                                    continue
                                if not d.supported:
                                    continue
                            else:
                                log.warn("    Device URI: (Makeuri FAILED)")
                                continue

                            devnode = os.path.join("/", "dev", "bus", "usb", bus, dev)

                            if not os.path.exists(devnode):
                                devnode = os.path.join("/", "proc", "bus", "usb", bus, dev)

                            if os.path.exists(devnode):
                                log.info("    Device node: %s" % devnode)

                                st_mode, st_ino, st_dev, st_nlink, st_uid, st_gid, \
                                    st_size, st_atime, st_mtime, st_ctime = \
                                    os.stat(devnode)

                                log.info("    Mode: 0%o" % (st_mode & 0777))

                                getfacl = utils.which('getfacl')
                                if getfacl:
                                    getfacl = os.path.join(getfacl, "getfacl")

                                    status, output = utils.run("%s %s" % (getfacl, devnode))

                                    log.info(output)

    tui.header("USER GROUPS")

    groups = utils.which('groups')
    if groups:
        groups = os.path.join(groups, 'groups')
        status, output = utils.run(groups)

        if status == 0:
            log.info(output)

        if "lp " in output:
            log.info(log.green("User member of group 'lp'. Enables print/ scan/ fax."))
        else:
            log.error("User needs to be member of group 'lp' to enable print, scan & fax.")

        if "lpadmin" in output:
            log.info(log.green("User member of group 'lpadmin'."))
        else:
            log.error("User needs to be member of group 'lpadmin' to manage printers.")


    tui.header("SUMMARY")

    if num_errors:
        if num_errors == 1:
            log.error("1 error or warning.")
        else:
            log.error("%d errors and/or warnings." % num_errors)

        if overall_commands_to_run:
            log.info()
            log.info(log.bold("Summary of needed commands to run to satisfy missing dependencies:"))
            for c in overall_commands_to_run:
                log.info(c)

        log.info()
        log.info("Please refer to the installation instructions at:")
        log.info("http://hplip.sourceforge.net/install/index.html\n")

    else:
        log.info(log.green("No errors or warnings."))

except KeyboardInterrupt:
    log.error("User exit")

log.info()
log.info("Done.")

