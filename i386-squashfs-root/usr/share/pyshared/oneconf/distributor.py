# Copyright (C) 2009-2010 Canonical
#
# Authors:
#  Michael Vogt
#  Didier Roche <didrocks@ubuntu.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


import logging
import os
import subprocess

from gettext import gettext as _

LOG = logging.getLogger(__name__)

class UnimplementedError(Exception):
    pass


class Distro(object):
    """ abstract base class for a distribution """
        
    def compute_local_packagelist(self):
        '''Introspect what's installed on this hostid

        Return: installed_packages list
        '''
        raise UnimplementedError


def _get_distro():
    distro_id = subprocess.Popen(["lsb_release","-i","-s"], 
                                 stdout=subprocess.PIPE).communicate()[0].strip()
    LOG.debug("get_distro: '%s'" % distro_id)
    # start with a import, this gives us only a oneconf module
    module =  __import__(distro_id, globals(), locals(), [], -1)
    # get the right class and instanciate it
    distro_class = getattr(module, distro_id)
    instance = distro_class()
    return instance

def get_distro():
    """ factory to return the right Distro object """
    return distro_instance

# singelton
distro_instance=_get_distro()


if __name__ == "__main__":
    print get_distro()

