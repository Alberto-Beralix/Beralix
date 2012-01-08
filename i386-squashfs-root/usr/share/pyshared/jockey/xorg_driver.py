# (c) 2007 Canonical Ltd.
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'''Abstract handler for a restricted X.org graphics driver.'''

import os.path, logging

import XKit.xutils
import XKit.xorgparser

from handlers import KernelModuleHandler
from jockey.oslib import OSLib

# dummy stub for xgettext
def _(x): return x

#--------------------------------------------------------------------#

class XorgDriverHandler(KernelModuleHandler):
    '''Abstract class for a restricted X.org graphics driver.'''

    def __init__(self, backend, module, driver_package, xorg_driver,
        alt_free_driver, extra_conf_options={}, add_modules=[],
            disable_modules=[], remove_modules=[], name=None, description=None,
            rationale=None, do_blacklist=True):
        '''Create handler for a particular X.org graphics driver.
        
        This usually consists of a kernel module and a driver package, plus
        some xorg.conf configuration.

        - backend, module, driver_package, name, description, rationale: as in
          KernelModuleHandler
        - xorg_driver: name of the X.org driver as it appears in xorg.conf
          (None if the driver will be detected automatically, then it won't be
          changed)
        - alt_free_driver: free fallback driver if this one gets disabled (None
          if xorg_driver is None)
        - extra_conf_options: dictionary of extra "Option"s that go into the
          Device section of xorg.conf
        - add_modules: list of modules that get added to the "Module" section
          of xorg.conf when enabling this driver (and removed when disabling)
        - remove_modules: list of modules that get removed from the "Module"
          section of xorg.conf when enabling this driver (and added when disabling)
        '''
        KernelModuleHandler.__init__(self, backend, module, name, description,
            rationale, do_blacklist=do_blacklist)
        self.package = driver_package
        self.xorg_driver = xorg_driver
        self.alt_free_driver = alt_free_driver
        self.extra_conf_options = extra_conf_options
        self.add_modules = add_modules
        self.disable_modules = disable_modules
        self.remove_modules = remove_modules

        if self.xorg_driver:
            self.old_conf = os.path.join(OSLib.inst.backup_dir, self.xorg_driver + '.oldconf')
            self.no_conf = os.path.join(OSLib.inst.backup_dir, self.xorg_driver + '.noconf')
        else:
            self.old_conf = os.path.join(OSLib.inst.backup_dir, self.package + '.oldconf')
            self.no_conf = os.path.join(OSLib.inst.backup_dir, self.package + '.noconf')

        if os.path.exists(OSLib.inst.xorg_conf_path):
            try:
                self.xorg_conf = XKit.xutils.XUtils(OSLib.inst.xorg_conf_path)
            except XKit.xorgparser.ParseException:
                # for now, do not mess up an already broken xorg.conf any
                # further; TODO: UI dialog question to start from scratch
                self.xorg_conf = None
        else:
            self.xorg_conf = XKit.xutils.XUtils()

    def id(self):
        '''Return a unique identifier of the handler.'''

        i = 'xorg:' + self.module
        if self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def can_change(self):
        if self.xorg_conf:
            return None
        else:
            # translators: %s is the path to xorg.conf
            return _('Reconfiguring X.org video drivers is not '
                'possible: %s is invalid.') % OSLib.inst.xorg_conf_path

    def available(self):
        if self.package:
            cur_abi = OSLib.inst.current_xorg_video_abi()
            pkg_abi = OSLib.inst.video_driver_abi(self.package)
            if cur_abi and pkg_abi and cur_abi != pkg_abi:
                logging.debug('XorgDriverHandler(%s, %s, %s): Disabling as package video ABI %s does not match X.org video ABI %s',
                        self.module, self.package, self.xorg_driver, pkg_abi, cur_abi)
                return False

        return KernelModuleHandler.available(self)

    def enabled(self):
        if self.xorg_conf:
            if self.xorg_driver:
                if self.xorg_conf.isDriverEnabled(self.xorg_driver) == False:
                    logging.debug('XorgDriverHandler(%s, %s, %s).enabled(): considering xorg driver disabled',
                        self.module, self.package, self.xorg_driver)
                    return False
            
                logging.debug('XorgDriverHandler(%s, %s, %s).enabled(): xorg.conf driver matches',
                        self.module, self.package, self.xorg_driver)
            else:
                logging.debug('XorgDriverHandler(%s, %s).enabled(): No X.org driver set, not checking')
        else:
            logging.debug('%s: xkit object does not exist!', self.module)
            return False
        return KernelModuleHandler.enabled(self)

    def used(self):
        '''Return if the handler is currently in use.'''

        # if we just enabled the driver, it cannot possibly be in use yet
        # TODO: it would be much better to ask X directly, or at least parse
        # /var/log/Xorg.0.log
        if self.changed() and self.enabled():
            return False
        return KernelModuleHandler.used(self)

    def _mod_status(self, module, action):
        '''Check if a module is handled in current configuration.

        action can be "Load" or "Disable".
        '''
        for i in xrange(len(self.xorg_conf.globaldict['Module'])):
            try:
                modules = self.xorg_conf.getValue('Module', action, i)
            except XKit.xorgparser.OptionException:
                # there is no matching action
                continue
            
            # see if it's a list or a string
            if type(modules) == type(''): # string
                if modules == module:
                    return True
            else: # list
                for mod in modules:
                    if mod == module:
                        return True
        return False
    
    def _mod_enabled(self, module):
        #See whether the xorg.conf has a module set to "Load"
        return self._mod_status(module, 'Load')
    
    def _mod_disabled(self, module):
        #See whether the xorg.conf has a module set to "Disable"
        return self._mod_status(module, 'Disable')
    
    def enable(self):
        if not self.xorg_conf:
            logging.error('XorgDriverHandler.enable(): invalid xorg.conf, skipping')
            return False

        KernelModuleHandler.enable(self)

        # do not mangle xorg.conf if package installation has been aborted or
        # module is not available (e. g. because DKMS did not build it)
        if not KernelModuleHandler.enabled(self):
            logging.error('XorgDriverHandler.enable(): package or module not installed, aborting')
            return False
        
        # see if the same proprietary driver is in use
        # in the xorg.conf. If so do not create a backup
        has_proprietary = False
        if self.xorg_driver:
            it = 0
            for section in self.xorg_conf.globaldict['Device']:
                try:
                    driver = self.xorg_conf.getDriver('Device', it)
                    if driver == self.xorg_driver:
                        has_proprietary = True
                        break
                except XKit.xorgparser.OptionException:
                    # no driver is specified
                    pass
                it += 1
        
        # backup the current xorg.conf
        if os.path.exists(OSLib.inst.xorg_conf_path):
            if not has_proprietary:
                open(self.old_conf, 'w').write(open(OSLib.inst.xorg_conf_path).read())
        else:
            open(self.no_conf, 'w')
        
        relevant_devices = []
        
        if self.xorg_driver or self.extra_conf_options:
            if len(self.xorg_conf.globaldict['Device']) == 0:
                # Create a new Device section. "device" = position of the section
                device = self.xorg_conf.makeSection('Device', identifier='Default Device')
                relevant_devices.append(device)
                # Set the driver
                if self.xorg_driver:
                    self.xorg_conf.setDriver('Device', self.xorg_driver, device)
            else:
                # Get the relevant sections by checking the ServerLayout section
                # in case of multiple screens layouts or modify all the Device
                # sections
                devices = self.xorg_conf.getDevicesInUse()
                if len(devices) > 0:
                    relevant_devices = devices
                else:
                    relevant_devices = self.xorg_conf.globaldict['Device'].keys()
                if self.xorg_driver:
                    for device in relevant_devices:
                        self.xorg_conf.setDriver('Device', self.xorg_driver, device)
            logging.debug('XorgDriverHandler device sections (%s)' % (
                str(self.xorg_conf.globaldict['Device'])))
        
        module_sections = self.xorg_conf.globaldict['Module']
        have_modules = len(module_sections) > 0
        
        if have_modules:
            for section in module_sections:
                for mod in self.remove_modules:
                    self.xorg_conf.removeOption('Module', 'Load', value=mod, position=section)
        
        if self.add_modules:
            if not have_modules:
                module_section = self.xorg_conf.makeSection('Module')
            else:
                module_section = 0 #the 1st module section
            
            for mod in self.add_modules:
                if not self._mod_enabled(mod):
                    self.xorg_conf.addOption('Module', 'Load', mod, optiontype=None, position=module_section, reference=True)
        
        if self.disable_modules:
            for mod in self.disable_modules:
                if not self._mod_disabled(mod):
                    self.xorg_conf.addOption('Module', 'Disable', mod, optiontype=None, position=module_section, reference=True)
        
        for device_section in relevant_devices:
            for k, v in self.extra_conf_options.iteritems():
                self.xorg_conf.addOption('Device', k, v, optiontype='Option', position=device_section)
        
        self.enable_config_hook()
        
        self.xorg_conf.writeFile(OSLib.inst.xorg_conf_path)

        return False

    def disable(self):
        if not self.xorg_conf:
            logging.error('XorgDriverHandler.enable(): invalid xorg.conf, skipping')
            return False

        KernelModuleHandler.disable(self)

        # do not mangle xorg.conf if package uninstallation has been aborted
        if OSLib.inst.package_installed(self.package):
            return

        # if we previously didn't have an xorg.conf, delete it
        if os.path.exists(self.no_conf):
            logging.debug('XorgDriverHandler.disable(%s): previously had no xorg.conf, deleting xorg.conf', 
                    self.xorg_driver or self.package)
            os.unlink(self.no_conf)
            if os.path.exists(OSLib.inst.xorg_conf_path):
                os.unlink(OSLib.inst.xorg_conf_path)
            self.xorg_conf = XKit.xutils.XUtils()
        # if we have the previous xorg.conf, restore that
        elif os.path.exists(self.old_conf):
            logging.debug('XorgDriverHandler.disable(%s): restoring xorg.conf backup', 
                    self.xorg_driver or self.package)
            open(OSLib.inst.xorg_conf_path, 'w').write(open(self.old_conf).read())
            os.unlink(self.old_conf)
            self.xorg_conf = XKit.xutils.XUtils(OSLib.inst.xorg_conf_path)
        else: # no backup, so mangle current config manually
            logging.debug('XorgDriverHandler.disable(%s): missing xorg.conf, reversing changes from enable()',
                    self.xorg_driver or self.package)
            relevant_devices = []
            
            if len(self.xorg_conf.globaldict['Device']) > 0:
                devices = self.xorg_conf.getDevicesInUse()
                if len(devices) > 0:
                    relevant_devices = devices
                else:
                    relevant_devices.append(0)
                
                module_sections = self.xorg_conf.globaldict['Module']
        
                have_modules = len(module_sections) > 0
                
                if have_modules:
                    for section in module_sections:
                        for mod in self.add_modules:
                            self.xorg_conf.removeOption('Module', 'Load', value=mod, position=section)
                        
                        for mod in self.disable_modules:
                            self.xorg_conf.removeOption('Module', 'Disable', value=mod, position=section)
                
                if self.remove_modules:
                    if not have_modules:
                        module_section = self.xorg_conf.makeSection('Module')
                    else:
                        module_section = 0 #the 1st module section
                    
                    for mod in self.remove_modules:
                        if not self._mod_enabled(mod):
                            self.xorg_conf.addOption('Module', 'Load', mod,
                                optiontype=None, position=module_section,
                                reference=True)
                    
                for device_section in relevant_devices:
                    if self.alt_free_driver:
                        self.xorg_conf.setDriver('Device', self.alt_free_driver, device_section)
                    
                    for k, v in self.extra_conf_options.iteritems():
                        self.xorg_conf.removeOption('Device', k, v, position=device_section)
                
            self.disable_config_hook()

            logging.debug('XorgDriverHandler.disable(%s): writing restored xorg.conf', 
                    self.xorg_driver or self.package)
            self.xorg_conf.writeFile(OSLib.inst.xorg_conf_path)
 
        return False

    def enable_config_hook(self):
        '''Custom self.xorg_config changes after driver, modules, and extra
        driver options have been changed.
        '''
        pass

    def disable_config_hook(self):
        '''Custom self.xorg_config changes after driver, modules, and extra
        driver options have been changed.
        '''
        pass

    def enables_composite(self):
        '''Return whether this driver enables the composite extension.
        
        Note that this is true if and only if the current driver does *not*
        support composite, but this driver does.'''

        return False

