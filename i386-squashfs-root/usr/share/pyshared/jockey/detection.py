# -*- coding: UTF-8 -*-

'''Check the hardware and software environment on the computer for available
devices, query the driver database, and generate a set of handlers.

The central function is get_handlers() which checks the system for available
hardware and, if given a driver database, queries that about updates and
unknown hardware.
'''

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

import os, os.path, subprocess, sys, logging, re, locale
from glob import glob
# prefer Python 2 module here, as in Python 2 io.StringIO is broken
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

try:
    from xmlrpc.client import ServerProxy
    import pickle
except ImportError:
    import cPickle as pickle
    from xmlrpclib import ServerProxy
    import pycurl

from jockey.oslib import OSLib
import handlers, xorg_driver

#--------------------------------------------------------------------#

class HardwareID:
    '''A piece of hardware is denoted by an identification type and value.

    The most common identification type is a 'modalias', but in the future we
    might support other types (such as bus/vendorid/productid, printer
    device ID, etc.).
    '''
    _recache = {}

    def __init__(self, type, id):
        self.type = type
        self.id = id

    def __repr__(self):
        return "HardwareID('%s', '%s')" % (self.type, self.id)

    def __eq__(self, other):
        if type(self) != type(other) or self.type != other.type:
            return False

        if self.type != 'modalias':
            return self.id == other.id

        # modalias pattern matching
        if '*' in self.id:
            # if used as dictionary keys we do need to compare two patterns; in
            # that case they should just be tested for string equality
            if '*' in other.id:
                return self.id == other.id
            else:
                return self.regex(self.id).match(other.id)
        else:
            if '*' in other.id:
                return self.regex(other.id).match(self.id)
            else:
                return self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # This is far from efficient, but we usually have a very small number
        # of handlers, so it doesn't matter.

        if self.type == 'modalias':
            # since we might have patterns, we cannot rely on hash identidy of
            # id
            return hash(self.type) ^ hash(self.id[:self.id.find(':')])
        else:
            return hash(self.type) ^ hash(self.id)

    @classmethod
    def regex(klass, pattern):
        '''Convert modalias pattern to a regular expression.'''

        r = klass._recache.get(pattern)
        if not r:
            r = re.compile(re.escape(pattern).replace('\\*', '.*') + '$')
            klass._recache[pattern] = r
        return r

#--------------------------------------------------------------------#

class DriverID:
    '''Driver database entry describing a driver.
    
    This consists of a set of (type, value) pairs, the semantics of which can
    be defined and used freely for every distribution. A few conventional
    standard types exist:
    
    - driver_type: 'kernel_module' | 'printer_driver' | ... [required]
    - description: locale → string (human-readable single-line) [required]
    - long_description: locale → string (human-readable paragraph) [optional]
    - driver_vendor: very short string, requirements as in pci.ids [required]
    - version: string, arbitrary differentiation [optional]
    - jockey_handler: class name (inferred from driver_type for standard handlers) [optional]
    - repository: URL [optional]
    - fingerprint: GPG fingerprint of repository [for binary packages, if repository is present]
    - package: string [optional]
    - free: boolean (licensed as free software) [required]
    - license: string (license text) [required if free is False]
    '''
    def __init__(self, **properties):
        self.properties = properties

    def __getitem__(self, key):
        return self.properties.__getitem__(key)

    def __contains__(self, key):
        return self.properties.__contains__(key)

    def __setitem__(self, key, value):
        self.properties.__setitem__(key, value)

    def __str__(self):
        return str(self.properties)

#--------------------------------------------------------------------#

