# ubuntuone.platform.linux - linux platform imports
#
# Author: Lucio Torre <lucio.torre@canonical.com>
#
# Copyright 2009 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Linux import for ubuntuone-client

This module has to have all linux specific modules and provide the api required
to support the linux platform.
"""

import errno
import logging
import os
import shutil
import stat
import sys

if 'gobject' in sys.modules:
    import gio
    has_gi = False
else:
    from gi.repository import Gio, GLib
    has_gi = True

from contextlib import contextmanager

platform = "linux2"

logger = logging.getLogger('ubuntuone.SyncDaemon')


def set_no_rights(path):
    """Remove all rights from the file."""
    os.chmod(path, 0o000)


def set_file_readonly(path):
    """Change path permissions to readonly in a file."""
    os.chmod(path, 0444)


def set_file_readwrite(path):
    """Change path permissions to readwrite in a file."""
    os.chmod(path, 0664)


def set_dir_readonly(path):
    """Change path permissions to readonly in a dir."""
    os.chmod(path, 0555)


def set_dir_readwrite(path):
    """Change path permissions to readwrite in a dir."""
    os.chmod(path, 0775)


@contextmanager
def allow_writes(path):
    """A very simple context manager to allow writting in RO dirs."""
    prev_mod = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, 0755)
    yield
    os.chmod(path, prev_mod)


def remove_file(path):
    """Remove a file."""
    os.remove(path)


def remove_tree(path):
    """Remove a dir and all its children."""
    shutil.rmtree(path)


def remove_dir(path):
    """Remove a dir."""
    os.rmdir(path)


def path_exists(path):
    """Return if the path exists."""
    return os.path.exists(path)


def make_dir(path, recursive=False):
    """Make a dir, optionally creating all the middle ones."""
    if recursive:
        os.makedirs(path)
    else:
        os.mkdir(path)


def open_file(path, mode='r'):
    """Open a file."""
    return open(path, mode)


def rename(path_from, path_to):
    """Rename a file or directory."""
    os.rename(path_from, path_to)


def recursive_move(path_from, path_to):
    """Perform a recursive move."""
    shutil.move(path_from, path_to)


def make_link(target, destination):
    """Create a link from the destination to the target."""
    os.symlink(target, destination)


def read_link(path):
    """Read the destination of a link."""
    return os.readlink(path)


def is_link(path):
    """Returns if a path is a link or not."""
    return os.path.islink(path)


def remove_link(path):
    """Removes a link."""
    if is_link(path):
        os.unlink(path)


def listdir(directory):
    """List a directory."""
    return os.listdir(directory)


def walk(path, topdown=True):
    return os.walk(path, topdown)


def access(path):
    """Return if the path is at least readable."""
    return os.access(path, os.R_OK)


def can_write(path):
    """Return if the path can be written to."""
    return os.access(path, os.W_OK)


def stat_path(path):
    """Return stat info about a path."""
    return os.lstat(path)


def move_to_trash(path):
    """Move the file or dir to trash.

    If had any error, or the system can't do it, just remove it.
    """
    if has_gi:
        not_supported = Gio.IOErrorEnum.NOT_SUPPORTED
        try:
            return_code = Gio.File.new_for_path(path).trash(None)
        except GLib.GError:
            exc = OSError()
            exc.errno = errno.ENOENT
            raise exc
    else:
        not_supported = gio.ERROR_NOT_SUPPORTED
        try:
            return_code = gio.File(path).trash()
        except gio.Error:
            exc = OSError()
            exc.errno = errno.ENOENT
            raise exc

    if not return_code or return_code == not_supported:
        logger.warning("Problems moving to trash! (%s) Removing anyway: %r",
                       return_code, path)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def set_application_name(app_name):
    """Set the name of the application."""
    if has_gi:
        from gi.repository import GObject
        GObject.set_application_name(app_name)
    else:
        import gobject
        gobject.set_application_name(app_name)

def is_root():
    """Return if the user is running as root."""
    return not os.geteuid()


def get_path_list(path):
    """Return a list with the diff components of the path."""
    return os.path.abspath(path).split(os.path.sep)


def normpath(path):
    """Normalize path, eliminating double slashes, etc."""
    return os.path.normpath(path)
