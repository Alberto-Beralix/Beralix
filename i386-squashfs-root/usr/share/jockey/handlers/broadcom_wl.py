# (c) 2008 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# License: GPL v2 or later

import re, os.path, logging, subprocess
from glob import glob

from jockey.oslib import OSLib
from jockey.handlers import KernelModuleHandler

# dummy stub for xgettext
def _(x): return x

class BroadcomWLHandler(KernelModuleHandler):
    '''Handler for Broadcom Wifi chipsets which use the wl module.'''

    def __init__(self, ui):
        self._free = False
        KernelModuleHandler.__init__(self, ui, 'wl',
            name=_('Broadcom STA wireless driver'))
        self.package = 'bcmwl-kernel-source'
        self._auto_install = True
        self.needs_kernel_headers = True

    def enabled(self):
        km =  KernelModuleHandler.enabled(self)
        bcm = OSLib.inst.module_blacklisted('bcm43xx')
        b43 = OSLib.inst.module_blacklisted('b43')
        b43_legacy = OSLib.inst.module_blacklisted('b43legacy')
        b43_loaded = KernelModuleHandler.module_loaded('bcm43xx') or \
                     KernelModuleHandler.module_loaded('b43')   or \
                     KernelModuleHandler.module_loaded('b43legacy')
        logging.debug('BroadcomWLHandler enabled(): kmod %s, bcm43xx: %s, b43: %s, b43legacy: %s' % (
            km and 'enabled' or 'disabled',
            bcm and 'blacklisted' or 'enabled',
            b43 and 'blacklisted' or 'enabled',
            b43_legacy and 'blacklisted' or 'enabled'))

        return (km and not b43_loaded) or (km and bcm and b43 and b43_legacy)

    def used(self):
        '''Return if the handler is currently in use.'''

        return KernelModuleHandler.used(self) and self.enabled() and \
            not (KernelModuleHandler.module_loaded('b43') or
            KernelModuleHandler.module_loaded('b43legacy') or
            KernelModuleHandler.module_loaded('bcm43xx'))

    def enable(self):
        subprocess.call(['/sbin/rmmod', 'b43'])
        subprocess.call(['/sbin/rmmod', 'b43legacy'])
        subprocess.call(['/sbin/rmmod', 'bcm43xx'])
        subprocess.call(['/sbin/rmmod', 'ssb'])
        KernelModuleHandler.enable(self)

