# -*- coding: utf-8 -*-

# __init__.py -- plugin object
#
# Copyright (C) 2006 - Steve Frécinaux
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# Parts from "Interactive Python-GTK Console" (stolen from epiphany's console.py)
#     Copyright (C), 1998 James Henstridge <james@daa.com.au>
#     Copyright (C), 2005 Adam Hooper <adamh@densi.com>
# Bits from gedit Python Console Plugin
#     Copyrignt (C), 2005 Raphaël Slinckx

from gi.repository import GObject, Gtk, Gedit, Peas, PeasGtk

from console import PythonConsole
from config import PythonConsoleConfigWidget

PYTHON_ICON = 'gnome-mime-text-x-python'

class PythonConsolePlugin(GObject.Object, Gedit.WindowActivatable, PeasGtk.Configurable):
    __gtype_name__ = "PythonConsolePlugin"

    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        self._console = PythonConsole(namespace = {'__builtins__' : __builtins__,
                                                   'gedit' : Gedit,
                                                   'window' : self.window})
        self._console.eval('print "You can access the main window through ' \
                           '\'window\' :\\n%s" % window', False)
        bottom = self.window.get_bottom_panel()
        image = Gtk.Image()
        image.set_from_icon_name(PYTHON_ICON, Gtk.IconSize.MENU)
        bottom.add_item(self._console, "GeditPythonConsolePanel",
                        _('Python Console'), image)

    def do_deactivate(self):
        self._console.stop()
        bottom = self.window.get_bottom_panel()
        bottom.remove_item(self._console)

    def do_update_state(self):
        pass

    def do_create_configure_widget(self):
        config_widget = PythonConsoleConfigWidget(self.plugin_info.get_data_dir())

        return config_widget.configure_widget()

# ex:et:ts=4:
