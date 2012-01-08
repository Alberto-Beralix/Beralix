# (c) 2009 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# License: GPL v2 or later

import logging, subprocess

from jockey.oslib import OSLib
from jockey.handlers import KernelModuleHandler

# dummy stub for xgettext
def _(x): return x

class DvbUsbFirmwareHandler(KernelModuleHandler):
    '''Handler for USB DVB cards which need firmware.

    We implement our own available() here, since dvb_usb itself does not have
    modaliases (it's a dependency of particular drivers such as dib7000p).
    '''
    def __init__(self, ui):
        KernelModuleHandler.__init__(self, ui, 'dvb_usb', 
            name=_('Firmware for DVB cards'))
        self.package = 'linux-firmware-nonfree'
        self._free = False
        self._do_rebind = False # does not work, don't bother

    def id(self):
        '''Return an unique identifier of the handler.'''

        i = 'firmware:' + self.module
        if self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def available(self):
        r = KernelModuleHandler.available(self)
        if r is not None:
            return r
        return self.module_loaded(self.module)

    def enable(self):
        KernelModuleHandler.enable(self)

        # rebinding does not work, we have to unload/reload
        mods = []
        proc_modules = open(OSLib.inst.proc_modules)
        for line in open(OSLib.inst.proc_modules):
            if 'dvb_usb' in line:
                mods.append(line.split()[0])
        logging.debug('reloading modules: %s' % ' '.join(mods))
        subprocess.call([OSLib.inst.modprobe_path, '-r'] + mods)
        subprocess.call([OSLib.inst.modprobe_path, '-a'] + mods)
