# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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

from datetime import datetime

import logging
import re
import string

LOG = logging.getLogger(__name__)

def ascii_lower(key):
    ascii_trans_table = string.maketrans(string.ascii_uppercase,
                                        string.ascii_lowercase)
    return key.translate(ascii_trans_table)

class Transaction(object):
    """ Represents an pkg transaction 

o    Attributes:
    - 'start_date': the start date/time of the transaction as datetime
    - 'install', 'upgrade', 'downgrade', 'remove', 'purge':
        contain the list of packagenames affected by this action
    """

    PKGACTIONS=["Install", "Upgrade", "Downgrade", "Remove", "Purge"]

    def __init__(self, sec):
        self.start_date = datetime.strptime(sec["Start-Date"],
                                            "%Y-%m-%d  %H:%M:%S")
        # set the object attributes "install", "upgrade", "downgrade",
        #                           "remove", "purge", error
        for k in self.PKGACTIONS+["Error"]:
            # we use ascii_lower for issues described in LP: #581207
            attr = ascii_lower(k)
            if k in sec:
                value = map(self._fixup_history_item, sec[k].split("),"))
            else:
                value = []
            setattr(self, attr, value)
    def __len__(self):
        count=0
        for k in self.PKGACTIONS:
            count += len(getattr(self, k.lower()))
        return count
    def __repr__(self):
        return ('<Transaction: start_date:%s install:%s upgrade:%s downgrade:%s remove:%s purge:%s' % (self.start_date, self.install, self.upgrade, self.downgrade, self.remove, self.purge))
    def __cmp__(self, other):
        return cmp(self.start_date, other.start_date)
    @staticmethod
    def _fixup_history_item(s):
        """ strip history item string and add missing ")" if needed """
        s=s.strip()
        # remove the infomation about the architecture
        s = re.sub(":\w+", "", s)
        if "(" in s and not s.endswith(")"):
            s+=")"
        return s
               
class PackageHistory(object):
    """ Represents the history of the transactions """    

    def __init__(self, use_cache=True):
        pass

    # FIXME: this should also emit a signal
    @property
    def history_ready(self):
        """ The history is ready for consumption """
        return False

    @property
    def transactions(self):
        """ Return a ordered list of Transaction objects """
        return []

    # FIXME: this should be a gobect signal
    def set_on_update(self,update_callback):
        """ callback when a update is ready """
        pass

    def get_installed_date(self, pkg_name):
        """Return the date that the given package name got instaled """
        return None


# make it a singleton
pkg_history = None
def get_pkg_history():
    """ get the global PackageHistory() singleton object """
    global pkg_history
    if pkg_history is None:
        from softwarecenter.enums import USE_APT_HISTORY
        if USE_APT_HISTORY:
            from history_impl.apthistory import AptHistory
            pkg_history = AptHistory()
        else:
            pkg_history = PackageHistory()
    return pkg_history
