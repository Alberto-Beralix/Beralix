# -*- coding: utf-8 -*-
# (c) 2008 Canonical Ltd.
# Authors: Martin Pitt <martin.pitt@ubuntu.com>
#          Alberto Milone <alberto.milone@canonical.com>
# License: GPL v2 or later

import logging, os, os.path

import XKit.xorgparser
from jockey.xorg_driver import XorgDriverHandler
from NvidiaDetector.alternatives import Alternatives
from NvidiaDetector.alternatives import MultiArchUtils
import subprocess

# dummy stub for xgettext
def _(x): return x

class FglrxDriver(XorgDriverHandler):
    def __init__(self, backend, package=None):
        self._free = False

        if package and 'update' in package:
            name=_('ATI/AMD proprietary FGLRX graphics driver (post-release updates)')
        else:
            name=_('ATI/AMD proprietary FGLRX graphics driver')

        XorgDriverHandler.__init__(self, backend, (package and
            package.replace('-', '_') or 'fglrx'), (package and
            package or 'fglrx'), None, None, add_modules=['glx'],
            disable_modules=[], name=name,
            description=_('3D-accelerated proprietary graphics driver for '
                'ATI cards.'),
            rationale=_('This driver is required to fully utilise the 3D '
                'potential of some ATI graphics cards, as well as provide '
                '2D acceleration of newer cards.'))

        (self._alternatives, self._other_alternatives) = self._get_alternatives()
        self.needs_kernel_headers = True

    def _get_alternatives(self):
        '''Get multi-arch alternatives names'''
        arch_utils = MultiArchUtils()
        main_name = arch_utils.get_main_alternative_name()
        other_name = arch_utils.get_other_alternative_name()
        return Alternatives(main_name), Alternatives(other_name)

    def available(self):
        # we don't offer fglrx in a life CD environment, as we will run out of
        # RAM trying to download and install all the packages in the RAM disk.
        if os.path.isdir('/rofs'):
            logging.debug('Disabling fglrx driver on live system')
            return False

        logging.debug('fglrx.available: falling back to default')
        return XorgDriverHandler.available(self)

    def enable_config_hook(self):
        # TODO: this method should look for the right Screen section(s) and
        # if none can be found, use section 0. use get_devices_from_serverlayout()

        # X.org does not work otherwise
        if len(self.xorg_conf.globaldict['Screen']) == 0:
            self.xorg_conf.makeSection('Screen', identifier='Default Screen')
        
        self.xorg_conf.addOption('Screen', 'DefaultDepth', '24', position=0, prefix='')
        
        # make sure that RGB path is not in the xorg.conf otherwise xorg will crash
        it = 0
        for section in self.xorg_conf.globaldict['Files']:
            try:
                self.xorg_conf.removeOption('Files', 'RgbPath', position=it)
            except (XKit.xorgparser.OptionException):
                pass
            it += 1
        
        # remove any Disable "dri2" otherwise amdcccle will crash
        module_sections = self.xorg_conf.globaldict['Module']
        have_modules = len(module_sections) > 0
        
        if have_modules:
            for section in module_sections:
                self.xorg_conf.removeOption('Module', 'Disable', value='dri2', position=section)

    def enable(self):
        XorgDriverHandler.enable(self)
        
        # Set the alternative to FGLRX
        fglrx_alternative = self._alternatives.get_alternative_by_name(self.package)
        if not fglrx_alternative:
            logging.error('%s: get_alternative_by_name(%s) returned nothing' % (
                self.id(), self.package))
            return
        self._alternatives.set_alternative(fglrx_alternative)
        other_fglrx_alternative = self._other_alternatives.get_alternative_by_name(self.package)
        self._other_alternatives.set_alternative(other_fglrx_alternative)
        subprocess.call(['update-initramfs', '-u'])
        subprocess.call(['update-initramfs', '-u', '-k', os.uname()[2]])

    def enabled(self):
        # See if fglrx is the current alternative
        target_alternative = self._alternatives.get_alternative_by_name(self.package)
        current_alternative = self._alternatives.get_current_alternative()
        other_target_alternative = self._other_alternatives.get_alternative_by_name(self.package)
        other_current_alternative = self._other_alternatives.get_current_alternative()

        logging.debug('fglrx.enabled(%s): target_alt %s current_alt %s other target alt %s other current alt %s',
                self.module, target_alternative, current_alternative,
                other_target_alternative, other_current_alternative)

        if current_alternative is None:
            logging.debug('current alternative of %s is None, not enabled', self.module)
            return False
        if current_alternative != target_alternative or \
           other_current_alternative != other_target_alternative:
            logging.debug('%s is not the alternative in use', self.module)
            return False

        return XorgDriverHandler.enabled(self)

    def disable(self):
        # make sure that fglrx-kernel-source is removed too
        XorgDriverHandler.disable(self)
        #kernel_source = 'fglrx-kernel-source'
        #self.backend.remove_package(kernel_source)

        # Set the alternative back to open drivers
        open_drivers = self._alternatives.get_open_drivers_alternative()
        logging.debug('fglrx.disable(%s): open_drivers: %s', self.module, open_drivers)
        if open_drivers:
            self._alternatives.set_alternative(open_drivers)
        other_open_drivers = self._other_alternatives.get_open_drivers_alternative()
        logging.debug('fglrx.disable(%s): other_open_drivers: %s', self.module, other_open_drivers)
        if other_open_drivers:
            self._other_alternatives.set_alternative(other_open_drivers)
        subprocess.call(['update-initramfs', '-u'])
        subprocess.call(['update-initramfs', '-u', '-k', os.uname()[2]])

        return False

    def enables_composite(self):
        '''Return whether this driver supports the composite extension.'''

        if not self.xorg_conf:
            return False

        # the radeon X.org driver supports composite nowadays, so don't force
        # installation of fglrx upon those users. Treat absent driver
        # configuration as radeon, since that's what X.org should autodetect.
        # Only suggest fglrx if people use something else, like vesa.
        try:
            if self.xorg_conf.getDriver('Device', 0) in ['fglrx', 'ati', 'radeon', None]:
                return False
        except (XKit.xorgparser.OptionException, XKit.xorgparser.SectionException) as error:
            return False # unconfigured driver -> defaults to ati

        return True

class FglrxDriverUpdate(FglrxDriver):
    def __init__(self, backend):
        FglrxDriver.__init__(self, backend, 'fglrx-updates')
