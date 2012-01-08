# Copyright (C) 2008, 2009 Canonical Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import stat
import sys
import shutil
from usbcreator.misc import popen, USBCreatorProcessException, fs_size
from usbcreator.remtimest import RemainingTimeEstimator
from threading import Thread, Event
import logging
from hashlib import md5

if sys.platform != 'win32':
    from usbcreator.misc import MAX_DBUS_TIMEOUT


class progress(Thread):
    def __init__(self, start_free, to_write, device):
        Thread.__init__(self)
        self.start_free = start_free
        self.to_write = to_write
        self.device = device
        self._stopevent = Event()
        # TODO evand 2009-07-24: We should fiddle with the min_age and max_age
        # parameters so this doesn't constantly remind me of the Windows file
        # copy dialog: http://xkcd.com/612/
        self.remtime = RemainingTimeEstimator()

    def progress(self, per, remaining, speed):
        pass

    def run(self):
        try:
            while not self._stopevent.isSet():
                free = fs_size(self.device)[1]
                written = self.start_free - free
                v = int((written / float(self.to_write)) * 100)
                est = self.remtime.estimate(written, self.to_write)
                if callable(self.progress):
                    self.progress(v, est[0], est[1])
                self._stopevent.wait(2)
        except StandardError:
            logging.exception('Could not update progress:')

    def join(self, timeout=None):
        self._stopevent.set()
        Thread.join(self, timeout)

