# -*- coding: utf-8 -*-
# (c) 2008 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# License: GPL v2 or later

import re, os.path, logging, subprocess

from jockey.handlers import Handler

# dummy stub for xgettext
def _(x): return x

class SlModem(Handler):
    def __init__(self, backend):
        Handler.__init__(self, backend, name=_('Software modem'),
            rationale=_(
                'This driver enables the usage of many software modems, as '
                'commonly found in laptops.\n\n'
                'If this driver is not enabled, you will not be able to use '
                'your modem.'))
        self.package = 'sl-modem-daemon'

        self.modem_re = re.compile('^\s*\d+\s*\[Modem\s*\]')
        self.modem_as_subdevice_re = re.compile('^card [0-9].*[mM]odem')

    def available(self):
        '''Check /proc/asound/cards and aplay -l for a "Modem" card.'''
                
        if Handler.available(self) == False:
            return False
        
        try:
            for l in open('/proc/asound/cards'):
                if self.modem_re.match(l):
                    return True
        except IOError as e:
            logging.error('could not open /proc/asound/cards: %s' % str(e))
                
        try:
            aplay = subprocess.Popen(['aplay', '-l'], env={},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (aplay_out, aplay_err) = aplay.communicate()
        except OSError as e:
            logging.error('could not open aplay -l: %s' % str(e))
            return False

        if aplay.returncode != 0:
            logging.error('aplay -l failed with %i: %s' % (aplay.returncode,
                aplay_err))
            return False

        for row in aplay_out.splitlines():
            if self.modem_as_subdevice_re.match(row):
                return True        
        
        return False

    def used(self):
        return self.enabled() and os.path.exists('/dev/modem')
