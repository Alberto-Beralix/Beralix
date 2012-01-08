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

# Std Lib
import sys
import os
import os.path
import re
import time
import cStringIO
import grp
import pwd
import tarfile

try:
    import hashlib # new in 2.5

    def get_checksum(s):
        return hashlib.sha1(s).hexdigest()

except ImportError:
    import sha # deprecated in 2.6/3.0

    def get_checksum(s):
        return sha.new(s).hexdigest()


import urllib # TODO: Replace with urllib2 (urllib is deprecated in Python 3.0)


# Local
from base.g import *
from base.codes import *
from base import utils, pexpect
from dcheck import *



DISTRO_UNKNOWN = 0
DISTRO_VER_UNKNOWN = '0.0'

MODE_INSTALLER = 0 # hplip-install/hp-setup
MODE_CHECK = 1 # hp-check
MODE_CREATE_DOCS = 2 # create_docs

TYPE_STRING = 1
TYPE_LIST = 2
TYPE_BOOL = 3
TYPE_INT = 4

DEPENDENCY_RUN_TIME = 1
DEPENDENCY_COMPILE_TIME = 2
DEPENDENCY_RUN_AND_COMPILE_TIME = 3

# Plug-in download errors
PLUGIN_INSTALL_ERROR_NONE = 0
PLUGIN_INSTALL_ERROR_PLUGIN_FILE_NOT_FOUND = 1
PLUGIN_INSTALL_ERROR_DIGITAL_SIG_NOT_FOUND = 2
PLUGIN_INSTALL_ERROR_DIGITAL_SIG_BAD = 3
PLUGIN_INSTALL_ERROR_PLUGIN_FILE_CHECKSUM_ERROR = 4
PLUGIN_INSTALL_ERROR_NO_NETWORK = 5
PLUGIN_INSTALL_ERROR_DIRECTORY_ERROR = 6
PLUGIN_INSTALL_ERROR_UNABLE_TO_RECV_KEYS = 7


PING_TARGET = "www.google.com"
HTTP_GET_TARGET = "http://www.google.com"

EXPECT_WORD_LIST = [
    pexpect.EOF, # 0
    pexpect.TIMEOUT, # 1
    "Continue?", # 2 (for zypper)
    "passwor[dt]", # en/de/it/ru
    "kennwort", # de?
    "password for", # en
    "mot de passe", # fr
    "contraseña", # es
    "palavra passe", # pt
    "口令", # zh
    "wachtwoord", # nl
    "heslo", # czech
]

# Mapping from patterns to probability contribution of pattern
# Example code from David Mertz' Text Processing in Python.
# Released in the Public Domain.
err_pats = {r'(?is)<TITLE>.*?(404|403).*?ERROR.*?</TITLE>': 0.95,
            r'(?is)<TITLE>.*?ERROR.*?(404|403).*?</TITLE>': 0.95,
            r'(?is)<TITLE>ERROR</TITLE>': 0.30,
            r'(?is)<TITLE>.*?ERROR.*?</TITLE>': 0.10,
            r'(?is)<META .*?(404|403).*?ERROR.*?>': 0.80,
            r'(?is)<META .*?ERROR.*?(404|403).*?>': 0.80,
            r'(?is)<TITLE>.*?File Not Found.*?</TITLE>': 0.80,
            r'(?is)<TITLE>.*?Not Found.*?</TITLE>': 0.40,
            r'(?is)<BODY.*(404|403).*</BODY>': 0.10,
            r'(?is)<H1>.*?(404|403).*?</H1>': 0.15,
            r'(?is)<BODY.*not found.*</BODY>': 0.10,
            r'(?is)<H1>.*?not found.*?</H1>': 0.15,
            r'(?is)<BODY.*the requested URL.*</BODY>': 0.10,
            r'(?is)<BODY.*the page you requested.*</BODY>': 0.10,
            r'(?is)<BODY.*page.{1,50}unavailable.*</BODY>': 0.10,
            r'(?is)<BODY.*request.{1,50}unavailable.*</BODY>': 0.10,
            r'(?i)does not exist': 0.10,
           }
# end


EXPECT_LIST = []
for s in EXPECT_WORD_LIST:
    try:
        p = re.compile(s, re.I)
    except TypeError:
        EXPECT_LIST.append(s)
    else:
        EXPECT_LIST.append(p)

OK_PROCESS_LIST = ['adept-notifier',
                   'adept_notifier',
                   'yum-updatesd',
                   ]

CONFIGURE_ERRORS = { 1 : "General/unknown error",
                     2 : "libusb not found",
                     3 : "cups-devel not found",
                     4 : "libnetsnmp not found",
                     5 : "netsnmp-devel not found",
                     6 : "python-devel not found",
                     7 : "pthread-devel not found",
                     8 : "ppdev-devel not found",
                     9 : "libcups not found",
                     10 : "libm not found",
                     11 : "libusb-devel not found",
                     12 : "sane-backends-devel not found",
                     13 : "libdbus not found",
                     14 : "dbus-devel not found",
                     15 : "fax requires dbus support",
                     102 : "libjpeg not found",
                     103 : "jpeg-devel not found",
                     104 : "libdi not found",
                   }


try:
    from functools import update_wrapper
except ImportError: # using Python version < 2.5
    def trace(f):
        def newf(*args, **kw):
           log.debug("TRACE: func=%s(), args=%s, kwargs=%s" % (f.__name__, args, kw))
           return f(*args, **kw)
        newf.__name__ = f.__name__
        newf.__dict__.update(f.__dict__)
        newf.__doc__ = f.__doc__
        newf.__module__ = f.__module__
        return newf
else: # using Python 2.5+
    def trace(f):
        def newf(*args, **kw):
            log.debug("TRACE: func=%s(), args=%s, kwargs=%s" % (f.__name__, args, kw))
            return f(*args, **kw)
        return update_wrapper(newf, f)



