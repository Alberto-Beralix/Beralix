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

'''Abstract user interface, which provides all logic and strings.

Concrete implementations need to implement a set of abstract presentation
functions with an appropriate toolkit.
'''

import gettext, optparse, urllib2, tempfile, sys, time, os, threading, signal

import dbus
import dbus.service
import dbus.mainloop.glib

try:
    from gi.repository import AppIndicator3 as AppIndicator
except:
    # UIs will need to implement their own status icon if app indicator isn't
    # available
    pass

from jockey.oslib import OSLib
from backend import UnknownHandlerException, PermissionDeniedByPolicy, \
    BackendCrashError, convert_dbus_exceptions, \
    dbus_sync_call_signal_wrapper, Backend, DBUS_BUS_NAME

def bool(str):
    '''Convert backend encoding of a boolean to a real boolean.'''

    if str == 'True':
        return True
    assert str == 'False'
    return False

# Avoid having to do .encode('UTF-8') everywhere. This is a pain; I wish
# Python supported something like "sys.stdout.encoding = 'UTF-8'".
def fix_stdouterr():
    import codecs
    import locale
    def null_decode(input, errors='strict'):
        return input, len(input)
    encoding = locale.getpreferredencoding()
    # happens for e. g. LC_MESSAGES=*.UTF-8 LANG=C (forgetting to set LC_CTYPE
    # as well); force UTF-8 in that case
    if encoding == 'ANSI_X3.4-1968':
        encoding = 'UTF-8'
    sys.stdout = codecs.EncodedFile(sys.stdout, encoding)
    sys.stdout.decode = null_decode
    sys.stderr = codecs.EncodedFile(sys.stderr, encoding)
    sys.stderr.decode = null_decode