class DriverDB:
    '''Interface definition for a driver database.
    
       This maps a HWIdentifier to a list of DriverID instances (sorted by
       preference) which match the OS version.

       Initialization of a DriverDB should be relatively cheap. For DBs
       querying remote services this means that they should not do remote
       operations in __init__() and query(), only in update().

       This base class also provides caching infrastructure.
       '''

    def __init__(self, use_cache=False):
        '''Initialize the DriverDB.
        
        This also initializes the cache if caching is used.
        '''
        self.use_cache = use_cache
        self.cache = None
        if self.use_cache:
            assert self._cache_id()
            self.cache_path = os.path.join(OSLib.inst.backup_dir,
                'driverdb-%s.cache' % self._cache_id())
            try:
                self.cache = pickle.load(open(self.cache_path, 'rb'))
            except (pickle.PickleError, IOError) as e:
                logging.warning('Could not open DriverDB cache %s: %s',
                    self.cache_path, str(e))
                self.cache = None

    def query(self, hwid):
        '''Return a set or list of applicable DriverIDs for a HardwareID.
        
        This uses the cache, if available, and otherwise calls _do_query().
        '''
        if self.use_cache and self.cache is not None:
            return self.cache.get(hwid, [])

        return self._do_query(hwid)

    def update(self, hwids):
        '''Query remote server for driver updates for a set of HardwareIDs.

        This is a no-op for local-only driver databases. For remote ones, this
        is the only method which should actually do network operations.
        When enabling caching in __init__, this takes care of writing the
        cache.
        '''
        logging.debug('updating %s', self)
        self._do_update(hwids)

        # write cache
        if self.use_cache:
            try:
                f = open(self.cache_path, 'wb')
                pickle.dump(self.cache, f)
                f.close()
            except (pickle.PickleError, IOError) as e:
                logging.warning('Could not create DriverDB cache %s: %s',
                    self.cache_path, str(e))

    #
    # The following methods must be implemented in subclasses
    # 

    def _cache_id(self):
        '''Get the cache ID for this DriverDB.

        If the driver DB implementation uses disk caching, it needs to define
        an unique ID for the cache file name. For parameterized DBs (such as a
        remote DB with a particular URL), those parameters must be included
        into the cache ID.
        
        By default this returns the classname, which is appropriate for
        singleton DriverDBs.
        '''
        return str(self.__class__).split('.')[-1]

    def _do_query(self, hwid):
        '''Return a set or list of applicable DriverIDs for a HardwareID.

        This should not be called directly. Users call query() which wraps this
        function into caching.
        '''
        raise NotImplementedError('subclasses need to implement this')

    def _do_update(self, hwids):
        '''Query remote server for driver updates for a set of HardwareIDs.

        This should not be called directly. Users call update() which wraps this
        function into caching.

        This is a no-op for local-only driver databases. For remote ones, this
        is the only method which should actually do network operations.
        When enabling caching in __init__, implementations need to write the
        detected hardware->driver mapping into self.cache (mapping HardwareID
        to a set/list of DriverIDs).
        '''
        pass

#--------------------------------------------------------------------#

