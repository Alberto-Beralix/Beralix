#    Gedit snippets plugin
#    Copyright (C) 2005-2006  Jesse van den Kieboom <jesse@icecrew.nl>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import re
import os
import gettext

from gi.repository import Gtk, Gdk, Gedit, GObject

from document import Document
from library import Library
from shareddata import SharedData
from signals import Signals

class Activate(Gedit.Message):
        view = GObject.property(type=Gedit.View)
# FIXME: fix as soon as fix lands in pygobject
#        iter = GObject.property(type=Gtk.TextIter)
        trigger = GObject.property(type=str)

class WindowActivatable(GObject.Object, Gedit.WindowActivatable, Signals):
        __gtype_name__ = "GeditSnippetsWindowActivatable"

        window = GObject.property(type=Gedit.Window)

        def __init__(self):
                GObject.Object.__init__(self)
                Signals.__init__(self)

                self.current_language_accel_group = None

        def do_activate(self):
                self.insert_menu()
                self.register_messages()

                library = Library()
                library.add_accelerator_callback(self.accelerator_activated)

                self.accel_group = Library().get_accel_group(None)

                if self.accel_group:
                        self.window.add_accel_group(self.accel_group)

                self.connect_signal(self.window,
                                    'active-tab-changed',
                                    self.on_active_tab_changed)

                self.do_update_state()

                SharedData().register_window(self)

        def do_deactivate(self):
                if self.accel_group:
                        self.window.remove_accel_group(self.accel_group)

                self.accel_group = None

                self.remove_menu()
                self.unregister_messages()

                library = Library()
                library.remove_accelerator_callback(self.accelerator_activated)

                self.disconnect_signals(self.window)

                SharedData().unregister_window(self)

        def do_update_state(self):
                controller = SharedData().get_active_controller(self.window)

                self.update_language(controller)

        def register_messages(self):
                bus = self.window.get_message_bus()

                bus.register(Activate, '/plugins/snippets', 'activate')
                bus.register(Activate, '/plugins/snippets', 'parse-and-activate')

                self.signal_ids = set()
                sid = bus.connect('/plugins/snippets', 'activate', self.on_message_activate, None)
                self.signal_ids.add(sid)
                sid = bus.connect('/plugins/snippets', 'parse-and-activate', self.on_message_parse_and_activate, None)
                self.signal_ids.add(sid)

        def unregister_messages(self):
                bus = self.window.get_message_bus()
                for sid in self.signal_ids:
                    bus.disconnect(sid)
                signal_ids = None
                bus.unregister_all('/plugins/snippets')

        def on_message_activate(self, bus, message, userdata):
                view = message.props.view

                if not view:
                        view = self.window.get_active_view()

                controller = SharedData().get_controller(view)

                if not controller:
                        return

                # TODO: fix me as soon as the property fix lands in pygobject
                #iter = message.props.iter

                #if not iter:
                iter = view.get_buffer().get_iter_at_mark(view.get_buffer().get_insert())
                controller.run_snippet_trigger(message.props.trigger, (iter, iter))

        def on_message_parse_and_activate(self, bus, message, userdata):
                view = message.props.view

                if not view:
                        view = self.window.get_active_view()

                controller = SharedData().get_controller(view)

                if not controller:
                        return

                # TODO: fix me as soon as the property fix lands in pygobject
                #iter = message.props.iter
                
                #if not iter:
                iter = view.get_buffer().get_iter_at_mark(view.get_buffer().get_insert())
                controller.parse_and_run_snippet(message.snippet, iter)

        def insert_menu(self):
                manager = self.window.get_ui_manager()

                self.action_group = Gtk.ActionGroup("GeditSnippetPluginActions")
                self.action_group.set_translation_domain('gedit')
                self.action_group.add_actions([('ManageSnippets', None,
                                _('Manage _Snippets...'), \
                                None, _('Manage snippets'), \
                                self.on_action_snippets_activate)])

                self.merge_id = manager.new_merge_id()
                manager.insert_action_group(self.action_group, -1)
                manager.add_ui(self.merge_id, '/MenuBar/ToolsMenu/ToolsOps_5', \
                                'ManageSnippets', 'ManageSnippets', Gtk.UIManagerItemType.MENUITEM, False)

        def remove_menu(self):
                manager = self.window.get_ui_manager()
                manager.remove_ui(self.merge_id)
                manager.remove_action_group(self.action_group)
                self.action_group = None

        def find_snippet(self, snippets, tag):
                result = []

                for snippet in snippets:
                        if Snippet(snippet)['tag'] == tag:
                                result.append(snippet)

                return result

        def update_language(self, controller):
                if not self.window:
                        return

                if controller:
                        langid = controller.language_id
                else:
                        langid = None

                if langid != None:
                        accelgroup = Library().get_accel_group(langid)
                else:
                        accelgroup = None

                if accelgroup != self.current_language_accel_group:
                        if self.current_language_accel_group:
                                self.window.remove_accel_group(self.current_language_accel_group)

                        if accelgroup:
                                self.window.add_accel_group(accelgroup)

                self.current_language_accel_group = accelgroup

        def on_active_tab_changed(self, window, tab):
                self.update_language(SharedData().get_controller(tab.get_view()))

        # Callbacks
        def create_configure_dialog(self):
                SharedData().show_manager(self.window, self.plugin_info.get_data_dir())

        def on_action_snippets_activate(self, action):
                self.create_configure_dialog()

        def accelerator_activated(self, group, obj, keyval, mod):
                if obj == self.window:
                        controller = SharedData().get_active_controller(self.window)

                        if controller:
                                return controller.accelerator_activate(keyval, mod)
                else:
                        return False

# ex:ts=8:et:
