#!/usr/bin/python

# Copyright (C) 2009 Canonical Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging, logging.handlers
import os, sys
import subprocess

# The minimum size, in megabytes a persistence file can be.
MIN_PERSISTENCE = 1024
MAX_PERSISTENCE = 4096 # VFAT maximum file size.
# Padding for the kernel and initramfs, in megabytes
PADDING = 30
(CAN_USE,     # Obvious.
 CANNOT_USE,  # The partition or disk is too small for the source image.
 NEED_SPACE,  # There is not enough free space, but there could be.
 NEED_FORMAT, # The device has the wrong filesystem type, or the source is a
              # disk image.
) = range(4)
SOURCE_CD, SOURCE_ISO, SOURCE_IMG = range(3)
MAX_LOG_SIZE = 1024 * 1024 * 1
MAX_LOG_BACKUP = 0

if sys.platform != 'win32':
    from IN import INT_MAX
    MAX_DBUS_TIMEOUT = INT_MAX / 1000.0

def setup_logging():
    log = logging.getLogger('')
    # usb-creator used to write ~/.usb-creator.log as root (whoops!), so lets
    # use a different name here. -- ev
    # new location so let's go back to original name =) -- xnox
    cache_dir = os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
    log_file = os.path.join(cache_dir, 'usb-creator.log')
    handler = None
    try:
        handler = logging.handlers.RotatingFileHandler(log_file,
                     maxBytes=MAX_LOG_SIZE, backupCount=MAX_LOG_BACKUP)
    except IOError:
        logging.exception('Could not set up file logging:')
    if handler:
        formatter = logging.Formatter('usb-creator %(asctime)s (%(levelname)s)'
                                      ' %(filename)s:%(lineno)d: %(message)s')
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        log.addHandler(handler)
    log.setLevel(logging.DEBUG)

def format_size(size):
    """Format a partition size."""
    # Taken from ubiquity's ubiquity/misc.py
    # TODO evand 2009-07-28: Localized size formatting.
    if size < 1024:
        unit = 'B'
        factor = 1
    elif size < 1024 * 1024:
        unit = 'kB'
        factor = 1024
    elif size < 1024 * 1024 * 1024:
        unit = 'MB'
        factor = 1024 * 1024
    elif size < 1024 * 1024 * 1024 * 1024:
        unit = 'GB'
        factor = 1024 * 1024 * 1024
    else:
        unit = 'TB'
        factor = 1024 * 1024 * 1024 * 1024
    return '%.1f %s' % (float(size) / factor, unit)

def format_mb_size(size):
    if size < 1024:
        unit = 'MB'
        factor = 1
    elif size < 1024 * 1024:
        unit = 'GB'
        factor = 1024
    elif size < 1024 * 1024 * 1024:
        unit = 'TB'
        factor = 1024 * 1024
    return '%.1f %s' % (float(size) / factor, unit)

def fs_size(device):
    '''Returns a tuple of the total size of the filesystem
       and the free space on it.'''
    # FIXME evand 2009-06-05: Do we want the free bytes available to the user,
    # or the total free bytes?  Right now we're using the latter.

    if sys.platform == 'win32':
        # Taken from Wubi.
        import ctypes
        freeuser = ctypes.c_int64()
        total = ctypes.c_int64()
        free = ctypes.c_int64()
        try:
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    unicode(device),
                    ctypes.byref(freeuser),
                    ctypes.byref(total),
                    ctypes.byref(free))
        except:
            return (0, 0)
        return (total.value, free.value)
    else:
        try:
            stat = os.statvfs(device)
        except:
            return (0, 0)
        free = stat.f_bsize * stat.f_bavail # Include reserved blocks.
        total = stat.f_bsize * stat.f_blocks
        return (total, free)

class USBCreatorProcessException(Exception):
    pass

def popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
          stdin=subprocess.PIPE):
    logging.debug(str(cmd))
    if sys.platform == 'win32':
        STARTF_USESHOWWINDOW = 1
        SW_HIDE = 0
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
    else:
        startupinfo = None
    process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, stdin=stdin,
                               startupinfo=startupinfo)
    out, err = process.communicate()
    if process.returncode is None:
        process.wait()
    elif process.returncode != 0:
        raise USBCreatorProcessException(err)
    return out

# Taken from ubiquity.
def find_on_path(command):
    """Is command on the executable search path?"""
    if 'PATH' not in os.environ:
        return False
    path = os.environ['PATH']
    for element in path.split(os.pathsep):
        if not element:
            continue
        filename = os.path.join(element, command)
        if os.path.isfile(filename) and os.access(filename, os.X_OK):
            return True
    return False

def prepend_path(directory):
    if 'PATH' in os.environ and os.environ['PATH'] != '':
        os.environ['PATH'] = '%s:%s' % (directory, os.environ['PATH'])
    else:
        os.environ['PATH'] = directory

def sane_path():
    elements = os.environ.get('PATH', '').split(os.pathsep)
    for element in ('/bin', '/sbin', '/usr/bin', '/usr/sbin'):
        if element not in elements:
            prepend_path(element)
