# -*- coding: utf-8 -*-
#
# (c) Copyright 2001-2009 Hewlett-Packard Development Company, L.P.
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
# Author: Don Welch, Naga Samrat Chowdary Narla, Goutam Kodu
#
# Thanks to Henrique M. Holschuh <hmh@debian.org> for various security patches
#

from __future__ import generators

# Std Lib
import sys
import os
import grp
import fnmatch
import tempfile
import socket
import struct
import select
import time
import fcntl
import errno
import stat
import string
import commands # TODO: Replace with subprocess (commands is deprecated in Python 3.0)
import cStringIO
import re
import xml.parsers.expat as expat
import getpass
import locale
import htmlentitydefs

try:
    import platform
    platform_avail = True
except ImportError:
    platform_avail = False

# Local
from g import *
from codes import *
import pexpect

BIG_ENDIAN = 0
LITTLE_ENDIAN = 1

def addgroup():
    lis = []
    try:
        fp=open('/etc/cups/cupsd.conf')
    except IOError:
        try:
            if "root" != grp.getgrgid(os.stat('/etc/cups/cupsd.conf').st_gid).gr_name:
                return [grp.getgrgid(os.stat('/etc/cups/cupsd.conf').st_gid).gr_name]
        except OSError:
            return lis

    try:
        lis = ((re.findall('SystemGroup [\w* ]*',fp.read()))[0].replace('SystemGroup ','')).split(' ')
    except IndexError:
        return lis

    if 'root' in lis:
        lis.remove('root')
    fp.close()
    return lis

def list_to_string(lis):
    if len(lis) == 0:
        return ""
    if len(lis) == 1:
        return str("\""+lis[0]+"\"")
    if len(lis) >= 1:
        return "\""+"\", \"".join(lis)+"\" and \""+str(lis.pop())+"\""
        
def lock(f):
    log.debug("Locking: %s" % f.name)
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        log.debug("Failed to unlock %s." % f.name)
        return False


def unlock(f):
    if f is not None:
        log.debug("Unlocking: %s" % f.name)
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            os.remove(f.name)
        except (IOError, OSError):
            pass


def lock_app(application, suppress_error=False):
    dir = prop.user_dir
    if os.geteuid() == 0:
        dir = '/var'

    elif not os.path.exists(dir):
        os.makedirs(dir)

    lock_file = os.path.join(dir, '.'.join([application, 'lock']))
    try:
        lock_file_f = open(lock_file, "w")
    except IOError:
        if not suppress_error:
            log.error("Unable to open %s lock file." % lock_file)
        return False, None

    #log.debug("Locking file: %s" % lock_file)

    if not lock(lock_file_f):
        if not suppress_error:
            log.error("Unable to lock %s. Is %s already running?" % (lock_file, application))
        return False, None

    return True, lock_file_f


#xml_basename_pat = re.compile(r"""HPLIP-(\d*)_(\d*)_(\d*).xml""", re.IGNORECASE)


def Translator(frm='', to='', delete='', keep=None):
    allchars = string.maketrans('','')

    if len(to) == 1:
        to = to * len(frm)
    trans = string.maketrans(frm, to)

    if keep is not None:
        delete = allchars.translate(allchars, keep.translate(allchars, delete))

    def callable(s):
        return s.translate(trans, delete)

    return callable


def to_bool_str(s, default='0'):
    """ Convert an arbitrary 0/1/T/F/Y/N string to a normalized string 0/1."""
    if isinstance(s, str) and s:
        if s[0].lower() in ['1', 't', 'y']:
            return u'1'
        elif s[0].lower() in ['0', 'f', 'n']:
            return u'0'

    return default

def to_bool(s, default=False):
    """ Convert an arbitrary 0/1/T/F/Y/N string to a boolean True/False value."""
    if isinstance(s, str) and s:
        if s[0].lower() in ['1', 't', 'y']:
            return True
        elif s[0].lower() in ['0', 'f', 'n']:
            return False
    elif isinstance(s, bool):
        return s

    return default


def walkFiles(root, recurse=True, abs_paths=False, return_folders=False, pattern='*', path=None):
    if path is None:
        path = root

    try:
        names = os.listdir(root)
    except os.error:
        raise StopIteration

    pattern = pattern or '*'
    pat_list = pattern.split(';')

    for name in names:
        fullname = os.path.normpath(os.path.join(root, name))

        for pat in pat_list:
            if fnmatch.fnmatch(name, pat):
                if return_folders or not os.path.isdir(fullname):
                    if abs_paths:
                        yield fullname
                    else:
                        try:
                            yield os.path.basename(fullname)
                        except ValueError:
                            yield fullname

        #if os.path.islink(fullname):
        #    fullname = os.path.realpath(os.readlink(fullname))

        if recurse and os.path.isdir(fullname): # or os.path.islink(fullname):
            for f in walkFiles(fullname, recurse, abs_paths, return_folders, pattern, path):
                yield f


def is_path_writable(path):
    if os.path.exists(path):
        s = os.stat(path)
        mode = s[stat.ST_MODE] & 0777

        if mode & 02:
            return True
        elif s[stat.ST_GID] == os.getgid() and mode & 020:
            return True
        elif s[stat.ST_UID] == os.getuid() and mode & 0200:
            return True

    return False


# Provides the TextFormatter class for formatting text into columns.
# Original Author: Hamish B Lawson, 1999
# Modified by: Don Welch, 2003
class TextFormatter:

    LEFT  = 0
    CENTER = 1
    RIGHT  = 2

    def __init__(self, colspeclist):
        self.columns = []
        for colspec in colspeclist:
            self.columns.append(Column(**colspec))

    def compose(self, textlist, add_newline=False):
        numlines = 0
        textlist = list(textlist)
        if len(textlist) != len(self.columns):
            log.error("Formatter: Number of text items does not match columns")
            return
        for text, column in map(None, textlist, self.columns):
            column.wrap(text)
            numlines = max(numlines, len(column.lines))
        complines = [''] * numlines
        for ln in range(numlines):
            for column in self.columns:
                complines[ln] = complines[ln] + column.getline(ln)
        if add_newline:
            return '\n'.join(complines) + '\n'
        else:
            return '\n'.join(complines)