class LocalKernelModulesDriverDB(DriverDB):
    '''DriverDB implementation for kernel modules which are already available
    in the system.
    
    This evaluates modalias lists and overrides (such as /lib/modules/<kernel
    version>/modules.alias and other alias files/directories specified in
    OSLib.modaliases) to map modaliases in /sys to kernel modules and wrapping
    them into a KernelModuleHandler.
    
    As an addition to the 'alias' lines in modalias files, you can also specify
    lines "reset <module>" which will cause the current modalias mapping that
    was built up to that point to be discarded. Since modaliases are evaluated
    in the order they appear in OSLib.modaliases, this can be used to disable
    wrong upstream modaliases (like the ones from the proprietary NVIDIA
    graphics driver).
    '''
    def __init__(self):
        '''Initialize self.alias_cache.
        
        This maps bus → vendor → modalias → [module].
        '''
        # TODO: check if caching is beneficial
        DriverDB.__init__(self, use_cache=False)
        self.update({})

    def _do_update(self, hwids):
        # bus -> vendor -> alias -> [(module, package)]; vendor == None -> no vendor,
        # or vendor patterns, needs fnmatching
        self.alias_cache = {} 
        # patterns for which we can optimize lookup
        self.vendor_pattern_re = re.compile('(pci|usb):v([0-9A-F]{4,8})(?:d|p)')

        # first, read stuff from package headers
        # structure: package_name -> module_name -> [list of modaliases]
        for pkg, ma_map in OSLib.inst.package_header_modaliases().iteritems():
            for module, aliases in ma_map.iteritems():
                for alias in aliases:
                    vp = self.vendor_pattern_re.match(alias)
                    if vp:
                        self.alias_cache.setdefault(vp.group(1), {}).setdefault(
                            vp.group(2), {}).setdefault(alias, []).append((module, pkg))
                    else:
                        colon = alias.find(':')
                        if colon > 0:
                            bus = alias[:colon]
                        else:
                            bus = None
                        self.alias_cache.setdefault(bus, {}).setdefault(
                            None, {}).setdefault(alias, []).append((module, pkg))

        # local modalias lists override package header information
        for alias_location in OSLib.inst.modaliases:
            if not os.path.exists(alias_location):
                continue
            if os.path.isdir(alias_location):
                alias_files = [os.path.join(alias_location, f) 
                    for f in sorted(os.listdir(alias_location))]
            else:
                alias_files = [alias_location]

            for alias_file in alias_files:
                logging.debug('reading modalias file ' + alias_file)
                for line in open(alias_file):
                    fields = line.split()
                    try:
                        (c, a, m, p) = fields
                    except ValueError:
                        p = None
                        try:
                            (c, a, m) = fields
                        except ValueError:
                            try:
                                (c, m) = line.split()
                                a = None
                            except ValueError:
                                continue

                    if c == 'alias' and a:
                        vp = self.vendor_pattern_re.match(a)
                        if vp:
                            self.alias_cache.setdefault(vp.group(1), {}).setdefault(
                                vp.group(2), {}).setdefault(a, []).append((m, p))
                        else:
                            colon = a.find(':')
                            if colon > 0:
                                bus = a[:colon]
                            else:
                                bus = None
                            self.alias_cache.setdefault(bus, {}).setdefault(
                                None, {}).setdefault(a, []).append((m, p))
                    elif c == 'reset':
                        for map in self.alias_cache.itervalues():
                            for vmap in map.itervalues():
                                for k, mods in vmap.iteritems():
                                    for i in range(len(mods)):
                                        if mods[i][0] == m:
                                            mods.pop(i)
                                            break

            #for bus, inf in self.alias_cache.iteritems():
            #    print '*********', bus, '*************'
            #    for vendor, alias in inf.iteritems():
            #        print '#', vendor, ':', alias

    def _do_query(self, hwid):
        '''Return a list of applicable DriverIDs for a HardwareID.'''

        if hwid.type != 'modalias' or ':' not in hwid.id:
            return []

        # we can't build large dictionaries with HardwareID as keys, that's too
        # inefficient; thus we have to do some more clever matching and data
        # structure

        # TODO: we return all matching handlers here, which is
        # confusing; picking the first one is too arbitrary, though;
        # find a good heuristics for returning the best one

        result = []

        # look up vendor patterns
        m = self.vendor_pattern_re.match(hwid.id)
        if m:
            bus = m.group(1)
            for a, mods in self.alias_cache.get(bus, {}).get(m.group(2), {}).iteritems():
                if mods and HardwareID('modalias', a) == hwid:
                    for (m, p) in mods:
                        did = DriverID(driver_type='kernel_module', kernel_module=m)
                        if p:
                            if m == 'hwe':
                                did.properties.pop('kernel_module')
                                did.properties['driver_type'] = 'hwe'
                            did.properties['package'] = p
                        result.append(did)
        else:
            bus = hwid.id[:hwid.id.index(':')]

        # look up the remaining ones
        for a, mods in self.alias_cache.get(bus, {}).get(None, {}).iteritems():
            if mods and HardwareID('modalias', a) == hwid:
                for (m, p) in mods:
                    did = DriverID(driver_type='kernel_module', kernel_module=m)
                    if p:
                        if m == 'hwe':
                            did.properties.pop('kernel_module')
                            did.properties['driver_type'] = 'hwe'                        
                        did.properties['package'] = p
                    result.append(did)

        return result

#--------------------------------------------------------------------#

