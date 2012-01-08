# -*- coding: UTF-8 -*-

# (c) 2008 Canonical Ltd.
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

'''Backend manager.

This encapsulates all services of the backend and manages all handlers.
'''

import logging, os, os.path, signal, threading, sys

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GObject

from jockey.oslib import OSLib
import detection, xorg_driver

DBUS_BUS_NAME = 'com.ubuntu.DeviceDriver'

#--------------------------------------------------------------------#

class UnknownHandlerException(dbus.DBusException):
    _dbus_error_name = 'com.ubuntu.DeviceDriver.UnknownHandlerException'

class InvalidModeException(dbus.DBusException):
    _dbus_error_name = 'com.ubuntu.DeviceDriver.InvalidModeException'

class InvalidDriverDBException(dbus.DBusException):
    _dbus_error_name = 'com.ubuntu.DeviceDriver.InvalidDriverDBException'

class PermissionDeniedByPolicy(dbus.DBusException):
    _dbus_error_name = 'com.ubuntu.DeviceDriver.PermissionDeniedByPolicy'

class BackendCrashError(SystemError):
    pass

#--------------------------------------------------------------------#

def dbus_sync_call_signal_wrapper(dbus_iface, fn, handler_map, *args, **kwargs):
    '''Run a D-BUS method call while receiving signals.

    This function is an Ugly Hack™, since a normal synchronous dbus_iface.fn()
    call does not cause signals to be received until the method returns. Thus
    it calls fn asynchronously and sets up a temporary main loop to receive
    signals and call their handlers; these are assigned in handler_map (signal
    name → signal handler).
    '''
    if not hasattr(dbus_iface, 'connect_to_signal'):
        # not a D-BUS object
        return getattr(dbus_iface, fn)(*args, **kwargs)

    def _h_reply(result):
        global _h_reply_result
        _h_reply_result = result
        loop.quit()

    def _h_error(exception):
        global _h_exception_exc
        _h_exception_exc = exception
        loop.quit()

    loop = GObject.MainLoop()
    global _h_reply_result, _h_exception_exc
    _h_reply_result = None
    _h_exception_exc = None
    kwargs['reply_handler'] = _h_reply
    kwargs['error_handler'] = _h_error
    kwargs['timeout'] = 86400
    for signame, sighandler in handler_map.iteritems():
        dbus_iface.connect_to_signal(signame, sighandler)
    dbus_iface.get_dbus_method(fn)(*args, **kwargs)
    loop.run()
    if _h_exception_exc:
        raise _h_exception_exc
    return _h_reply_result

#--------------------------------------------------------------------#

def convert_dbus_exceptions(fn, *args, **kwargs):
    '''Convert D-Bus exceptions to their actual exception types'''
    try:
        return fn(*args, **kwargs)
    except dbus.DBusException as e:
        if e._dbus_error_name == PermissionDeniedByPolicy._dbus_error_name:
            raise PermissionDeniedByPolicy(str(e))
        elif e._dbus_error_name == InvalidModeException._dbus_error_name:
            raise InvalidModeException(str(e))
        elif e._dbus_error_name == UnknownHandlerException._dbus_error_name:
            raise UnknownHandlerException(str(e))
        elif e._dbus_error_name == 'org.freedesktop.DBus.Python.SystemError':
            raise SystemError(str(e))
        elif e._dbus_error_name == 'org.freedesktop.DBus.Error.NoReply':
            raise BackendCrashError
        else:
            raise

#--------------------------------------------------------------------#