class Column:

    def __init__(self, width=78, alignment=TextFormatter.LEFT, margin=0):
        self.width = width
        self.alignment = alignment
        self.margin = margin
        self.lines = []

    def align(self, line):
        if self.alignment == TextFormatter.CENTER:
            return line.center(self.width)
        elif self.alignment == TextFormatter.RIGHT:
            return line.rjust(self.width)
        else:
            return line.ljust(self.width)

    def wrap(self, text):
        self.lines = []
        words = []
        for word in text.split():
            if word <= self.width:
                words.append(word)
            else:
                for i in range(0, len(word), self.width):
                    words.append(word[i:i+self.width])
        if not len(words): return
        current = words.pop(0)
        for word in words:
            increment = 1 + len(word)
            if len(current) + increment > self.width:
                self.lines.append(self.align(current))
                current = word
            else:
                current = current + ' ' + word
        self.lines.append(self.align(current))

    def getline(self, index):
        if index < len(self.lines):
            return ' '*self.margin + self.lines[index]
        else:
            return ' ' * (self.margin + self.width)



class Stack:
    def __init__(self):
        self.stack = []

    def pop(self):
        return self.stack.pop()

    def push(self, value):
        self.stack.append(value)

    def as_list(self):
        return self.stack

    def clear(self):
        self.stack = []

    def __len__(self):
        return len(self.stack)



class Queue(Stack):
    def __init__(self):
        Stack.__init__(self)

    def get(self):
        return self.stack.pop(0)

    def put(self, value):
        Stack.push(self, value)



# RingBuffer class
# Source: Python Cookbook 1st Ed., sec. 5.18, pg. 201
# Credit: Sebastien Keim
# License: Modified BSD
class RingBuffer:
    def __init__(self, size_max=50):
        self.max = size_max
        self.data = []

    def append(self,x):
        """append an element at the end of the buffer"""
        self.data.append(x)

        if len(self.data) == self.max:
            self.cur = 0
            self.__class__ = RingBufferFull

    def replace(self, x):
        """replace the last element instead off appending"""
        self.data[-1] = x

    def get(self):
        """ return a list of elements from the oldest to the newest"""
        return self.data


class RingBufferFull:
    def __init__(self, n):
        #raise "you should use RingBuffer"
        pass

    def append(self, x):
        self.data[self.cur] = x
        self.cur = (self.cur+1) % self.max

    def replace(self, x):
        # back up 1 position to previous location
        self.cur = (self.cur-1) % self.max
        self.data[self.cur] = x
        # setup for next item
        self.cur = (self.cur+1) % self.max

    def get(self):
        return self.data[self.cur:] + self.data[:self.cur]



def sort_dict_by_value(d):
    """ Returns the keys of dictionary d sorted by their values """
    items=d.items()
    backitems=[[v[1],v[0]] for v in items]
    backitems.sort()
    return [backitems[i][1] for i in range(0, len(backitems))]


def commafy(val):
    return locale.format("%d", val, grouping=True).decode(locale.getpreferredencoding())


def format_bytes(s, show_bytes=False):
    if s < 1024:
        return ''.join([commafy(s), ' B'])
    elif 1024 < s < 1048576:
        if show_bytes:
            return ''.join([unicode(round(s/1024.0, 1)) , u' KB (',  commafy(s), ')'])
        else:
            return ''.join([unicode(round(s/1024.0, 1)) , u' KB'])
    elif 1048576 < s < 1073741824:
        if show_bytes:
            return ''.join([unicode(round(s/1048576.0, 1)), u' MB (',  commafy(s), ')'])
        else:
            return ''.join([unicode(round(s/1048576.0, 1)), u' MB'])
    else:
        if show_bytes:
            return ''.join([unicode(round(s/1073741824.0, 1)), u' GB (',  commafy(s), ')'])
        else:
            return ''.join([unicode(round(s/1073741824.0, 1)), u' GB'])



try:
    make_temp_file = tempfile.mkstemp # 2.3+
except AttributeError:
    def make_temp_file(suffix='', prefix='', dir='', text=False): # pre-2.3
        path = tempfile.mktemp(suffix)
        fd = os.open(path, os.O_RDWR|os.O_CREAT|os.O_EXCL, 0700)
        return ( os.fdopen( fd, 'w+b' ), path )



def which(command, return_full_path=False):
    path = os.getenv('PATH').split(':')

    # Add these paths for Fedora
    path.append('/sbin')
    path.append('/usr/sbin')
    path.append('/usr/local/sbin')

    found_path = ''
    for p in path:
        try:
            files = os.listdir(p)
        except OSError:
            continue
        else:
            if command in files:
                found_path = p
                break

    if return_full_path:
        if found_path:
            return os.path.join(found_path, command)
        else:
            return ''
    else:
        return found_path