class XMLRPCDriverDB(DriverDB):
    '''DriverDB implementation for a remote XML-RPC server.

    This implements XML-RPC DriverDB protocol version 20080407:

    query: (protocol_version, protocol_subversion, query_data) →
      (protocol_version, protocol_subversion, HardwareID → DriverID*])
    
    HardwareID: hwid_type ':' hwid_value
    hwid_type: 'modalias' | 'printer_deviceid'
    hwid_value: string (modalias value, printer device ID, etc.)
    DriverID: property → value
    
    Example:
    query('20080407', '0', {
            'components': ['modalias:pci:crap', 'printer:Canon_BJ2'],
            'system_vendor': 'Dell',
            'system_product': 'Latitude D430',
            'os_name': 'RedSock',
            'os_version': '2.0',
            'kernel_ver': '2.6.24-15-generic',
            'architecture': 'i686'}) =
      ('20080407', '0', {'modalias:pci:crap': [dr_crap1, dr_crap2], 'printer:Canon_BJ2': [dr_pr1]})

    where dr_* are DriverID property dictionaries.
    '''
    def __init__(self, url):
        '''Create XML-RPC Driver DB instance for a given server URL.'''

        self.url = url
        DriverDB.__init__(self, use_cache=True)
        (self.sys_vendor, self.sys_product) = OSLib.inst.get_system_vendor_product()

    def _cache_id(self):
        # chop off protocol from URL, and remove slashes
        u = self.url
        pos = u.find('://')
        if pos >= 0:
            u = u[(pos+3):]
        u = u.replace('/', '_')

        return DriverDB._cache_id(self) + '@' + u

    def _do_query(self, hwid):
        '''Return a set or list of applicable DriverIDs for a HardwareID.'''

        # we only get here if we haven't update()d, since after that the cache
        # does its magic
        return []

    def _do_update(self, hwids):
        '''Query remote server for driver updates for a set of HardwareIDs.'''

        logging.debug('Querying XML-RPC driver database %s...', self.url)
        client = ServerProxy(self.url)
        # TODO: error handling; pass kernel_version, architecture
        (res_proto_ver, res_proto_subver, drivers) = client.query(
            '20080407', '0', { 
            'os_name': OSLib.inst.os_vendor,
            'os_version': OSLib.inst.os_version, 
            'system_vendor': self.sys_vendor,
            'system_product': self.sys_product,
            'components': ['%s:%s' % (h.type, h.id) for h in hwids]
            })
        logging.debug('  -> protocol: %s/%s, drivers: %s', res_proto_ver,
            res_proto_subver, str(drivers))

        self.cache = {}
        if res_proto_ver != '20080407':
            logging.warning('   unknown protocol version, not updating')
            return

        for hwid in hwids:
            for drv in drivers.get('%s:%s' % (hwid.type, hwid.id), []):
                if 'driver_type' not in drv:
                    continue
                self.cache.setdefault(hwid, []).append(DriverID(**drv))

#--------------------------------------------------------------------#

