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

'''Define some common abstract basic handler types.

These provide the common functionality for concrete handlers of different
classes, like handlers for a kernel module, a driver package, a handler group,
etc.

Custom concrete handlers need to fulfill the following requirements:
 - __init__(self, backend) must take exactly one argument (a reference to a
   Backend instance). All othe properties must be detected by the
   constructor or changed with methods. These classes are instantiated
   automatically, which is not possible with constructors which need more
   arguments.

 - All handler types in this module have some abstract functions which need to
   be implemented (see the documentation of the particular classes).
'''

import subprocess, os.path, sys, logging
from gettext import gettext as _

import detection
from jockey.oslib import OSLib

#--------------------------------------------------------------------#

class Handler:
    '''Abstract basic handler.'''

    def __init__(self, backend, name, description=None, rationale=None):
        '''Create a handler with given (human readable) name.
        
        Every handler should have a human readable name. A custom rationale and
        a multi-line description can be given, too. Every handler gets a
        reference to the currently used Backend so that it can request
        installation of packages and other system changes.

        By default, available handlers are announced in
        AbstractUI.check(). If you want to have a handler which is
        available, but not announced that way, set self.annonuce to False.

        If a handler needs to build a kernel module from source, it should set
        self.needs_kernel_headers to True. Then the handler will try to install
        the matching kernel header package for the currently running kernel.
        (See OSLib.kernel_header_package).
        '''
        self._hwids = [] # covered HardwareIDs
        self._changed = False
        self.backend = backend

        self._name = name
        self._description = description
        self._rationale = rationale
        self.license = None
        self.announce = True
        self.needs_kernel_headers = False

        # the following properties are not specified in the ctor, since they
        # might be changed after instantiation;
        # subclass ctors might set that before calling us
        if not hasattr(self, '_free'):
            self._free = None
        if hasattr(self, 'package') and self.package:
            self._package_defaults()
        else:
            self.package = None
        self.driver_vendor = None
        self.version = None
        self.repository = None
        self.repository_sign_fp = None
        self._recommended = False
        self._auto_install = False

    def _package_defaults(self):
        '''Set fallback name/description/freeness from package.'''

        if self.package and (not self._name or self._description is None):
            (distro_name, distro_desc) = OSLib.inst.package_description(self.package)
            if not self._name:
                self._name = distro_name
            if self._description is None:
                self._description = distro_desc
        if self.package and self._free is None:
            try:
                self._free = OSLib.inst.is_package_free(self.package)
            except (KeyError, ValueError):
                # we cannot determine it right now
                pass

    def name(self):
        '''Return one-line name of the handler (for human consumption).'''

        self._package_defaults()
        return self._name

    def description(self):
        '''Return multi-line description of the handler.'''

        self._package_defaults()
        return self._description

    def id(self):
        '''Return an unique identifier of the handler.

        This is used for specifying a handler with --enable/--disable on the
        command line, and is mentioned in the --list output.
        '''
        if self.package:
            i = 'pkg:' + self.package
        else:
            i = '%s:%s' % (str(self.__class__).split('.')[-1], self.name())
        if self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def rationale(self):
        '''Return rationale as to why this driver might be enabled.
        
        Might return None if no rationale is available.
        '''
        return self._rationale

    def changed(self):
        '''Return if the module has been enabled/disabled at least once.'''

        return self._changed

    #
    # The following methods can be specialized in subclasses
    # 

    def can_change(self):
        '''Check whether we can actually modify settings of this handler.

        This might not be the case if e. g. the user manually modified a
        configuration file. Return an explanatory text if settings can not be
        changed, or None if changing is ok.
        '''
        return None

    def __str__(self):
        return '%s([%s, %s, %s] %s)' % (
            self.id(),
            str(self.__class__).split('.')[-1],
            self.free() and 'free' or 'nonfree',
            self.enabled() and 'enabled' or 'disabled',
            self.name())

    #
    # The following methods must be implemented in subclasses
    # 

    def free(self):
        '''Return if the handler represents a free software driver.'''

        if self._free is not None:
            return self._free
        else:
            raise NotImplementedError('subclasses need to implement this')

    def auto_install(self):
        '''Return if the handler should be automatically installed.

        This can be done by hardcoding self._auto_install = True, but the
        recommended approach is to create a flag file
        <handler_dir>/autoinstall.d/<driver id>, because that is easier to
        customize.
        '''
        if self._auto_install:
            return True

        # check autoinstall.d/ flag
        if os.path.exists(os.path.join(OSLib.inst.handler_dir, 'autoinstall.d', self.id())):
            return True

        return False

    def enabled(self):
        '''Return if the handler is enabled.
        
        'Enabled' means that the user agreed to use this driver if it is
        applicable.
        '''
        if self.package:
            return OSLib.inst.package_installed(self.package)
        else:
            return True

    def used(self):
        '''Return if the handler is currently in use.'''

        raise NotImplementedError('subclasses need to implement this')

    def recommended(self):
        '''Return if the version of a certain driver is recommended over others
        when more than one driver flavour supports the same device.
        
        This method should return True only for the recommended version while
        it will return False for any other compatible version. If only one
        version of a driver is provided, then it should return False.
        '''
        return self._recommended
    
    def available(self):
        '''Return if the conditions to use this handler on the system are met.

        This usually means that the hardware for this driver is available, but
        there might be hardware independent drivers, too.
        
        If this returns True or False, the answer is definitive and no further
        detection, db querying, etc is performed. If this returns None, then
        the handler cannot decide availability on its own; in that case it is
        merely available in the handler pool, and an external driver database
        (detection.DriverDB) is queried.
        '''
        if self.package:
            if not self.repository or OSLib.inst.repository_enabled(self.repository):
                try:
                    OSLib.inst.package_description(self.package)
                    return None
                except ValueError:
                    return False
            else:
                return None # undecidable until the repo is added
        else:
            raise NotImplementedError('subclasses need to implement this')

    def enable(self):
        '''Allow the OS to use it if the hardware is available.
        
        If possible, the handler should be loaded, too. Return True if
        immediately successful, or False if the system needs to be rebooted for
        the changes to become effective.
        '''
        # first ensure that the kernel header packages are installed, if
        # requested
        if self.needs_kernel_headers and OSLib.inst.kernel_header_package:
            try:
                self.backend.install_package(OSLib.inst.kernel_header_package)
            except ValueError:
                # package not available; most likely we have a custom kernel?
                logging.error('enabling %s: Unable to install kernel header package %s',
                        self.id(), OSLib.inst.kernel_header_package)
                pass

        if self.package:
            self.backend.install_package(self.package, self.repository,
                    self.repository_sign_fp)
            if not OSLib.inst.package_installed(self.package):
                # do not touch _changed if package failed to install
                return True
        # packages might install/remove blacklists
        OSLib.inst._load_module_blacklist()
        self._changed = True
        return True

    def disable(self):
        '''Prevent the OS from using it even if the hardware is available.

        If possible, the handler should be unloaded, too. Return True if
        immediately successful, or False if the system needs to be rebooted for
        the changes to become effective.
        '''
        if self.package:
            self.backend.remove_package(self.package)
            if OSLib.inst.package_installed(self.package):
                # do not touch _changed if package failed to remove
                return
        self._changed = True

        return True

