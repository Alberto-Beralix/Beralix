# (c) 2009 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# License: GPL v2 or later

import logging, subprocess, os.path

from jockey.oslib import OSLib
from jockey.handlers import Handler, KernelModuleHandler

# dummy stub for xgettext
def _(x): return x

class MadwifiHandler(KernelModuleHandler):
    '''Handler for the Madwifi driver.

    The free ath5k driver should work with most Atheros cards nowadays, but on
    some models madwifi still works better (or at all).  This driver (ath_pci)
    should be disabled by default by blacklisting it in self.blacklist_file.
    '''
    def __init__(self, ui):
        KernelModuleHandler.__init__(self, ui, 'ath_pci',
                name=_('Alternate Atheros "madwifi" driver'),
                description=_('Alternate "madwifi" driver for Atheros wireless LAN cards.'),
                rationale=_('Only activate this driver if you have problems '
                    'with your wireless LAN connection.\n\n'
                    'The free "ath5k" driver should work with most '
                    'Atheros cards nowadays, but on some computers this '
                    'alternate (but proprietary) driver still works better, '
                    'or at all.'))
        self._free = False
        # do not announce this if ath5k works
        self.announce = not self.module_loaded('ath5k')
        self.blacklist_file = os.path.join(os.path.dirname(
            OSLib.inst.module_blacklist_file), 'blacklist-ath_pci.conf')

    def can_change(self):
        if not os.path.exists(self.blacklist_file):
            return _('You removed the configuration file %s') % self.blacklist_file
        return None

    def enable(self):
        Handler.enable(self)
        self._update_blacklist('ath5k')
        subprocess.call([OSLib.inst.modprobe_path, self.module])
        self.read_loaded_modules()
        return self.rebind(self.module)

    def disable(self):
        self._update_blacklist(self.module)
        self.read_loaded_modules()
        Handler.disable(self)
        return False

    def _update_blacklist(self, module):
        '''Update self.blacklist_file to blacklist given module.'''

        logging.debug('MadwifiHandler._update_blacklist(%s)' % module)

        lines = []
        f = open(self.blacklist_file)
        for l in f:
            if l.startswith('blacklist '):
                l = 'blacklist %s\n' % module
            lines.append(l)
        f.close()
        f = open(self.blacklist_file + '.new', 'w')
        for l in lines:
            f.write(l)
        f.close()
        os.rename(self.blacklist_file + '.new', self.blacklist_file)

        OSLib.inst._load_module_blacklist()