class OpenPrintingDriverDB(DriverDB):
    '''DriverDB for openprinting.org printer drivers.'''

    def __init__(self):
            DriverDB.__init__(self, use_cache=True)

    def _do_query(self, hwid):
        '''Return a set or list of applicable DriverIDs for a HardwareID.'''

        # we only get here if we haven't update()d, since after that the cache
        # does its magic
        return []

    def _do_update(self, hwids):
        '''Query remote server for driver updates for a set of HardwareIDs.'''

        # map OSLib.packaging_system() strings to OpenPrinting.org
        # "packagesystem" arguments
        pkg_system_map = {
            'apt': 'deb',
            'yum': 'rpm',
            'urpmi': 'rpm',
        }

        pkgsystem = OSLib.inst.packaging_system()
        try:
            opo_pkgsystem = pkg_system_map[pkgsystem]
        except KeyError:
            logging.warning('cannot map local packaging system to an OpenPrinting.org supported one')
            return

        try:
            import cupshelpers
        except ImportError:
            logging.warning('cupshelpers Python module is not present; openprinting.org query is not available')
            return

        def _pkgname_from_fname(pkgname):
            '''Extract package name from a package file name.'''

            if pkgname.endswith('.deb'):
                return pkgname.split('_')[0]
            elif pkgname.endswith('.rpm'):
                return '-'.join(pkgname.split('-')[0:-2])
            else:
                raise ValueError('Unknown package type: ' + pkgname)

        def _ld_callback(status, drv_list, data):
            if status != 0:
                logging.error('  openprinting.org query failed: %s', str(data))
                return

            for driver, info in data.iteritems():
                info_shortlicense = info.copy()
                if 'licensetext' in info_shortlicense:
                    info_shortlicense['licensetext'] = info_shortlicense['licensetext'][:20] + '..'
                logging.debug('OpenPrintingDriverDB: driver %s info: %s',
                    driver, str(info_shortlicense))
                pkgs = info.get('packages', {})
                arches = pkgs.keys()
                if len(arches) == 0:
                    logging.debug('No packages for ' + info['name'])
                    continue
                if len(arches) > 1:
                    logging.error('Returned more than one matching architecture, please report this as a bug: %s', str(arches))
                    continue

                pkgs = pkgs[arches[0]]

                if len(pkgs) != 1:
                    logging.error('Returned more than one package, this is currently not handled')
                    return
                pkg = pkgs.keys()[0]

                # require signature for binary packages; architecture
                # independent packages are usually PPDs, which we trust enough
                fingerprint = None
                if arches[0] not in ['all', 'noarch']: 
                    if 'fingerprint' not in pkgs[pkg]:
                        logging.debug('Ignoring driver as it does not have a GPG fingerprint URL')
                        continue
                    fingerprint = download_gpg_fingerprint(pkgs[pkg]['fingerprint'])
                    if not fingerprint:
                        logging.debug('Ignoring driver as it does not have a valid GPG fingerprint')
                        continue

                repo = pkgs[pkg].get('repositories', {}).get(pkgsystem)
                if not repo:
                    logging.error('Local package system %s not found in %s',
                        pkgsystem, pkgs[pkg].get('repositories', {}))
                    return

                desc = info.get('shortdescription',
                    info['name']).replace('<b>', '').replace('</b>',
                    '').replace('<br>', ' ')

                did = DriverID(driver_type='printer_driver',
                    description={'C': desc},
                    driver_vendor=info.get('supplier', 'openprinting.org').replace(' ', '_'),
                    free=info.get('freesoftware', False),
                    package=_pkgname_from_fname(pkg),
                    repository=repo,
                    recommended=info.get('recommended', False),
                )
                desc = ''
                if 'functionality' in info:
                    desc = 'Functionality:'
                    for f, percent in info['functionality'].iteritems():
                        desc += '\n  %s: %s%%' % (f, percent)
                    desc += '\n'
                if 'supplier' in info:
                    desc += 'Supplied by: ' + info['supplier']
                    if info.get('manufacturersupplied'):
                        desc += ' (printer manufacturer)'
                    desc += '\n'
                if 'supportcontacts' in info:
                    desc += 'Support contacts:\n'
                    for s in info['supportcontacts']:
                        desc += ' - %s (%s): %s' % (s['name'],
                            s.get('level', 'voluntary'), s['url'])
                did.properties['long_description'] = {'C': desc}

                if 'version' in pkgs[pkg]:
                    did.properties['version'] = pkgs[pkg]['version']

                if fingerprint:
                    did.properties['fingerprint'] = fingerprint

                logging.debug('Created DriverID: ' + str(did.properties))

                if 'licensetext' in info:
                    did.properties['license'] = info['licensetext']

                drv_list.append(did)

        logging.debug('Querying openprinting.org database...')
        self.cache = {}
        op = cupshelpers.openprinting.OpenPrinting()
        op.onlyfree = 0

        # fire searches for all detected printers
        threads = []
        for hwid in hwids:
            if hwid.type != 'printer_deviceid':
                continue
            logging.debug('   ... querying for %s', hwid.id)
            t = op.listDrivers(hwid.id, _ld_callback,
                self.cache.setdefault(hwid, []), 
                extra_options={'packagesystem': opo_pkgsystem})
            threads.append(t)

        # wait until all threads have finished
        for t in threads:
            t.join()
        logging.debug('openprinting.org database query finished')

#--------------------------------------------------------------------#
# internal helper functions

def _get_modaliases():
    '''Return a set of modalias HardwareIDs for available hardware.'''

    if _get_modaliases.cache:
        return _get_modaliases.cache

    hw = set()
    for path, dirs, files in os.walk(os.path.join(OSLib.inst.sys_dir, 'devices')):
        modalias = None

        # most devices have modalias files
        if 'modalias' in files:
            modalias = open(os.path.join(path, 'modalias')).read().strip()
        # devices on SSB bus only mention the modalias in the uevent file (as
        # of 2.6.24)
        elif 'ssb' in path and 'uevent' in files:
            info = {}
            for l in open(os.path.join(path, 'uevent')):
                if l.startswith('MODALIAS='):
                    modalias = l.split('=', 1)[1].strip()
                    break

        if not modalias:
            continue

        # ignore drivers which are statically built into the kernel
        driverlink =  os.path.join(path, 'driver')
        modlink = os.path.join(driverlink, 'module')
        if os.path.islink(driverlink) and not os.path.islink(modlink):
            continue

        hw.add(HardwareID('modalias', modalias))

    _get_modaliases.cache = hw
    return hw