class UserSettings(object): # Note: Deprecated after 2.8.8 in Qt4 (see ui4/ui_utils.py)
    def __init__(self):
        self.load()

    def loadDefaults(self):
        # Print
        self.cmd_print = ''
        path = which('hp-print')

        if len(path) > 0:
            self.cmd_print = 'hp-print -p%PRINTER%'
        else:
            path = which('kprinter')
            if len(path) > 0:
                self.cmd_print = 'kprinter -P%PRINTER% --system cups'
            else:
                path = which('gtklp')
                if len(path) > 0:
                    self.cmd_print = 'gtklp -P%PRINTER%'
                else:
                    path = which('xpp')
                    if len(path) > 0:
                        self.cmd_print = 'xpp -P%PRINTER%'

        # Scan
        self.cmd_scan = ''
        path = which('simple-scan')
        if len(path) > 0:
            self.cmd_scan = 'simple-scan %SANE_URI%'
        else:
            path = which('xsane')
            if len(path) > 0:
                self.cmd_scan = 'xsane -V %SANE_URI%'
            else:
                path = which('kooka')
                if len(path) > 0:
                    self.cmd_scan = 'kooka'
                else:
                    path = which('xscanimage')
                    if len(path) > 0:
                        self.cmd_scan = 'xscanimage'

        # Photo Card
        path = which('hp-unload')

        if len(path):
            self.cmd_pcard = 'hp-unload -d %DEVICE_URI%'
        else:
            self.cmd_pcard = 'python %HOME%/unload.py -d %DEVICE_URI%'

        # Copy
        path = which('hp-makecopies')

        if len(path):
            self.cmd_copy = 'hp-makecopies -d %DEVICE_URI%'
        else:
            self.cmd_copy = 'python %HOME%/makecopies.py -d %DEVICE_URI%'

        # Fax
        path = which('hp-sendfax')

        if len(path):
            self.cmd_fax = 'hp-sendfax -d %FAX_URI%'
        else:
            self.cmd_fax = 'python %HOME%/sendfax.py -d %FAX_URI%'

        # Fax Address Book
        path = which('hp-fab')

        if len(path):
            self.cmd_fab = 'hp-fab'
        else:
            self.cmd_fab = 'python %HOME%/fab.py'

    def load(self):
        self.loadDefaults()
        log.debug("Loading user settings...")
        self.auto_refresh = to_bool(user_conf.get('refresh', 'enable', '0'))

        try:
            self.auto_refresh_rate = int(user_conf.get('refresh', 'rate', '30'))
        except ValueError:
            self.auto_refresh_rate = 30 # (secs)

        try:
            self.auto_refresh_type = int(user_conf.get('refresh', 'type', '0'))
        except ValueError:
            self.auto_refresh_type = 0 # refresh 1 (1=refresh all)

        self.cmd_print = user_conf.get('commands', 'prnt', self.cmd_print)
        self.cmd_scan = user_conf.get('commands', 'scan', self.cmd_scan)
        self.cmd_pcard = user_conf.get('commands', 'pcard', self.cmd_pcard)
        self.cmd_copy = user_conf.get('commands', 'cpy', self.cmd_copy)
        self.cmd_fax = user_conf.get('commands', 'fax', self.cmd_fax)
        self.cmd_fab = user_conf.get('commands', 'fab', self.cmd_fab)
        self.debug()

    def debug(self):
        log.debug("Print command: %s" % self.cmd_print)
        log.debug("PCard command: %s" % self.cmd_pcard)
        log.debug("Fax command: %s" % self.cmd_fax)
        log.debug("FAB command: %s" % self.cmd_fab)
        log.debug("Copy command: %s " % self.cmd_copy)
        log.debug("Scan command: %s" % self.cmd_scan)
        log.debug("Auto refresh: %s" % self.auto_refresh)
        log.debug("Auto refresh rate: %s" % self.auto_refresh_rate)
        log.debug("Auto refresh type: %s" % self.auto_refresh_type)

    def save(self):
        log.debug("Saving user settings...")
        user_conf.set('commands', 'prnt', self.cmd_print)
        user_conf.set('commands', 'pcard', self.cmd_pcard)
        user_conf.set('commands', 'fax', self.cmd_fax)
        user_conf.set('commands', 'scan', self.cmd_scan)
        user_conf.set('commands', 'cpy', self.cmd_copy)
        user_conf.set('refresh', 'enable',self.auto_refresh)
        user_conf.set('refresh', 'rate', self.auto_refresh_rate)
        user_conf.set('refresh', 'type', self.auto_refresh_type)
        self.debug()



def no_qt_message_gtk():
    try:
        import gtk
        w = gtk.Window()
        dialog = gtk.MessageDialog(w, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                                   "PyQt not installed. GUI not available. Please check that the PyQt package is installed. Exiting.")
        dialog.run()
        dialog.destroy()

    except ImportError:
        log.error("PyQt not installed. GUI not available. Please check that the PyQt package is installed. Exiting.")


def canEnterGUIMode(): # qt3
    if not prop.gui_build:
        log.warn("GUI mode disabled in build.")
        return False

    elif not os.getenv('DISPLAY'):
        log.warn("No display found.")
        return False

    elif not checkPyQtImport():
        log.warn("Qt/PyQt 3 initialization failed.")
        return False

    return True


def canEnterGUIMode4(): # qt4
    if not prop.gui_build:
        log.warn("GUI mode disabled in build.")
        return False

    elif not os.getenv('DISPLAY'):
        log.warn("No display found.")
        return False

    elif not checkPyQtImport4():
        log.warn("Qt/PyQt 4 initialization failed.")
        return False

    return True


def checkPyQtImport(): # qt3
    # PyQt
    try:
        import qt
    except ImportError:
        if os.getenv('DISPLAY') and os.getenv('STARTED_FROM_MENU'):
            no_qt_message_gtk()

        log.error("PyQt not installed. GUI not available. Exiting.")
        return False

    # check version of Qt
    qtMajor = int(qt.qVersion().split('.')[0])

    if qtMajor < MINIMUM_QT_MAJOR_VER:

        log.error("Incorrect version of Qt installed. Ver. 3.0.0 or greater required.")
        return False

    #check version of PyQt
    try:
        pyqtVersion = qt.PYQT_VERSION_STR
    except AttributeError:
        pyqtVersion = qt.PYQT_VERSION

    while pyqtVersion.count('.') < 2:
        pyqtVersion += '.0'

    (maj_ver, min_ver, pat_ver) = pyqtVersion.split('.')

    if pyqtVersion.find('snapshot') >= 0:
        log.warning("A non-stable snapshot version of PyQt is installed.")
    else:
        try:
            maj_ver = int(maj_ver)
            min_ver = int(min_ver)
            pat_ver = int(pat_ver)
        except ValueError:
            maj_ver, min_ver, pat_ver = 0, 0, 0

        if maj_ver < MINIMUM_PYQT_MAJOR_VER or \
            (maj_ver == MINIMUM_PYQT_MAJOR_VER and min_ver < MINIMUM_PYQT_MINOR_VER):
            log.error("This program may not function properly with the version of PyQt that is installed (%d.%d.%d)." % (maj_ver, min_ver, pat_ver))
            log.error("Incorrect version of pyQt installed. Ver. %d.%d or greater required." % (MINIMUM_PYQT_MAJOR_VER, MINIMUM_PYQT_MINOR_VER))
            log.error("This program will continue, but you may experience errors, crashes or other problems.")
            return True

    return True


def checkPyQtImport4():
    try:
        import PyQt4
    except ImportError:
        return False
    else:
        return True


try:
    from string import Template # will fail in Python <= 2.3