class install(Thread):
    def __init__(self, source, target, persist, device=None,
                 allow_system_internal=False):
        Thread.__init__(self)
        self.source = source
        self.target = target
        self.persist = persist
        self.device = device
        self.allow_system_internal = allow_system_internal
        self._stopevent = Event()
        self.progress_thread = None
        logging.debug('install thread source: %s' % source)
        logging.debug('install thread target: %s' % target)
        logging.debug('install thread persistence: %d' % persist)

    # Signals.

    def success(self):
        pass
    
    def _success(self):
        if self.progress_thread and self.progress_thread.is_alive():
            logging.debug('Shutting down the progress thread.')
            self.progress_thread.join()
        if callable(self.success):
            self.success()

    def failure(self, message=None):
        pass

    def _failure(self, message=None):
        logging.critical(message)
        if self.progress_thread and self.progress_thread.is_alive():
            self.progress_thread.join()
        if callable(self.failure):
            self.failure(message)
        sys.exit(1)

    def progress(self, complete, remaining, speed):
        '''Emitted with an integer percentage of progress completed, time
        remaining, and speed.'''
        pass

    def progress_message(self, message):
        '''Emitted with a translated string like "Installing the
        bootloader..."
        '''
        pass

    def retry(self, message):
        '''Will be called when we need to know if the user wants to try a
        failed operation again.  Must return a boolean value.'''
        pass
    
    def join(self, timeout=None):
        self._stopevent.set()
        Thread.join(self, timeout)

    def check(self):
        if self._stopevent.isSet():
            logging.debug('Asked by the controlling thread to shut down.')
            if self.progress_thread and self.progress_thread.is_alive():
                self.progress_thread.join()
            sys.exit(0)
    
    # Exception catching wrapper.

    def run(self):
        try:
            if os.path.isfile(self.source):
                ext = os.path.splitext(self.source)[1].lower()
                if ext not in ['.iso', '.img']:
                    self._failure(_('The extension "%s" is not supported.') %
                                    ext)
                if ext == '.iso':
                    if sys.platform == 'win32':
                        self.cdimage_install()
                    else:
                        self.install()
                elif ext == '.img':
                    self.diskimage_install()
            else:
                self.install()
            self._success()
        except StandardError, e:
            # TODO evand 2009-07-25: Bring up our own apport-like utility.
            logging.exception('Exception raised:')
            self._failure(_('An uncaught exception was raised:\n%s') % str(e))

    # Helpers for core routines.
    
    def initialize_progress_thread(self):
        logging.debug('initialize_progress_thread')
        if os.path.isfile(self.source):
            s_total = os.path.getsize(self.source)
        else:
            s_total, s_free = fs_size(self.source)
        t_total, t_free = fs_size(self.target)
        # We don't really care if we can't write the entire persistence
        # file.
        if s_total > t_total:
            s_total = s_total / 1024 / 1024
            t_total = t_total / 1024 / 1024
            self._failure(_('Insufficient free space to write the image:\n'
                            '%s\n\n(%d MB) > %s (%d MB)') %
                          (self.source, s_total, self.target, t_total))
        # TODO evand 2009-07-24: Make sure dd.exe doesn't do something
        # stupid, like write past the end of the device.
        damage = s_total + (self.persist * 1024 * 1024)
        self.progress_thread = progress(t_free, damage, self.target)
        self.progress_thread.progress = self.progress
        self.progress_thread.start()
        self.check()
    
    def remove_extras(self):
        logging.debug('remove_extras')
        '''Remove files created by usb-creator.'''
        casper = os.path.join(self.target, 'casper-rw')
        if os.path.exists(casper):
            os.remove(casper)
        syslinux = os.path.join(self.target, 'syslinux')
        if os.path.exists(syslinux):
            shutil.rmtree(syslinux)
        ldlinux = os.path.join(self.target, 'ldlinux.sys')
        if os.path.exists(ldlinux):
            os.remove(ldlinux)

    def install_bootloader(self, grub_location=''):
        logging.debug('install_bootloader')
        self.progress_pulse()
        self.progress_message(_('Installing the bootloader...'))
        message = _('Failed to install the bootloader.')
        if sys.platform == 'win32':
            # TODO evand 2009-07-23: Zero out the MBR.  Check to see if the
            # first 446 bytes are all NULs, and if not, ask the user if they
            # want to wipe it.  Confirm with a USB disk that never has had an
            # OS installed to it.
            opts = '-fma'
            dev = str(os.path.splitdrive(self.target)[0])
            try:
                popen(['syslinux', opts, dev])
            except (USBCreatorProcessException, IOError):
                self._failure(message)
        else:
            import dbus
            try:
                bus = dbus.SystemBus()
                obj = bus.get_object('com.ubuntu.USBCreator',
                                     '/com/ubuntu/USBCreator')
                obj.InstallBootloader(self.device, self.allow_system_internal,
                                      grub_location,
                                      dbus_interface='com.ubuntu.USBCreator',
                                      timeout=MAX_DBUS_TIMEOUT)
            except dbus.DBusException:
                self._failure(message)
        self.progress_pulse_stop()
        self.check()

    def mangle_syslinux(self):
        logging.debug('mangle_syslinux')
        self.progress_message(_('Modifying configuration...'))
        try:
            # Syslinux expects syslinux/syslinux.cfg.
            os.renames(os.path.join(self.target, 'isolinux'),
                    os.path.join(self.target, 'syslinux'))
            os.renames(os.path.join(self.target, 'syslinux', 'isolinux.cfg'),
                    os.path.join(self.target, 'syslinux', 'syslinux.cfg'))
        except (OSError, IOError), e:
            # Failure here probably means the source was not really an Ubuntu
            # image and did not have the files we wanted to move, see
            # <https://bugs.launchpad.net/launchpad-code/+bug/513432>
            self._failure(_('Could not move syslinux files in "%s": %s. '
                'Maybe "%s" is not an Ubuntu image?') %
                (self.target, e, self.source))
        self.check()
        
        # Mangle the configuration files based on the options we've selected.
        import glob
        import lsb_release
        try:
            from debian import debian_support
        except ImportError:
            from debian_bundle import debian_support
        for filename in glob.iglob(os.path.join(self.target, 'syslinux', '*.cfg')):
            if os.path.basename(filename) == 'gfxboot.cfg':
                continue
            f = None
            target_os_ver = None
            our_os_ver = debian_support.Version(
                lsb_release.get_distro_information()['RELEASE'])

            if os.path.exists(os.path.join(self.target, '.disk', 'info')):
                with open(os.path.join(self.target, '.disk', 'info'),'r') as f:
                    contents = f.readline().split()
                if len(contents) > 2:
                    target_os_ver = debian_support.Version(contents[1])
            try:
                f = open(filename, 'r')
                label = ''
                to_write = []
                for line in f.readlines():
                    line = line.strip('\n\t').split()
                    if len(line) and len(line[0]):
                        command = line[0]
                        if command.lower() == 'label':
                            label = line[1].strip()
                        elif command.lower() == 'append':
                            if label not in ('check', 'memtest', 'hd'):
                                if self.persist != 0:
                                    line.insert(1, 'persistent')
                                line.insert(1, 'cdrom-detect/try-usb=true')
                            if label not in ('memtest', 'hd'):
                                line.insert(1, 'noprompt')
                        #OS version specific mangles
                        #The syntax in syslinux changed with the version
                        #shipping in Ubuntu 10.10
                        elif (target_os_ver and our_os_ver and
                              target_os_ver != our_os_ver):
                            lucid = debian_support.Version('10.04')
                            maverick = debian_support.Version('10.10')
                            #10.10 or newer image, burning on 10.04 or lower
                            if (command.lower() == 'ui' and
                                our_os_ver <= lucid and
                                target_os_ver >= maverick):
                                line.remove('ui')
                            #10.04 or earlier image, burning on 10.10 or higher
                            #Currently still broke.
                            #elif (command.lower() == 'gfxboot' and
                            #      our_os_ver >= maverick and
                            #      target_os_ver <= lucid):
                            #    line.insert(0, 'ui')

                    to_write.append(' '.join(line) + '\n')
                f.close()
                f = open(filename, 'w')
                f.writelines(to_write)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                # TODO evand 2009-07-28: Fail?  Warn?
                logging.exception('Unable to add persistence support to %s:' %
                                  filename)
            finally:
                if f:
                    f.close()
        self.check()

    def create_persistence(self):
        logging.debug('create_persistence')
        if self.persist != 0:
            dd_cmd = ['dd', 'if=/dev/zero', 'bs=1M', 'of=%s' %
                      os.path.join(str(self.target), 'casper-rw'),
                      'count=%d' % self.persist]
            if sys.platform == 'win32':
                # XXX evand 2009-07-30: Do not read past the end of the device.
                # See http://www.chrysocome.net/dd for details.
                dd_cmd.append('--size')
            if sys.platform != 'win32':
                mkfs_cmd = ['mkfs.ext3', '-F', '%s/casper-rw' % str(self.target)]
            else:
                # FIXME evand 2009-07-23: Need a copy of mke2fs.exe.
                mkfs_cmd = []
            
            self.progress_message(_('Creating a persistence file...'))
            popen(dd_cmd)
            self.check()
            self.progress_message(_('Creating an ext2 filesystem in the '
                                    'persistence file...'))
            if sys.platform != 'win32':
                popen(mkfs_cmd)
            self.check()

    def sync(self):
        logging.debug('sync')
        # FIXME evand 2009-07-27: Use FlushFileBuffers on the volume (\\.\e:)
        # http://msdn.microsoft.com/en-us/library/aa364439(VS.85).aspx
        if sys.platform != 'win32':
            self.progress_pulse()
            self.progress_message(_('Finishing...'))
            # I would try to unmount the device using umount here to get the
            # pretty GTK+ message, but umount now returns 1 when you do that.
            # We could call udisk's umount method over dbus, but I now think
            # that this would look a lot cleaner if done in the usb-creator UI.
            import dbus
            try:
                bus = dbus.SystemBus()
                obj = bus.get_object('com.ubuntu.USBCreator',
                                     '/com/ubuntu/USBCreator')
                obj.UnmountFile(self.device,
                          dbus_interface='com.ubuntu.USBCreator',
                          timeout=MAX_DBUS_TIMEOUT)
            except dbus.DBusException:
                # TODO: Notify the user.
                logging.exception('Unable to unmount:')

    # Core routines.

    def diskimage_install(self):
        # TODO evand 2009-09-02: Disabled until we can find a cross-platform
        # way of determining dd progress.
        #self.initialize_progress_thread()
        self.progress_message(_('Writing disk image...'))
        failure_msg = _('Could not write the disk image (%s) to the device'
                        ' (%s).') % (self.source, self.device)
        
        cmd = ['dd', 'if=%s' % str(self.source), 'of=%s' % str(self.device),
               'bs=1M']
        if sys.platform == 'win32':
            cmd.append('--size')
            try:
                popen(cmd)
            except USBCreatorProcessException:
                self._failure(failure_msg)
        else:
            import dbus
            try:
                bus = dbus.SystemBus()
                obj = bus.get_object('com.ubuntu.USBCreator',
                                     '/com/ubuntu/USBCreator')
                obj.Image(self.source, self.device, self.allow_system_internal,
                          dbus_interface='com.ubuntu.USBCreator',
                          timeout=MAX_DBUS_TIMEOUT)
            except dbus.DBusException:
                self._failure(failure_msg)

    def cdimage_install(self):
        # Build.

        cmd = ['7z', 'l', self.source]
        output = popen(cmd, stderr=None)
        processing = False
        listing = []
        for line in output.splitlines():
            if line.startswith('----------'):
                processing = not processing
                continue
            if not processing:
                continue
            listing.append(line.split())
        self.check()
        
        # Clear.

        self.progress_message(_('Removing files...'))
        for line in listing:
            length = len(line)
            assert length == 3 or length == 5
            t = os.path.join(self.target, line[-1])
            if os.path.exists(t):
                self.check()
                if os.path.isfile(t):
                    logging.debug('Removing %s' % t)
                    os.unlink(t)
                elif os.path.isdir(t):
                    logging.debug('Removing %s' % t)
                    shutil.rmtree(t)
        self.check()
        self.remove_extras()
        
        self.initialize_progress_thread()

        # Copy.
        
        cmd = ['7z', 'x', self.source, 'md5sum.txt', '-so']
        md5sums = {}
        try:
            output = popen(cmd, stderr=None)
            for line in output.splitlines():
                md5sum, filename = line.split()
                filename = os.path.normpath(filename[2:])
                md5sums[filename] = md5sum
        except StandardError:
            logging.error('Could not generate the md5sum list from md5sum.txt.')

        self.progress_message(_('Copying files...'))
        for line in listing:
            # TODO evand 2009-07-27: Because threads cannot kill other threads
            # in Python, and because it takes a significant amount of time to
            # copy the filesystem.sqaushfs file, we'll end up with a long wait
            # after the user presses the cancel button.  This is far from ideal
            # and should be resolved.
            # One possibility is to deal with subprocesses asynchronously.
            self.check()
            length = len(line)
            if length == 5:
                path = line[4]
                logging.debug('Writing %s' % os.path.join(self.target, path))
                cmd = ['7z', 'x', '-o%s' % self.target, self.source, path]
                popen(cmd)

                # Check md5sum.

                if path in md5sums:
                    targethash = md5()
                    targetfh = None
                    try:
                        targetfh = open(os.path.join(self.target, path), 'rb')
                        while 1:
                            buf = targetfh.read(16 * 1024)
                            if not buf:
                                break
                            targethash.update(buf)
                        if targethash.hexdigest() != md5sums[path]:
                            self._failure(_('md5 checksums do not match.'))
                            # TODO evand 2009-07-27: Recalculate md5 hash.
                    finally:
                        if targetfh:
                            targetfh.close()
                else:
                    logging.warn('md5 hash not available for %s' % path)
                    # TODO evand 2009-07-27: Recalculate md5 hash.
            elif length == 3:
                # TODO evand 2009-07-27: Update mtime with line[0] (YYYY-MM-DD)
                # and line[1] (HH:MM:SS).
                logging.debug('mkdir %s' % os.path.join(self.target, line[2]))
                os.mkdir(os.path.join(self.target, line[2]))

        self.install_efi()

        grub = os.path.join(self.target, 'boot', 'grub', 'i386-pc')
        if os.path.isdir(grub):
            self.install_bootloader(grub)
        else:
            self.install_bootloader()
            self.mangle_syslinux()

        self.create_persistence()
        self.sync()

    def install_efi(self):
        logging.debug('install_efi')
        self.progress_pulse()
        self.progress_message(_('Installing the EFI bootloader...'))
        message = _('Failed to install the EFI bootloader.')
        efi_file = os.path.join(self.target, 'efi', 'boot', 'bootx64.efi')
        efi_image = os.path.join(self.target, 'boot', 'grub', 'efi.img')
        if os.path.exists(efi_file):
            return
        if not os.path.exists(efi_image):
            return
        import dbus
        try:
            bus = dbus.SystemBus()
            obj = bus.get_object('com.ubuntu.USBCreator',
                                 '/com/ubuntu/USBCreator')
            obj.InstallEFI(self.target, efi_image,
                                  dbus_interface='com.ubuntu.USBCreator',
                                  timeout=MAX_DBUS_TIMEOUT)
        except dbus.DBusException:
            self._failure(message)


    def install(self):
        # Some of the code in this function was copied from Ubiquity's
        # scripts/install.py

        self.progress_message(_('Removing files...'))

        # TODO evand 2009-07-23: This should throw up some sort of warning
        # before removing the files.  Add files to self.files, directories to
        # self.directories, and then process each after the warning.  If we can
        # detect that it's Ubuntu (.disk/info), have the warning first say
        # "Would you like to remove Ubuntu VERSION".

        for f in os.listdir(self.source):
            self.check()
            f = os.path.join(self.target, f)
            if os.path.exists(f):
                if os.path.isfile(f):
                    logging.debug('Removing %s' % f)
                    os.unlink(f)
                elif os.path.isdir(f):
                    logging.debug('Removing %s' % f)
                    shutil.rmtree(f)
        self.remove_extras()
        self.check()
        
        self.initialize_progress_thread()

        self.progress_message(_('Copying files...'))
        for dirpath, dirnames, filenames in os.walk(self.source):
            sp = dirpath[len(self.source.rstrip(os.path.sep))+1:]
            for name in dirnames + filenames:
                relpath = os.path.join(sp, name)
                sourcepath = os.path.join(self.source, relpath)
                targetpath = os.path.join(self.target, relpath)
                logging.debug('Writing %s' % targetpath)
                st = os.lstat(sourcepath)
                mode = stat.S_IMODE(st.st_mode)
                if stat.S_ISLNK(st.st_mode):
                    if os.path.lexists(targetpath):
                        os.unlink(targetpath)
                    linkto = os.readlink(sourcepath)
                    # XXX evand 2009-07-24: VFAT does not have support for
                    # symlinks.
                    logging.warn('Tried to symlink %s -> %s\n' %
                                 (linkto, targetpath))
                elif stat.S_ISDIR(st.st_mode):
                    if not os.path.isdir(targetpath):
                        os.mkdir(targetpath, mode)
                elif stat.S_ISCHR(st.st_mode):
                    os.mknod(targetpath, stat.S_IFCHR | mode, st.st_rdev)
                elif stat.S_ISBLK(st.st_mode):
                    os.mknod(targetpath, stat.S_IFBLK | mode, st.st_rdev)
                elif stat.S_ISFIFO(st.st_mode):
                    os.mknod(targetpath, stat.S_IFIFO | mode)
                elif stat.S_ISSOCK(st.st_mode):
                    os.mknod(targetpath, stat.S_IFSOCK | mode)
                elif stat.S_ISREG(st.st_mode):
                    if os.path.exists(targetpath):
                        os.unlink(targetpath)
                    self.copy_file(sourcepath, targetpath)

        self.install_efi()

        grub = os.path.join(self.target, 'boot', 'grub', 'i386-pc')
        if os.path.isdir(grub):
            self.install_bootloader(grub)
        else:
            self.install_bootloader()
            self.mangle_syslinux()

        self.create_persistence()
        self.sync()
    
    def copy_file(self, sourcepath, targetpath):
        self.check()
        sourcefh = None
        targetfh = None
        # TODO evand 2009-07-24: Allow the user to disable this with a command
        # line option.
        md5_check = True
        try:
            while 1:
                sourcefh = open(sourcepath, 'rb')
                targetfh = open(targetpath, 'wb')
                if md5_check:
                    sourcehash = md5()
                while 1:
                    self.check()
                    buf = sourcefh.read(16 * 1024)
                    if not buf:
                        break
                    try:
                        targetfh.write(buf)
                    except IOError:
                        # TODO evand 2009-07-23: Catch exceptions around the
                        # user removing the flash drive mid-write.  Give the
                        # user the option of selecting the re-inserted disk
                        # from a drop down list and continuing.
                        # TODO evand 2009-07-23: Fail more gracefully.
                        self._failure(_('Could not read from %s') % self.source)
                    if md5_check:
                        sourcehash.update(buf)

                if not md5_check:
                    break
                targethash = md5()
                # TODO evand 2009-07-25: First check the MD5SUMS.txt file for
                # the hash.  If it exists, and matches the source hash,
                # continue on. If it exists and does not match the source hash,
                # or it does not exist, calculate a new hash and compare again.
                targetfh.close()
                targetfh = open(targetpath, 'rb')
                while 1:
                    buf = targetfh.read(16 * 1024)
                    if not buf:
                        break
                    targethash.update(buf)
                if targethash.digest() != sourcehash.digest():
                    if targetfh:
                        targetfh.close()
                    if sourcefh:
                        sourcefh.close()
                    logging.error('Checksums do not match.')
                    if callable(self.retry):
                        response = self.retry(_('Checksums do not match.  Retry?'))
                    else:
                        respose = False
                    if not response:
                        self._failure(_('Checksums do not match.'))
                else:
                    break
        finally:
            if targetfh:
                targetfh.close()
            if sourcefh:
                sourcefh.close()