_get_modaliases.cache = None

def _handler_license_filter(handler, mode):
    '''Filter handlers by license.
    
    Return handler if the handler is compatible with mode (MODE_FREE,
    MODE_NONFREE, or MODE_ANY), else return None.
    '''
    if mode == MODE_FREE and handler and not handler.free():
        return None
    elif mode == MODE_NONFREE and handler and handler.free():
        return None
    return handler

def _driverid_to_handler(did, backend, mode):
    '''Create handler for a DriverID from a handler pool.

    mode is MODE_FREE, MODE_NONFREE, or MODE_ANY; see get_handlers() for
    details.
    '''
    explicit_handler = 'jockey_handler' in did
    if not explicit_handler:
        if 'driver_type' not in did:
            return None

        if did['driver_type'] == 'kernel_module':
            did['jockey_handler'] = 'KernelModuleHandler'
        elif did['driver_type'] == 'printer_driver':
            did['jockey_handler'] = 'PrinterDriverHandler'
        elif did['driver_type'] == 'hwe':
            did['jockey_handler'] = 'HWEHandler'
        else:
            logging.warning('Cannot map driver type %s to a default handler' %
                did['driver_type'])
            return None

    kwargs = did.properties.copy()
    args = []

    # special treatment of some standard attributes: those must be applied
    # to the particular handler instance
    for a in ('driver_type', 'jockey_handler', 'version', 'description',
        'long_description', 'repository', 'fingerprint', 'package',
        'driver_vendor', 'free', 'license', 'recommended'):
        try:
            del kwargs[a]
        except KeyError:
            pass

    hclass = None

    # instantiation of kernel module handlers; first try to find a custom
    # handler for this module
    if did['jockey_handler'] in ('KernelModuleHandler', 'FirmwareHandler') and \
            'kernel_module' in did:
        if not explicit_handler:
            # if the DriverDB did not set a handler explicitly, custom handlers
            # win over autogenerated standard ones
            for h in backend.handler_pool.itervalues():
                if isinstance(h, handlers.KernelModuleHandler) and \
                        h.module == did['kernel_module'] and \
                        (not h.package or not 'package' in did or h.package == did['package']):
                    logging.debug('found match in handler pool %s', h)
                    del kwargs['kernel_module']
                    hclass = h.__class__
                    break

        if not hclass:
            # no custom handler → fall back to creating a standard one

            # lazily initialize and check ignored modules
            if _driverid_to_handler.ignored is None:
                _driverid_to_handler.ignored = OSLib.inst.ignored_modules()
            if did['kernel_module'] not in _driverid_to_handler.ignored:
                # only create default handlers for modules which actually
                # exist or which we can install
                if not get_modinfo(did['kernel_module']):
                    if 'package' not in did.properties:
                        logging.warning('Module %s does not specify package', did['kernel_module'])
                        return None
                    try:
                        if 'free' not in did.properties:
                            did.properties['free'] = OSLib.inst.is_package_free(did.properties['package'])
                        if 'description' not in did.properties:
                            short = {}
                            long = {}
                            (short['C'], long['C'])  = OSLib.inst.package_description(did.properties['package'])
                            did.properties['description'] = short
                            did.properties['long_description'] = long
                    except ValueError as e:
                        logging.warning('Cannot determine properties of package %s: %s' % (did.properties['package'], str(e)))
                        return None

                hclass = getattr(handlers, did['jockey_handler'])

                # kernel_module is a positional parameter
                args.append(did['kernel_module'])
                del kwargs['kernel_module']

                # KernelModuleHandler needs the name passed for non-local
                # kmods; we override it later anyway, so just pass a dummy
                if 'description' in did.properties and 'name' not in kwargs:
                    kwargs['name'] = 'dummy'

    # instantiation of printer driver handlers
    if did['jockey_handler'] == 'PrinterDriverHandler' and not explicit_handler:
        if 'free' not in did.properties or \
           'description' not in did.properties or \
           'package' not in did.properties:
           logging.warning('DriverID for printer driver %s does not '
               'specify free/description/package; ignoring', str(did))
           return None

        hclass = handlers.PrinterDriverHandler
        args.append('dummy') # name is overridden later
        kwargs['description'] = ''

    # instantiation of HWE handlers
    if did['jockey_handler'] == 'HWEHandler':
        hclass = getattr(handlers, did['jockey_handler'])
        if not 'package' in did.properties:
            logging.warning('Hardware Enablement handler requires specifying a package')
        package = did.properties['package']
        kwargs['package'] = package

    # TODO: HandlerGroup standard handlers

    # default: look up handler in the handler pool
    if not hclass:
        try:
            hclass = backend.handler_pool[did['jockey_handler']].__class__
        except KeyError:
            pass

    if not hclass:
        return None

    # create instance and set specific properties from DriverID
    try:
        h = hclass(backend, *args, **kwargs)
    except Exception as e:
        logging.warning('could not instantiate handler class %s with args %s and kwargs %s: %s', 
            str(hclass), str(args), str(kwargs), str(e))
        return None

    if 'description' in did.properties:
        h._name = _get_locale_string(did.properties['description'])
    if 'long_description' in did.properties:
        h._description = _get_locale_string(did.properties['long_description'])
    if 'version' in did.properties:
        h.version = did.properties['version']
    if 'driver_vendor' in did.properties:
        h.driver_vendor = did.properties['driver_vendor']
    if 'package' in did.properties:
        h.package = did.properties['package']
    if 'repository' in did.properties:
        h.repository = did.properties['repository']
    if 'fingerprint' in did.properties:
        h.repository_sign_fp = did.properties['fingerprint']
    if 'free' in did.properties:
        h._free = did.properties['free']
    if 'license' in did.properties:
        h.license = did.properties['license']
    if did.properties.get('recommended'):
        h._recommended = True

    return _handler_license_filter(h, mode)