except ImportError:
    # Code from Python 2.4 string.py
    #import re as _re

    class _multimap:
        """Helper class for combining multiple mappings.

        Used by .{safe_,}substitute() to combine the mapping and keyword
        arguments.
        """
        def __init__(self, primary, secondary):
            self._primary = primary
            self._secondary = secondary

        def __getitem__(self, key):
            try:
                return self._primary[key]
            except KeyError:
                return self._secondary[key]


    class _TemplateMetaclass(type):
        pattern = r"""
        %(delim)s(?:
          (?P<escaped>%(delim)s) |   # Escape sequence of two delimiters
          (?P<named>%(id)s)      |   # delimiter and a Python identifier
          {(?P<braced>%(id)s)}   |   # delimiter and a braced identifier
          (?P<invalid>)              # Other ill-formed delimiter exprs
        )
        """

        def __init__(cls, name, bases, dct):
            super(_TemplateMetaclass, cls).__init__(name, bases, dct)
            if 'pattern' in dct:
                pattern = cls.pattern
            else:
                pattern = _TemplateMetaclass.pattern % {
                    'delim' : re.escape(cls.delimiter),
                    'id'    : cls.idpattern,
                    }
            cls.pattern = re.compile(pattern, re.IGNORECASE | re.VERBOSE)


    class Template:
        """A string class for supporting $-substitutions."""
        __metaclass__ = _TemplateMetaclass

        delimiter = '$'
        idpattern = r'[_a-z][_a-z0-9]*'

        def __init__(self, template):
            self.template = template

        # Search for $$, $identifier, ${identifier}, and any bare $'s
        def _invalid(self, mo):
            i = mo.start('invalid')
            lines = self.template[:i].splitlines(True)
            if not lines:
                colno = 1
                lineno = 1
            else:
                colno = i - len(''.join(lines[:-1]))
                lineno = len(lines)
            raise ValueError('Invalid placeholder in string: line %d, col %d' %
                             (lineno, colno))

        def substitute(self, *args, **kws):
            if len(args) > 1:
                raise TypeError('Too many positional arguments')
            if not args:
                mapping = kws
            elif kws:
                mapping = _multimap(kws, args[0])
            else:
                mapping = args[0]
            # Helper function for .sub()
            def convert(mo):
                # Check the most common path first.
                named = mo.group('named') or mo.group('braced')
                if named is not None:
                    val = mapping[named]
                    # We use this idiom instead of str() because the latter will
                    # fail if val is a Unicode containing non-ASCII characters.
                    return '%s' % val
                if mo.group('escaped') is not None:
                    return self.delimiter
                if mo.group('invalid') is not None:
                    self._invalid(mo)
                raise ValueError('Unrecognized named group in pattern',
                                 self.pattern)
            return self.pattern.sub(convert, self.template)


        def safe_substitute(self, *args, **kws):
            if len(args) > 1:
                raise TypeError('Too many positional arguments')
            if not args:
                mapping = kws
            elif kws:
                mapping = _multimap(kws, args[0])
            else:
                mapping = args[0]
            # Helper function for .sub()
            def convert(mo):
                named = mo.group('named')
                if named is not None:
                    try:
                        # We use this idiom instead of str() because the latter
                        # will fail if val is a Unicode containing non-ASCII
                        return '%s' % mapping[named]
                    except KeyError:
                        return self.delimiter + named
                braced = mo.group('braced')
                if braced is not None:
                    try:
                        return '%s' % mapping[braced]
                    except KeyError:
                        return self.delimiter + '{' + braced + '}'
                if mo.group('escaped') is not None:
                    return self.delimiter
                if mo.group('invalid') is not None:
                    return self.delimiter
                raise ValueError('Unrecognized named group in pattern',
                                 self.pattern)
            return self.pattern.sub(convert, self.template)



#cat = lambda _ : Template(_).substitute(sys._getframe(1).f_globals, **sys._getframe(1).f_locals)

def cat(s):
    globals = sys._getframe(1).f_globals.copy()
    if 'self' in globals:
        del globals['self']

    locals = sys._getframe(1).f_locals.copy()
    if 'self' in locals:
        del locals['self']

    return Template(s).substitute(sys._getframe(1).f_globals, **locals)


identity = string.maketrans('','')
unprintable = identity.translate(identity, string.printable)


def printable(s):
    return s.translate(identity, unprintable)


def any(S,f=lambda x:x):
    for x in S:
        if f(x): return True
    return False


def all(S,f=lambda x:x):
    for x in S:
        if not f(x): return False
    return True


BROWSERS = ['firefox', 'mozilla', 'konqueror', 'galeon', 'skipstone'] # in preferred order
BROWSER_OPTS = {'firefox': '-new-window', 'mozilla' : '', 'konqueror': '', 'galeon': '-w', 'skipstone': ''}


def find_browser():
    if platform_avail and platform.system() == 'Darwin':
        return "open"
    else:
        for b in BROWSERS:
            if which(b):
                return b
        else:
            return None


def openURL(url, use_browser_opts=True):
    if platform_avail and platform.system() == 'Darwin':
        cmd = 'open "%s"' % url
        log.debug(cmd)
        os.system(cmd)
    else:
        for b in BROWSERS:
            bb = which(b)
            if bb:
                bb = os.path.join(bb, b)
                if use_browser_opts:
                    cmd = """%s %s "%s" &""" % (bb, BROWSER_OPTS[b], url)
                else:
                    cmd = """%s "%s" &""" % (bb, url)
                log.debug(cmd)
                os.system(cmd)
                break
        else:
            log.warn("Unable to open URL: %s" % url)


def uniqueList(input):
    temp = []
    [temp.append(i) for i in input if not temp.count(i)]
    return temp


def list_move_up(l, m, cmp=None):
    if cmp is None:
        f = lambda x: l[x] == m
    else:
        f = lambda x: cmp(l[x], m)

    for i in range(1, len(l)):
        if f(i):
            l[i-1], l[i] = l[i], l[i-1]


def list_move_down(l, m, cmp=None):
    if cmp is None:
        f = lambda x: l[x] == m
    else:
        f = lambda x: cmp(l[x], m)

    for i in range(len(l)-2, -1, -1):
        if f(i):
            l[i], l[i+1] = l[i+1], l[i]