class AbstractUI(dbus.service.Object):
    '''Abstract user interface.

    This encapsulates the entire program logic and all strings, but does not
    implement any concrete user interface.
    '''
    def __init__(self):
        '''Initialize system.
        
        This parses command line arguments, detects available hardware,
        and already installed drivers and handlers.
        '''
        gettext.install('jockey', unicode=True)

        (self.argv_options, self.argv_args) = self.parse_argv()
        fix_stdouterr()

        if not OSLib.inst:
            OSLib.inst = OSLib(client_only=not self.argv_options.no_dbus,
                    target_kernel=self.argv_options.kernel)

        if self.argv_options.check:
            time.sleep(self.argv_options.check)

        self.init_strings()

        self._dbus_iface = None
        self.dbus_server_main_loop = None
        self.have_ui = False
        self.search_only = False
        self.current_search = (None, None) # query, result

        # make Control-C work properly
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def backend(self):
        '''Return D-BUS backend client interface.

        This gets initialized lazily.

        Set self.search_only to True to suppress a full system hardware
        detection, especially if you use only search_driver() to
        find a remote driver for a selected, already detected device.
        '''
        if self._dbus_iface is None:
            try:
                if self.argv_options.no_dbus:
                    self._dbus_iface = Backend()
                else:
                    self._dbus_iface = Backend.create_dbus_client()
            except Exception as e:
                if hasattr(e, '_dbus_error_name') and e._dbus_error_name == \
                    'org.freedesktop.DBus.Error.FileNotFound':
                    if self.have_ui:
                        self.error_message(self._('Cannot connect to D-BUS'),
                            str(e))
                    else:
                        self.error_msg(str(e))
                    sys.exit(1)
                else:
                    raise
            self._check_repositories()
            self._call_progress_dialog(
                self._('Searching for available drivers...'),
                self.search_only and self._dbus_iface.db_init or self._dbus_iface.detect, 
                timeout=600)
        else:
            # handle backend timeouts
            try:
                self._dbus_iface.handler_info(' ')
            except Exception as e:
                if hasattr(e, '_dbus_error_name') and e._dbus_error_name == \
                    'org.freedesktop.DBus.Error.ServiceUnknown':
                    self._dbus_iface = Backend.create_dbus_client()
                    self._check_repositories()
                    self._call_progress_dialog(
                        self._('Searching for available drivers...'),
                        self.search_only and self._dbus_iface.db_init or self._dbus_iface.detect, 
                        timeout=600)

        return self._dbus_iface

    def _(self, str, convert_keybindings=False):
        '''Keyboard accelerator aware gettext() wrapper.
        
        This optionally converts keyboard accelerators to the appropriate
        format for the frontend.

        All strings in the source code should use the '_' prefix for key
        accelerators (like in GTK). For inserting a real '_', use '__'.
        '''
        result = _(str)

        if convert_keybindings:
            result = self.convert_keybindings(result)

        return result

    def init_strings(self):
        '''Initialize all static strings which are used in UI implementations.'''

        self.string_handler = self._('Component')
        self.string_button_enable = self._('_Enable', True)
        self.string_button_disable = self._('_Disable', True)
        self.string_enabled = self._('Enabled')
        self.string_disabled = self._('Disabled')
        self.string_status = self._('Status')
        self.string_restart = self._('Needs computer restart')
        self.string_in_use = self._('In use')
        self.string_not_in_use = self._('Not in use')
        self.string_license_label = self._('License:')
        self.string_details = self._('details')
        # this is used in the GUI and in --list output to denote free/restricted drivers
        self.string_free = self._('Free')
        # this is used in the GUI and in --list output to denote free/restricted drivers
        self.string_restricted = self._('Proprietary')
        self.string_download_progress_title = self._('Download in progress')
        self.string_unknown_driver = self._('Unknown driver')
        self.string_unprivileged = self._('You are not authorized to perform this action.')
        # %s is the name of the operating system
        self.string_support_certified = self._('Tested by the %s developers') % OSLib.inst.os_vendor
        # %s is the name of the operating system
        self.string_support_uncertified = self._('Not tested by the %s developers') % OSLib.inst.os_vendor
        # this is used when one version of a driver is recommended over others
        self.string_recommended = self._('Recommended')
        self.string_license_dialog_title = self._('License Text for Device Driver')
        self.string_install_drivers = self._('Install Drivers')

    def main_window_title(self):
        '''Return an appropriate translated window title.

        This might depend on the mode the program is called (e. g. showing only
        free drivers, only restricted ones, etc.).
        '''
        if self.argv_options.mode == 'nonfree':
            return self._('Restricted Additional Drivers')
        else:
            return self._('Additional Drivers')

    def main_window_text(self):
        '''Return a tuple (heading, subtext) of main window texts.

        This changes depending on whether restricted or free drivers are
        used/available, or if a search is currently running. Thus the UI should
        update it whenever it changes a handler.
        '''
        if self.current_search[0]:
            return (self._('Driver search results'),
                self.hwid_to_display_string(self.current_search[0]))

        proprietary_in_use = False
        proprietary_available = False

        for h_id in self.backend().available(self.argv_options.mode):
            info = self.backend().handler_info(h_id)
            #print 'main_window_text: info for', h_id, info
            if not bool(info['free']):
                proprietary_available = True
                if bool(info['used']):
                    proprietary_in_use = True
                    break

        if proprietary_in_use:
            heading = self._('Proprietary drivers are being used to make '
                    'this computer work properly.')
        else:
            heading = self._('No proprietary drivers are in use on this system.')

        if proprietary_available:
            subtext = self._(
            # %(os)s stands for the OS name. Prefix it or suffix it,
            # but do not replace it.
            'Proprietary drivers do not have public source code that %(os)s '
            'developers are free to modify. Security updates and corrections '
            'depend solely on the responsiveness of the manufacturer. '
            '%(os)s cannot fix or improve these drivers.') % {'os': OSLib.inst.os_vendor}
        else:
            subtext = ''

        return (heading, subtext)

    def get_handler_category(self, handler_id):
        '''Return string for handler category.'''

        if handler_id.startswith('xorg:'):
            return self._('Graphics driver')
        elif handler_id.startswith('firmware:'):
            return self._('Firmware')
        else:
            return self._('Device driver')

    def get_ui_driver_name(self, handler_info):
        '''Return handler name, as it should be presented in the UI.
        
        This cares about translation, as well as tagging recommended drivers.
        '''
        result = handler_info['name']
        result = self._(result)
        if 'version' in handler_info:
            result += ' (%s)' % (self._('version %s') % handler_info['version'])
        if bool(handler_info['recommended']):
            result += ' [%s]' % self.string_recommended
        return result

    # TODO: this desperately needs test cases
    def get_ui_driver_info(self, handler_id):
        '''Get strings and icon types for displaying driver information.
        
        If handler_id is None, this returns empty strings, suitable for
        displaying if no driver is selected, and "None" for the bool values,
        (UIs should disable the corresponding UI element then).
        
        This returns a mapping with the following keys: name (string),
        description (string), certified (bool, for icon), certification_label
        (label string), free (bool, for icon), license_label
        (Free/Proprietary, label string), license_text (string, might be
        empty), enabled (bool, for icon), used (bool), needs_reboot(bool),
        status_label (label string), button_toggle_label (string)'''

        if not handler_id:
            return { 'name': '', 'description': '', 'free': None, 
                'enabled': None, 'used': None, 'license_text': '',
                'status_label': '', 'license_label': '', 'certified': None,
                'certification_label': '', 'button_toggle_label': None,
            }

        info = self.backend().handler_info(handler_id)

        result = {
            'name': self.get_ui_driver_name(info),
            'description': self._get_description_rationale_text(info),
            'free': bool(info['free']),
            'enabled': bool(info['enabled']),
            'used': bool(info['used']),
            'needs_reboot': False,
            'license_text': info.get('license', '')
        }

        if result['free']:
            result['license_label'] = self.string_free
        else:
            result['license_label'] = self.string_restricted

        # TODO: support distro certification of third party drivers
        if 'repository' not in info:
            result['certified'] = True 
            result['certification_label'] = self.string_support_certified
        else:
            result['certified'] = False 
            result['certification_label'] = self.string_support_uncertified

        if result['enabled']:
            if 'package' in info:
                result['button_toggle_label'] = self._('_Remove', True)
            else:
                result['button_toggle_label'] = self._('_Deactivate', True)
            if result['used']:
                result['status_label'] = self._('This driver is activated and currently in use.')
            else:
                if bool(info['changed']):
                    result['needs_reboot'] = True
                    result['status_label'] = self._('You need to restart the computer to activate this driver.')
                else:
                    result['status_label'] = self._('This driver is activated but not currently in use.')
        else:
            result['button_toggle_label'] = self._('_Activate', True)
            if result['used']:
                if bool(info['changed']):
                    result['needs_reboot'] = True
                    result['status_label'] = self._('This driver was just disabled, but is still in use.')
                else:
                    result['status_label'] = self._('A different version of this driver is in use.')
            else:
                result['status_label'] = self._('This driver is not activated.')

        return result

    def parse_argv(self):
        '''Parse command line arguments, and return (options, args) pair.'''

        # --check can have an optional numeric argument which sleeps for the
        # given number of seconds; this is mostly useful for the XDG autostart
        # .desktop file, to not do expensive operations right at session start
        def check_option_callback(option, opt_str, value, parser):
            if len(parser.rargs) > 0 and parser.rargs[0].isdigit():
                setattr(parser.values, 'check', int(parser.rargs.pop(0)))
            else:
                setattr(parser.values, 'check', 0)

        parser = optparse.OptionParser()
        parser.set_defaults(check=None)
        parser.add_option ('-c', '--check', action='callback',
                callback=check_option_callback,
                help=self._('Check for newly used or usable drivers and notify the user.'))
        parser.add_option ('-u', '--update-db', action='store_true',
                dest='update_db', default=False,
                help=self._('Query driver databases for newly available or updated drivers.'))
        parser.add_option ('-l', '--list', action='store_true',
                dest='list', default=False,
                help=self._('List available drivers and their status.'))
        parser.add_option ('-a', '--auto-install', action='store_true',
                dest='auto_install', default=False,
                help=self._('Enable drivers that can be automatically installed.'))
        parser.add_option ('--hardware-ids', action='store_true',
                dest='list_hwids', default=False,
                help=self._('List hardware identifiers from this system.'))
        parser.add_option ('-e', '--enable', type='string',
                dest='enable', default=None, metavar='DRIVER',
                help=self._('Enable a driver'))
        parser.add_option ('-d', '--disable', type='string',
                dest='disable', default=None, metavar='DRIVER',
                help=self._('Disable a driver'))
        parser.add_option ('--confirm', action='store_true',
                dest='confirm', default=False,
                help=self._('Ask for confirmation for --enable/--disable'))
        parser.add_option ('-C', '--check-composite', action='store_true',
                dest='check_composite', default=False,
                help=self._('Check if there is a graphics driver available that supports composite and offer to enable it'))
        parser.add_option ('-m', '--mode',
                type='choice', dest='mode', default='any',
                choices=['free', 'nonfree', 'any'],
                metavar='free|nonfree|any',
                help=self._('Only manage free/nonfree drivers. By default, all'
                ' available drivers with any license are presented.'))
        parser.add_option ('--dbus-server', action='store_true',
                dest='dbus_server', default=False,
                help=self._('Run as session D-BUS server.'))
        parser.add_option ('--no-dbus', action='store_true', default=False,
                help=self._('Do not use D-BUS for communicating with the backend. Needs root privileges.'))
        parser.add_option ('-k', '--kernel', type='string',
                help=_('Use a different target kernel version than the currently running one. This is only relevant with --no-dbus.'))

        #parser.add_option ('--debug', action='store_true',
        #        dest='debug', default=False,
        #        help=self._('Enable debugging messages.'))

        (opts, args) = parser.parse_args()

        return (opts, args)

    def run(self):
        '''Evaluate command line arguments and do the appropriate action.

        If no argument was specified, this starts the interactive UI.
        
        This returns the exit code of the program.
        '''
        # first, modes without GUI
        if self.argv_options.update_db:
            self.backend().update_driverdb()
            return 0
        elif self.argv_options.list:
            self.list()
            return 0
        elif self.argv_options.list_hwids:
            self.list_hwids()
            return 0
        elif self.argv_options.dbus_server:
            self.dbus_server()
            return 0
        elif self.argv_options.check is not None:
            if self.check():
                return 0
            else:
                return 1

        # all other modes involve the GUI, so load it
        self.ui_init()
        self.have_ui = True

        if self.argv_options.enable:
            if self.set_handler_enable(self.argv_options.enable, 'enable',
                self.argv_options.confirm, False):
                return 0
            else:
                return 1
        elif self.argv_options.disable:
            if self.set_handler_enable(self.argv_options.disable, 'disable',
                self.argv_options.confirm, False):
                return 0
            else:
                return 1
        elif self.argv_options.check_composite:
            if self.check_composite():
                return 0
            else:
                return 1

        elif self.argv_options.auto_install:
            ret = 0
            for h_id in self.backend().available(self.argv_options.mode):
                i = self.backend().handler_info(h_id)
                if bool(i['auto_install']) and not bool(i['enabled']):
                    if not self.set_handler_enable(i['id'], 'enable',
                        self.argv_options.confirm, False):
                        ret = 1
            return ret

        # start the UI
        self.ui_show_main()
        res = self.ui_main_loop()
        self.backend().shutdown()
        return res

    def list(self):
        '''Print a list of available handlers and their status to stdout.'''

        for h_id in self.backend().available(self.argv_options.mode):
            i = self.backend().handler_info(h_id)
            print '%s - %s (%s, %s, %s)%s' % (
                h_id, self._(i['name']),
                bool(i['free']) and self.string_free or self.string_restricted,
                bool(i['enabled']) and self.string_enabled or self.string_disabled,
                bool(i['used']) and self.string_in_use or self.string_not_in_use,
                bool(i['auto_install']) and ' [auto-install]' or '')

    def list_hwids(self):
        '''Print a list of available handlers and their status to stdout.'''

        for h_id in self.backend().get_hardware():
            print h_id

    def check(self):
        '''Notify the user about newly used or available drivers since last check().
        
        Return True if any new driver is available which is not yet enabled.
        '''
        # if the user is running Jockey with package installation or another
        # long-running task in parallel, the automatic --check invocation will
        # time out on this.
        try:
            convert_dbus_exceptions(self.backend)
        except Exception as e:
            print >> sys.stderr, 'Cannot connect to backend, is it busy?\n', e
            return False

        try:
            (new_used, new_avail) = convert_dbus_exceptions(
                    self.backend().new_used_available, self.argv_options.mode)
        except PermissionDeniedByPolicy:
            self.error_msg(self.string_unprivileged)
            return False

        # any new restricted drivers? also throw out the non-announced ones
        restricted_available = False
        for h_id in set(new_avail): # create copy
            info = self.backend().handler_info(h_id)
            if not bool(info['announce']):
                new_avail.remove(h_id)
                continue
            if not bool(info['free']):
                restricted_available = True
                break

        # throw out newly used free drivers; no need for education here
        for h_id in new_used + []: # create copy for iteration
            if bool(self.backend().handler_info(h_id)['free']):
                new_used.remove(h_id)

        notified = False

        # launch notifications if anything remains
        if new_avail or new_used:
            # defer UI initialization until here, since --check should not
            # spawn a progress dialog for searching drivers
            self.ui_init()
            self.have_ui = True

        if new_avail:
            if restricted_available:
                self.ui_notification(self._('Restricted drivers available'),
                    self._('In order to use your hardware more efficiently, you'
                    ' can enable drivers which are not free software.'))
            else:
                self.ui_notification(self._('New drivers available'),
                    self._('There are new or updated drivers available for '
                    'your hardware.'))
            notified = True
        elif new_used:
            self.ui_notification(self._('New restricted drivers in use'),
                # %(os)s stands for the OS name. Prefix it or suffix it,
                # but do not replace it.
                self._('In order for this computer to function properly, %(os)s is '
                'using driver software that cannot be supported by %(os)s.') % 
                    {'os': OSLib.inst.os_vendor})
            notified = True

        if notified:
            # we need to stay in the main loop so that the tray icon stays
            # around
            self.ui_main_loop()
            self.backend().shutdown()

        return len(new_avail) > 0

    def check_composite(self):
        '''Check for a composite-enabling X.org driver.

        If one is available and not installed, offer to install it and return
        True if installation succeeded. Otherwise return False.
        '''

        h_id = self.backend().check_composite()

        if h_id:
            self.set_handler_enable(h_id, 'enable', self.argv_options.confirm)
            return bool(self.backend().handler_info(h_id)['enabled'])

        self.error_msg(self._('There is no available graphics driver for your system which supports the composite extension, or the current one already supports it.'))
        return False

    def _install_progress_handler(self, phase, cur, total):
        if not self._install_progress_shown:
            self.ui_progress_start(self._('Additional Drivers'), 
                self._('Downloading and installing driver...'), total)
            self._install_progress_shown = True
        self.ui_progress_update(cur, total)
        self.ui_idle()

    def _remove_progress_handler(self, cur, total):
        if not self._install_progress_shown:
            self.ui_progress_start(self._('Additional Drivers'), 
                self._('Removing driver...'), total)
            self._install_progress_shown = True
        self.ui_progress_update(cur, total)
        self.ui_idle()

    def _repository_progress_handler(self, cur, total):
        if not self._repository_progress_shown:
            self.ui_progress_start(self._('Additional Drivers'), 
                self._('Downloading and updating package indexes...'), total)
            self._repository_progress_shown = True
        self.ui_progress_update(cur, total)
        self.ui_idle()

    def set_handler_enable(self, handler_id, action, confirm, gui=True):
        '''Enable, disable, or toggle a handler.

        action can be 'enable', 'disable', or 'toggle'. If confirm is True,
        this first presents a confirmation dialog. Then a progress dialog is
        presented for installation/removal of the handler.

        If gui is True, error messags and install progress will be shown
        in the GUI, otherwise just printed to stderr (CLI mode).

        Return True if anything was changed and thus the UI needs to be
        refreshed.
        '''
        try:
            i = convert_dbus_exceptions(self.backend().handler_info, handler_id)
        except UnknownHandlerException:
            self.error_msg('%s: %s' % (self.string_unknown_driver, handler_id))
            self.error_msg(self._('Use --list to see available drivers'))
            return False

        # determine new status
        if action == 'enable':
            enable = True
        elif action == 'disable':
            enable = False
        elif action == 'toggle':
            enable = not bool(i['enabled'])
        else:
            raise ValueError('invalid action %s; allowed are enable, disable, toggle')

        # check if we can change at all
        if 'can_change' in i:
            msg = i['can_change']
            if gui:
                self.error_message(self._('Cannot change driver'),
                    self._(msg))
            else:
                self.error_msg(self._(msg))
            return False

        # actually something to change?
        if enable == bool(i['enabled']):
            return False

        if confirm:
            # construct and ask confirmation question
            if enable:
                title = self._('Enable driver?')
                action = self.string_button_enable
            else:
                title = self._('Disable driver?')
                action = self.string_button_disable
            n = i['name'] # self._(i['name']) is misinterpreted by xgettext
            if not self.confirm_action(title, self._(n), 
                self._get_description_rationale_text(i), action):
                return False

        # go
        try:
            if gui:
                try:
                    self._install_progress_shown = False
                    convert_dbus_exceptions(dbus_sync_call_signal_wrapper, self.backend(),
                        'set_enabled',
                        {'install_progress': self._install_progress_handler, 
                         'remove_progress': self._remove_progress_handler}, 
                        handler_id, enable)
                finally:
                    if self._install_progress_shown:
                        self.ui_progress_finish()
            else:
                convert_dbus_exceptions(dbus_sync_call_signal_wrapper,
                        self.backend(), 'set_enabled', {}, handler_id, enable)
        except PermissionDeniedByPolicy:
            self.error_message('', self.string_unprivileged)
            return False
        except BackendCrashError:
            self._dbus_iface = None
            self.error_message('', '%s\n\n  ubuntu-bug jockey-common\n\n%s' % (
                self._('Sorry, the Jockey backend crashed. Please file a bug at:'),
                self._('Trying to recover by restarting backend.')))
            return False
        except SystemError as e:
            self.error_message('', str(e).strip().splitlines()[-1])
            return False

        newstate = bool(self.backend().handler_info(handler_id)['enabled'])

        if enable and not newstate:
            self.error_message('', '%s\n\n%s: /var/log/jockey.log' % (
                self._('Sorry, installation of this driver failed.'),
                self._('Please have a look at the log file for details')))

        return i['enabled'] != newstate

    def _get_description_rationale_text(self, h_info):
        d = h_info.get('description', '')
        r = h_info.get('rationale', '')
        # opportunistic translation (shipped example drivers have translations)
        if d:
            d = self._(d)
        if r:
            r = self._(r)

        if d and r:
            return d.strip() + '\n\n' + r
        elif d:
            return d
        elif r:
            return r
        else:
            return ''

    def download_url(self, url, filename=None, data=None):
        '''Download an URL into a local file, and display a progress dialog.
        
        If filename is not given, a temporary file will be created.

        Additional POST data can be submitted for HTTP requests in the data
        argument (see urllib2.urlopen).

        Return (filename, headers) tuple, or (None, headers) if the user
        cancelled the download.
        '''
        block_size = 8192
        current_size = 0
        try:
            f = urllib2.urlopen(url)
        except Exception as e:
            self.error_message(self._('Download error'), str(e))
            return (None, None)
        headers = f.info()

        if 'Content-Length' in headers:
            total_size = int(headers['Content-Length'])
        else:
            total_size = -1

        self.ui_progress_start(self.string_download_progress_title, url,
            total_size)

        if filename:
            tfp = open(filename, 'wb')
            result_filename = filename
        else:
            (fd, result_filename) = tempfile.mkstemp()
            tfp = os.fdopen(fd, 'wb')

        try:
            while current_size < total_size:
                block = f.read(block_size)
                tfp.write (block)
                current_size += len(block)
                # if True, user canceled download
                if self.ui_progress_update(current_size, total_size):
                    # if we created a temporary file, clean it up
                    if not filename:
                        os.unlink(result_filename)
                    result_filename = None
                    break
        finally:
            tfp.close()
            f.close()
            self.ui_progress_finish()

        return (result_filename, headers)

    @classmethod
    def error_msg(klass, msg):
        '''Print msg to stderr, and intercept IOErrors.'''

        try:
            print >> sys.stderr, msg
        except IOError:
            pass

    def _call_progress_dialog(self, message, fn, *args, **kwargs):
        '''Call fn(*args, **kwargs) while showing a progress dialog.'''

        if self.argv_options.no_dbus:
            try:
                del kwargs['timeout']
            except KeyError:
                pass

        if not self.have_ui:
            return fn(*args, **kwargs)

        progress_shown = False
        t_fn = threading.Thread(None, fn, 'thread_call_progress_dialog',
            args, kwargs)
        t_fn.start()
        while True:
            t_fn.join(0.2)
            if not t_fn.isAlive():
                break
            if not progress_shown:
                progress_shown = True
                self.ui_progress_start(self._('Additional Drivers'), message, -1)
            if self.ui_progress_update(-1, -1):
                sys.exit(1) # cancel
            self.ui_idle()
        if progress_shown:
            self.ui_progress_finish()
            self.ui_idle()

    def get_displayed_handlers(self):
        '''Return the list of displayed handler IDs.

        This can either be a list of drivers which match your system, or which
        match a search_driver() invocation.
        '''
        if self.current_search[0]:
            return self.current_search[1]
        else:
            return self.backend().available(self.argv_options.mode)

    def hwid_to_display_string(self, hwid):
        '''Convert a type:value hardware ID string to a human friendly text.'''

        try:
            (type, value) = hwid.split(':', 1)
        except ValueError:
            return hwid

        if type == 'printer_deviceid':
            try:
                import cupshelpers
            except ImportError:
                return hwid
            info = cupshelpers.parseDeviceID(value)
            return info['MFG'] + ' ' + info['MDL']

        return hwid

    def _check_repositories(self):
        '''Check if we have package repositories, and if not, offer to update.'''

        if self._dbus_iface.has_repositories():
            return

        if self.have_ui:
            success = False
            try:
                self._repository_progress_shown = False
                success = convert_dbus_exceptions(dbus_sync_call_signal_wrapper,
                        self._dbus_iface, 'update_repository_indexes',
                        {'repository_update_progress':
                            self._repository_progress_handler})
            finally:
                if self._repository_progress_shown:
                    self.ui_progress_finish()

            # check success
            if not success:
                self.error_message('', self._(
                    'Downloading package indexes failed, please check your network status. '
                    'Most drivers will not be available.'))
        else:
            # This happens when running in --check mode. We do not particularly
            # care about success here.
            convert_dbus_exceptions(self._dbus_iface.update_repository_indexes)


    #
    # Session D-BUS server methods
    # 

    DBUS_INTERFACE_NAME = 'com.ubuntu.DeviceDriver'

    def dbus_server(self):
        '''Run session D-BUS server backend.'''

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        dbus_name = dbus.service.BusName(DBUS_BUS_NAME, bus)

        dbus.service.Object.__init__(self, bus, '/GUI')
        from gi.repository import GObject
        self.dbus_server_main_loop = GObject.MainLoop()
        self.dbus_server_main_loop.run()

    @classmethod
    def get_dbus_client(klass):
        '''Return a dbus.Interface object for the server.'''

        obj = dbus.SessionBus().get_object(DBUS_BUS_NAME, '/GUI')
        return dbus.Interface(obj, AbstractUI.DBUS_INTERFACE_NAME)

    @dbus.service.method(DBUS_INTERFACE_NAME,
        in_signature='s', out_signature='bas', sender_keyword='sender',
        connection_keyword='conn')
    def search_driver(self, hwid, sender=None, conn=None):
        '''Search configured driver DBs for a particular hardware component.

        The hardware component is described as HardwareID type and value,
        separated by a colon. E. g.  "modalias:pci:12345" or
        "printer_deviceid:MFG:FooTech;MDL:X-12;CMD:GDI". This searches the
        enabled driver databases for a matching driver. If it finds one, it
        offers it to the user. This returns a pair (success, files); where
        'success' is True if a driver was found, acknowledged by the user, and
        installed, otherwise False; "files" is the list of files shipped by the
        newly installed packages (useful for e. g. printer drivers to get a
        list of PPDs to check).
        '''
        self.ui_init() # we want to show progress
        self.have_ui = True
        self.search_only = False
        # Ubuntu does not currently support local printer driver handlers, so
        # let's speed up the lookup of remote ones
        if hwid.startswith('printer_deviceid:'):
            self.search_only = True

        b = self.backend()

        def _srch():
            # TODO: this is a hack: when calling through D-BUS, specify a
            # timeout, when calling a local object, the timeout parameter does
            # not exist
            if hasattr(b, '_locations'):
                drivers = self._dbus_iface.search_driver(hwid, timeout=600)
            else:
                drivers = b.search_driver(hwid)
            self.current_search = (hwid, drivers)

        self._call_progress_dialog(self._(
            'Searching driver for %s...') % self.hwid_to_display_string(hwid),
            _srch)

        result = False
        files = []

        if self.current_search[1]:
            self.ui_show_main()
            self.ui_main_loop()
            for d in self.current_search[1]:
                info = self.backend().handler_info(d)
                if bool(info['enabled']) and bool(info['changed']):
                    result = True
                    if 'package' in info:
                        files += self.backend().handler_files(d)

        # we are D-BUS activated, so let's free resources early
        if self.dbus_server_main_loop:
            self.dbus_server_main_loop.quit()

        # in case we do another operation after that, we need to reinitialize
        # the backend
        if self.search_only:
            self.search_only = False
            self._dbus_iface = None
        return (result, files)

    #
    # The following methods must be implemented in subclasses
    # 

    def convert_keybindings(self, str):
        '''Convert keyboard accelerators to the particular UI's format.

        The abstract UI and drivers use the '_' prefix to mark a keyboard
        accelerator.

        A double underscore ('__') is converted to a real '_'.'''

        raise NotImplementedError('subclasses need to implement this')

    def ui_init(self):
        '''Initialize UI.

        This should load the GUI components, such as GtkBuilder files, but not
        show the main window yet; that is done by ui_show_main().
        '''
        raise NotImplementedError('subclasses need to implement this')
        
    def ui_show_main(self):
        '''Show main window.

        This should set up presentation of handlers and show the main
        window. This must be called after ui_init().
        '''
        raise NotImplementedError('subclasses need to implement this')

    def ui_main_loop(self):
        '''Main loop for the user interface.
        
        This should return if the user wants to quit the program, and return
        the exit code.
        '''
        raise NotImplementedError('subclasses need to implement this')

    def error_message(self, title, text):
        '''Present an error message box.'''

        raise NotImplementedError('subclasses need to implement this')

    def confirm_action(self, title, text, subtext=None, action=None):
        '''Present a confirmation dialog.

        If action is given, it is used as button label instead of the default
        'OK'.  Return True if the user confirms, False otherwise.
        '''
        raise NotImplementedError('subclasses need to implement this')

    def ui_notification(self, title, text):
        '''Present a notification popup.

        This should preferably create a tray icon. Clicking on the tray icon or
        notification should run the GUI.

        This method will attempt to instantiate an appindicator to return to
        both the GTK and KDE children.  If whatever reason it fails (missing
        python-appindicator) then it should behave as it did before.
        '''
        try:
            indicator = AppIndicator.Indicator.new('jockey', 'jockey',
                    AppIndicator.IndicatorCategory.HARDWARE)
        except Exception as e:
            raise NotImplementedError('appindicator support not available: %s' \
                '\nsubclasses need to implement this' % str(e))
        
        indicator.set_status(AppIndicator.IndicatorStatus.ATTENTION)
        return indicator

    def ui_idle(self):
        '''Process pending UI events and return.

        This is called while waiting for external processes such as package
        installers.
        '''
        raise NotImplementedError('subclasses need to implement this')

    def ui_progress_start(self, title, description, total):
        '''Create a progress dialog.'''

        raise NotImplementedError('subclasses need to implement this')

    def ui_progress_update(self, current, total):
        '''Update status of current progress dialog.
        
        current/total specify the number of steps done and total steps to
        do, or -1 if it cannot be determined. In this case the dialog should
        display an indeterminated progress bar (bouncing back and forth).

        This should return True to cancel, and False otherwise.
        '''
        raise NotImplementedError('subclasses need to implement this')

    def ui_progress_finish(self):
        '''Close the current progress dialog.'''

        raise NotImplementedError('subclasses need to implement this')
