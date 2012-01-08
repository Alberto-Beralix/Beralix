
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
GObject.threads_init()
import subprocess
import sys

import os
import os.path

import apt_pkg


from AptUrl.UI import AbstractUI
from AptUrl import Helpers
from AptUrl.Helpers import _

from backend import get_backend

class GtkUI(AbstractUI):
    def __init__(self):
        Gtk.init_check(sys.argv)
        # create empty dialog
        self.dia_xml = Gtk.Builder()
        self.dia_xml.set_translation_domain("apturl")
        self.dia_xml.add_from_file('/usr/share/apturl/apturl-gtk.ui')
        self.dia = self.dia_xml.get_object('confirmation_dialog')
        self.dia.realize()
        self.backend = get_backend(self.dia)
        self.backend.connect("action-done", self._on_backend_done)

    def _on_backend_done(self, backend, action, authorized, success):
        self.dia.set_sensitive(True)
        Gtk.main_quit()

    # generic dialogs
    def _get_dialog(self, dialog_type, summary, msg="", buttons=Gtk.ButtonsType.CLOSE):
        " internal helper for dialog construction "
        d = Gtk.MessageDialog(parent=self.dia,
                              flags=Gtk.DialogFlags.MODAL,
                              type=dialog_type,
                              buttons=buttons)
        d.set_title("")
        d.set_markup("<big><b>%s</b></big>\n\n%s" % (summary, msg))
        d.set_icon(Gtk.IconTheme.get_default().load_icon('deb', 16, False))
        d.set_keep_above(True)
        d.realize()
        d.get_window().set_functions(Gdk.WMFunction.MOVE)
        return d
        
    def error(self, summary, msg=""):
        d = self._get_dialog(Gtk.MessageType.ERROR, summary, msg)
        d.run()
        d.destroy()
        return False

    def message(self, summary, msg="", title=""):
        d = self._get_dialog(Gtk.MessageType.INFO, summary, msg)
        d.set_title(title)
        d.run()
        d.destroy()
        return True

    def yesNoQuestion(self, summary, msg, title="", default='no'):
        d = self._get_dialog(Gtk.MessageType.QUESTION, summary, msg,
                             buttons=Gtk.ButtonsType.YES_NO)
        d.set_title(title)
        res = d.run()
        d.destroy()
        if res != Gtk.ResponseType.YES:
            return False
        return True
    
    # specific dialogs
    def askEnableChannel(self, channel, channel_info_html):
        summary = _("Enable additional software channel")
        msg = _("Do you want to enable the following "
                "software channel: '%s'?") % channel
        d = self._get_dialog(Gtk.MessageType.QUESTION, summary, msg,
                             buttons=Gtk.ButtonsType.YES_NO)
        if channel_info_html:
            try:
                from gi.repository import WebKit
                v=WebKit.WebView()
                v.load_string(channel_info_html, "text/html", "utf-8", "file:/")
                sw = Gtk.ScrolledWindow()
                sw.add(v)
                d.get_content_area().pack_start(sw, True, True, 0)
                sw.set_size_request(400, 200)
                sw.show_all()
            except ImportError:
                pass
        res = d.run()
        d.destroy()
        if res != Gtk.ResponseType.YES:
            return False
        return True

    def doEnableSection(self, sections):
        cmd = ["gksu", "--desktop",
               "/usr/share/applications/software-properties.desktop",
               "--",
               "software-properties-gtk",
               "-e", "%s" % ' '.join(sections)]
        try:
            output = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
        except OSError, e:
            print >>sys.stderr, "Execution failed:", e
            return True
        #FIXME: Very ugly, but gksu doesn't return the correct exit states
        if not output.startswith("Enabled the "):
            return False
        return True

    
    def doEnableChannel(self, channelpath, channelkey):
        cmd = ["gksu",
               "--desktop", "/usr/share/applications/gnome-app-install.desktop",
               "--",
               "install", "--mode=644","--owner=0",channelpath,
               apt_pkg.Config.FindDir("Dir::Etc::sourceparts")]
        res=subprocess.call(cmd)
        if not res == 0:
            return False
        # install the key as well
        if os.path.exists(channelkey):
            cmd = ["gksu",
                   "--desktop",
                   "/usr/share/applications/gnome-app-install.desktop",
                   "--",
                   "apt-key", "add",channelkey]
            res=subprocess.call(cmd)
            if not res == 0:
                return False
        return True

    def askInstallPackage(self, package, summary, description, homepage):
        # populate the dialog
        dia = self.dia
        dia_xml = self.dia_xml
        header = _("Install additional software?")
        body = _("Do you want to install package '%s'?") % package
        dia.set_keep_above(True)
        dia.set_title('')
        header_label = dia_xml.get_object('header_label')
        header_label.set_markup("<b><big>%s</big></b>" % header)
        body_label = dia_xml.get_object('body_label')
        body_label.set_label(body)
        description_text_view = dia_xml.get_object('description_text_view')
        tbuf = Gtk.TextBuffer()
        desc = "%s\n\n%s" % (summary, Helpers.format_description(description))
        tbuf.set_text(desc)
        description_text_view.set_buffer(tbuf)
        dia.set_icon(Gtk.IconTheme.get_default().load_icon('deb', 16, False))
        
        # check if another package manager is already running
        # FIXME: just checking for the existance of the file is
        #        not sufficient, it need to be tested if it can
        #        be locked via apt_pkg.GetLock() 
        #        - but that needs to run as root 
        #        - a dbus helper might be the best answer here
        #args = (update_button_status, dia_xml.get_object("yes_button"),
        #    dia_xml.get_object("infolabel"))
        #args[0](*args[1:])
        #timer_id = GObject.timeout_add(750, *args )
        
        # show the dialog
        res = dia.run()
        #GObject.source_remove(timer_id)
        if res != Gtk.ResponseType.YES:
            dia.hide()
            return False
        
        # don't set on-top while installing
        dia.set_keep_above(False)
        return True

    # progress etc
    def doUpdate(self):
        self.backend.update()
        self.dia.set_sensitive(False)
        Gtk.main()

    def doInstall(self, apturl):
        self.backend.commit([apturl.package], [], False)
        self.dia.set_sensitive(False)
        Gtk.main()

if __name__ == "__main__":
    ui = GtkUI()
    ui.error("foo","bar")