class XMLToDictParser:
    def __init__(self):
        self.stack = []
        self.data = {}
        self.last_start = ''

    def startElement(self, name, attrs):
        #print "START:", name, attrs
        self.stack.append(unicode(name).lower())
        self.last_start = unicode(name).lower()

        if len(attrs):
            for a in attrs:
                self.stack.append(unicode(a).lower())
                self.addData(attrs[a])
                self.stack.pop()

    def endElement(self, name):
        if name.lower() == self.last_start:
            self.addData('')

        #print "END:", name
        self.stack.pop()

    def charData(self, data):
        data = unicode(data).strip()

        if data and self.stack:
            self.addData(data)

    def addData(self, data):
        #print "DATA:", data
        self.last_start = ''
        try:
            data = int(data)
        except ValueError:
            data = unicode(data)

        stack_str = '-'.join(self.stack)
        stack_str_0 = '-'.join([stack_str, '0'])

        try:
            self.data[stack_str]
        except KeyError:
            try:
                self.data[stack_str_0]
            except KeyError:
                self.data[stack_str] = data
            else:
                j = 2
                while True:
                    try:
                        self.data['-'.join([stack_str, unicode(j)])]
                    except KeyError:
                        self.data['-'.join([stack_str, unicode(j)])] = data
                        break
                    j += 1

        else:
            self.data[stack_str_0] = self.data[stack_str]
            self.data['-'.join([stack_str, '1'])] = data
            del self.data[stack_str]


    def parseXML(self, text):
        parser = expat.ParserCreate()
        parser.StartElementHandler = self.startElement
        parser.EndElementHandler = self.endElement
        parser.CharacterDataHandler = self.charData
        parser.Parse(text.encode('utf-8'), True)
        return self.data


def dquote(s):
    return ''.join(['"', s, '"'])


# Python 2.2.x compatibility functions (strip() family with char argument added in Python 2.2.3)
if sys.hexversion < 0x020203f0:
    def xlstrip(s, chars=' '):
        i = 0
        for c, i in zip(s, range(len(s))):
            if c not in chars:
                break

        return s[i:]

    def xrstrip(s, chars=' '):
        return xreverse(xlstrip(xreverse(s), chars))

    def xreverse(s):
        l = list(s)
        l.reverse()
        return ''.join(l)

    def xstrip(s, chars=' '):
        return xreverse(xlstrip(xreverse(xlstrip(s, chars)), chars))

else:
    xlstrip = string.lstrip
    xrstrip = string.rstrip
    xstrip = string.strip


def getBitness():
    if platform_avail:
        return int(platform.architecture()[0][:-3])
    else:
        return struct.calcsize("P") << 3


def getProcessor():
    if platform_avail:
        return platform.machine().replace(' ', '_').lower() # i386, i686, power_macintosh, etc.
    else:
        return "i686" # TODO: Need a fix here


def getEndian():
    if sys.byteorder == 'big':
        return BIG_ENDIAN
    else:
        return LITTLE_ENDIAN


def get_password():
    return getpass.getpass("Enter password: ")

def get_password_ui():
    fp = open("/etc/hp/hplip.conf", "r")
    qt = "qt3"
    for line in fp:
        if string.find(line, "qt4") is not -1 and string.find(line, "yes") is not -1:
            qt = "qt4"
    fp.close()
    if qt is "qt4":
        from ui4.setupdialog import showPasswordUI
        username, password = showPasswordUI("Your printer requires to install HP proprietary plugin\nPlease enter root/superuser password to continue")
    if qt is "qt3":
        from ui.setupform import showPasswordUI
        username, password = showPasswordUI("Your priter requires to install HP proprietary plugin\nPlease enter root/superuser password to continue")
    return password

def run(cmd, log_output=True, password_func=get_password, timeout=1):
    output = cStringIO.StringIO()

    try:
        child = pexpect.spawn(cmd, timeout=timeout)
    except pexpect.ExceptionPexpect:
        return -1, ''

    try:
        while True:
            update_spinner()
            i = child.expect(["[pP]assword:", pexpect.EOF, pexpect.TIMEOUT])

            if child.before:
                output.write(child.before)
                if log_output:
                    log.debug(child.before)

            if i == 0: # Password:
                if password_func is not None:
                    if password_func == "get_password_ui":
                        child.sendline(get_password_ui())
                    else:
                        child.sendline(password_func())
                else:
                    child.sendline(get_password())

            elif i == 1: # EOF
                break

            elif i == 2: # TIMEOUT
                continue


    except Exception, e:
        log.error("Exception: %s" % e)

    cleanup_spinner()
    child.close()

    return child.exitstatus, output.getvalue()


def expand_range(ns): # ns -> string repr. of numeric range, e.g. "1-4, 7, 9-12"
    """Credit: Jean Brouwers, comp.lang.python 16-7-2004
       Convert a string representation of a set of ranges into a
       list of ints, e.g.
       u"1-4, 7, 9-12" --> [1,2,3,4,7,9,10,11,12]
    """
    fs = []
    for n in ns.split(u','):
        n = n.strip()
        r = n.split('-')
        if len(r) == 2:  # expand name with range
            h = r[0].rstrip(u'0123456789')  # header
            r[0] = r[0][len(h):]
             # range can't be empty
            if not (r[0] and r[1]):
                raise ValueError, 'empty range: ' + n
             # handle leading zeros
            if r[0] == u'0' or r[0][0] != u'0':
                h += '%d'
            else:
                w = [len(i) for i in r]
                if w[1] > w[0]:
                   raise ValueError, 'wide range: ' + n
                h += u'%%0%dd' % max(w)
             # check range
            r = [int(i, 10) for i in r]
            if r[0] > r[1]:
               raise ValueError, 'bad range: ' + n
            for i in range(r[0], r[1]+1):
                fs.append(h % i)
        else:  # simple name
            fs.append(n)

     # remove duplicates
    fs = dict([(n, i) for i, n in enumerate(fs)]).keys()
     # convert to ints and sort
    fs = [int(x) for x in fs if x]
    fs.sort()

    return fs


def collapse_range(x): # x --> sorted list of ints
    """ Convert a list of integers into a string
        range representation:
        [1,2,3,4,7,9,10,11,12] --> u"1-4,7,9-12"
    """
    if not x:
        return ''

    s, c, r = [str(x[0])], x[0], False

    for i in x[1:]:
        if i == (c+1):
            r = True
        else:
            if r:
                s.append(u'-%s,%s' % (c,i))
                r = False
            else:
                s.append(u',%s' % i)

        c = i

    if r:
        s.append(u'-%s' % i)

    return ''.join(s)