#--------------------------------------------------------------------#

class HandlerGroup(Handler):
    '''Perform operations on a group of handlers.

    A group should be provided if it makes little sense to present several very
    similar handlers in the UI. For example, the three VMWare or the dozens of
    commercial OSS drivers should be grouped.
    '''
    def __init__(self, backend, name, id, description=None, rationale=None):
        Handler.__init__(self, backend, name, description, rationale)
        self._id = id
        self.subhandlers = []

    def id(self):
        '''Return an unique identifier of the handler.'''

        return self._id

    def add(self, handler):
        '''Add a subhandler.'''

        self.subhandlers.append(handler)

    def free(self):
        '''Return if all subhandlers represent free software drivers.'''

        for h in self.subhandlers:
            if not h.free():
                return False

        return True

    def enabled(self):
        '''Return if all subhandlers are enabled.'''

        for h in self.subhandlers:
            if not h.enabled():
                return False

        return True

    def used(self):
        '''Return if any subhandler is used.'''

        for h in self.subhandlers:
            if h.used():
                return True

        return False

    def available(self):
        '''Return if the hardware for any subhandler is available.
        
        If all subhandlers return False, this returns False. If any subhandler
        returns True, this returns True. Otherwise this returns None.
        '''
        all_false = True

        for h in self.subhandlers:
            a = h.available()
            if a:
                return True
            if a == None:
                all_false = False
            else:
                assert a == False

        if all_false:
            return False
        else:
            return None

    def enable(self):
        '''Enable all subhandlers.'''

        result = True
        for h in self.subhandlers:
            result = h.enable() and result
        return result

    def disable(self):
        '''Disable all subhandlers.'''

        result = True
        for h in self.subhandlers:
            result = h.disable() and result
        return result

    def changed(self):
        '''Return if at least one subhandler has been enabled/disabled at
        least once.'''

        for h in self.subhandlers:
            if h.changed():
                return True

        return False

    def can_change(self):
        '''Check whether we can actually modify settings of this handler.'''

        assert self.subhandlers

        for h in self.subhandlers:
            c = h.can_change()
            if c:
                return c

        return None

