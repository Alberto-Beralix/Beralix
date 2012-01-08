#!/usr/bin/python

## Copyright (C) 2006, 2007, 2008, 2010 Red Hat, Inc.
## Author: Tim Waugh <twaugh@redhat.com>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import gtk
import os
import subprocess

class UserDefaultPrinter:
    def __init__ (self):
        try:
            lpoptions = os.environ["HOME"]
        except KeyError:
            try:
                lpoptions = "/home/" + os.environ["USER"]
            except KeyError:
                lpoptions = None

        if lpoptions:
            lpoptions += "/.cups/lpoptions"

        self.lpoptions = lpoptions

    def clear (self):
        if not self.lpoptions:
            return

        try:
            opts = file (self.lpoptions).readlines ()
        except IOError:
            return

        for i in range (len (opts)):
            if opts[i].startswith ("Default "):
                opts[i] = "Dest " + opts[i][8:]
        file (self.lpoptions, "w").writelines (opts)

    def get (self):
        if not self.lpoptions:
            return None

        try:
            opts = file (self.lpoptions).readlines ()
        except IOError:
            return None

        for i in range (len (opts)):
            if opts[i].startswith ("Default "):
                rest = opts[i][8:]
                slash = rest.find ("/")
                if slash != -1:
                    space = rest[:slash].find (" ")
                else:
                    space = rest.find (" ")
                return rest[:space]
        return None

    def set (self, default):
        p = subprocess.Popen ([ "lpoptions", "-d", default ],
                              close_fds=True,
                              stdin=file ("/dev/null"),
                              stdout=file ("/dev/null", "w"),
                              stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate ()
        exitcode = p.wait ()
        if exitcode != 0:
            raise RuntimeError (exitcode, stderr.strip ())
        return

    def __repr__ (self):
        return "<UserDefaultPrinter (%s)>" % repr (self.get ())

class UserDefaultPrompt:
    def __init__ (self,
                  set_default_fn,
                  refresh_fn,
                  name,
                  title,
                  parent,
                  primarylabel,
                  systemwidelabel,
                  clearpersonallabel,
                  personallabel):
        self.set_default_fn = set_default_fn
        self.refresh_fn = refresh_fn
        self.name = name
        dialog = gtk.Dialog (title,
                             parent,
                             gtk.DIALOG_MODAL |
                             gtk.DIALOG_DESTROY_WITH_PARENT |
                             gtk.DIALOG_NO_SEPARATOR,
                             (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                              gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_default_response (gtk.RESPONSE_OK)
        dialog.set_border_width (6)
        dialog.set_resizable (False)
        hbox = gtk.HBox (False, 12)
        hbox.set_border_width (6)
        image = gtk.Image ()
        image.set_from_stock (gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
        image.set_alignment (0.0, 0.0)
        hbox.pack_start (image, False, False, 0)
        vboxouter = gtk.VBox (False, 6)
        primary = gtk.Label ()
        primary.set_markup ('<span weight="bold" size="larger">' +
                            primarylabel + '</span>')
        primary.set_line_wrap (True)
        primary.set_alignment (0.0, 0.0)
        vboxouter.pack_start (primary, False, False, 0)
        vboxradio = gtk.VBox (False, 0)
        systemwide = gtk.RadioButton (label=systemwidelabel)
        vboxradio.pack_start (systemwide, False, False, 0)
        clearpersonal = gtk.CheckButton (clearpersonallabel)
        alignment = gtk.Alignment (0, 0, 0, 0)
        alignment.set_padding (0, 0, 12, 0)
        alignment.add (clearpersonal)
        vboxradio.pack_start (alignment)
        vboxouter.pack_start (vboxradio, False, False, 0)
        personal = gtk.RadioButton (group=systemwide,
                                    label=personallabel)
        vboxouter.pack_start (personal, False, False, 0)
        hbox.pack_start (vboxouter, False, False, 0)
        dialog.vbox.pack_start (hbox, False, False, 0)
        systemwide.set_active (True)
        clearpersonal.set_active (True)
        self.userdef = UserDefaultPrinter ()
        clearpersonal.set_sensitive (self.userdef.get () != None)

        self.systemwide = systemwide
        self.clearpersonal = clearpersonal
        self.personal = personal
        systemwide.connect ("toggled", self.on_toggled)
        dialog.connect ("response", self.on_response)
        dialog.show_all ()

    def on_toggled (self, button):
        self.clearpersonal.set_sensitive (self.userdef.get () != None and
                                          self.systemwide.get_active ())

    def on_response (self, dialog, response_id):
        if response_id != gtk.RESPONSE_OK:
            dialog.destroy ()
            return

        if self.systemwide.get_active ():
            if self.clearpersonal.get_active ():
                self.userdef.clear ()
            self.set_default_fn (self.name)
        else:
            try:
                self.userdef.set (self.name)
            except Exception, e:
                print "Error setting default: %s" % repr (e)

            self.refresh_fn ()

        dialog.destroy ()