def createSequencedFilename(basename, ext, dir=None, digits=3):
    if dir is None:
        dir = os.getcwd()

    m = 0
    for f in walkFiles(dir, recurse=False, abs_paths=False, return_folders=False, pattern='*', path=None):
        r, e = os.path.splitext(f)

        if r.startswith(basename) and ext == e:
            try:
                i = int(r[len(basename):])
            except ValueError:
                continue
            else:
                m = max(m, i)

    return os.path.join(dir, "%s%0*d%s" % (basename, digits, m+1, ext))


def validate_language(lang, default='en_US'):
    if lang is None:
        loc, encoder = locale.getdefaultlocale()
    else:
        lang = lang.lower().strip()
        for loc, ll in supported_locales.items():
            if lang in ll:
                break
        else:
            loc = 'en_US'
            log.warn("Unknown lang/locale. Using default of %s." % loc)

    return loc


def gen_random_uuid():
    try:
        import uuid # requires Python 2.5+
        return str(uuid.uuid4())

    except ImportError:
        uuidgen = which("uuidgen")
        if uuidgen:
            uuidgen = os.path.join(uuidgen, "uuidgen")
            return commands.getoutput(uuidgen) # TODO: Replace with subprocess (commands is deprecated in Python 3.0)
        else:
            return ''


class RestTableFormatter(object):
    def __init__(self, header=None):
        self.header = header # tuple of strings
        self.rows = [] # list of tuples

    def add(self, row_data): # tuple of strings
        self.rows.append(row_data)

    def output(self, w):
        if self.rows:
            num_cols = len(self.rows[0])
            for r in self.rows:
                if len(r) != num_cols:
                    log.error("Invalid number of items in row: %s" % r)
                    return

            if len(self.header) != num_cols:
                log.error("Invalid number of items in header.")

            col_widths = []
            for x, c in enumerate(self.header):
                max_width = len(c)
                for r in self.rows:
                    max_width = max(max_width, len(r[x]))

                col_widths.append(max_width+2)

            x = '+'
            for c in col_widths:
                x = ''.join([x, '-' * (c+2), '+'])

            x = ''.join([x, '\n'])
            w.write(x)

            # header
            if self.header:
                x = '|'
                for i, c in enumerate(col_widths):
                    x = ''.join([x, ' ', self.header[i], ' ' * (c+1-len(self.header[i])), '|'])

                x = ''.join([x, '\n'])
                w.write(x)

                x = '+'
                for c in col_widths:
                    x = ''.join([x, '=' * (c+2), '+'])

                x = ''.join([x, '\n'])
                w.write(x)

            # data rows
            for j, r in enumerate(self.rows):
                x = '|'
                for i, c in enumerate(col_widths):
                    x = ''.join([x, ' ', self.rows[j][i], ' ' * (c+1-len(self.rows[j][i])), '|'])

                x = ''.join([x, '\n'])
                w.write(x)

                x = '+'
                for c in col_widths:
                    x = ''.join([x, '-' * (c+2), '+'])

                x = ''.join([x, '\n'])
                w.write(x)

        else:
            log.error("No data rows")


def mixin(cls):
    import inspect

    locals = inspect.stack()[1][0].f_locals
    if "__module__" not in locals:
        raise TypeError("Must call mixin() from within class def.")

    dict = cls.__dict__.copy()
    dict.pop("__doc__", None)
    dict.pop("__module__", None)

    locals.update(dict)



# TODO: Move usage stuff to to base/module/Module class


 # ------------------------- Usage Help
USAGE_OPTIONS = ("[OPTIONS]", "", "heading", False)
USAGE_LOGGING1 = ("Set the logging level:", "-l<level> or --logging=<level>", 'option', False)
USAGE_LOGGING2 = ("", "<level>: none, info\*, error, warn, debug (\*default)", "option", False)
USAGE_LOGGING3 = ("Run in debug mode:", "-g (same as option: -ldebug)", "option", False)
USAGE_LOGGING_PLAIN = ("Output plain text only:", "-t", "option", False)
USAGE_ARGS = ("[PRINTER|DEVICE-URI]", "", "heading", False)
USAGE_ARGS2 = ("[PRINTER]", "", "heading", False)
USAGE_DEVICE = ("To specify a device-URI:", "-d<device-uri> or --device=<device-uri>", "option", False)
USAGE_PRINTER = ("To specify a CUPS printer:", "-p<printer> or --printer=<printer>", "option", False)
USAGE_BUS1 = ("Bus to probe (if device not specified):", "-b<bus> or --bus=<bus>", "option", False)
USAGE_BUS2 = ("", "<bus>: cups\*, usb\*, net, bt, fw, par\* (\*defaults) (Note: bt and fw not supported in this release.)", 'option', False)
USAGE_HELP = ("This help information:", "-h or --help", "option", True)
USAGE_SPACE = ("", "", "space", False)
USAGE_EXAMPLES = ("Examples:", "", "heading", False)
USAGE_NOTES = ("Notes:", "", "heading", False)
USAGE_STD_NOTES1 = ("If device or printer is not specified, the local device bus is probed and the program enters interactive mode.", "", "note", False)
USAGE_STD_NOTES2 = ("If -p\* is specified, the default CUPS printer will be used.", "", "note", False)
USAGE_SEEALSO = ("See Also:", "", "heading", False)
USAGE_LANGUAGE = ("Set the language:", "-q <lang> or --lang=<lang>. Use -q? or --lang=? to see a list of available language codes.", "option", False)
USAGE_LANGUAGE2 = ("Set the language:", "--lang=<lang>. Use --lang=? to see a list of available language codes.", "option", False)
USAGE_MODE = ("[MODE]", "", "header", False)
USAGE_NON_INTERACTIVE_MODE = ("Run in non-interactive mode:", "-n or --non-interactive", "option", False)
USAGE_GUI_MODE = ("Run in graphical UI mode:", "-u or --gui (Default)", "option", False)
USAGE_INTERACTIVE_MODE = ("Run in interactive mode:", "-i or --interactive", "option", False)