#--------------------------------------------------------------------#

class KernelModuleHandler(Handler):
    '''Handler for a kernel module.
    
    This class can be used as a standard handler for kernel modules (and in
    fact detection.get_handlers() uses this as a default handler if there is no
    custom one). Subclasses have to implement __init__() at least.
    '''
    _loaded_modules = None
    
    def __init__(self, backend, kernel_module, name=None, description=None, rationale=None,
                 do_blacklist=True):
        '''Create handler for a kernel module.
        
        If not given explicitly, the name is read from modinfo's 'description'
        field.
        '''
        self.module = kernel_module
        self.do_blacklist = do_blacklist
        self._modinfo = detection.get_modinfo(self.module)
        if not name:
            assert self._modinfo, 'kernel module %s exists' % self.module
            name = '\n'.join(self._modinfo.get('description', [self.module]))
        Handler.__init__(self, backend, name, description, rationale)
        self._do_rebind = True

    def id(self):
        '''Return an unique identifier of the handler.'''

        i = 'kmod:' + self.module
        if self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def free(self):
        '''Return if the handler represents a free software driver.'''

        # this function needs to be kept in sync with the kernel function
        # is_license_gpl_compatible()

        if self._free is not None:
            return self._free

        assert self._modinfo, 'kernel module %s exists' % self.module
        for l in self._modinfo.get('license', ['unknown']):
            if l in ('GPL', 'GPL v2', 'GPL and additional rights', 
                'Dual BSD/GPL', 'Dual MIT/GPL', 'Dual MPL/GPL', 'BSD'):
                return True
        return False

    def enabled(self):
        '''Return if the handler is enabled.
        
        'Enabled' means that the user agreed to use this driver if it is
        applicable.
        '''
        return not OSLib.inst.module_blacklisted(self.module) and \
            (self._modinfo is not None) and Handler.enabled(self)

    def used(self):
        '''Return if the handler is currently in use.'''

        return self.module_loaded(self.module) and (self.package is None or
            OSLib.inst.package_installed(self.package))

    def available(self):
        '''Return if the conditions to use this handler on the system are met
        (e. g. hardware for this driver is available).

        This defaults to None, because we usually want to delegate this to the
        driver db. Subclasses are welcome to override this, of course.
        '''
        # check for unavailable package, etc.
        try:
            if Handler.available(self) == False:
                return False
        except NotImplementedError:
            pass
        return None

    def enable(self):
        '''Allow the OS to use it if the hardware is available.
        
        This removes the module from the modprobe blacklist.
        '''
        Handler.enable(self)
        OSLib.inst.blacklist_module(self.module, False)
        subprocess.call([OSLib.inst.modprobe_path, self.module])
        self._modinfo = detection.get_modinfo(self.module)
        self.read_loaded_modules()
        if self._do_rebind:
            return self.rebind(self.module)

    def disable(self):
        '''Prevent the OS from using it even if the hardware is available.

        This adds the module to the modprobe blacklist.
        '''
        Handler.disable(self)
        if self.do_blacklist:
            OSLib.inst.blacklist_module(self.module, True)
        self._modinfo = detection.get_modinfo(self.module)
        return False # TODO: can we make this automatic?

    @classmethod
    def rebind(klass, module):
        '''Re-bind all devices using the module.
        
        This is necessary for example to reload firmware. Return True on
        success, or False if rebind failed for any device.
        '''
        drivers_dir = os.path.join(OSLib.inst.sys_dir, 'module', module, 'drivers')
        if not os.path.isdir(drivers_dir):
            logging.warning('%s does not exist, cannot rebind %s driver' % (
                drivers_dir, module))
            return

        succeeded = True

        for driver in os.listdir(drivers_dir):
            driver_path = os.path.join(drivers_dir, driver)
            for device in os.listdir(driver_path):
                # only consider subdirs which are not called 'module'
                if device == 'module' or not os.path.isdir(
                    os.path.join(driver_path, device)):
                    continue
                try:
                    logging.debug('unbind/rebind on driver %s: device %s', driver_path, device)
                    f = open(os.path.join(driver_path, 'unbind'), 'w')
                    f.write(device)
                    f.close()
                    f = open(os.path.join(driver_path, 'bind'), 'w')
                    f.write(device)
                    f.close()
                except IOError:
                    logging.warning('unbind/rebind for device %s on driver %s failed', 
                        device, driver_path, exc_info=True)
                    succeeded = False

        return succeeded

    @classmethod
    def read_loaded_modules(klass):
        '''Get the list of loaded kernel modules.'''

        klass._loaded_modules = []

        proc_modules = open(OSLib.inst.proc_modules)
        try:
            for line in proc_modules:
                try:
                    line = line[:line.index(' ')]
                except ValueError:
                    pass

                klass._loaded_modules.append(line.strip())
        finally:
            proc_modules.close()

    @classmethod
    def module_loaded(klass, module):
        '''Return if a module is currently loaded.'''

        if klass._loaded_modules == None:
            klass.read_loaded_modules()

        return module in klass._loaded_modules

