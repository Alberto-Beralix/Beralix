# -*- coding: utf-8 -*-

# pythonconsole.py -- plugin object
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
#
# The Totem project hereby grant permission for non-gpl compatible GStreamer
# plugins to be used and distributed together with GStreamer and Totem. This
# permission are above and beyond the permissions granted by the GPL license
# Totem is covered by.
#
# Monday 7th February 2005: Christian Schaller: Add exception clause.
# See license_change file for details.

from console import PythonConsole

__all__ = ('PythonConsole', 'OutFile')

from gi.repository import Peas
from gi.repository import Gtk
from gi.repository import Totem
from gi.repository import Gio
import gobject
try:
	import rpdb2
	have_rpdb2 = True
except:
	have_rpdb2 = False

import gettext
gettext.textdomain("totem")

D_ = gettext.dgettext
_ = gettext.gettext

ui_str = """
<ui>
  <menubar name="tmw-menubar">
    <menu name="Python" action="Python">
      <placeholder name="ToolsOps_5">
        <menuitem name="PythonConsole" action="PythonConsole"/>
        <menuitem name="PythonDebugger" action="PythonDebugger"/>
      </placeholder>
    </menu>
  </menubar>
</ui>
"""

class PythonConsolePlugin(gobject.GObject, Peas.Activatable):
	__gtype_name__ = 'PythonConsolePlugin'

	object = gobject.property(type = gobject.GObject)

	def __init__(self):
		self.totem = None
		self.window = None
	
	def do_activate(self):
		self.totem = self.object

		data = dict()
		manager = self.totem.get_ui_manager()

		data['action_group'] = Gtk.ActionGroup(name = 'Python')
		
		action = Gtk.Action(name = 'Python', label = 'Python', tooltip = _(u'Python Console Menu'), stock_id = None)
		data['action_group'].add_action(action)

		action = Gtk.Action(name = 'PythonConsole', label = _(u'_Python Console'),
		                    tooltip = _(u"Show Totem's Python console"),
		                    stock_id = 'gnome-mime-text-x-python')
		action.connect('activate', self.show_console)
		data['action_group'].add_action(action)

		action = Gtk.Action(name = 'PythonDebugger', label = _(u'Python Debugger'),
				    tooltip = _(u"Enable remote Python debugging with rpdb2"), stock_id = None)
		if have_rpdb2:
			action.connect('activate', self.enable_debugging)
		else:
			action.set_visible(False)
		data['action_group'].add_action(action)
				
		manager.insert_action_group(data['action_group'], 0)
		data['ui_id'] = manager.add_ui_from_string(ui_str)
		manager.ensure_update()
		
		self.totem.set_data('PythonConsolePluginInfo', data)
	
	def show_console(self, action):
		if not self.window:
			console = PythonConsole(namespace = {'__builtins__' : __builtins__,
			                                     'Totem' : Totem,
			                                     'totem_object' : self.totem},
			                                     destroy_cb = self.destroy_console)

			console.set_size_request(600, 400)
			console.eval('print "%s" %% totem_object' % _(u"You can access the Totem.Object through " \
				     "\'totem_object\' :\\n%s"), False)

			self.window = Gtk.Window()
			self.window.set_title(_(u'Totem Python Console'))
			self.window.add(console)
			self.window.connect('destroy', self.destroy_console)
			self.window.show_all()
		else:
			self.window.show_all()
			self.window.grab_focus()

	def enable_debugging(self, action):
		msg = _(u"After you press OK, Totem will wait until you connect to it with winpdb or rpdb2. If you have not set a debugger password in DConf, it will use the default password ('totem').")
		dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK_CANCEL, msg)
		if dialog.run() == Gtk.ResponseType.OK:
			settings = Gio.Settings.new ('org.gnome.totem.plugins.pythonconsole')
			password = settings.get_string('rpdb2-password') or "totem"
			def start_debugger(password):
				rpdb2.start_embedded_debugger(password)
				return False

			gobject.idle_add(start_debugger, password)
		dialog.destroy()

	def destroy_console(self, *args):
		self.window.destroy()
		self.window = None

	def do_deactivate(self):
		data = self.totem.get_data('PythonConsolePluginInfo')

		manager = self.totem.get_ui_manager()
		manager.remove_ui(data['ui_id'])
		manager.remove_action_group(data['action_group'])
		manager.ensure_update()

		self.totem.set_data('PythonConsolePluginInfo', None)
		
		if self.window is not None:
			self.window.destroy()