if sys_conf.get('configure', 'ui-toolkit', 'qt3') == 'qt3':
    USAGE_USE_QT3 = ("Use Qt3:",  "--qt3 (Default)",  "option",  False)
    USAGE_USE_QT4 = ("Use Qt4:",  "--qt4",  "option",  False)
else:
    USAGE_USE_QT3 = ("Use Qt3:",  "--qt3",  "option",  False)
    USAGE_USE_QT4 = ("Use Qt4:",  "--qt4 (Default)",  "option",  False)




def ttysize(): # TODO: Move to base/tui
    ln1 = commands.getoutput('stty -a').splitlines()[0]
    vals = {'rows':None, 'columns':None}
    for ph in ln1.split(';'):
        x = ph.split()
        if len(x) == 2:
            vals[x[0]] = x[1]
            vals[x[1]] = x[0]
    try:
        rows, cols = int(vals['rows']), int(vals['columns'])
    except TypeError:
        rows, cols = 25, 80

    return rows, cols


def usage_formatter(override=0): # TODO: Move to base/module/Module class
    rows, cols = ttysize()

    if override:
        col1 = override
        col2 = cols - col1 - 8
    else:
        col1 = int(cols / 3) - 8
        col2 = cols - col1 - 8

    return TextFormatter(({'width': col1, 'margin' : 2},
                            {'width': col2, 'margin' : 2},))


def format_text(text_list, typ='text', title='', crumb='', version=''): # TODO: Move to base/module/Module class
    """
    Format usage text in multiple formats:
        text: for --help in the console
        rest: for conversion with rst2web for the website
        man: for manpages
    """
    if typ == 'text':
        formatter = usage_formatter()

        for line in text_list:
            text1, text2, format, trailing_space = line

            # remove any reST/man escapes
            text1 = text1.replace("\\", "")
            text2 = text2.replace("\\", "")

            if format == 'summary':
                log.info(log.bold(text1))
                log.info("")

            elif format in ('para', 'name', 'seealso'):
                log.info(text1)

                if trailing_space:
                    log.info("")

            elif format in ('heading', 'header'):
                log.info(log.bold(text1))

            elif format in ('option', 'example'):
                log.info(formatter.compose((text1, text2), trailing_space))

            elif format == 'note':
                if text1.startswith(' '):
                    log.info('\t' + text1.lstrip())
                else:
                    log.info(text1)

            elif format == 'space':
                log.info("")

        log.info("")


    elif typ == 'rest':
        opt_colwidth1, opt_colwidth2 = 0, 0
        exmpl_colwidth1, exmpl_colwidth2 = 0, 0
        note_colwidth1, note_colwidth2 = 0, 0

        for line in text_list:
            text1, text2, format, trailing_space = line

            if format  == 'option':
                opt_colwidth1 = max(len(text1), opt_colwidth1)
                opt_colwidth2 = max(len(text2), opt_colwidth2)

            elif format == 'example':
                exmpl_colwidth1 = max(len(text1), exmpl_colwidth1)
                exmpl_colwidth2 = max(len(text2), exmpl_colwidth2)

            elif format == 'note':
                note_colwidth1 = max(len(text1), note_colwidth1)
                note_colwidth2 = max(len(text2), note_colwidth2)

        opt_colwidth1 += 4
        opt_colwidth2 += 4
        exmpl_colwidth1 += 4
        exmpl_colwidth2 += 4
        note_colwidth1 += 4
        note_colwidth2 += 4
        opt_tablewidth = opt_colwidth1 + opt_colwidth2
        exmpl_tablewidth = exmpl_colwidth1 + exmpl_colwidth2
        note_tablewidth = note_colwidth1 + note_colwidth2

        # write the rst2web header
        log.info("""restindex
page-title: %s
crumb: %s
format: rest
file-extension: html
encoding: utf8
/restindex\n""" % (title, crumb))

        t = "%s: %s (ver. %s)" % (crumb, title, version)
        log.info(t)
        log.info("="*len(t))
        log.info("")

        links = []
        needs_header = False
        for line in text_list:
            text1, text2, format, trailing_space = line

            if format == 'seealso':
                links.append(text1)
                text1 = "`%s`_" % text1

            len1, len2 = len(text1), len(text2)

            if format == 'summary':
                log.info(''.join(["**", text1, "**"]))
                log.info("")

            elif format in ('para', 'name'):
                log.info("")
                log.info(text1)
                log.info("")

            elif format in ('heading', 'header'):

                log.info("")
                log.info("**" + text1 + "**")
                log.info("")
                needs_header = True

            elif format == 'option':
                if needs_header:
                    log.info(".. class:: borderless")
                    log.info("")
                    log.info(''.join(["+", "-"*opt_colwidth1, "+", "-"*opt_colwidth2, "+"]))
                    needs_header = False

                if text1 and '`_' not in text1:
                    log.info(''.join(["| *", text1, '*', " "*(opt_colwidth1-len1-3), "|", text2, " "*(opt_colwidth2-len2), "|"]))
                elif text1:
                    log.info(''.join(["|", text1, " "*(opt_colwidth1-len1), "|", text2, " "*(opt_colwidth2-len2), "|"]))
                else:
                    log.info(''.join(["|", " "*(opt_colwidth1), "|", text2, " "*(opt_colwidth2-len2), "|"]))

                log.info(''.join(["+", "-"*opt_colwidth1, "+", "-"*opt_colwidth2, "+"]))

            elif format == 'example':
                if needs_header:
                    log.info(".. class:: borderless")
                    log.info("")
                    log.info(''.join(["+", "-"*exmpl_colwidth1, "+", "-"*exmpl_colwidth2, "+"]))
                    needs_header = False

                if text1 and '`_' not in text1:
                    log.info(''.join(["| *", text1, '*', " "*(exmpl_colwidth1-len1-3), "|", text2, " "*(exmpl_colwidth2-len2), "|"]))
                elif text1:
                    log.info(''.join(["|", text1, " "*(exmpl_colwidth1-len1), "|", text2, " "*(exmpl_colwidth2-len2), "|"]))
                else:
                    log.info(''.join(["|", " "*(exmpl_colwidth1), "|", text2, " "*(exmpl_colwidth2-len2), "|"]))

                log.info(''.join(["+", "-"*exmpl_colwidth1, "+", "-"*exmpl_colwidth2, "+"]))

            elif format == 'seealso':
                if text1 and '`_' not in text1:
                    log.info(text1)


            elif format == 'note':
                if needs_header:
                    log.info(".. class:: borderless")
                    log.info("")
                    log.info(''.join(["+", "-"*note_colwidth1, "+", "-"*note_colwidth2, "+"]))
                    needs_header = False

                if text1.startswith(' '):
                    log.info(''.join(["|", " "*(note_tablewidth+1), "|"]))

                log.info(''.join(["|", text1, " "*(note_tablewidth-len1+1), "|"]))
                log.info(''.join(["+", "-"*note_colwidth1, "+", "-"*note_colwidth2, "+"]))

            elif format == 'space':
                log.info("")

        for l in links:
            log.info("\n.. _`%s`: %s.html\n" % (l, l.replace('hp-', '')))

        log.info("")

    elif typ == 'man':
        log.info('.TH "%s" 1 "%s" Linux "User Manuals"' % (crumb, version))
        log.info(".SH NAME\n%s \- %s" % (crumb, title))

        for line in text_list:
            text1, text2, format, trailing_space = line

            text1 = text1.replace("\\*", "*")
            text2 = text2.replace("\\*", "*")

            len1, len2 = len(text1), len(text2)

            if format == 'summary':
                log.info(".SH SYNOPSIS")
                log.info(".B %s" % text1.replace('Usage:', ''))

            elif format == 'name':
                log.info(".SH DESCRIPTION\n%s" % text1)

            elif format in ('option', 'example', 'note'):
                if text1:
                    log.info('.IP "%s"\n%s' % (text1, text2))
                else:
                    log.info(text2)

            elif format in ('header', 'heading'):
                log.info(".SH %s" % text1.upper().replace(':', '').replace('[', '').replace(']', ''))

            elif format in ('seealso, para'):
                log.info(text1)

        log.info(".SH AUTHOR")
        log.info("HPLIP (Hewlett-Packard Linux Imaging and Printing) is an")
        log.info("HP developed solution for printing, scanning, and faxing with")
        log.info("HP inkjet and laser based printers in Linux.")

        log.info(".SH REPORTING BUGS")
        log.info("The HPLIP Launchpad.net site")
        log.info(".B https://launchpad.net/hplip")
        log.info("is available to get help, report")
        log.info("bugs, make suggestions, discuss the HPLIP project or otherwise")
        log.info("contact the HPLIP Team.")

        log.info(".SH COPYRIGHT")
        log.info("Copyright (c) 2001-9 Hewlett-Packard Development Company, L.P.")
        log.info(".LP")
        log.info("This software comes with ABSOLUTELY NO WARRANTY.")
        log.info("This is free software, and you are welcome to distribute it")
        log.info("under certain conditions. See COPYING file for more details.")

        log.info("")