#--------------------------------------------------------------------#

class FirmwareHandler(KernelModuleHandler):
    '''Handler for an already available kernel module needing firmware.

    Subclasses need to extend enable() and implement disable() to do something
    with the downloaded file (unpack it, put into the right directory, etc.).
    This class' enable() function will deal with downloading it and the UI
    progress reporting of the download.
    '''
    def __init__(self, backend, kernel_module, testfile, name=None, description=None, 
            rationale=None, url=None, sha1sum=None, free=False):
        '''Create handler for a piece of firmware for a kernel module.
        
        The required argument 'url' specifies where the firmware can be
        downloaded from. The optional 'sha1sum' argument provides a checksum of
        the downloaded file. The file will not be installed if it does not
        match.

        enabled() will return True iff the path in testfile exists.

        By default this handler assumes that the firmware is not free (since
        otherwise the distribution could ship it together with the driver). You
        can set 'free' to True for free firmware or to None to use the kernel
        module's freeness.
    
        If not given explicitly, the name is read from modinfo's 'description'
        field.
        '''
        self.url = url
        self.sha1sum = sha1sum
        self._free = free
        self.testfile = testfile

        KernelModuleHandler.__init__(self, backend, kernel_module, name,
            description, rationale)

    def id(self):
        '''Return an unique identifier of the handler.'''

        i = 'firmware:' + self.module
        if self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def free(self):
        '''Return if the handler represents a free software driver.'''

        if self._free is None:
            return KernelModuleHandler.free(self)
        return self._free

    def enabled(self):
        '''Return if the handler is enabled.
        
        'Enabled' means that the user agreed to use this driver if it is
        applicable.
        '''
        return os.path.exists(self.testfile) and KernelModuleHandler.enabled(self)

    def used(self):
        '''Return if the handler is currently in use.'''

        return self.enabled() and KernelModuleHandler.used(self)

    def enable(self):
        '''Allow the OS to use it if the hardware is available.
        
        This downloads the url and puts it into self.firmware_file. Subclasses
        need to provide an actual implementation what to do with the file.
        '''
        raise NotImplementedError('FirmwareHandler is currently not implemented')
        #self.firmware_file = self.ui.download_url(self.url)[0]
        #if not self.firmware_file:
        #    return

        # TODO: sha1sum check

        KernelModuleHandler.enable(self)

    def disable(self):
        '''Prevent the OS from using it even if the hardware is available.
        
        Implementation in subclasses need to remove the firmware files and call
        KernelModuleHandler.disable().
        '''
        raise NotImplementedError('subclasses need to implement this')

#--------------------------------------------------------------------#

class PrinterDriverHandler(Handler):
    '''Handler for a printer driver.'''

    def id(self):
        '''Return an unique identifier of the handler.

        This is used for specifying a handler with --enable/--disable on the
        command line, and is mentioned in the --list output.
        '''
        if self.package:
            i = 'printer:' + self.package
        else:
            i = 'printer:%s' % self.name()
        if self.version:
            i += ':' + str(self.version)
        elif self.driver_vendor:
            i += ':' + self.driver_vendor.replace(' ', '_')
        return i

    def used(self):
        '''Return if the handler is currently in use.'''

        # TODO: query cups for actually using the driver
        return self.enabled()

class HWEHandler(Handler):
    '''Handler for general hardware enablement.
    
    This is for general quirks which aren't kernel modules. This uses aliases
    in a fashion similar to KernelModuleHandler, but ties directly to package
    names instead.
    '''
    def __init__(self, backend, package):
        self.package = package
        Handler.__init__(self, backend, '')

    def used(self):
        return self.enabled()

