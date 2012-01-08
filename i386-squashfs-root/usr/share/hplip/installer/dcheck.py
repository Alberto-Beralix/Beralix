# -*- coding: utf-8 -*-
#
# (c) Copyright 2003-2007 Hewlett-Packard Development Company, L.P.
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
import os
import os.path
import re
import sys

# Local
from base.g import *
from base import utils


ver_pat = re.compile("""(\d+.\d+)""", re.IGNORECASE)
proc_pat = re.compile(r"""(\d+)""", re.I)

ld_output = ''
#ps_output = ''
mod_output = ''



def update_ld_output():
    # For library checks
    global ld_output
    status, ld_output = utils.run('%s -p' % os.path.join(utils.which('ldconfig'), 'ldconfig'), log_output=False)

    if status != 0:
        log.debug("ldconfig failed.")

def check_tool(cmd, min_ver=0.0):
    log.debug("Checking: %s (min ver=%f)" % (cmd, min_ver))
    status, output = utils.run(cmd)

    if status != 0:
        log.debug("Not found!")
        return False
    else:
        if min_ver:
            try:
                line = output.splitlines()[0]
            except IndexError:
                line = ''
            log.debug(line)
            match_obj = ver_pat.search(line)
            try:
                ver = match_obj.group(1)
            except AttributeError:
                ver = ''

            try:
                v_f = float(ver)
            except ValueError:
                return False
            else:
                log.debug("Ver=%f Min ver=%f" % (v_f, min_ver))

                if v_f < min_ver:
                    log.debug("Found, but newer version required.")

                return v_f >= min_ver
        else:
            log.debug("Found.")
            return True


def check_lib(lib, min_ver=0):
    log.debug("Checking for library '%s'..." % lib)

    if ld_output.find(lib) >= 0:
        log.debug("Found.")

        #if min_ver:
        #    pass
        #else:
        return True
    else:
        log.debug("Not found.")
        return False

def check_file(f, dir="/usr/include"):
    log.debug("Searching for file '%s' in '%s'..." % (f, dir))
    for w in utils.walkFiles(dir, recurse=True, abs_paths=True, return_folders=False, pattern=f):
        log.debug("File found at '%s'" % w)
        return True

    log.debug("File not found.")
    return False


def locate_files(f, dir):
    log.debug("Searching for file(s) '%s' in '%s'..." % (f, dir))
    found = []
    for w in utils.walkFiles(dir, recurse=True, abs_paths=True, return_folders=False, pattern=f):
        log.debug(w)
        found.append(w)

    if found:
        log.debug("Found files: %s" % found)
    else:
        log.debug("No files not found.")

    return found

def locate_file_contains(f, dir, s):
    """
        Find a list of files located in a directory
        that contain a specified sub-string.
    """
    log.debug("Searching for file(s) '%s' in '%s' that contain '%s'..." % (f, dir, s))
    found = []
    for w in utils.walkFiles(dir, recurse=True, abs_paths=True, return_folders=False, pattern=f):

        if check_file_contains(w, s):
            log.debug(w)
            found.append(w)

    if found:
        log.debug("Found files: %s" % found)
    else:
        log.debug("No files not found.")

    return found

def check_file_contains(f, s):
    log.debug("Checking file '%s' for contents '%s'..." % (f, s))
    try:
        if os.path.exists(f):
            for a in file(f, 'r'):
                update_spinner()

                if s in a:
                    log.debug("'%s' found in file '%s'." % (s.replace('\n', ''), f))
                    return True

        log.debug("Contents not found.")
        return False

    finally:
        cleanup_spinner()


def get_process_list():
    processes = [] # (pid, cmdline), ...
    for x in utils.walkFiles("/proc", False, True, True):
        s = proc_pat.search(x) 
        if s is not None:
            try:
                cmdline = file(os.path.join(x, 'cmdline'), 'r').read().replace('\x00', '').replace('\n', '').strip()
            except IOError:
                cmdline = None
                
            if cmdline:
                processes.append((int(s.group(1)), cmdline))

    return processes


def check_ps(process_list):
    log.debug("Searching any process(es) '%s' in running processes..." % process_list)
    processes = get_process_list()

    try:
        for pid, cmdline in processes:
            update_spinner()
            for p in process_list:
                if p in cmdline:
                    log.debug("'%s' found." % cmdline)
                    return True

        log.debug("Not found")
        return False

    finally:
        cleanup_spinner()


def get_ps_pid(process):
    log.debug("Searching for the PID for process '%s' in running processes..." % process)
    processes = get_process_list()

    try:
        for pid, cmdline in processes:
            update_spinner()
            if process in cmdline:
                log.debug("'%s' found." % cmdline)
                return pid

        log.debug("Not found")
        return 0

    finally:
        cleanup_spinner()


def check_lsmod(module):
    global mod_output

    if not mod_output:
        lsmod = utils.which('lsmod')
        status, mod_output = utils.run(os.path.join(lsmod, 'lsmod'), log_output=False)

    return mod_output.find(module) >= 0