class Backend(dbus.service.Object):
    '''Backend manager.

    This encapsulates all services of the backend and manages all handlers. It
    is implemented as a dbus.service.Object, so that it can be called through
    D-BUS as well (on the /DeviceDriver object path).
    '''
    DBUS_INTERFACE_NAME = 'com.ubuntu.DeviceDriver'

    def __init__(self, handler_dir=None, detect=True):
        '''Initialize backend (no hardware/driver detection).

        In order to be fast and not block client side applications for very
        long, detect can be set to False; in that case this constructor does
        not detect hardware and drivers, and client-side applications must call
        detect() or db_init() at program start.
        '''
        self.handler_dir = handler_dir
        self.handler_pool = {}
        self.driver_dbs = None
        self.hardware = None

        # cached D-BUS interfaces for _check_polkit_privilege()
        self.dbus_info = None
        self.polkit = None
        self.main_loop = None

        self.enforce_polkit = True
        self._package_operation_in_progress = False

        if detect:
            self.detect()

    #
    # Client API (through D-BUS)
    #

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='', sender_keyword='sender',
        connection_keyword='conn')
    def detect(self, sender=None, conn=None):
        '''Detect available hardware and handlers.

        This method can take pretty long, so it should be called asynchronously
        with a large (or indefinite) timeout, and client UIs should display a
        bouncing progress bar (if appropriate). If the backend is already
        initialized, this returns immediately.

        This must be called once at client-side program start. If the Backend
        object is initialized with argument "detect=True", this happens
        automatically. If the client just wants to perform a search_driver()
        operation on remote driver DBs on already detected hardware, it can
        only call db_init() instead.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        if not self.hardware:
            self.hardware = detection.get_hardware()
            self.db_init()
            self._detect_handlers()

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='', sender_keyword='sender',
        connection_keyword='conn')
    def db_init(self, sender=None, conn=None):
        '''Initialize the driver databases for search_driver()

        When a client wants to search a remote driver for a piece of already
        detected hardware (for example a printer detected by CUPS) we do not
        need the time-consuming operation of detect(). It is enough to
        initialize the driver databases.

        This must be called once at client-side program start, if not using
        detect() or initializing the Backend with argument "detect=True".
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        if not self.driver_dbs:
            self.driver_dbs = [detection.LocalKernelModulesDriverDB(),
                detection.OpenPrintingDriverDB()]
            self.handlers = {}

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='as', sender_keyword='sender',
        connection_keyword='conn')
    def available(self, mode='any', sender=None, conn=None):
        '''List available driver IDs.
        
        Mode can be "any" (default) to return all available drivers, or
        "free"/"nonfree" to select by license.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        if mode == 'any':
            return self.handlers.keys()

        if mode not in ('free', 'nonfree'):
            raise InvalidModeException(
                'invalid mode %s: must be "free", "nonfree", or "any"' % mode)

        recommended = []
        nonrecommended = []
        for (h_id, h) in self.handlers.iteritems():
            if h.free() == (mode == 'free'):
                if h.recommended():
                    recommended.append(h_id)
                else:
                    nonrecommended.append(h_id)
        return recommended + nonrecommended

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='as', sender_keyword='sender',
        connection_keyword='conn')
    def get_hardware(self, sender=None, conn=None):
        '''List available hardware IDs.'''

        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')
        return [hwid.type + ':' + hwid.id for hwid in self.hardware]

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='a{ss}', sender_keyword='sender',
        connection_keyword='conn')
    def handler_info(self, handler_id, sender=None, conn=None):
        '''Return details about a particular handler.

        The information is returned in a property_name → property_value
        dictionary. Boolean values are encoded as 'True' and 'False' strings.
        If a particular attribute is not set, it will not appear in the
        dictionary.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        try:
            h = self.handlers[handler_id]
        except KeyError:
            raise UnknownHandlerException('Unknown handler: %s' % handler_id)

        info = {
            'id': h.id(),
            'name': h.name(),
            'free': str(h.free()),
            'enabled': str(h.enabled()),
            'used': str(h.used()),
            'changed': str(h.changed()),
            'recommended': str(h.recommended()),
            'announce': str(h.announce),
            'auto_install': str(h.auto_install())
        }
        for f in ['description', 'rationale', 'can_change']:
            v = getattr(h, f)()
            if v:
                info[f] = v
        for f in ['package', 'repository', 'repository_sign_fp',
                'driver_vendor', 'version', 'license']:
            v = getattr(h, f)
            if v:
                info[f] = v

        return info

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='as', sender_keyword='sender',
        connection_keyword='conn')
    def handler_files(self, handler_id, sender=None, conn=None):
        '''Return list of files installed by a handler.'''

        try:
            h = self.handlers[handler_id]
        except KeyError:
            raise UnknownHandlerException('Unknown handler: %s' % handler_id)

        if not h.package or not h.enabled():
            return []

        try:
            return OSLib.inst.package_files(h.package)
        except ValueError:
            return []

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='sb', out_signature='b', sender_keyword='sender',
        connection_keyword='conn')
    def set_enabled(self, handler_id, enable, sender=None, conn=None):
        '''Enable or disable a driver.

        This enables (enable=True) or disables (enable=False) the given Driver
        ID. Return True if the handler could be activated immediately, or False
        if the system needs a reboot for the changes to become effective.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.install')

        try:
            h = self.handlers[handler_id]
        except KeyError:
            raise UnknownHandlerException('Unknown handler: %s' % handler_id)

        if enable:
            f = h.enable
        else:
            f = h.disable

        if not conn:
            # not called through D-BUS, thus don't send progress signals
            return f()

        if h.package:
            # start progress information early; for package operations we will
            # always have a progress bar, avoid delays from the package manager
            # with progress reporting
            if enable:
                self.install_progress('download', -1, -1)
            else:
                self.remove_progress(-1, -1)

        def _f_result_wrapper():
            try:
                self._f_result = f()
            except:
                self._f_exception = sys.exc_info()

        # Call enable/disable in a separate thread, in case it does long
        # actions and thus we need to signal progress
        self._f_exception = None
        t_f = threading.Thread(None, _f_result_wrapper,
            'thread_enable_disable', [], {})
        t_f.start()
        while True:
            t_f.join(0.2)
            if not t_f.isAlive():
                break
            # {install,remove}_package() already report percentage process,
            # don't interfere with that
            if not self._package_operation_in_progress:
                if enable:
                    self.install_progress('install', -1, -1)
                else:
                    self.remove_progress(-1, -1)
        if self._f_exception:
            raise self._f_exception[0], self._f_exception[1], self._f_exception[2]
            # with py3:
            #raise self._f_exception[0](self._f_exception[1]).with_traceback(self._f_exception[2])

        # notify about reboot
        if not self._f_result:
            OSLib.inst.notify_reboot_required()
        return self._f_result

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='(asas)', sender_keyword='sender',
        connection_keyword='conn')
    def new_used_available(self, mode='any', sender=None, conn=None):
        '''Check for newly used or available drivers since last call.
        
        Return (new_used, new_avail) with lists of new drivers which are in
        use, and new drivers which got available but are disabled.
        Mode can be "any" (default) to return all available drivers, or
        "free"/"nonfree" to select by license.

        This will return empty lists if no package repositories are available.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.check')

        if mode not in ('any', 'free', 'nonfree'):
            raise InvalidModeException(
                'invalid mode %s: must be "free", "nonfree", or "any"' % mode)

        if not self.has_repositories():
            logging.warning('new_used_available(): No package repositories available, skipping check')
            return ([], [])

        # read previously seen/used handlers
        seen = set()
        used = set()

        if os.path.exists(OSLib.inst.check_cache):
            f = open(OSLib.inst.check_cache)
            for line in f:
                try:
                    (flag, h) = line.split(None, 1)
                    h = unicode(h, 'UTF-8')
                except ValueError:
                    logging.error('invalid line in %s: %s',
                        OSLib.inst.check_cache, line)
                if flag == 'seen':
                    seen.add(h.strip())
                elif flag == 'used':
                    used.add(h.strip())
                else:
                    logging.error('invalid flag in %s: %s',
                        OSLib.inst.check_cache, line)
            f.close()

        # check for newly used/available handlers
        new_avail = []
        new_used = []
        for h_id, h in self.handlers.iteritems():
            if (mode == 'free' and not h.free()) or \
               (mode == 'nonfree' and h.free()):
               continue
            if h_id not in seen:
                new_avail.append(h_id)
                logging.debug('handler %s previously unseen', h_id)
            if h_id not in used and h.used():
                new_used.append(h_id)
                logging.debug('handler %s previously unused', h_id)

        # write back cache
        logging.debug('writing back check cache %s', 
            OSLib.inst.check_cache)
        seen.update(new_avail)
        used.update(new_used)
        f = open(OSLib.inst.check_cache, 'w')
        for s in seen:
            print >> f, 'seen', s
        for u in used:
            print >> f, 'used', u
        f.close()

        # throw out newly available handlers which are already enabled, no need
        # to bother people about them
        for h_id in new_avail + []: # create a copy for iteration
            try:
                if self.handlers[h_id].enabled():
                    logging.debug('%s is already enabled or not available, not announcing', h_id)
                    new_avail.remove(h_id)
            except ValueError:
                # thrown if package does not exist; might be a race condition
                # between jockey --check and a cron job fetching new package
                # indexes at session start, see LP #200089
                continue

        return (new_used, new_avail)

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='s', sender_keyword='sender',
        connection_keyword='conn')
    def check_composite(self, sender=None, conn=None):
        '''Check for a composite-enabling X.org driver.

        If one is available and not enabled, return its ID, otherwise return
        an empty string.
        '''
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        for h_id, h in self.handlers.iteritems():
            if isinstance(h, xorg_driver.XorgDriverHandler) and \
                h.enables_composite():
                if h.enabled():
                    logging.debug('Driver "%s" is already enabled and supports the composite extension.' % h.name())
                    return ''
                else:
                    return h_id
        return ''

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='sas', out_signature='', sender_keyword='sender',
        connection_keyword='conn')
    def add_driverdb(self, db_class, db_args, sender=None, conn=None):
        '''Add driver DB.

        db_class is a DriverDB class name; db_args are its constructor
        arguments. If there is an error instantiating the driver DB, an
        InvalidDriverDBException is thrown.
        '''
        try:
            cls = getattr(detection, db_class)
        except AttributeError as e:
            raise InvalidDriverDBException(str(e))

        try:
            inst = cls(*db_args)
        except Exception as e:
            raise InvalidDriverDBException(str(e))

        logging.debug('add_driverdb: Adding %s', str(inst))

        self.driver_dbs.append(inst)

        # do not call _detect_handlers(), it re-detects everything
        for h in detection.get_db_handlers(self, inst, self.hardware):
            self.handlers[h.id()] = h

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='', sender_keyword='sender',
        connection_keyword='conn')
    def update_driverdb(self, sender=None, conn=None):
        '''Query driver DBs for updates.'''

        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.update')

        for db in self.driver_dbs:
            logging.debug('update_driverdb: updating %s', db.__class__)
            db.update(self.hardware)

        self._detect_handlers()

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='as', sender_keyword='sender',
        connection_keyword='conn')
    def search_driver(self, hwid, sender=None, conn=None):
        '''Search drivers matching a HardwareID.

        This also finds drivers for hardware which is not present locally and
        thus checks all the driver DBs again.

        Mode can be "any" (default) to return all available drivers, or
        "free"/"nonfree" to select by license.
        '''
        # TODO: support freeness mode
        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.info')

        (t, i) = hwid.split(':', 1)
        hardware_id = detection.HardwareID(t, i)

        recommended = []
        nonrecommended = []
        for db in self.driver_dbs:
            db.update([hardware_id])
        handlers = detection.get_handlers(self, self.driver_dbs,
            hardware=[hardware_id], hardware_only=True)
        for h in handlers:
            id = h.id()
            if id not in self.handlers:
                self.handlers[id] = h
            if h.recommended():
                recommended.append(id)
            else:
                nonrecommended.append(id)

        return recommended + nonrecommended

    @dbus.service.signal(DBUS_INTERFACE_NAME)
    def install_progress(self, phase, curr, total):
        '''Report package installation progress.

        'phase' is 'download' or 'install'. current and/or total might be -1 if
        time cannot be determined.
        '''
        return False # TODO: cancel not implemented

    @dbus.service.signal(DBUS_INTERFACE_NAME)
    def remove_progress(self, curr, total):
        '''Report package removal progress.

        current and/or total might be -1 if time cannot be determined.
        '''
        return False

    @dbus.service.signal(DBUS_INTERFACE_NAME)
    def repository_update_progress(self, curr, total):
        '''Report repository index update progress.

        current and/or total might be -1 if time cannot be determined.
        '''
        return False

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='b', sender_keyword='sender',
        connection_keyword='conn')
    def has_repositories(self, sender=None, conn=None):
        '''Check if there are package respository indexes available.'''

        return OSLib.inst.has_repositories()

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='b', sender_keyword='sender',
        connection_keyword='conn')
    def update_repository_indexes(self, sender=None, conn=None):
        '''Update package respository indexes
        
        Return True on success, False on failure.'''

        self._reset_timeout()
        self._check_polkit_privilege(sender, conn, 'com.ubuntu.devicedriver.check')

        logging.debug('Updating repository indexes...')
        OSLib.inst.update_repository_indexes(
            hasattr(self, '_locations') and self.repository_update_progress or None)
        if self.has_repositories():
            logging.debug('... success')
            return True
        else:
            logging.debug('... fail!')
            return False

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='', out_signature='', sender_keyword='sender',
        connection_keyword='conn')
    def shutdown(self, sender=None, conn=None):
        '''Shut down the daemon.'''

        logging.debug('Shutting down')
        self._timeout = True
        if self.main_loop:
            self.main_loop.quit()

    #
    # Internal API for calling from Handlers (not exported through D-BUS)
    #

    def install_package(self, package, repository=None, fingerprint=None):
        '''Install software package.'''

        if OSLib.inst.package_installed(package):
            return

        # only pass D-BUS signal callback if we are called as a D-BUS backend
        self._package_operation_in_progress = True
        OSLib.inst.install_package(package, 
            hasattr(self, '_locations') and self.install_progress or None,
            repository, fingerprint)
        if OSLib.inst.package_installed(package):
            self._update_installed_packages([package], [])
        self._package_operation_in_progress = False

    def remove_package(self, package):
        '''Remove software package.'''

        if not OSLib.inst.package_installed(package):
            return

        # only pass D-BUS signal callback if we are called as a D-BUS backend
        self._package_operation_in_progress = True
        OSLib.inst.remove_package(package,
            hasattr(self, '_locations') and self.remove_progress or None)
        if not OSLib.inst.package_installed(package):
            self._update_installed_packages([], [package])
        self._package_operation_in_progress = False

    #
    # D-BUS control API
    #

    def run_dbus_service(self, timeout=None, send_usr1=False):
        '''Run D-BUS server.

        If no timeout is given, the server will run forever, otherwise it will
        return after the specified number of seconds.

        If send_usr1 is True, this will send a SIGUSR1 to the parent process
        once the server is ready to take requests.
        '''
        dbus.service.Object.__init__(self, self.bus, '/DeviceDriver')
        self.main_loop = GObject.MainLoop()
        self._timeout = False
        if timeout:
            def _t():
                self.main_loop.quit()
                return True
            GObject.timeout_add(timeout * 1000, _t)

        # send parent process a signal that we are ready now
        if send_usr1:
            os.kill(os.getppid(), signal.SIGUSR1)

        # run until we time out
        while not self._timeout:
            if timeout:
                self._timeout = True
            self.main_loop.run()

    @classmethod
    def create_dbus_server(klass, session_bus=False, handler_dir=None):
        '''Return a D-BUS server backend instance.

        Normally this connects to the system bus. Set session_bus to True to
        connect to the session bus (for testing). 
        
        The created backend does not yet have hardware and drivers detected,
        thus clients need to call detect().
        '''
        import dbus.mainloop.glib

        backend = Backend(handler_dir, detect=False)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        if session_bus:
            backend.bus = dbus.SessionBus()
            backend.enforce_polkit = False
        else:
            backend.bus = dbus.SystemBus()
        backend.dbus_name = dbus.service.BusName(DBUS_BUS_NAME, backend.bus)
        return backend

    @classmethod
    def create_dbus_client(klass, session_bus=False):
        '''Return a client-side D-BUS interface for Backend.

        Normally this connects to the system bus. Set session_bus to True to
        connect to the session bus (for testing).
        '''
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        if session_bus:
            bus = dbus.SessionBus()
        else:
            bus = dbus.SystemBus()
        obj = bus.get_object(DBUS_BUS_NAME, '/DeviceDriver')
        return dbus.Interface(obj, Backend.DBUS_INTERFACE_NAME)

    #
    # Internal methods
    #

    def _update_installed_packages(self, add, remove):
        '''Update backup_dir/installed_packages list of driver packages.
        
        This keeps a log of all packages that jockey installed for supporting
        drivers, so that distribution installers on live CDs can push them into
        the installed system as well.

        add and remove are lists which package names to add/remove from it.
        '''
        # get current list
        current = set()
        path = os.path.join(OSLib.inst.backup_dir, 'installed_packages')
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if line:
                    current.add(line)
    
        current = current.union(add).difference(remove)
        
        if current:
            # write it back
            f = open(path, 'w')
            for p in current:
                print >> f, p
            f.close()
        else:
            # delete it if it is empty
            if os.path.exists(path):
                os.unlink(path)

    def _detect_handlers(self):
        '''Detect available handlers and their state.
        
        This initializes self.handlers as id → Handler map.'''

        self.handlers = {}

        # shortcut if we do not have package repos
        if not self.has_repositories():
            logging.warning('_detect_handlers(): No package repositories available, skipping check')
            return

        for h in detection.get_handlers(self,
                self.driver_dbs,
                handler_dir=self.handler_dir,
                hardware=self.hardware):
            self.handlers[h.id()] = h

    def _reset_timeout(self):
        '''Reset the D-BUS server timeout.'''

        self._timeout = False

    def _check_polkit_privilege(self, sender, conn, privilege):
        '''Verify that sender has a given PolicyKit privilege.

        sender is the sender's (private) D-BUS name, such as ":1:42"
        (sender_keyword in @dbus.service.methods). conn is
        the dbus.Connection object (connection_keyword in
        @dbus.service.methods). privilege is the PolicyKit privilege string.

        This method returns if the caller is privileged, and otherwise throws a
        PermissionDeniedByPolicy exception.
        '''
        if sender is None and conn is None:
            # called locally, not through D-BUS
            return
        if not self.enforce_polkit:
            # that happens for testing purposes when running on the session
            # bus, and it does not make sense to restrict operations here
            return

        # get peer PID
        if self.dbus_info is None:
            self.dbus_info = dbus.Interface(conn.get_object('org.freedesktop.DBus',
                '/org/freedesktop/DBus/Bus', False), 'org.freedesktop.DBus')
        pid = self.dbus_info.GetConnectionUnixProcessID(sender)
        
        # query PolicyKit
        if self.polkit is None:
            self.polkit = dbus.Interface(dbus.SystemBus().get_object(
                'org.freedesktop.PolicyKit1',
                '/org/freedesktop/PolicyKit1/Authority', False),
                'org.freedesktop.PolicyKit1.Authority')
        try:
            # we don't need is_challenge return here, since we call with AllowUserInteraction
            (is_auth, _, details) = self.polkit.CheckAuthorization(
                    ('unix-process', {'pid': dbus.UInt32(pid, variant_level=1),
                        'start-time': dbus.UInt64(0, variant_level=1)}), 
                    privilege, {'': ''}, dbus.UInt32(1), '', timeout=600)
        except dbus.DBusException as e:
            if e._dbus_error_name == 'org.freedesktop.DBus.Error.ServiceUnknown':
                # polkitd timed out, connect again
                self.polkit = None
                return self._check_polkit_privilege(sender, conn, privilege)
            else:
                raise

        if not is_auth:
            logging.debug('_check_polkit_privilege: sender %s on connection %s pid %i is not authorized for %s: %s' %
                    (sender, conn, pid, privilege, str(details)))
            raise PermissionDeniedByPolicy(privilege)

