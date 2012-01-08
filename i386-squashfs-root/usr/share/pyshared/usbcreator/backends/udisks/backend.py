import dbus
import logging
from dbus.mainloop.glib import DBusGMainLoop
from usbcreator.backends.base import Backend
from usbcreator.misc import *

DISKS_IFACE = 'org.freedesktop.UDisks'
DEVICE_IFACE = 'org.freedesktop.UDisks.Device'
PROPS_IFACE = 'org.freedesktop.DBus.Properties'

import time

class UDisksBackend(Backend):
    def __init__(self, allow_system_internal=False, bus=None, show_all=False):
        Backend.__init__(self)
        self.mounted_source = ''
        self.formatting = []
        self.show_all = show_all
        self.allow_system_internal = allow_system_internal
        logging.debug('UDisksBackend')
        DBusGMainLoop(set_as_default=True)
        if bus:
            self.bus = bus
        else:
            self.bus = dbus.SystemBus()
        udisks_obj = self.bus.get_object(DISKS_IFACE,
                                         '/org/freedesktop/UDisks')
        self.udisks = dbus.Interface(udisks_obj, DISKS_IFACE)
        self.helper = self.bus.get_object('com.ubuntu.USBCreator',
                                          '/com/ubuntu/USBCreator')
        self.helper = dbus.Interface(self.helper, 'com.ubuntu.USBCreator')

    # Adapted from udisk's test harness.
    # This is why the entire backend needs to be its own thread.
    def retry_mount(self, device):
        '''Try to mount until it does not fail with "Busy".'''
        timeout = 10
        dev_obj = self.bus.get_object(DISKS_IFACE, device)
        props = dbus.Interface(dev_obj, dbus.PROPERTIES_IFACE)
        device_i = dbus.Interface(dev_obj, DEVICE_IFACE)
        while timeout >= 0:
            if props.Get(device, 'device-is-mounted'):
                break
            try:
                device_i.FilesystemMount('', [])
            except dbus.DBusException, e:
                if e._dbus_error_name != 'org.freedesktop.UDisks.Error.Busy':
                    raise
                logging.debug('Busy.')
                time.sleep(0.3)
                timeout -= 1
    
    # Device detection and processing functions.

    def detect_devices(self):
        '''Start looking for new devices to add.  Devices added will be sent to
        the fronted using frontend.device_added.  Devices will only be added as
        they arrive if a main loop is present.'''
        logging.debug('detect_devices')
        self.bus.add_signal_receiver(self._device_added,
            'DeviceAdded',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')
        self.bus.add_signal_receiver(self._device_changed,
            'DeviceChanged',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')
        self.bus.add_signal_receiver(self._device_removed,
            'DeviceRemoved',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')
        def handle_reply(res):
            for r in res:
                self._device_added(r)
        def handle_error(err):
            logging.error('Unable to enumerate devices: %s' % str(err))
        self.udisks.EnumerateDevices(reply_handler=handle_reply,
                                     error_handler=handle_error)
        
    def _device_added(self, device):
        logging.debug('device_added: %s' % device)
        udisks_obj = self.bus.get_object(DISKS_IFACE, device)
        d = dbus.Interface(udisks_obj, 'org.freedesktop.DBus.Properties')

        if d.Get(device, 'device-is-optical-disc'):
            self._add_cd(device)
        if (self.allow_system_internal or
            not d.Get(device, 'device-is-system-internal')):
            if d.Get(device, 'device-is-partition'):
                self._add_partition(device)
            elif d.Get(device, 'device-is-drive'):
                if not d.Get(device, 'device-is-optical-disc'):
                    self._add_drive(device)

    def _device_changed(self, device):
        udisks_obj = self.bus.get_object(DISKS_IFACE, device)
        d = dbus.Interface(udisks_obj, 'org.freedesktop.DBus.Properties')
        logging.debug('device change %s' % str(device))
        # As this will happen in the same event, the frontend wont change
        # (though it needs to make sure the list is sorted, otherwise it will).
        self._device_removed(device)
        self._device_added(device)

    def _add_cd(self, device):
        logging.debug('cd added: %s' % device)
        dk = self.bus.get_object(DISKS_IFACE, device)
        def get(prop):
            return dk.Get(device, prop, dbus_interface=PROPS_IFACE)
        label = get('id-label')
        if not get('device-is-mounted'):
            try:
                mp = dk.FilesystemMount('', [], dbus_interface=DEVICE_IFACE)
            except dbus.DBusException, e:
                logging.exception('Could not mount the device:')
                return
        mount = get('device-mount-paths')[0]
        device_file = get('device-file')
        total, free = fs_size(mount)
        self.sources[device] = {
            'device' : device_file,
            'size' : total,
            'label' : label,
            'type' : SOURCE_CD,
        }
        if callable(self.source_added_cb):
            self.source_added_cb(device)

    def _add_partition(self, device):
        logging.debug('partition added: %s' % device)
        dk = self.bus.get_object(DISKS_IFACE, device)
        def get(prop):
            return dk.Get(device, prop, dbus_interface=PROPS_IFACE)

        model = get('DriveModel')
        vendor = get('DriveVendor')
        fstype = get('id-type')
        logging.debug('id-type: %s' % fstype)
        if fstype == 'vfat':
            status = CAN_USE
        else:
            status = NEED_FORMAT
        label = get('id-label')
        logging.debug('id-label: %s' % label)
        parent = get('partition-slave')
        if fstype == 'vfat' and not get('device-is-mounted'):
            parent_i = self.bus.get_object(DISKS_IFACE, parent)
            parent_f = parent_i.Get(parent, 'device-file', dbus_interface=PROPS_IFACE)
            if device not in self.formatting and parent not in self.formatting:
                try:
                    self.retry_mount(device)
                except:
                    logging.exception('Could not mount the device:')
                    return
        mount = get('device-mount-paths') or ''
        if mount:
            mount = mount[0]
            total, free = fs_size(mount)
        else:
            # FIXME evand 2009-09-11: This is going to have weird side effects.
            # If the device cannot be mounted, but is a vfat filesystem, that
            # is.  Is this really the right approach?
            total = get('partition-size')
            free = -1
        logging.debug('mount: %s' % mount)
        device_file = get('device-file')
        if total > 0:
            self.targets[unicode(device)] = {
                'vendor'     : vendor,
                'model'      : model,
                'label'      : unicode(label),
                'free'       : free,
                'device'     : unicode(device_file),
                'capacity'   : total,
                'status'     : status,
                'mountpoint' : mount,
                'persist'    : 0,
                'parent'     : unicode(parent),
                'formatting' : False,
            }
            self._update_free(unicode(device))
            if self.show_all:
                if callable(self.target_added_cb):
                    self.target_added_cb(device)
            else:
                if status != NEED_FORMAT:
                    if unicode(parent) in self.targets:
                        if callable(self.target_removed_cb):
                            self.target_removed_cb(parent)
                    if callable(self.target_added_cb):
                        self.target_added_cb(device)
        else:
            logging.debug('not adding device: 0 byte partition.')

    def _add_drive(self, device):
        logging.debug('disk added: %s' % device)
        dk = self.bus.get_object(DISKS_IFACE, device)
        def get(prop):
            return dk.Get(device, prop, dbus_interface=PROPS_IFACE)
        model = get('DriveModel')
        vendor = get('DriveVendor')
        device_file = get('device-file')
        size = get('device-size')
        if size > 0:
            self.targets[unicode(device)] = {
                'vendor'     : vendor,
                'model'      : model,
                'label'      : '',
                'free'       : -1,
                'device'     : unicode(device_file),
                'capacity'   : size,
                'status'     : NEED_FORMAT,
                'mountpoint' : None,
                'persist'    : 0,
                'parent'     : None,
                'formatting' : False,
            }
            if callable(self.target_added_cb):
                if self.show_all:
                    self.target_added_cb(device)
                else:
                    children = [x for x in self.targets
                                if self.targets[x]['parent'] == unicode(device) and
                                   self.targets[x]['status'] != NEED_FORMAT]
                    if not children:
                        self.target_added_cb(device)
        else:
            logging.debug('not adding device: 0 byte disk.')

    def _device_removed(self, device):
        logging.debug('Device has been removed from the system: %s' % device)
        if device in self.sources:
            if callable(self.source_removed_cb):
                self.source_removed_cb(device)
            self.sources.pop(device)
        elif device in self.targets:
            if callable(self.target_removed_cb):
                self.target_removed_cb(device)
            self.targets.pop(device)

    # Device manipulation functions.
    def _is_casper_cd(self, filename):
        cmd = ['isoinfo', '-J', '-i', filename, '-x', '/.disk/info']
        try:
            output = popen(cmd, stderr=None)
            if output:
                return output
        except USBCreatorProcessException:
            # TODO evand 2009-07-26: Error dialog.
            logging.error('Could not extract .disk/info.')
        return None

    def open(self, udi):
        mp = self.targets[udi]['mountpoint']
        if not mp:
            try:
                dk = self.bus.get_object(DISKS_IFACE, udi)
                mp = dk.FilesystemMount('', [], dbus_interface=DEVICE_IFACE)
            except dbus.DBusException:
                logging.exception('Could not mount the device:')
                return ''
        try:
            popen(['mount', '-o', 'remount,rw', mp])
        except USBCreatorProcessException:
            logging.exception('Could not mount the device:')
            return ''
        return mp
    
    def format_done(self, dev=None):
        if dev in self.targets:
            p = self.targets[dev]['parent']
            if p and p in self.targets:
                dev = p
            self.targets[dev]['formatting'] = False
            self.formatting.remove(dev)

    def format_failed(self, message, dev=None):
        self.format_done(dev)
        self.format_failed_cb(message)

    def format(self, device):
        try:
            dk = self.bus.get_object(DISKS_IFACE, device)
            dev = dk.Get(device, 'device-file', dbus_interface=PROPS_IFACE)
            if dk.Get(dev, 'device-is-partition', dbus_interface=PROPS_IFACE):
                dev = dk.Get(dev, 'partition-slave', dbus_interface=PROPS_IFACE)
                dk = self.bus.get_object(DISKS_IFACE, dev)
                dev = dk.Get(device, 'device-file', dbus_interface=PROPS_IFACE)
            p = self.targets[device]['parent']
            if p and p in self.targets:
                self.formatting.append(p)
                self.targets[p]['formatting'] = True
            else:
                self.formatting.append(device)
                self.targets[device]['formatting'] = True
            self.helper.Format(dev, self.allow_system_internal,
                    # There must be a better way...
                    reply_handler=lambda: self.format_done(device),
                    error_handler=lambda x: self.format_failed(x, device))
        except dbus.DBusException:
            # Could not talk to usb-creator-helper or devkit.
            logging.exception('Could not format the device:')

    def install(self, source, target, persist, allow_system_internal=False):
        # TODO evand 2009-07-31: Lock source and target.
        logging.debug('install source: %s' % source)
        logging.debug('install target: %s' % target)
        logging.debug('install persistence: %d' % persist)

        # There's no going back now...
        self.bus.remove_signal_receiver(self._device_added,
            'DeviceAdded',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')
        self.bus.remove_signal_receiver(self._device_changed,
            'DeviceChanged',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')
        self.bus.remove_signal_receiver(self._device_removed,
            'DeviceRemoved',
            DISKS_IFACE,
            DISKS_IFACE,
            '/org/freedesktop/UDisks')

        stype = self.sources[source]['type']
        if stype == SOURCE_CD:
            dk = self.bus.get_object(DISKS_IFACE, source)
            def get(prop):
                return dk.Get(source, prop, dbus_interface=PROPS_IFACE)
            if not get('device-is-mounted'):
                source = dk.FilesystemMount('', [], dbus_interface=DEVICE_IFACE)
            else:
                source = get('device-mount-paths')[0]
        elif stype == SOURCE_ISO:
            isofile = self.sources[source]['device']
            source = self.helper.MountISO(isofile)
            self.mounted_source = source
        
        dk = self.bus.get_object(DISKS_IFACE, target)
        def get(prop):
            return dk.Get(target, prop, dbus_interface=PROPS_IFACE)
        dev = get('device-file')
        if stype == SOURCE_IMG:
            target = None
            self.helper.Unmount(target)
        else:
            if not get('device-is-mounted'):
                target = dk.FilesystemMount('', [], dbus_interface=DEVICE_IFACE)
            else:
                target = get('device-mount-paths')[0]
            self.helper.RemountRW(dev)
        Backend.install(self, source, target, persist, device=dev,
                        allow_system_internal=allow_system_internal)

    def cancel_install(self):
        Backend.cancel_install(self)
        self.unmount()

    def unmount(self):
        try:
            if self.mounted_source:
                self.helper.UnmountFile(self.mounted_source)
        except:
            # TODO let the user know via the frontend.
            logging.exception('Could not unmount the source ISO.')

    def shutdown(self):
        try:
            self.helper.Shutdown()
        except dbus.DBusException:
            logging.exception('Could not shut down the dbus service.')