class CoreInstall(object):
    def __init__(self, mode=MODE_INSTALLER, ui_mode=INTERACTIVE_MODE, ui_toolkit='qt4'):
        os.umask(0022)
        self.mode = mode
        self.ui_mode = ui_mode
        self.password = ''
        self.version_description, self.version_public, self.version_internal = '', '', ''
        self.bitness = 32
        self.endian = utils.LITTLE_ENDIAN
        self.distro, self.distro_name, self.distro_version = DISTRO_UNKNOWN, '', DISTRO_VER_UNKNOWN
        self.distro_version_supported = False
        self.install_location = '/usr'
        self.hplip_present = False
        self.have_dependencies = {}
        self.native_cups = True
        self.ppd_dir = None
        self.drv_dir = None
        self.distros = {}
        self.network_connected = False
        self.ui_toolkit = ui_toolkit
        self.enable = None
        self.disable = None
        self.plugin_path = "/tmp"
        self.plugin_version = '0.0.0'
        self.plugin_name = ''
        self.reload_dbus = False


        self.FIELD_TYPES = {
            'distros' : TYPE_LIST,
            'index' : TYPE_INT,
            'versions' : TYPE_LIST,
            'display_name' : TYPE_STRING,
            'alt_names': TYPE_LIST,
            'display': TYPE_BOOL,
            'notes': TYPE_STRING,
            'package_mgrs': TYPE_LIST,
            'package_mgr_cmd':TYPE_STRING,
            'pre_install_cmd': TYPE_LIST,
            'pre_depend_cmd': TYPE_LIST,
            'post_depend_cmd': TYPE_LIST,
            'hpoj_remove_cmd': TYPE_STRING,
            'hplip_remove_cmd': TYPE_STRING,
            'su_sudo': TYPE_STRING,
            'ppd_install': TYPE_STRING,
            'udev_mode_fix': TYPE_BOOL,
            'ppd_dir': TYPE_STRING,
            'drv_dir' : TYPE_STRING,
            'fix_ppd_symlink': TYPE_BOOL,
            'code_name': TYPE_STRING,
            'supported': TYPE_BOOL, # Supported by installer
            'release_date': TYPE_STRING,
            'packages': TYPE_LIST,
            'commands': TYPE_LIST,
            'same_as_version' : TYPE_STRING,
            'scan_supported' : TYPE_BOOL,
            'fax_supported' : TYPE_BOOL,
            'pcard_supported' : TYPE_BOOL,
            'network_supported' : TYPE_BOOL,
            'parallel_supported' : TYPE_BOOL,
            'usb_supported' : TYPE_BOOL,
            'packaged_version': TYPE_STRING, # Version of HPLIP pre-packaged in distro
            'cups_path_with_bitness' : TYPE_BOOL,
            'ui_toolkit' : TYPE_STRING,  # qt3 or qt4 [or gtk] or none
            'policykit' : TYPE_BOOL,
            'native_cups' : TYPE_BOOL,
            'package_available' : TYPE_BOOL,
            'package_arch' : TYPE_LIST,
            'add_user_to_group': TYPE_STRING,
            'open_mdns_port' : TYPE_LIST, # command to use to open mdns multicast port 5353
            'acl_rules' : TYPE_BOOL, # Use ACL uDEV rules (Ubuntu 9.10+)
        }

        # components
        # 'name': ('description', [<option list>])
        self.components = {
            'hplip': ("HP Linux Imaging and Printing System", ['base', 'network', 'gui_qt4',
                                                               'fax', 'scan', 'docs']),
        }

        self.selected_component = 'hplip'

        # options
        # name: (<required>, "<display_name>", [<dependency list>]), ...
        self.options = {
            'base':     (True,  'Required HPLIP base components (including hpcups)', []), # HPLIP
            'network' : (False, 'Network/JetDirect I/O', []),
            'gui_qt4' : (False, 'Graphical User Interfaces (Qt4)', []),
            'fax' :     (False, 'PC Send Fax support', []),
            'scan':     (False, 'Scanning support', []),
            'docs':     (False, 'HPLIP documentation (HTML)', []),
            'policykit': (False, 'Administrative policy framework', []),
        }


        # holds whether the user has selected (turned on each option)
        # initial values are defaults (for GUI only)
        self.selected_options = {
            'base':        True,
            'network':     True,
            'gui_qt4':     True,
            'fax':         True,
            'scan':        True,
            'docs':        True,
            'policykit':   False,
            'native_cups': False,
        }

        # dependencies
        # 'name': (<required for option>, [<option list>], <display_name>, <check_func>, <runtime/compiletime>), ...
        # Note: any change to the list of dependencies must be reflected in base/distros.py
        self.dependencies = {
            # Required base packages
            'libjpeg':          (True,  ['base'], "libjpeg - JPEG library", self.check_libjpeg, DEPENDENCY_RUN_AND_COMPILE_TIME),
            'libtool':          (True,  ['base'], "libtool - Library building support services", self.check_libtool, DEPENDENCY_COMPILE_TIME),
            'cups' :            (True,  ['base'], 'CUPS - Common Unix Printing System', self.check_cups, DEPENDENCY_RUN_TIME),
            'cups-devel':       (True,  ['base'], 'CUPS devel- Common Unix Printing System development files', self.check_cups_devel, DEPENDENCY_COMPILE_TIME),
            'cups-image':       (True,  ['base'], "CUPS image - CUPS image development files", self.check_cups_image, DEPENDENCY_COMPILE_TIME),
            'gcc' :             (True,  ['base'], 'gcc - GNU Project C and C++ Compiler', self.check_gcc, DEPENDENCY_COMPILE_TIME),
            'make' :            (True,  ['base'], "make - GNU make utility to maintain groups of programs", self.check_make, DEPENDENCY_COMPILE_TIME),
            'python-devel' :    (True,  ['base'], "Python devel - Python development files", self.check_python_devel, DEPENDENCY_COMPILE_TIME),
            'libpthread' :      (True,  ['base'], "libpthread - POSIX threads library", self.check_libpthread, DEPENDENCY_RUN_AND_COMPILE_TIME),
            'python2x':         (True,  ['base'], "Python 2.2 or greater - Python programming language", self.check_python2x, DEPENDENCY_RUN_AND_COMPILE_TIME),
            'python-xml'  :     (True,  ['base'], "Python XML libraries", self.check_python_xml, DEPENDENCY_RUN_TIME),
            'gs':               (True,  ['base'], "GhostScript - PostScript and PDF language interpreter and previewer", self.check_gs, DEPENDENCY_RUN_TIME),
            'libusb':           (True,  ['base'], "libusb - USB library", self.check_libusb, DEPENDENCY_RUN_AND_COMPILE_TIME),

            # Optional base packages
            'cups-ddk':          (False, ['base'], "CUPS DDK - CUPS driver development kit", self.check_cupsddk, DEPENDENCY_RUN_TIME), # req. for .drv PPD installs


            # Required scan packages
            'sane':             (True,  ['scan'], "SANE - Scanning library", self.check_sane, DEPENDENCY_RUN_TIME),
            'sane-devel' :      (True,  ['scan'], "SANE - Scanning library development files", self.check_sane_devel, DEPENDENCY_COMPILE_TIME),

            # Optional scan packages
            'xsane':            (False, ['scan'], "xsane - Graphical scanner frontend for SANE", self.check_xsane, DEPENDENCY_RUN_TIME),
            'scanimage':        (False, ['scan'], "scanimage - Shell scanning program", self.check_scanimage, DEPENDENCY_RUN_TIME),
            'pil':              (False, ['scan'], "PIL - Python Imaging Library (required for commandline scanning with hp-scan)", self.check_pil, DEPENDENCY_RUN_TIME),

            # Required fax packages
            'python23':         (True,  ['fax'], "Python 2.3 or greater - Required for fax functionality", self.check_python23, DEPENDENCY_RUN_TIME),
            'dbus':             (True,  ['fax'], "DBus - Message bus system", self.check_dbus, DEPENDENCY_RUN_AND_COMPILE_TIME),
            'python-dbus':      (True,  ['fax'], "Python DBus - Python bindings for DBus", self.check_python_dbus, DEPENDENCY_RUN_TIME),

            # Optional fax packages
            'reportlab':        (False, ['fax'], "Reportlab - PDF library for Python", self.check_reportlab, DEPENDENCY_RUN_TIME),

            # Required and optional qt4 GUI packages
            'pyqt4':            (True,  ['gui_qt4'], "PyQt 4- Qt interface for Python (for Qt version 4.x)", self.check_pyqt4, DEPENDENCY_RUN_TIME), # PyQt 4.x )
            'pyqt4-dbus' :      (True,  ['gui_qt4'], "PyQt 4 DBus - DBus Support for PyQt4", self.check_pyqt4_dbus, DEPENDENCY_RUN_TIME),
            'policykit':        (False, ['gui_qt4'], "PolicyKit - Administrative policy framework", self.check_policykit, DEPENDENCY_RUN_TIME), # optional for non-sudo behavior of plugins (only optional for Qt4 option)
            'python-notify' :   (False, ['gui_qt4'], "Python libnotify - Python bindings for the libnotify Desktop notifications", self.check_pynotify, DEPENDENCY_RUN_TIME), # Optional for libnotify style popups from hp-systray

            # Required network I/O packages
            'libnetsnmp-devel': (True,  ['network'], "libnetsnmp-devel - SNMP networking library development files", self.check_libnetsnmp, DEPENDENCY_RUN_AND_COMPILE_TIME),
            'libcrypto':        (True,  ['network'], "libcrypto - OpenSSL cryptographic library", self.check_libcrypto, DEPENDENCY_RUN_AND_COMPILE_TIME),
        }

        for opt in self.options:
            update_spinner()
            for d in self.dependencies:
                if opt in self.dependencies[d][1]:
                    self.options[opt][2].append(d)

        self.load_distros()

        self.distros_index = {}
        for d in self.distros:
            self.distros_index[self.distros[d]['index']] = d


    def init(self, callback=None):
        if callback is not None:
            callback("Init...\n")

        update_spinner()

        # Package manager names
        self.package_mgrs = []
        for d in self.distros:
            update_spinner()

            for a in self.distros[d].get('package_mgrs', []):
                if a and a not in self.package_mgrs:
                    self.package_mgrs.append(a)

        self.version_description, self.version_public, self.version_internal = self.get_hplip_version()
        log.debug("HPLIP Description=%s Public version=%s Internal version = %s"  %
            (self.version_description, self.version_public, self.version_internal))

        # have_dependencies
        # is each dependency satisfied?
        # start with each one 'No'
        for d in self.dependencies:
            update_spinner()
            self.have_dependencies[d] = False

        self.get_distro()
        self.distro_changed()

        if callback is not None:
            callback("Distro: %s\n" % self.distro)

        self.check_dependencies(callback)

        for d in self.dependencies:
            update_spinner()

            log.debug("have %s = %s" % (d, self.have_dependencies[d]))

            if callback is not None:
                callback("Result: %s = %s\n" % (d, self.have_dependencies[d]))

        pid, cmdline = self.check_pkg_mgr()
        if pid:
            log.debug("Running package manager: %s (%d)" % (cmdline, pid) )

        self.bitness = utils.getBitness()
        log.debug("Bitness = %d" % self.bitness)

        update_spinner()

        self.endian = utils.getEndian()
        log.debug("Endian = %d" % self.endian)

        update_spinner()

        self.distro_name = self.distros_index[self.distro]
        self.distro_version_supported = self.get_distro_ver_data('supported', False)

        log.debug("Distro = %s Distro Name = %s Display Name= %s Version = %s Supported = %s" %
            (self.distro, self.distro_name, self.distros[self.distro_name]['display_name'],
             self.distro_version, self.distro_version_supported))

        update_spinner()

        self.hplip_present = self.check_hplip()
        log.debug("HPLIP (prev install) = %s" % self.hplip_present)

        status, output = self.run('cups-config --version')
        self.cups_ver = output.strip()
        log.debug("CUPS version = %s" % self.cups_ver)

        if self.distro_name == "ubuntu":
            self.reload_dbus = True

        log.debug("DBUS configuration reload possible? %s" % self.reload_dbus)

        status, self.sys_uname_info = self.run('uname -a')
        self.sys_uname_info = self.sys_uname_info.replace('\n', '')
        log.debug(self.sys_uname_info)

        # Record the installation time/date and version.
        # Also has the effect of making the .hplip.conf file user r/w
        # on the 1st run so that running hp-setup as root doesn't lock
        # the user out of owning the file
        user_conf.set('installation', 'date_time', time.strftime("%x %H:%M:%S", time.localtime()))
        user_conf.set('installation', 'version', self.version_public)

        if callback is not None:
            callback("Done")


    def init_for_docs(self, distro_name, version, bitness=32):
        self.distro_name = distro_name
        self.distro_version = version

        try:
            self.distro = self.distros[distro_name]['index']
        except KeyError:
            log.error("Invalid distro name: %s" % distro_name)
            sys.exit(1)

        self.bitness = bitness

        for d in self.dependencies:
            self.have_dependencies[d] = True

        self.enable_ppds = self.get_distro_ver_data('ppd_install', 'ppd') == 'ppd'
        self.ppd_dir = self.get_distro_ver_data('ppd_dir')
        self.drv_dir = self.get_distro_ver_data('drv_dir')

        self.distro_version_supported = True # for manual installs


    def check_dependencies(self, callback=None):
        update_ld_output()

        for d in self.dependencies:
            update_spinner()

            log.debug("Checking for dependency '%s'...\n" % d)

            if callback is not None:
                callback("Checking: %s\n" % d)

            self.have_dependencies[d] = self.dependencies[d][3]()
            log.debug("have %s = %s" % (d, self.have_dependencies[d]))

        cleanup_spinner()


    def password_func(self):
        if self.password:
            return self.password
        elif self.ui_mode == INTERACTIVE_MODE:
            import getpass
            return getpass.getpass("Enter password: ")
        else:
            return ''


    def run(self, cmd, callback=None, timeout=300): # ==> status, output
        if cmd is None:
            return 1, ''
        output = cStringIO.StringIO()
        ok, ret = False, ''
        # Hack! TODO: Fix!
        check_timeout = not (cmd.startswith('xterm') or cmd.startswith('gnome-terminal'))

        try:
            child = pexpect.spawn(cmd, timeout=1)
        except pexpect.ExceptionPexpect:
            return 1, ''

        try:
            try:
                start = time.time()

                while True:
                    update_spinner()

                    i = child.expect_list(EXPECT_LIST)

                    cb = child.before
                    if cb:
                        # output
                        start = time.time()
                        log.log_to_file(cb)
                        log.debug(cb)
                        output.write(cb)

                        if callback is not None:
                            if callback(cb): # cancel
                                break

                    elif check_timeout:
                        # no output
                        span = int(time.time()-start)

                        if span:
                            if span % 5 == 0:
                                log.debug("No output seen in %d secs" % span)

                            if span > timeout:
                                log.error("No output seen in over %d sec... (Is the CD-ROM/DVD source repository enabled? It shouldn't be!)" % timeout)
                                child.close()
                                child.terminate(force=True)
                                break

                    if i == 0: # EOF
                        ok, ret = True, output.getvalue()
                        break

                    elif i == 1: # TIMEOUT
                        continue

                    elif i == 2: # zypper "Continue?"
                        child.sendline("YES")

                    else: # password
                        child.sendline(self.password)

            except (Exception, pexpect.ExceptionPexpect):
                log.exception()

        finally:
            cleanup_spinner()

            try:
                child.close()
            except OSError:
                pass

        if ok:
            return child.exitstatus, ret
        else:
            return 1, ''


    def get_distro(self):
        log.debug("Determining distro...")
        self.distro, self.distro_version = DISTRO_UNKNOWN, '0.0'

        found = False

        lsb_release = utils.which("lsb_release")

        if lsb_release:
            log.debug("Using 'lsb_release -is/-rs'")
            cmd = os.path.join(lsb_release, "lsb_release")
            status, name = self.run(cmd + ' -is')
            name = name.lower().strip()
            log.debug("Distro name=%s" % name)

            if not status and name:
                status, ver = self.run(cmd + ' -rs')
                ver = ver.lower().strip()
                log.debug("Distro version=%s" % ver)

                if not status and ver:
                    for d in self.distros:
                        if name.find(d) > -1:
                            self.distro = self.distros[d]['index']
                            found = True
                            self.distro_version = ver
                            break

        if not found:
            try:
                name = file('/etc/issue', 'r').read().lower().strip()
            except IOError:
                # Some O/Ss don't have /etc/issue (Mac)
                self.distro, self.distro_version = DISTRO_UNKNOWN, '0.0'
            else:
                for d in self.distros:
                    if name.find(d) > -1:
                        self.distro = self.distros[d]['index']
                        found = True
                    else:
                        for x in self.distros[d].get('alt_names', ''):
                            if x and name.find(x) > -1:
                                self.distro = self.distros[d]['index']
                                found = True
                                break

                    if found:
                        break

                if found:
                    for n in name.split():
                        m= n
                        if '.' in n:
                            m = '.'.join(n.split('.')[:2])

                        try:
                            float(m)
                        except ValueError:
                            try:
                                int(m)
                            except ValueError:
                                self.distro_version = '0.0'
                            else:
                                self.distro_version = m
                                break
                        else:
                            self.distro_version = m
                            break

                    log.debug("/etc/issue: %s %s" % (name, self.distro_version))

        log.debug("distro=%d, distro_version=%s" % (self.distro, self.distro_version))


    def distro_changed(self):
        ppd_install = self.get_distro_ver_data('ppd_install', 'ppd')

        if ppd_install not in ('ppd', 'drv'):
            log.warning("Invalid ppd_install value: %s" % ppd_install)

        self.enable_ppds = (ppd_install == 'ppd')

        log.debug("Enable PPD install: %s (False=drv)" % self.enable_ppds)

        self.ppd_dir = self.get_distro_ver_data('ppd_dir')

        self.drv_dir = self.get_distro_ver_data('drv_dir')
        if not self.enable_ppds and not self.drv_dir:
            log.warning("Invalid drv_dir value: %s" % self.drv_dir)

        self.distro_version_supported = self.get_distro_ver_data('supported', False)
        self.selected_options['fax'] = self.get_distro_ver_data('fax_supported', True)
        self.selected_options['network'] = self.get_distro_ver_data('network_supported', True)
        self.selected_options['scan'] = self.get_distro_ver_data('scan_supported', True)
        self.selected_options['policykit'] = self.get_distro_ver_data('policykit', False)
        self.native_cups = self.get_distro_ver_data('native_cups', False)

        # Adjust required flag based on the distro ver ui_toolkit value
        ui_toolkit = self.get_distro_ver_data('ui_toolkit',  'qt4').lower()

        if ui_toolkit == 'qt4':
            log.debug("Default UI toolkit: Qt4")
            self.ui_toolkit = 'qt4'
            self.selected_options['gui_qt4'] = True

        # todo: gtk
        else:
            self.selected_options['gui_qt4'] = False

        # Override with --qt4 command args
        if self.enable is not None:
            if 'qt4' in self.enable:
                log.debug("User selected UI toolkit: Qt4")
                self.ui_toolkit = 'qt4'
                self.selected_options['gui_qt4'] = True

        if self.disable is not None:
            if 'qt4' in self.disable:
                log.debug("User deselected UI toolkit: Qt4")
                self.selected_options['gui_qt4'] = False


    def __fixup_data(self, key, data):
        field_type = self.FIELD_TYPES.get(key, TYPE_STRING)
        #log.debug("%s (%s) %d" % (key, data, field_type))

        if field_type == TYPE_BOOL:
            return utils.to_bool(data)

        elif field_type == TYPE_STRING:
            if type('') == type(data):
                return data.strip()
            else:
                return data

        elif field_type == TYPE_INT:
            try:
                return int(data)
            except ValueError:
                return 0

        elif field_type == TYPE_LIST:
            return [x for x in data.split(',') if x]


    def load_distros(self):
        if self.mode  == MODE_INSTALLER:
            distros_dat_file = os.path.join('installer', 'distros.dat')

        elif self.mode == MODE_CREATE_DOCS:
            distros_dat_file = os.path.join('..', '..', 'installer', 'distros.dat')

        else: # MODE_CHECK
            distros_dat_file = os.path.join(prop.home_dir, 'installer', 'distros.dat')

            if not os.path.exists(distros_dat_file):
                log.debug("DAT file not found at %s. Using local relative path..." % distros_dat_file)
                distros_dat_file = os.path.join('installer', 'distros.dat')

        distros_dat = ConfigBase(distros_dat_file)
        distros_list = self.__fixup_data('distros', distros_dat.get('distros', 'distros'))
        log.debug(distros_list)

        for distro in distros_list:
            update_spinner()
            d = {}

            if not distros_dat.has_section(distro):
                log.debug("Missing distro section in distros.dat: [%s]" % distro)
                continue

            for key in distros_dat.keys(distro):
                d[key] = self.__fixup_data(key, distros_dat.get(distro, key))

            self.distros[distro] = d
            versions = self.__fixup_data("versions", distros_dat.get(distro, 'versions'))
            self.distros[distro]['versions'] = {}

            for ver in versions:
                same_as_version, supported = False, True
                v = {}
                ver_section = "%s:%s" % (distro, ver)

                if not distros_dat.has_section(ver_section):
                    log.error("Missing version section in distros.dat: [%s:%s]" % (distro, ver))
                    continue

                if 'same_as_version' in distros_dat.keys(ver_section):
                    same_as_version = True

                supported = self.__fixup_data('supported', distros_dat.get(ver_section, 'supported'))

                for key in distros_dat.keys(ver_section):
                    v[key] = self.__fixup_data(key, distros_dat.get(ver_section, key))

                self.distros[distro]['versions'][ver] = v
                self.distros[distro]['versions'][ver]['dependency_cmds'] = {}

                if same_as_version: # or not supported:
                    continue

                for dep in self.dependencies:
                    dd = {}
                    dep_section = "%s:%s:%s" % (distro, ver, dep)

                    if not distros_dat.has_section(dep_section) and not same_as_version:
                        log.debug("Missing dependency section in distros.dat: [%s:%s:%s]" % (distro, ver, dep))
                        continue

                    #if same_as_version:
                    #    continue

                    for key in distros_dat.keys(dep_section):
                        dd[key] = self.__fixup_data(key, distros_dat.get(dep_section, key))

                    self.distros[distro]['versions'][ver]['dependency_cmds'][dep] = dd

            versions = self.distros[distro]['versions']
            for ver in versions:
                ver_section = "%s:%s" % (distro, ver)

                if 'same_as_version' in distros_dat.keys(ver_section):
                    v = self.__fixup_data("same_as_version", distros_dat.get(ver_section, 'same_as_version'))
                    log.debug("Setting %s:%s to %s:%s" % (distro, ver, distro, v))

                    try:
                        vv = self.distros[distro]['versions'][v].copy()
                        vv['same_as_version'] = v
                        self.distros[distro]['versions'][ver] = vv
                    except KeyError:
                        log.debug("Missing 'same_as_version=' version in distros.dat for section [%s:%s]." % (distro, v))
                        continue

        #import pprint
        #pprint.pprint(self.distros)

    def pre_install(self):
        pass


    def pre_depend(self):
        pass


    def check_python2x(self):
        py_ver = sys.version_info
        py_major_ver, py_minor_ver = py_ver[:2]
        log.debug("Python ver=%d.%d" % (py_major_ver, py_minor_ver))
        return py_major_ver >= 2


    def check_gcc(self):
        return check_tool('gcc --version', 0) and check_tool('g++ --version', 0)


    def check_make(self):
        return check_tool('make --version', 3.0)


    def check_libusb(self):
        if not check_lib('libusb'):
            return False

        return len(locate_file_contains("usb.h", '/usr/include', 'usb_init(void)'))


    def check_libjpeg(self):
        return check_lib("libjpeg") and check_file("jpeglib.h")


    def check_libcrypto(self):
        return check_lib("libcrypto") and check_file("crypto.h")


    def check_libpthread(self):
        return check_lib("libpthread") and check_file("pthread.h")


    def check_libnetsnmp(self):
        return check_lib("libnetsnmp") and check_file("net-snmp-config.h")


    def check_reportlab(self):
        try:
            log.debug("Trying to import 'reportlab'...")
            import reportlab

            ver = reportlab.Version
            try:
                ver_f = float(ver)
            except ValueError:
                log.debug("Can't determine version.")
                return False
            else:
                log.debug("Version: %.1f" % ver_f)
                if ver_f >= 2.0:
                    log.debug("Success.")
                    return True
                else:
                    return False

        except ImportError:
            log.debug("Failed.")
            return False


    def check_python23(self):
        py_ver = sys.version_info
        py_major_ver, py_minor_ver = py_ver[:2]
        log.debug("Python ver=%d.%d" % (py_major_ver, py_minor_ver))
        return py_major_ver >= 2 and py_minor_ver >= 3


    def check_python_xml(self):
        try:
            import xml.parsers.expat
        except ImportError:
            return False
        else:
            return True


    def check_sane(self):
        return check_lib('libsane')


    def check_sane_devel(self):
        return len(locate_file_contains("sane.h", '/usr/include', 'extern SANE_Status sane_init'))


    def check_xsane(self):
        if os.getenv('DISPLAY'):
            return check_tool('xsane --version', 0.9) # will fail if X not running...
        else:
            return bool(utils.which("xsane")) # ...so just see if it installed somewhere


    def check_scanimage(self):
        return check_tool('scanimage --version', 1.0)


    def check_gs(self):
        return check_tool('gs -v', 7.05)


    def check_pyqt4(self):
        if self.ui_toolkit == 'qt4':
            try:
                import PyQt4
            except ImportError:
                return False
            else:
                return True

        else:
            return False


    def check_pyqt4_dbus(self):
        if self.ui_toolkit == 'qt4':
            try:
                from dbus.mainloop.qt import DBusQtMainLoop
            except ImportError:
                return False
            else:
                return True
        else:
            return False


    def check_python_devel(self):
        return check_file('Python.h')


    def check_pynotify(self):
        try:
            import pynotify
        except ImportError:
            return False

        return True


    def check_python_dbus(self):
        log.debug("Checking for python-dbus (>= 0.80)...")
        try:
            import dbus
            try:
                ver = dbus.version
                log.debug("Version: %s" % '.'.join([str(x) for x in dbus.version]))
                return ver >= (0,80,0)

            except AttributeError:
                try:
                    ver = dbus.__version__
                    log.debug("Version: %s" % dbus.__version__)
                    log.debug("HPLIP requires dbus version > 0.80.")
                    return False

                except AttributeError:
                    log.debug("Unknown version. HPLIP requires dbus version > 0.80.")
                    return False

        except ImportError:
            return False


    def check_python_ctypes(self):
        try:
            import ctypes
            return True
        except ImportError:
            return False


    def check_dbus(self):
        log.debug("Checking for dbus running and header files present (dbus-devel)...")
        return check_ps(['dbus-daemon'])  and \
            len(locate_file_contains("dbus-message.h", '/usr/include', 'dbus_message_new_signal'))


    def check_cups_devel(self):
        return check_file('cups.h') and bool(utils.which('lpr'))


    def check_cups(self):
        status, output = self.run('lpstat -r')
        if status > 0:
            log.debug("CUPS is not running.")
            return False
        else:
            log.debug("CUPS is running.")
            return True


    def check_cups_image(self):
      return check_file("raster.h", "/usr/include/cups")


    def check_hplip(self):
        log.debug("Checking for HPLIP...")
        return locate_files('hplip.conf', '/etc/hp')


    def check_hpssd(self):
        log.debug("Checking for hpssd...")
        return check_ps(['hpssd'])


    def check_libtool(self):
        log.debug("Checking for libtool...")
        return check_tool('libtool --version')


    def check_pil(self):
        log.debug("Checking for PIL...")
        try:
            import Image
            return True
        except ImportError:
            return False


    def check_cupsddk(self):
        log.debug("Checking for cups-ddk...")
        # TODO: Compute these paths some way or another...
        #return check_tool("/usr/lib/cups/driver/drv list") and os.path.exists("/usr/share/cupsddk/include/media.defs")
        return (check_file('drv', "/usr/lib/cups/driver") or check_file('drv', "/usr/lib64/cups/driver")) and \
            check_file('media.defs', "/usr/share/cupsddk/include")


    def check_policykit(self):
        log.debug("Checking for PolicyKit...")
        return (check_file('PolicyKit.conf', "/etc/PolicyKit") and check_file('org.gnome.PolicyKit.AuthorizationManager.service', "/usr/share/dbus-1/services")) or (check_file('50-localauthority.conf', "/etc/polkit-1/localauthority.conf.d") and check_file('org.freedesktop.PolicyKit1.service', "/usr/share/dbus-1/system-services"))

    def check_pkg_mgr(self):
        """
            Check if any pkg mgr processes are running
        """
        log.debug("Searching for '%s' in running processes..." % self.package_mgrs)

        processes = get_process_list()

        for pid, cmdline in processes:
            for p in self.package_mgrs:
                if p in cmdline:
                    for k in OK_PROCESS_LIST:
                        #print k, cmdline
                        if k in cmdline:
                            break

                    else:
                        log.debug("Found: %s (%d)" % (cmdline, pid))
                        return (pid, cmdline)

        log.debug("Not found")
        return (0, '')


    def get_hplip_version(self):
        self.version_description, self.version_public, self.version_internal = '', '', ''

        if self.mode == MODE_INSTALLER:
            ac_init_pat = re.compile(r"""AC_INIT\(\[(.*?)\], *\[(.*?)\], *\[(.*?)\], *\[(.*?)\] *\)""", re.IGNORECASE)

            try:
                config_in = open('./configure.in', 'r')
            except IOError:
                self.version_description, self.version_public, self.version_internal = \
                    '', sys_conf.get('configure', 'internal-tag', '0.0.0'), prop.installed_version
            else:
                for c in config_in:
                    if c.startswith("AC_INIT"):
                        match_obj = ac_init_pat.search(c)
                        self.version_description = match_obj.group(1)
                        self.version_public = match_obj.group(2)
                        self.version_internal = match_obj.group(3)
                        name = match_obj.group(4)
                        break

                config_in.close()

                if name != 'hplip':
                    log.error("Invalid archive!")


        else: # MODE_CHECK
            try:
                self.version_description, self.version_public, self.version_internal = \
                    '', sys_conf.get('configure', 'internal-tag', '0.0.0'), prop.installed_version
            except KeyError:
                self.version_description, self.version_public, self.version_internal = '', '', ''

        return self.version_description, self.version_public, self.version_internal


    def configure(self):
        configure_cmd = './configure'
        configuration = {}
        dbus_avail = self.have_dependencies['dbus'] and self.have_dependencies['python-dbus']
        configuration['network-build'] = self.selected_options['network']
        configuration['fax-build'] = self.selected_options['fax'] and dbus_avail
        configuration['dbus-build'] = dbus_avail
        configuration['qt4'] = self.selected_options['gui_qt4']
        configuration['scan-build'] = self.selected_options['scan']
        configuration['doc-build'] = self.selected_options['docs']
        configuration['policykit'] = self.selected_options['policykit']

        # Setup printer driver configure flags based on distro data...
        if self.native_cups: # hpcups
            configuration['hpcups-install'] = True
            configuration['hpijs-install'] = False
            configuration['foomatic-ppd-install'] = False
            configuration['foomatic-drv-install'] = False

            if self.enable_ppds:
                configuration['cups-ppd-install'] = True
                configuration['cups-drv-install'] = False
            else:
                configuration['cups-ppd-install'] = False
                configuration['cups-drv-install'] = True

        else: # HPIJS/foomatic
            configuration['hpcups-install'] = False
            configuration['hpijs-install'] = True
            configuration['cups-ppd-install'] = False
            configuration['cups-drv-install'] = False

            if self.enable_ppds:
                configuration['foomatic-ppd-install'] = True
                configuration['foomatic-drv-install'] = False
            else:
                configuration['foomatic-ppd-install'] = False
                configuration['foomatic-drv-install'] = True


        # ... and then override and adjust for consistency with passed in parameters
        if self.enable is not None:
            for c in self.enable:
                if c == 'hpcups-install':
                    configuration['hpijs-install'] = False
                    configuration['foomatic-ppd-install'] = False
                    configuration['foomatic-drv-install'] = False
                elif c == 'hpijs-install':
                    configuration['hpcups-install'] = False
                    configuration['cups-ppd-install'] = False
                    configuration['cups-drv-install'] = False
                elif c == 'foomatic-ppd-install':
                    configuration['foomatic-drv-install'] = False
                elif c == 'foomatic-drv-install':
                    configuration['foomatic-ppd-install'] = False
                elif c == 'cups-ppd-install':
                    configuration['cups-drv-install'] = False
                elif c == 'cups-drv-install':
                    configuration['cups-ppd-install'] = False

        if self.disable is not None:
            for c in self.disable:
                if c == 'hpcups-install':
                    configuration['hpijs-install'] = True
                    configuration['cups-ppd-install'] = False
                    configuration['cups-drv-install'] = False
                elif c == 'hpijs-install':
                    configuration['hpcups-install'] = True
                    configuration['foomatic-ppd-install'] = False
                    configuration['foomatic-drv-install'] = False
                elif c == 'foomatic-ppd-install':
                    configuration['foomatic-drv-install'] = True
                elif c == 'foomatic-drv-install':
                    configuration['foomatic-ppd-install'] = True
                elif c == 'cups-ppd-install':
                    configuration['cups-drv-install'] = True
                elif c == 'cups-drv-install':
                    configuration['cups-ppd-install'] = True

        if self.ppd_dir is not None:
            configure_cmd += ' --with-hpppddir=%s' % self.ppd_dir

        if self.bitness == 64:
            configure_cmd += ' --libdir=/usr/lib64'

        configure_cmd += ' --prefix=%s' % self.install_location

        if self.get_distro_ver_data('cups_path_with_bitness', False) and self.bitness == 64:
            configure_cmd += ' --with-cupsbackenddir=/usr/lib64/cups/backend --with-cupsfilterdir=/usr/lib64/cups/filter'

        if self.get_distro_ver_data('acl_rules', False):
            configure_cmd += ' --enable-udev-acl-rules'

        if self.enable is not None:
            for c in self.enable:
                configuration[c] = True

        if self.disable is not None:
            for c in self.disable:
                configuration[c] = False

        for c in configuration:
            if configuration[c]:
                configure_cmd += ' --enable-%s' % c
            else:
                configure_cmd += ' --disable-%s' % c

        return configure_cmd

    def configure_html(self):
        configure_cmd = './configure'
        configure_cmd += ' --prefix=/usr' 
        configure_cmd += ' --with-hpppddir=%s' % self.ppd_dir

        if self.bitness == 64:
            configure_cmd += ' --libdir=/usr/lib64'

        self.ui_toolkit =  self.get_distro_ver_data('ui_toolkit') 
        if self.ui_toolkit is not None and self.ui_toolkit == 'qt3':
            configure_cmd += ' --enable-qt3 --disable-qt4'
        else:
            configure_cmd += ' --enable-qt4'

        self.native_cups =  self.get_distro_ver_data('native_cups')
        if self.native_cups is not None and self.native_cups == 1:
            configure_cmd += ' --enable-hpcups-install --enable-cups-drv-install --enable-cups-ppd-install --disable-hpijs-install --disable-foomatic-drv-install --disable-foomatic-ppd-install --disable-foomatic-rip-hplip-install' 
        else:
            configure_cmd += ' --disable-hpcups-install --disable-cups-drv-install --disable-cups-ppd-install --enable-hpijs-install --enable-foomatic-drv-install --enable-foomatic-ppd-install --enable-foomatic-rip-hplip-install' 

        self.fax_supported =  self.get_distro_ver_data('fax_supported')
        if self.fax_supported is None:
            configure_cmd += ' --disable-fax-build --disable-dbus-build'
        else:
	    configure_cmd += ' --enable-fax-build --enable-dbus-build'

        self.network_supported = self.get_distro_ver_data('network_supported')
        if self.network_supported is None:
            configure_cmd += ' --disable-network-build'
	else:
	    configure_cmd += ' --enable-network-build'
          
        self.scan_supported = self.get_distro_ver_data('scan_supported')
        if self.scan_supported is None:
            configure_cmd += ' --disable-scan-build'
	else:
	    configure_cmd += ' --enable-scan-build'
  
        self.policykit = self.get_distro_ver_data('policykit')
        if self.policykit is not None and self.policykit == 1:
            configure_cmd += ' --enable-policykit'
	else:
	    configure_cmd += ' --disable-policykit'
	
        return configure_cmd

    def configure_qt4(self):
        configure_cmd = './configure'
        configure_cmd += ' --prefix=/usr'
        configure_cmd += ' --with-hpppddir=%s' % self.ppd_dir

        if self.bitness == 64:
            configure_cmd += ' --libdir=/usr/lib64'

        self.ui_toolkit =  self.get_distro_ver_data('ui_toolkit')
        if self.ui_toolkit is not None and self.ui_toolkit == 'qt3':
            configure_cmd += ' --enable-qt3 --disable-qt4'
        else:
            configure_cmd += ' --enable-qt4'

        self.native_cups =  self.get_distro_ver_data('native_cups')
        self.ppd_install = self.get_distro_ver_data('ppd_install')
        if self.native_cups is not None and self.native_cups == 1:
            configure_cmd += ' --enable-hpcups-install'
	    if self.ppd_install == 'drv':
	        configure_cmd += ' --enable-cups-drv-install --disable-cups-ppd-install'
	    else:
		configure_cmd += ' --enable-cups-ppd-install --disable-cups-drv-install'
	    configure_cmd += ' --disable-hpijs-install --disable-foomatic-drv-install --disable-foomatic-ppd-install --disable-foomatic-rip-hplip-install'
        else:
	    configure_cmd += ' --enable-hpijs-install'
	    if self.ppd_install == 'drv':
	        configure_cmd += ' --enable-foomatic-drv-install --disable-foomatic-ppd-install'
	    else:
		configure_cmd += ' --enable-foomatic-ppd-install --disable-foomatic-drv-install'
	    configure_cmd += ' --enable-foomatic-rip-hplip-install --disable-hpcups-install --disable-cups-drv-install --disable-cups-ppd-install'

        self.fax_supported =  self.get_distro_ver_data('fax_supported')
        if self.fax_supported is None:
            configure_cmd += ' --disable-fax-build --disable-dbus-build'
        else:
            configure_cmd += ' --enable-fax-build --enable-dbus-build'

        self.network_supported = self.get_distro_ver_data('network_supported')
        if self.network_supported is None:
            configure_cmd += ' --disable-network-build'
        else:
            configure_cmd += ' --enable-network-build'

        self.scan_supported = self.get_distro_ver_data('scan_supported')
        if self.scan_supported is None:
            configure_cmd += ' --disable-scan-build'
        else:
            configure_cmd += ' --enable-scan-build'

        self.policykit = self.get_distro_ver_data('policykit')
        if self.policykit is not None and self.policykit == 1:
            configure_cmd += ' --enable-policykit'
        else:
            configure_cmd += ' --disable-policykit'

        return configure_cmd


    def restart_cups(self):
        if os.path.exists('/etc/init.d/cups'):
            cmd = self.su_sudo() % '/etc/init.d/cups restart'

        elif os.path.exists('/etc/init.d/cupsys'):
            cmd = self.su_sudo() % '/etc/init.d/cupsys restart'

        else:
            cmd = self.su_sudo() % 'killall -HUP cupsd'

        self.run(cmd)


    def stop_hplip(self):
        return self.su_sudo() % "/etc/init.d/hplip stop"


    def su_sudo(self):
        if os.geteuid() == 0:
            return '%s'
        else:
            try:
                cmd = self.distros[self.distro_name]['su_sudo']
            except KeyError:
                cmd = 'su'

            if cmd == 'su':
                return 'su -c "%s"'
            else:
                return 'sudo %s'

    def su_sudo_str(self):
        return self.get_distro_data('su_sudo', 'su')


    def build_cmds(self):
        return [self.configure(),
                'make clean',
                'make',
                self.su_sudo() % 'make install']


    def get_distro_ver_data(self, key, default=None):
        try:
            return self.distros[self.distro_name]['versions'][self.distro_version].get(key, None) or \
                self.distros[self.distro_name].get(key, None) or default
        except KeyError:
            return default

        return value


    def get_distro_data(self, key, default=None):
        try:
            return self.distros[self.distro_name].get(key, None) or default
        except KeyError:
            return default


    def get_ver_data(self, key, default=None):
        try:
            return self.distros[self.distro_name]['versions'][self.distro_version].get(key, None) or default
        except KeyError:
            return default

        return value


    def get_dependency_data(self, dependency):
        dependency_cmds = self.get_ver_data("dependency_cmds", {})
        dependency_data = dependency_cmds.get(dependency, {})
        packages = dependency_data.get('packages', [])
        commands = dependency_data.get('commands', [])
        return packages, commands


    def get_dependency_commands(self):
        dd = self.dependencies.keys()
        dd.sort()
        commands_to_run = []
        packages_to_install = []
        overall_commands_to_run = []
        for d in dd:
            include = False
            for opt in self.dependencies[d][1]:
                if self.selected_options[opt]:
                    include = True
            if include:
                pkgs, cmds = self.get_dependency_data(d)

                if pkgs:
                    for p in pkgs:
                        if not p in packages_to_install:
                            packages_to_install.append(p)

                if cmds:
                    commands_to_run.extend(cmds)

        package_mgr_cmd = self.get_distro_data('package_mgr_cmd')

        overall_commands_to_run.extend(commands_to_run)

        if package_mgr_cmd:
            packages_to_install = ' '.join(packages_to_install)
            overall_commands_to_run.append(utils.cat(package_mgr_cmd))

        if not overall_commands_to_run:
            log.error("No cmds/pkgs")

        return overall_commands_to_run


    def distro_known(self):
        return self.distro != DISTRO_UNKNOWN and self.distro_version != DISTRO_VER_UNKNOWN


    def distro_supported(self):
        if self.mode == MODE_INSTALLER:
            return self.distro != DISTRO_UNKNOWN and self.distro_version != DISTRO_VER_UNKNOWN and self.get_ver_data('supported', False)
        else:
            return True # For docs (manual install)


    def sort_vers(self, x, y):
        try:
            return cmp(float(x), float(y))
        except ValueError:
            return cmp(x, y)


    def running_as_root(self):
        return os.geteuid() == 0


    def show_release_notes_in_browser(self):
        url = "file://%s" % os.path.join(os.getcwd(), 'doc', 'release_notes.html')
        log.debug(url)
        status, output = self.run("xhost +")
        utils.openURL(url)


    def count_num_required_missing_dependencies(self):
        num_req_missing = 0
        for d, desc, opt in self.missing_required_dependencies():
            num_req_missing += 1
        return num_req_missing


    def count_num_optional_missing_dependencies(self):
        num_opt_missing = 0
        for d, desc, req, opt in self.missing_optional_dependencies():
            num_opt_missing += 1
        return num_opt_missing


    def missing_required_dependencies(self): # missing req. deps in req. options
        for opt in self.components[self.selected_component][1]:
            if self.options[opt][0]: # required options
                for d in self.options[opt][2]: # dependencies for option
                    if self.dependencies[d][0]: # required option
                        if not self.have_dependencies[d]: # missing
                            log.debug("Missing required dependency: %s" % d)
                            yield d, self.dependencies[d][2], opt
                            # depend, desc, option

    def missing_optional_dependencies(self):
        # missing deps in opt. options
        for opt in self.components[self.selected_component][1]:
            if not self.options[opt][0]: # not required option
                if self.selected_options[opt]: # only for options that are ON
                    for d in self.options[opt][2]: # dependencies
                        if not self.have_dependencies[d]: # missing dependency
                            log.debug("Missing optional dependency: %s" % d)
                            yield d, self.dependencies[d][2], self.dependencies[d][0], opt
                            # depend, desc, required_for_opt, opt

        # opt. deps in req. options
        for opt in self.components[self.selected_component][1]:
            if self.options[opt][0]: # required options
                for d in self.options[opt][2]: # dependencies for option
                    if d == 'cups-ddk':
                        status, output = self.run('cups-config --version')
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
                                continue
	            if not self.dependencies[d][0]: # optional dep
                        if not self.have_dependencies[d]: # missing
                            log.debug("Missing optional dependency: %s" % d)
                            yield d, self.dependencies[d][2], self.dependencies[d][0], opt
                            # depend, desc, option

    def select_options(self, answer_callback):
        num_opt_missing = 0
        # not-required options
        for opt in self.components[self.selected_component][1]:
            if not self.options[opt][0]: # not required
                default = 'y'

                if not self.selected_options[opt]:
                    default = 'n'

                self.selected_options[opt] = answer_callback(opt, self.options[opt][1], default)

                if self.selected_options[opt]: # only for options that are ON
                    for d in self.options[opt][2]: # dependencies
                        if not self.have_dependencies[d]: # missing dependency
                            log.debug("Missing optional dependency: %s" % d)
                            num_opt_missing += 1

        return num_opt_missing


    def check_network_connection(self):
        self.network_connected = False

        wget = utils.which("wget")
        if wget:
            wget = os.path.join(wget, "wget")
            cmd = "%s --timeout=60 --output-document=- %s" % (wget, HTTP_GET_TARGET)
            log.debug(cmd)
            status, output = self.run(cmd)
            log.debug("wget returned: %d" % status)
            self.network_connected = (status == 0)

        else:
            curl = utils.which("curl")
            if curl:
                curl = os.path.join(curl, "curl")
                cmd = "%s --output - --connect-timeout 5 --max-time 10 %s" % (curl, HTTP_GET_TARGET)
                log.debug(cmd)
                status, output = self.run(cmd)
                log.debug("curl returned: %d" % status)
                self.network_connected = (status == 0)

            else:
                ping = utils.which("ping")

                if ping:
                    ping = os.path.join(ping, "ping")
                    cmd = "%s -c1 -W1 -w10 %s" % (ping, PING_TARGET)
                    log.debug(cmd)
                    status, output = self.run(cmd)
                    log.debug("ping returned: %d" % status)
                    self.network_connected = (status == 0)

        return self.network_connected


    def run_pre_install(self, callback=None):
        pre_cmd = self.get_distro_ver_data('pre_install_cmd')
        log.debug(pre_cmd)
        if pre_cmd:
            x = 1
            for cmd in pre_cmd:
                status, output = self.run(cmd)

                if status != 0:
                    log.warn("An error occurred running '%s'" % cmd)

                if callback is not None:
                    callback(cmd, "Pre-install step %d" % x)

                x += 1

            return True

        else:
            return False


    def run_pre_depend(self, callback=None):
        pre_cmd = self.get_distro_ver_data('pre_depend_cmd')
        log.debug(pre_cmd)
        if pre_cmd:
            x = 1
            for cmd in pre_cmd:
                status, output = self.run(cmd)

                if status != 0:
                    log.warn("An error occurred running '%s'" % cmd)

                if callback is not None:
                    callback(cmd, "Pre-depend step %d" % x)

                x += 1


    def run_post_depend(self, callback=None):
        post_cmd = self.get_distro_ver_data('post_depend_cmd')
        log.debug(post_cmd)
        if post_cmd:
            x = 1
            for cmd in post_cmd:
                status, output = self.run(cmd)

                if status != 0:
                    log.warn("An error occurred running '%s'" % cmd)

                if callback is not None:
                    callback(cmd, "Post-depend step %d" % x)

                x += 1


    def run_open_mdns_port(self, callback=None):
        open_mdns_port_cmd = self.get_distro_ver_data('open_mdns_port')
        log.debug(open_mdns_port_cmd)
        if open_mdns_port_cmd:
            x = 1
            for cmd in open_mdns_port_cmd:
                cmd = self.su_sudo() % cmd
                status, output = self.run(cmd)

                if status != 0:
                    log.warn("An error occurred running '%s'" % cmd)
                    log.warn(output)

                if callback is not None:
                    callback(cmd, "Open mDNS/Bonjour step %d" % x)

                x += 1


    def pre_build(self):
        cmds = []
        if self.get_distro_ver_data('fix_ppd_symlink', False):
            cmds.append(self.su_sudo() % 'python ./installer/fix_symlink.py')

        return cmds


    def run_pre_build(self, callback=None):
        x = 1
        for cmd in self.pre_build():
            status, output = self.run(cmd)
            if callback is not None:
                callback(cmd, "Pre-build step %d"  % x)

            x += 1


    def run_post_build(self, callback=None):
        x = 1
        for cmd in self.post_build():
            status, output = self.run(cmd)
            if callback is not None:
                callback(cmd, "Post-build step %d"  % x)

            x += 1


    def post_build(self):
        cmds = []
        # Reload DBUS configuration if distro supports it and PolicyKit
        # support installed
        if self.reload_dbus and self.selected_options['policykit']:
            cmds.append(self.su_sudo() % "sh /etc/init.d/dbus reload")
            log.debug("Will reload DBUS configuration for PolicyKit support")

        # Kill any running hpssd.py instance from a previous install
        if self.check_hpssd():
            pid = get_ps_pid('hpssd')
            if pid:
                kill = os.path.join(utils.which("kill"), "kill") + " %d" % pid
                cmds.append(self.su_sudo() % kill)

        # Add user to group if needed
        # add_user_to_group=<usermod params> [TYPE_STRING] (leave empty for none) [ex. "-a -G sys" or "-G lp"]
        add_user_to_group = self.get_distro_ver_data('add_user_to_group', '')
        if add_user_to_group:
            usermod = os.path.join(utils.which("usermod"), "usermod") + " %s %s" % (add_user_to_group, prop.username)
            cmds.append(self.su_sudo() % usermod)

        return cmds


    def logoff(self):
        ok = False
        pkill = utils.which('pkill')
        if pkill:
            cmd = "%s -KILL -u %s" % (os.path.join(pkill, "pkill"), prop.username)
            cmd = self.su_sudo() % cmd
            status, output = self.run(cmd)

            ok = (status == 0)

        return ok


    def restart(self):
        ok = False
        shutdown = utils.which('shutdown')
        if shutdown:
            cmd = "%s -r now" % (os.path.join(shutdown, "shutdown"))
            cmd = self.su_sudo() % cmd
            status, output = self.run(cmd)

            ok = (status == 0)

        return ok


    def run_hp_setup(self):
        status = 0
        hpsetup = utils.which("hp-setup")

        if hpsetup:
            cmd = 'hp-setup'
        else:
            cmd = './setup.py'

        log.debug(cmd)
        status, output = self.run(cmd)
        return status == 0


    def remove_hplip(self, callback=None):
        failed = True
        self.stop_pre_2x_hplip(callback)

        hplip_remove_cmd = self.get_distro_data('hplip_remove_cmd')
        if hplip_remove_cmd:
            if callback is not None:
                callback(hplip_remove_cmd, "Removing old HPLIP version")

                status, output = self.run(hplip_remove_cmd)

            if status == 0:
                self.hplip_present = self.check_hplip()

                if not self.hplip_present:
                    failed = False

        return failed


    def stop_pre_2x_hplip(self, callback=None):
        hplip_init_script = '/etc/init.d/hplip stop'
        if os.path.exists(hplip_init_script):
            cmd = self.su_sudo() % hplip_init_script

            if callback is not None:
                callback(cmd, "Stopping old HPLIP version.")

            status, output = self.run(cmd)



    def check_password(self, password_entry_callback, callback=None):
        self.clear_su_sudo_password()
        x = 1
        while True:
            self.password = password_entry_callback()
            cmd = self.su_sudo() % "true"

            log.debug(cmd)

            status, output = self.run(cmd)

            log.debug(status)
            log.debug(output)

            if status == 0:
                if callback is not None:
                    callback("", "Password accepted")
                return True

            if callback is not None:
                callback("", "Password incorrect. %d attempt(s) left." % (3-x))

            x += 1

            if x > 3:
                return False


    def clear_su_sudo_password(self):
        if self.su_sudo_str() == 'sudo':
            log.debug("Clearing password...")
            self.run("sudo -K")



    # PLUGIN HELPERS

    def set_plugin_version(self):
        self.plugin_version = prop.installed_version
        log.debug("Plug-in version=%s" % self.plugin_version)
        self.plugin_name = 'hplip-%s-plugin.run' % self.plugin_version
        log.debug("Plug-in=%s" % self.plugin_name)


    def get_plugin_conf_url(self):
        url = "http://hplip.sf.net/plugin.conf"
        home = sys_conf.get('dirs', 'home')

        if os.path.exists('/etc/hp/plugin.conf'):
            url = "file:///etc/hp/plugin.conf"

        elif os.path.exists(os.path.join(home, 'plugin.conf')):
            url = "file://" + os.path.join(home, 'plugin.conf')

        log.debug("Plugin.conf url: %s" % url)
        return url


    def get_plugin_info(self, plugin_conf_url, callback):
        ok, size, checksum, timestamp, url = False, 0, 0, 0.0, ''

        if not self.create_plugin_dir():
            log.error("Could not create plug-in directory.")
            return '', 0, 0, 0, False

        local_conf_fp, local_conf = utils.make_temp_file()

        #if os.path.exists(local_conf):
            #os.remove(local_conf)

        try:
            try:
                #filename, headers = urllib.urlretrieve(plugin_conf_url, local_conf, callback)
                wget = utils.which("wget")
                if wget:
                    wget = os.path.join(wget, "wget")
                    status, output = self.run("%s --timeout=60 --output-document=%s %s" %(wget, local_conf, plugin_conf_url))
                    if status:
			log.error("Plugin download failed with error code = %d" %status)
                	return '', 0, 0, 0, False
                else:
                    log.error("Please install wget package to download the plugin.")
                    return '', 0, 0, 0, False
            except IOError, e:
                log.error("I/O Error: %s" % e.strerror)
                return '', 0, 0, 0, False

            if not os.path.exists(local_conf):
                log.error("plugin.conf not found.")
                return '', 0, 0, 0, False

            plugin_conf_p = ConfigParser.ConfigParser()

            try:
                plugin_conf_p.read(local_conf)
            except (ConfigParser.MissingSectionHeaderError, ConfigParser.ParsingError):
                log.error("Error parsing file - 404 error?")
                return '', 0, 0, 0, False

            try:
                url = plugin_conf_p.get(self.plugin_version, 'url')
                size = plugin_conf_p.getint(self.plugin_version, 'size')
                checksum = plugin_conf_p.get(self.plugin_version, 'checksum')
                timestamp = plugin_conf_p.getfloat(self.plugin_version, 'timestamp')
                ok = True
            except (KeyError, ConfigParser.NoSectionError):
                log.error("Error reading plugin.conf: Missing section [%s]" % self.plugin_version)
                return '', 0, 0, 0, False

        finally:
            os.close(local_conf_fp)
            os.remove(local_conf)

        return url, size, checksum, timestamp, ok


    def create_plugin_dir(self):
        if not os.path.exists(self.plugin_path):
            try:
                log.debug("Creating plugin directory: %s" % self.plugin_path)
                os.umask(0)
                os.makedirs(self.plugin_path, 0755)
                return True
            except (OSError, IOError), e:
                log.error("Unable to create directory: %s" % e.strerror)
                return False

        return True


    def isErrorPage(self, page):
        """
        Example code from David Mertz' Text Processing in Python.
        Released in the Public Domain.
        """
        err_score = 0.0

        for pat, prob in err_pats.items():
            if err_score > 0.9: break
            if re.search(pat, page):
                err_score += prob

        log.debug("File error page score: %f" % (err_score))

        return err_score > 0.50


    def download_plugin(self, url, size, checksum, timestamp, callback=None):
        log.debug("Downloading %s plug-in file from '%s' to '%s'..." % (self.plugin_version, url, self.plugin_path))

        if not self.create_plugin_dir():
            return PLUGIN_INSTALL_ERROR_DIRECTORY_ERROR, self.plugin_path

        plugin_file = os.path.join(self.plugin_path, self.plugin_name)

        try:
            filename, headers = urllib.urlretrieve(url, plugin_file, callback)
        except IOError, e:
            log.error("Plug-in download failed: %s" % e.strerror)
            return PLUGIN_INSTALL_ERROR_PLUGIN_FILE_NOT_FOUND, e.strerror

        if self.isErrorPage(file(plugin_file, 'r').read(1024)):
            log.debug(file(plugin_file, 'r').read(1024))
            os.remove(plugin_file)
            return PLUGIN_INSTALL_ERROR_PLUGIN_FILE_NOT_FOUND, -1

        calc_checksum = get_checksum(file(plugin_file, 'r').read())
        log.debug("D/L file checksum=%s" % calc_checksum)

        # Try to download and check the GPG digital signature
        digsig_url = url + '.asc'
        digsig_file = plugin_file + '.asc'

        log.debug("Downloading %s plug-in digital signature file from '%s' to '%s'..." % (self.plugin_version, digsig_url, digsig_file))

        try:
            filename, headers = urllib.urlretrieve(digsig_url, digsig_file, callback)
        except IOError, e:
            log.error("Plug-in GPG file download failed: %s" % e.strerror)
            return PLUGIN_INSTALL_ERROR_DIGITAL_SIG_NOT_FOUND, e.strerror

        if self.isErrorPage(file(digsig_file, 'r').read(1024)):
            log.debug(file(digsig_file, 'r').read())
            os.remove(digsig_file)
            return PLUGIN_INSTALL_ERROR_DIGITAL_SIG_NOT_FOUND, -1

        gpg = utils.which('gpg')
        if gpg:
            gpg = os.path.join(gpg, 'gpg')
            cmd = '%s --no-permission-warning --keyserver pgp.mit.edu --recv-keys 0xA59047B9' % gpg
            log.info("Receiving digital keys: %s" % cmd)
            status, output = self.run(cmd)
            log.debug(output)

            if status != 0:
                return PLUGIN_INSTALL_ERROR_UNABLE_TO_RECV_KEYS, status

            cmd = '%s --no-permission-warning --verify %s %s' % (gpg, digsig_file, plugin_file)
            log.debug("Verifying plugin with digital keys: %s" % cmd)
            status, output = self.run(cmd)
            log.debug(output)
            log.debug("%s status: %d" % (gpg, status))

            if status != 0:
                return PLUGIN_INSTALL_ERROR_DIGITAL_SIG_BAD, status


        return PLUGIN_INSTALL_ERROR_NONE, plugin_file


    def check_for_plugin(self):
        sys_state.read()
        is_installed = utils.to_bool(sys_state.get('plugin', 'installed', '0'))
        if is_installed:
            log.debug("plugin is installed")
        else:
            log.debug("plugin is not installed")
        return is_installed


    def run_plugin(self, mode=GUI_MODE, callback=None):
        plugin_file = os.path.join(self.plugin_path, self.plugin_name)

        if not os.path.exists(plugin_file):
            return False

        if mode == GUI_MODE:
            return os.system("sh %s --nox11 -- -u" % plugin_file) == 0
        else:
            if os.system("sh %s --nox11 -- -i" % plugin_file) == 0:
                return True
            else:
                log.error("Python gobject/dbus may be not installed")
                return False


    def delete_plugin(self):
        plugin_file = os.path.join(self.plugin_path, self.plugin_name)
        digsig_file = plugin_file + ".asc"

        if os.path.exists(plugin_file):
            os.unlink(plugin_file)
        if os.path.exists(digsig_file):
            os.unlink(digsig_file)
