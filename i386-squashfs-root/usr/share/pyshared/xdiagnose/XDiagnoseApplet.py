import os
import sys
import subprocess
import shutil
from gi.repository import Gtk
import re
from string import split

from xdiagnose.config_update import (
    config_update,
    config_dict,
    safe_backup,
    )
from xdiagnose.errors_treeview import ErrorsTreeView

class XDiagnoseApplet:
    def __init__(self):
        self.__enable_debugging = None
        self.__disable_splash = None
        self.__disable_vesafb = None
        self.__disable_pat = None
#        self.__disable_grub_graphics = None
#        self.__grub_gfxpayload_linux = None
        self.is_running = True
        self.dialog = Gtk.Dialog("X Diagnostics Settings", None, 0, (
            Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY,
            Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        self.dialog.set_default_size(300, 200)
        self.dialog.connect("delete_event", self.destroy)
   
        area = self.dialog.get_content_area()
        area.set_spacing(20)
        
        area.add(self.build_toolbar())
        area.add(self.build_settings_list(
            title="Debug", settings=[
                {'text':'Extra graphics _debug messages',
                 'tip':'Makes dmesg logs more verbose with 3D-related details',
                 'active':self.has_enable_debugging(),
                 'handler':self.handle_enable_debugging},
                {'text':'Display boot messages',
                 'tip':'Removes splash and quiet from kernel options so you can see kernel details during boot',
                 'active':self.has_disable_splash(),
                 'handler':self.handle_disable_splash},
                ]))
        area.add(self.build_settings_list(
            title="Workarounds", settings=[
#                {'text':'Disable bootloader _graphics',
#                 'tip':'The grub bootloader has a graphics mode using the VESA framebuffer driver which can sometimes interfere with later loading of the proper video driver.  Checking this forces grub to use text mode only.',
#                 'active':self.has_disable_grub_graphics(),
#                 'handler':self.handle_disable_grub_graphics},
                {'text':'Disable _VESA framebuffer driver',
                 'tip':'vesafb is loaded early during boot so the boot logo can display, but can cause issues when switching to a real graphics driver.  Checking this prevents vesafb from loading so these issues do not occur.',
                 'active':self.has_disable_vesafb(),
                 'handler':self.handle_disable_vesafb},
                {'text':'Disable _PAT memory',
                 'tip':"This pagetable extension can interfere with the memory management of proprietary drivers under certain situations and cause lagging or failures to allocate video memory, so turning it off can prevent those problems.",
                 'active':self.has_disable_pat(),
                 'handler':self.handle_disable_pat},
                ]))
        self.dialog.show_all()

    def destroy(self, widget=None, event=None, data=None):
        self.is_running = False
        self.dialog.destroy()
        return False

    def build_toolbar(self):
        hbox = Gtk.HBox()
        hbox.set_spacing(10)

        b = Gtk.Button('View Errors')
        b.connect('clicked', self.on_scan_errors)
        hbox.pack_start(b, False, False, 0)

        b = Gtk.Button('Report an Xorg Bug')
        b.connect('clicked', self.on_report_bug_action)
        hbox.pack_start(b, False, False, 0)

        return hbox

    def build_settings_list(self, title, settings=None):
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        label = Gtk.Label(label="<b>%s</b>" %(title))
        label.set_use_markup(True)
        frame.set_label_widget(label)

        alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        alignment.set_padding(5, 0, 12, 0)

        vbox = Gtk.VBox()
        for s in settings:
            checkbutton = Gtk.CheckButton(s['text'], use_underline=True)
            checkbutton.connect("toggled", s['handler'])
            if 'tip' in s and s['tip']:
                checkbutton.set_tooltip_text(s['tip'])
            if 'active' in s:
                if s['active']:
                    checkbutton.set_active(1)
                else:
                    checkbutton.set_active(0)
            if 'inconsistent' in s and s['inconsistent']:
                checkbutton.set_inconsistent(s['inconsistent'])
            vbox.pack_start(checkbutton, False, False, 0)

        alignment.add(vbox)
        frame.add(alignment)
        return frame

    def load_config(self):
        d = config_dict('/etc/default/grub')
        kparams = {}
        if 'GRUB_CMDLINE_LINUX_DEFAULT' in d:
            re_kparam = re.compile("^([\w\.]+)=(.*)")
            kparam_str = d['GRUB_CMDLINE_LINUX_DEFAULT'].replace('"', '')
            for param in kparam_str.split(' '):
                value = 1
                m = re_kparam.match(param)
                if m:
                    param = m.group(1)
                    value = m.group(2)
                kparams[param] = value
#        if 'GRUB_GFXPAYLOAD_LINUX' in d:
#            re_kparam = re.compile("^([\w\.]+)=(.*)")
#            value = d['GRUB_GFXPAYLOAD_LINUX'].replace('"', '')
#            self.__grub_gfxpayload_linux = value
#            if value == 'text':
#                self.has_disable_grub_graphics(True)
#            else:
#                self.has_disable_grub_graphics(False)
#        else:
#            self.has_disable_grub_graphics(False)

        if 'drm.debug' in kparams:
            self.has_enable_debugging(True)
        else:
            self.has_enable_debugging(False)

        if 'splash' not in kparams:
            self.has_disable_splash(True)
        else:
            self.has_disable_splash(False)

        if 'vesafb.invalid' in kparams:
            self.has_disable_vesafb(True)
        else:
            self.has_disable_vesafb(False)

        if 'nopat' in kparams:
            self.has_disable_pat(True)
        else:
            self.has_disable_pat(False)

    def has_enable_debugging(self, value=None):
        if value is not None:
            self.__enable_debugging = value
        elif self.__enable_debugging is None:
            self.load_config()
        return self.__enable_debugging
    def handle_enable_debugging(self, widget):
        self.has_enable_debugging(widget.get_active())

    def has_disable_splash(self, value=None):
        if value is not None:
            self.__disable_splash = value
        elif self.__disable_splash is None:
            self.load_config()
        return self.__disable_splash
    def handle_disable_splash(self, widget):
        self.has_disable_splash(widget.get_active())

    def has_disable_vesafb(self, value=None):
        if value is not None:
            self.__disable_vesafb = value
        elif self.__disable_vesafb is None:
            self.load_config()
        return self.__disable_vesafb
    def handle_disable_vesafb(self, widget):
        self.has_disable_vesafb(widget.get_active())

    def has_disable_pat(self, value=None):
        if value is not None:
            self.__disable_pat = value
        elif self.__disable_pat is None:
            self.load_config()
        return self.__disable_pat
    def handle_disable_pat(self, widget):
        self.has_disable_pat(widget.get_active())

#    def has_disable_grub_graphics(self, value=None):
#        if value is not None:
#            self.__disable_grub_graphics = value
#        elif self.__disable_grub_graphics is None:
#            self.load_config()
#        return self.__disable_grub_graphics
#    def handle_disable_grub_graphics(self, widget):
#        self.has_disable_grub_graphics(widget.get_active())

    def update_grub(self):
        try:
            subprocess.call(['/usr/sbin/update-grub'])
            return True
        except:
            # TODO: Indicate error occurred
            return False

    def on_report_bug_action(self, widget):
        process = subprocess.Popen(['ubuntu-bug', 'xorg'])
        process.communicate()

    def on_scan_errors(self, widget):
        re_xorg_error = re.compile("^\[\s*([\d\.]+)\] \(EE\) (.*)$")
        re_dmesg_error = re.compile("^\[\s*(\d+\.\d+)\] (.*(?:BUG|ERROR|WARNING).*)$")
        errors = []

        # Xorg.0.log errors
        process = subprocess.Popen(['grep', '(EE)', '/var/log/Xorg.0.log'], stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        for err in stdout.split("\n"):
            m = re_xorg_error.match(err)
            if not m:
                continue
            timestamp = m.group(1)
            errmsg = m.group(2)
            errors.append(errmsg)

        # dmesg errors
        process = subprocess.Popen(['dmesg'], stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        for err in stdout.split("\n"):
            m = re_dmesg_error.match(err)
            if not m:
                continue
            timestamp = m.group(1)
            errmsg = m.group(2)
            errors.append(errmsg)

        tv = ErrorsTreeView(errors)

    def run(self):
        response = self.dialog.run()
        if response == Gtk.ResponseType.APPLY:
            grub = {}
            params = []
            grub_path = "/etc/default/grub"
            # TODO: Write to a temp file ala mktemp
            temp_grub_path = "/tmp/foo.txt"

            fd = os.open(temp_grub_path, os.O_RDWR|os.O_CREAT)
            fo = os.fdopen(fd, "w+")
            if self.__disable_pat:
                params.append('nopat')
            if self.__disable_vesafb:
                params.append('vesafb.invalid=1')
            if self.__enable_debugging:
                # TODO: Enable debug for Xorg.0.log
                params.append('drm.debug=0xe')
#            if self.__disable_grub_graphics is not None:
#                if self.__disable_grub_graphics:
#                    grub['GRUB_GFXPAYLOAD_LINUX'] = 'text'
#                elif self.__grub_gfxpayload_linux != 'text':
#                    grub['GRUB_GFXPAYLOAD_LINUX'] = self.__grub_gfxpayload_linux
#                else:
#                    grub['GRUB_GFXPAYLOAD_LINUX'] = 'keep'

            grub['GRUB_CMDLINE_LINUX_DEFAULT'] = '"%s"' %(' '.join(params))

            if self.__disable_splash:
                config_update(grub_path, override_params=grub, merge_params=None, fileio=fo)
            else:
                config_update(grub_path, override_params=None, merge_params=grub, fileio=fo)

            fo.close()

            # Backup the old file
            try:
                bak_path = safe_backup(grub_path)
                if not bak_path:
                    # TODO: Display error message dialog
                    print "Error:  Could not backup file %s.  Changes not applied." %(grub_path)
                    return
            except IOError, err:
                # TODO: Display error message dialog
                print "Error:  Failure creating backup file for %s.  Changes not applied." %(grub_path)
                print err
                return

            # Move new file into place
            shutil.move(temp_grub_path, grub_path)

            # Finally, update grub
            self.update_grub()

            # TODO: Mark Apply button insensitive
             
        elif response == Gtk.ResponseType.CLOSE:
            self.destroy()

# TODO: cmdline option to display grub file contents (--dryrun?)