_driverid_to_handler.ignored = None

def _get_locale_string(map):
    '''Given a locale → string map, return the one for the current locale.'''

    loc = locale.getlocale(locale.LC_MESSAGES)[0] or 'C'
    lang = loc.split('_')[0]
    if loc in map:
        return map[loc]
    elif lang in map:
        return map[lang]
    else:
        return map['C']

#--------------------------------------------------------------------#
# public functions

def get_modinfo(module):
    '''Return information about a kernel module.
    
    This is delivered as a dictionary; keys are property names (strings),
    values are lists of strings (some properties might have multiple
    values, such as multi-line description fields or multiple PCI
    modaliases).
    '''
    try:
        return get_modinfo.cache[module]
    except KeyError:
        pass

    proc = subprocess.Popen((OSLib.inst.modinfo_path, module),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        logging.warning('modinfo for module %s failed: %s' % (module, stderr))
        return None

    modinfo = {}
    for line in stdout.split('\n'):
        if ':' not in line:
            continue

        (key, value) = line.split(':', 1)
        modinfo.setdefault(key.strip(), []).append(value.strip())

    get_modinfo.cache[module] = modinfo
    return modinfo

get_modinfo.cache = {}

def get_hardware():
    '''Return a set of HardwareID objects for the local hardware.'''

    # modaliases
    result = _get_modaliases()

    # other hardware detection goes here

    return result

(MODE_FREE, MODE_NONFREE, MODE_ANY) = range(3)

def get_handlers(backend, driverdb=None, handler_dir=None, mode=MODE_ANY,
    available_only=True, hardware=None, hardware_only=False):
    '''Return a set of handlers which are applicable on this system.
    
    backend (a Backend instance) is passed to the generated handlers. If a
    DriverDB instance is given (or a list of DriverDB objects), this will be
    queried for unknown detected devices and possible handlers for them.
    handler_dir specifies the directory where the custom handlers are stored
    (can be a list, too); if None, it defaults to OSLib.handler_dir.
    
    If mode is set to MODE_FREE, this will deliver only free handlers;
    MODE_NONFREE will only deliver nonfree handlers; by default (MODE_ANY), all
    available handlers are returned, regardless of their license.

    Usually this function only returns drivers that match the available
    hardware. With available_only=False, all handlers are returned (This is
    only useful for testing, though)

    By default, get_hardware() is called for detecting the local hardware; if
    that set is already known, it can be passed explicitly.

    If hardware_only is True, then this will only return handlers which match
    one of the hardware IDs in the "hardware" argument; otherwise all available
    drivers are returned.
    '''
    available_handlers = set()

    # get all custom handlers which are available
    if handler_dir == None:
        handler_dir = OSLib.inst.handler_dir
    if hasattr(handler_dir, 'isspace'):
        handler_dir = [handler_dir]
    for dir in handler_dir:
        for mod in glob(os.path.join(dir, '*.py')):
            symb = {}
            logging.debug('loading custom handler %s', mod)
            try:
                execfile(mod, symb)
            except Exception:
                logging.warning('Invalid custom handler module %s', mod,
                    exc_info=True)
                continue

            for name, obj in symb.iteritems():
                try:
                    # ignore non-Handler things; also ignore imports of
                    # standard base handlers into the global namespace
                    if not issubclass(obj, handlers.Handler) or \
                        hasattr(handlers, name) or hasattr(xorg_driver, name):
                        continue
                except TypeError:
                    continue

                try:
                    inst = obj(backend)
                    desc = inst.name()
                except:
                    logging.debug('Could not instantiate Handler subclass %s from name %s',
                        str(obj), name, exc_info=True)
                    continue

                logging.debug('Instantiated Handler subclass %s from name %s',
                    str(obj), name)
                inst = _handler_license_filter(inst, mode)
                if not inst:
                    logging.debug('%s does not match license mode %i', str(obj), mode)
                    continue

                backend.handler_pool[name] = inst

                avail = (not available_only) or inst.available()
                if avail:
                    if hardware_only:
                        logging.debug('hardware_only -> ignoring available handler %s', desc)
                    else:
                        logging.debug('%s is available', desc)
                        available_handlers.add(inst)
                elif avail == None:
                    logging.debug('%s availability undetermined, adding to pool', desc)
                else:
                    logging.debug('%s not available', desc)

    logging.debug('all custom handlers loaded')

    if not driverdb:
        return available_handlers

    # ask the driver dbs about all hardware
    if isinstance(driverdb, DriverDB):
        driverdb = [driverdb]
    if hardware is None:
        hardware = get_hardware()
    for db in driverdb:
        available_handlers.update(get_db_handlers(backend, db, hardware, mode))
    return available_handlers

def get_db_handlers(backend, db, hardware, mode=MODE_ANY):
    '''Return handlers for given hardware from a particular DriverDB.
    
    backend (a Backend instance) is passed to the generated handlers.

    If mode is set to MODE_FREE, this will deliver only free handlers;
    MODE_NONFREE will only deliver nonfree handlers; by default (MODE_ANY), all
    available handlers are returned, regardless of their license.
    '''
    available_handlers = set()
    for hwid in hardware:
        logging.debug('querying driver db %s about %s', db, hwid)
        dids = db.query(hwid)

        # if the DB returns just one handler, do not show it as recommended
        # even if the DB marks it as such; since there is no alternative, it
        # would just be confusing
        if len(dids) == 1:
            try:
                del dids[0].properties['recommended']
            except KeyError:
                pass

        for did in dids:
            logging.debug('searching handler for driver ID %s', str(did))
            h = _driverid_to_handler(did, backend, mode)
            if h:
                if h.available() == False:
                    logging.debug('ignoring unavailable handler %s', h)
                    continue
                logging.debug('got handler %s', h)
                h._hwids.append(hwid)
                available_handlers.add(h)
            else:
                logging.debug('no corresponding handler available for %s',
                    did.properties)

    return available_handlers

def download_gpg_fingerprint(url):
    '''Get GPG fingerprint from URL.

    Check that the URL is HTTPS with a valid and trusted server
    certificate, read it, extract the GPG fingerprint from it, and return
    it. Return None if the URL is invalid, not trusted, or the fingerprint
    can't be found.
    '''
    if not url.startswith('https://'):
        logging.debug('Not a https fingerprint URL: %s, ignoring driver' % url)
        return None

    cert = OSLib.inst.ssl_cert_file()
    if not cert:
        logging.debug('No system SSL certificates available for trust checking')
        return None

    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    content = StringIO()
    c.setopt(pycurl.WRITEFUNCTION, content.write)
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 5)
    c.setopt(pycurl.CAINFO, cert)

    try:
        c.perform()
    except pycurl.error as e:
        logging.warning('Cannot retrieve %s: %s' % (url, str(e)))
        return None

    fingerprint_re = re.compile(' ((?:(?:[0-9A-F]{4})(?:\s+|$)){10})$', re.M)
    
    m = fingerprint_re.search(content.getvalue())
    if m:
        return m.group(1).strip()

    return None