def log_title(program_name, version, show_ver=True): # TODO: Move to base/module/Module class
    log.info("")

    if show_ver:
        log.info(log.bold("HP Linux Imaging and Printing System (ver. %s)" % prop.version))
    else:
        log.info(log.bold("HP Linux Imaging and Printing System"))

    log.info(log.bold("%s ver. %s" % (program_name, version)))
    log.info("")
    log.info("Copyright (c) 2001-9 Hewlett-Packard Development Company, LP")
    log.info("This software comes with ABSOLUTELY NO WARRANTY.")
    log.info("This is free software, and you are welcome to distribute it")
    log.info("under certain conditions. See COPYING file for more details.")
    log.info("")


def ireplace(old, search, replace):
    regex = '(?i)' + re.escape(search)
    return re.sub(regex, replace, old)


def su_sudo():
    su_sudo_str = None

    if which('kdesu'):
        su_sudo_str = 'kdesu -- %s'

    elif utils.which('/usr/lib/kde4/libexec/kdesu'):
        su_sudo_str = '/usr/lib/kde4/libexec/kdesu -- %s'

    elif utils.which('kdesudo'):
        su_sudo_str = 'kdesudo -- %s'

    elif which('gnomesu'):
        su_sudo_str = 'gnomesu -c "%s"'

    elif which('gksu'):
        su_sudo_str = 'gksu "%s"'
    
    elif which('su'):
        su_sudo_str = 'su'

    return su_sudo_str

# This function returns the distro name and distro version. 
#This is provided to check on Fedora 14 in pkit.py file for Plugin-installation. 
#is_su variable is used to provide a check on Fedora 8 
def os_release():
    os_name = None;
    os_version = None;
    is_su = None;
    if which('lsb_release'):
       name = os.popen('lsb_release -i | cut -f 2')
       os_name = name.read().strip()
       name.close()
       version = os.popen('lsb_release -r | cut -f 2')
       os_version=version.read().strip()
       version.close()
       is_su = True
    else:
       name = os.popen('cat /etc/issue | cut -c 1-6 | head -n 1')
       os_name = name.read().strip()
       name.close()
       version1=os.popen('cat /etc/issue | cut -c 16 | head -n 1')
       version2=version1.read().strip()
       version1.close()
       if (version2 == '1'):
           version=os.popen('cat /etc/issue | cut -c 16-17 | head -n 1')
           is_su = True
       else: 
           version=os.popen('cat /etc/issue | cut -c 16 | head -n 1')
           is_su = False
       os_version=version.read().strip()
       version.close()

    return os_name,os_version,is_su 
    

#
# Removes HTML or XML character references and entities from a text string.
#

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    #return unichr(int(text[3:-1], 16))
                    return chr(int(text[3:-1], 16))
                else:
                    #return unichr(int(text[2:-1]))
                    return chr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                #text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
                text = chr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)


# Adds HTML or XML character references and entities from a text string

def escape(s):
    if not isinstance(s, unicode):
        s = unicode(s) # hmmm...

    s = s.replace(u"&", u"&amp;")

    for c in htmlentitydefs.codepoint2name:
        if c != 0x26: # exclude &
            s = s.replace(unichr(c), u"&%s;" % htmlentitydefs.codepoint2name[c])

    for c in range(0x20) + range(0x7f, 0xa0):
        s = s.replace(unichr(c), u"&#%d;" % c)

    return s
