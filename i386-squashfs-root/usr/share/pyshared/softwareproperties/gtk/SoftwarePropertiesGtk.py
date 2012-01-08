#  GTK+ based frontend to software-properties
#
#  Copyright (c) 2004-2007 Canonical Ltd.
#                2004-2005 Michiel Sikkes
#
#  Author: Michiel Sikkes <michiel@eyesopened.nl>
#          Michael Vogt <mvo@debian.org>
#          Sebastian Heinlein <glatzor@ubuntu.com>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

import apt
import apt_pkg
import dbus
import tempfile
from gettext import gettext as _
import os

from gi.repository import GObject, Gdk, Gtk, Gio

from SimpleGtkbuilderApp import SimpleGtkbuilderApp
from aptsources.sourceslist import SourceEntry
from DialogAdd import DialogAdd
from DialogMirror import DialogMirror
from DialogEdit import DialogEdit
from DialogCacheOutdated import DialogCacheOutdated
from DialogAddSourcesList import DialogAddSourcesList
from CdromProgress import CdromProgress

import softwareproperties
import softwareproperties.distro
from softwareproperties.SoftwareProperties import SoftwareProperties
import softwareproperties.SoftwareProperties

(LIST_MARKUP, LIST_ENABLED, LIST_ENTRY_OBJ) = range(3)

(
    COLUMN_ACTIVE,
    COLUMN_DESC
) = range(2)

RESPONSE_REPLACE = 1
RESPONSE_ADD = 2

# columns of the source_store
(
    STORE_ACTIVE, 
    STORE_DESCRIPTION, 
    STORE_SOURCE, 
    STORE_SEPARATOR,
    STORE_VISIBLE
) = range(5)

def error(parent_window, summary, msg):
    """ show a error dialog """
    dialog = Gtk.MessageDialog(parent=parent_window,
                               flags=Gtk.DialogFlags.MODAL,
                               type=Gtk.MessageType.ERROR,
                               buttons=Gtk.ButtonsType.OK,
                               message_format=None)
    dialog.set_markup("<big><b>%s</b></big>\n\n%s" % (summary, msg))
    res = dialog.run()
    dialog.destroy()
    return False

class SoftwarePropertiesGtk(SoftwareProperties,SimpleGtkbuilderApp):

  def __init__(self, datadir=None, options=None, file=None, parent=None):
    """ Provide a GTK based graphical user interface to configure
        the used software repositories, corresponding authentication keys
        and update automation """
    SoftwareProperties.__init__(self, options=options, datadir=datadir)
    Gtk.Window.set_default_icon_name("software-properties")

    SimpleGtkbuilderApp.__init__(self,
                                 os.path.join(datadir, "gtkbuilder", "main.ui"),
                                 domain="software-properties")

    if parent:
      self.window_main.set_type_hint(Gdk.WindowTypeHint.DIALOG)
      self.window_main.show()
      try:
        self.window_main.set_transient_for(parent)
      except:
        pass

    # If externally called, reparent to external application.
    self.options = options
    if options and options.toplevel != None:
      self.window_main.set_type_hint(Gdk.WindowTypeHint.DIALOG)
      self.window_main.show()
      try:
        toplevel = Gdk.window_foreign_new(int(options.toplevel))
      except AttributeError:
        toplevel = None
      if (toplevel):
        try:
          self.window_main.set_transient_for(toplevel)
        except: 
          pass
    if options and options.open_tab:
      self.notebook_main.set_current_page(int(options.open_tab))

    # gsettings
    all_schemas = Gio.Settings.list_schemas()
    if "com.ubuntu.update-notifier" in all_schemas:
        self.settings = Gio.Settings("com.ubuntu.update-notifier")
        # we need this for reverting
        self.initial_auto_launch = self.settings.get_int("regular-auto-launch-interval") 
    else:
        self.settings = None
        self.initial_auto_launch = 0
        self.combobox_other_updates.set_sensitive(False)

    # get the dbus backend
    bus = dbus.SystemBus()
    proxy = bus.get_object("com.ubuntu.SoftwareProperties", "/")
    self.backend = dbus.Interface(proxy, "com.ubuntu.SoftwareProperties")
    self.backend.connect_to_signal(
        "SourcesListModified", self.on_sources_list_modified)
    self.backend.connect_to_signal(
        "ConfigModified", self.on_config_modified)
    self.backend.connect_to_signal(
        "KeysModified", self.on_keys_modified)
    self.backend.connect_to_signal(
        "AuthFailed", self.on_auth_failed)
    self.backend.connect_to_signal(
        "CdromScanFailed", self.on_cdrom_scan_failed)
    
    # Show what we have early
    self.window_main.show()

    # used to store the handlers of callbacks
    self.handlers = []

    # Put some life into the user interface:
    self.init_popcon()
    self.init_auto_update()
    self.init_release_upgrades()
    self.show_auto_update_level()
    # Setup the key list
    self.init_keys()
    self.show_keys()
    # Setup the ISV sources list
    self.init_isv_sources()
    self.show_isv_sources()
    self.show_cdrom_sources()
    # Setup and show the distro elements
    self.init_distro()
    self.show_distro()

    # Show the import/replace sources.list dialog if a file different
    # to the default sources.list was specified 
    # NOTE: If the file path points to the default sources.list the user
    #       perhaps assumed that s-p would act like a normal editor.
    #       We have got some bug reports from users calling
    #       "sudo software-properties-gtk /etc/apt/sources.list" from the
    #       command line.
    if (file != None and
       os.path.abspath(file) !=  "%s%s" % (apt_pkg.config.find_dir("Dir::Etc"),
                                           apt_pkg.config.find("Dir::Etc::sourcelist"))):
        self.open_file(file)

  def update_interface(self):
    """ abstract interface to keep the UI alive """
    while Gtk.events_pending():
      Gtk.main_iteration()

  def init_popcon(self):
    """ If popcon is enabled show the statistics tab and an explanation
        corresponding to the used distro """
    is_helpful = self.get_popcon_participation()
    if is_helpful != None:
      self.label_popcon_desc.set_label(
          softwareproperties.distro.get_popcon_description(self.distro))
      self.vbox_popcon.show()
      self.checkbutton_popcon.set_active(is_helpful)

  def init_release_upgrades(self):
    " setup the widgets that allow configuring the release upgrades "
    i = self.get_release_upgrades_policy()
    self.combobox_release_upgrades.set_active(i)
    self.combobox_release_upgrades.connect(
        'changed', self.on_combobox_release_upgrades_changed)

  def init_auto_update(self):
    """ Set up the widgets that allow to configure the update automation """
    self.combobox_update_interval.show()

    # normal updates
    # this maps the key (combo-box-index) to the auto-update-interval value
    # we build it dynamically from the model
    model = self.combobox_update_interval.get_model()
    self.combobox_interval_mapping = {}
    for (i, row) in enumerate(model):
      # column 1 is the update interval in days
      value = model.get_value(row.iter, 1)
      self.combobox_interval_mapping[i] = value

    # normal updates
    update_days = self.get_update_interval()

    # If a custom period is defined add a corresponding entry
    if not update_days in self.combobox_interval_mapping.values():
        if update_days > 0:
            self.combobox_update_interval.append_text(_("Every %s days") 
                                                      % update_days)
            self.combobox_interval_mapping[-1] = update_days
    
    for key in self.combobox_interval_mapping:
      if self.combobox_interval_mapping[key] == update_days:
        self.combobox_update_interval.set_active(key)
        break

    self.handlers.append(
        (self.combobox_update_interval,
         self.combobox_update_interval.connect("changed", 
                                     self.on_combobox_update_interval_changed)))
    
    self.handlers.append(
        (self.combobox_security_updates,
         self.combobox_security_updates.connect("changed",
                                     self.set_sec_update_automation_level)))
    
    self.handlers.append(
        (self.combobox_security_updates,
         self.combobox_other_updates.connect("changed",
                                     self.set_other_update_automation_level)))
  
  def show_auto_update_level(self):
    """Represent the level of update automation in the user interface"""

    # Security Updates
    level_sec = self.get_update_automation_level()
    if level_sec == None:
      self.combobox_security_updates.set_sensitive(False)
    else:
      self.combobox_security_updates.set_sensitive(True)
          
    if (level_sec == softwareproperties.UPDATE_MANUAL or
        level_sec == softwareproperties.UPDATE_NOTIFY):
      self.combobox_security_updates.set_active(0) # Display immediately
    elif level_sec == softwareproperties.UPDATE_DOWNLOAD:
      self.combobox_security_updates.set_active(1) # Download automatically
    elif level_sec == softwareproperties.UPDATE_INST_SEC:
      self.combobox_security_updates.set_active(2) # Download and install automatically
    
    # Other Updates
    if self.settings:
        level_other = self.settings.get_int("regular-auto-launch-interval")
        model = self.combobox_other_updates.get_model()
        for (i, row) in enumerate(model):
            level = model.get_value(row.iter, 1)
            if level_other == level:
                self.combobox_other_updates.set_active(i)
                break

  def init_distro(self):
    """Setup the user interface elements to represent the distro"""

    # TRANS: %s stands for the distribution name e.g. Debian or Ubuntu
    self.label_dist_name.set_label(_("%s Software") % self.distro.id.encode('UTF-8'))

    self.handlers.append((self.checkbutton_source_code,
                          self.checkbutton_source_code.connect("toggled",
                              self.on_checkbutton_source_code_toggled)))

    # Setup the checkbuttons for the components
    for checkbutton in self.vbox_dist_comps.get_children():
         self.vbox_dist_comps.remove(checkbutton)
    for comp in self.distro.source_template.components:
        # TRANSLATORS: Label for the components in the Internet section
        #              first %s is the description of the component
        #              second %s is the code name of the comp, eg main, universe
        label = _("%s (%s)") % (comp.get_description(), comp.name)
        checkbox = Gtk.CheckButton(label)

        checkbox.comp = comp
        # setup the callback and show the checkbutton
        self.handlers.append((checkbox,
                              checkbox.connect("toggled", 
                                               self.on_component_toggled, 
                                               comp.name)))
        self.vbox_dist_comps.add(checkbox)
        checkbox.show()

    # Setup the checkbuttons for the child repos / updates
    for checkbutton in self.vbox_updates.get_children():
         self.vbox_updates.remove(checkbutton)
    if len(self.distro.source_template.children) < 1:
        self.frame_children.hide()
    for template in self.distro.source_template.children:
        # Do not show source entries in there
        if template.type == "deb-src":
            continue

        checkbox = Gtk.CheckButton(label="%s (%s)" % (template.description,
                                                      template.name))
        checkbox.template = template
        self.handlers.append((checkbox,
                              checkbox.connect("toggled",
                                               self.on_checkbutton_child_toggled,
                                               template)))
        self.vbox_updates.add(checkbox)
        checkbox.show()


    # setup the server chooser
    cell = Gtk.CellRendererText()
    self.combobox_server.pack_start(cell, True)
    self.combobox_server.add_attribute(cell, 'text', 0)
    self.handlers.append((self.combobox_server,
                          self.combobox_server.connect("changed",
                              self.on_combobox_server_changed)))
    server_store = Gtk.ListStore(GObject.TYPE_STRING,
                                 GObject.TYPE_STRING,
                                 GObject.TYPE_BOOLEAN)
    self.combobox_server.set_model(server_store)
    self.combobox_server.set_row_separator_func(self.is_row_separator, 2)

  def block_handlers(self):
    for (widget, handler) in self.handlers:
        widget.handler_block(handler)
 
  def unblock_handlers(self):
    for (widget, handler) in self.handlers:
        widget.handler_unblock(handler)

  def show_distro(self):
    """Fill the distro user interface with life"""
    self.block_handlers()

    # Enable or disable the child source checkbuttons
    for checkbox in self.vbox_updates.get_children():
        (active, inconsistent) = self.get_comp_child_state(checkbox.template)
        checkbox.set_active(active)
        checkbox.set_inconsistent(inconsistent)

    # Enable or disable the component checkbuttons
    for checkbox in self.vbox_dist_comps.get_children():
        # check if the comp is enabled
        (active, inconsistent) = self.get_comp_download_state(checkbox.comp)
        checkbox.set_inconsistent(inconsistent)
        checkbox.set_active(active)

    # If no components are enabled there will be no need for updates
    # and source code
    if len(self.distro.enabled_comps) < 1:
        self.vbox_updates.set_sensitive(False)
        self.checkbutton_source_code.set_sensitive(False)
    else:
        self.vbox_updates.set_sensitive(True)
        self.checkbutton_source_code.set_sensitive(True)

    # Check for source code sources
    source_code_state = self.get_source_code_state()
    if source_code_state == None:
        self.checkbutton_source_code.set_inconsistent(True)
    elif source_code_state == True:        
        self.checkbutton_source_code.set_active(True)
        self.checkbutton_source_code.set_inconsistent(False)
    else:
        self.checkbutton_source_code.set_active(False)
        self.checkbutton_source_code.set_inconsistent(False)

    # Will show a short explanation if no CDROMs are used
    if len(self.get_cdrom_sources()) == 0:
        self.scrolledwindow_cd.hide()
        self.scrolledwindow_no_cd.show()
    else:
        self.scrolledwindow_cd.show()
        self.scrolledwindow_no_cd.hide()

    # provide a list of mirrors
    server_store = self.combobox_server.get_model()
    server_store.clear()
    seen_server_new = []
    for (name, uri, active) in self.distro.get_server_list():
        server_store.append([name, uri, False])
        if [name, uri] in self.seen_server:
            self.seen_server.remove([name, uri])
        elif uri != None:
            seen_server_new.append([name, uri])
        if active == True:
            self.active_server = len(server_store) - 1
            self.combobox_server.set_active(self.active_server)
    for [name, uri] in self.seen_server:
        server_store.append([name, uri, False])
    self.seen_server = seen_server_new
    # add a separator and the option to choose another mirror from the list
    server_store.append(["sep", None, True])
    server_store.append([_("Other..."), None, False])

    # make the interface respond to user interput again
    self.unblock_handlers()

    # Output a lot of debug stuff
    if self.options.debug == True or self.options.massive_debug == True:
        print "ENABLED COMPS: %s" % self.distro.enabled_comps
        print "INTERNET COMPS: %s" % self.distro.download_comps
        print "MAIN SOURCES"
        for source in self.distro.main_sources:
            self.print_source_entry(source)
        print "CHILD SOURCES"
        for source in self.distro.child_sources:
            self.print_source_entry(source)
        print "CDROM SOURCES"
        for source in self.distro.cdrom_sources:
            self.print_source_entry(source)
        print "SOURCE CODE SOURCES"
        for source in self.distro.source_code_sources:
            self.print_source_entry(source)
        print "DISABLED SOURCES"
        for source in self.distro.disabled_sources:
            self.print_source_entry(source)
        print "ISV"
        for source in self.sourceslist_visible:
            self.print_source_entry(source)

  def set_sec_update_automation_level(self, widget):
    """Call the backend to set the security update automation level to the given
       value"""
    index = widget.get_active()
    state = -1
    if index == 0: # Display immediately
      state = softwareproperties.UPDATE_NOTIFY
    elif index == 1: # Download automatically
      state = softwareproperties.UPDATE_DOWNLOAD
    elif index == 2: # Download and install automatically
      state = softwareproperties.UPDATE_INST_SEC
    # only set if something actually changed
    if state != self.get_update_automation_level():
        self.backend.SetUpdateAutomationLevel(state)
    
  def set_other_update_automation_level(self, widget):
    """Set the other update automation level to the given value via gconf"""
    index = widget.get_active()
    model = self.combobox_other_updates.get_model()
    # the second column is the update interval days
    days = model[index][1]
    self.settings.set_int("regular-auto-launch-interval", days)

  def is_row_separator(self, model, iter, column=0):
    ''' Check if a given row is a separator '''
    return model.get_value(iter, column)

  def on_combobox_release_upgrades_changed(self, combobox):
    """ set the release upgrades policy """
    #print "on_combobox_release_upgrades_changed()"
    i = combobox.get_active()
    self.backend.SetReleaseUpgradesPolicy(i)

  def on_combobox_server_changed(self, combobox):
    """
    Replace the servers used by the main and update sources with
    the selected one
    """
    if combobox.get_active() == self.active_server:
        return
    server_store = combobox.get_model()
    iter = combobox.get_active_iter()
    uri = server_store.get_value(iter, 1)
    name = server_store.get_value(iter, 0)
    if name == _("Other..."):
        dialog = DialogMirror(self.window_main, 
                              self.datadir,
                              self.distro,
                              self.custom_mirrors)
        res = dialog.run()
        if res != None:
            self.backend.ChangeMainDownloadServer(res)
        else:
            combobox.set_active(self.active_server)
    elif uri != None and len(self.distro.used_servers) > 0:
        self.active_server = combobox.get_active()
        self.backend.ChangeMainDownloadServer(uri)
    # mvo: is this still needed?
    #else:
    #    self.distro.default_server = uri

  def on_component_toggled(self, checkbutton, comp):
    """
    Sync the components of all main sources (excluding cdroms),
    child sources and source code sources
    """
    if checkbutton.get_active() == True:
        self.backend.EnableComponent(comp)
    else:
        self.backend.DisableComponent(comp)

  def on_checkbutton_child_toggled(self, checkbutton, template):
    """
    Enable or disable a child repo of the distribution main repository
    """
    if checkbutton.get_active() == False:
        self.backend.DisableChildSource(template.name)
    else:
        self.backend.EnableChildSource(template.name)
          
  def on_checkbutton_source_code_toggled(self, checkbutton):
    """ Disable or enable the source code for all sources """
    if checkbutton.get_active() == True:
        self.backend.EnableSourceCodeSources()
    else:
        self.backend.DisableSourceCodeSources()

  def on_checkbutton_popcon_toggled(self, widget):
    """ The user clicked on the popcon paritipcation button """
    # only trigger the backend if something actually changed
    do_popcon = self.get_popcon_participation()
    if widget.get_active() != do_popcon:
        self.backend.SetPopconPariticipation(widget.get_active())

  def open_file(self, file):
    """Show a confirmation for adding the channels of the specified file"""
    dialog = DialogAddSourcesList(self.window_main,
                                  self.sourceslist,
                                  self.render_source,
                                  self.get_comparable,
                                  self.datadir,
                                  file)
    (res, new_sources) = dialog.run()
    if res == RESPONSE_REPLACE:
        self.sourceslist.list = []
    if res in (RESPONSE_ADD, RESPONSE_REPLACE):
        for source in new_sources:
            self.backend.AddSourceFromLine(str(source))

  def on_sources_drag_data_received(self, widget, context, x, y,
                                     selection, target_type, timestamp):
      """Extract the dropped file pathes and open the first file, only"""
      uri = selection.data.strip()
      uri_splitted = uri.split()
      if len(uri_splitted)>0:
          self.open_file(uri_splitted[0])

  def hide(self):
    self.window_main.hide()
    
  def init_isv_sources(self):
    """
    Read all valid sources into our ListStore
    """
    # STORE_ACTIVE - is the source enabled or disabled
    # STORE_DESCRIPTION - description of the source entry
    # STORE_SOURCE - the source entry object
    # STORE_SEPARATOR - if the entry is a separator
    # STORE_VISIBLE - if the entry is shown or hidden
    self.cdrom_store = Gtk.ListStore(GObject.TYPE_BOOLEAN, 
                                     GObject.TYPE_STRING,
                                     GObject.TYPE_PYOBJECT,
                                     GObject.TYPE_BOOLEAN,
                                     GObject.TYPE_BOOLEAN)
    self.treeview_cdroms.set_model(self.cdrom_store)
    self.source_store = Gtk.ListStore(GObject.TYPE_BOOLEAN, 
                                      GObject.TYPE_STRING,
                                      GObject.TYPE_PYOBJECT,
                                      GObject.TYPE_BOOLEAN,
                                      GObject.TYPE_BOOLEAN)
    self.treeview_sources.set_model(self.source_store)
    self.treeview_sources.set_row_separator_func(self.is_separator,
                                                 STORE_SEPARATOR)

    cell_desc = Gtk.CellRendererText()
    cell_desc.set_property("xpad", 2)
    cell_desc.set_property("ypad", 2)
    col_desc = Gtk.TreeViewColumn(_("Software Sources"), cell_desc,
                                  markup=COLUMN_DESC)
    col_desc.set_max_width(1000)

    cell_toggle = Gtk.CellRendererToggle()
    cell_toggle.set_property("xpad", 2)
    cell_toggle.set_property("ypad", 2)
    self.handlers.append([cell_toggle,
                          cell_toggle.connect('toggled', 
                                              self.on_isv_source_toggled, 
                                              self.cdrom_store)])
    col_active = Gtk.TreeViewColumn(_("Active"), cell_toggle,
                                    active=COLUMN_ACTIVE)

    self.treeview_cdroms.append_column(col_active)
    self.treeview_cdroms.append_column(col_desc)

    cell_desc = Gtk.CellRendererText()
    cell_desc.set_property("xpad", 2)
    cell_desc.set_property("ypad", 2)
    col_desc = Gtk.TreeViewColumn(_("Software Sources"), cell_desc,
                                  markup=COLUMN_DESC)
    col_desc.set_max_width(1000)

    cell_toggle = Gtk.CellRendererToggle()
    cell_toggle.set_property("xpad", 2)
    cell_toggle.set_property("ypad", 2)
    self.handlers.append([cell_toggle,
                          cell_toggle.connect('toggled', 
                                              self.on_isv_source_toggled, 
                                              self.source_store)])
    col_active = Gtk.TreeViewColumn(_("Active"), cell_toggle,
                                    active=COLUMN_ACTIVE)

    self.treeview_sources.append_column(col_active)
    self.treeview_sources.append_column(col_desc)
    # drag and drop support for sources.list
    try:
        Gtk.drag_dest_set(self.treeview_sources, Gtk.DestDefaults.ALL,
                                            [Gtk.TargetEntry.new('text/uri-list', 0, 0)],
                                            Gdk.DragAction.COPY)
        self.treeview_sources.connect("drag_data_received",
                                      self.on_sources_drag_data_received)
    except AttributeError:
        # does not work with Gtk2/GI
        pass

  def on_isv_source_activate(self, treeview, path, column):
    """Open the edit dialog if a channel was double clicked"""
    self.on_edit_clicked(treeview)

  def on_treeview_sources_cursor_changed(self, treeview):
    """Enable the buttons remove and edit if a channel is selected"""
    sel = self.treeview_sources.get_selection()
    (model, iter) = sel.get_selected()
    if iter:
        self.button_edit.set_sensitive(True)
        self.button_remove.set_sensitive(True)
    else:
        self.button_edit.set_sensitive(False)
        self.button_remove.set_sensitive(False)
  
  def on_isv_source_toggled(self, cell_toggle, path, store):
    """Enable or disable the selected channel"""
    #FIXME cdroms need to disable the comps in the childs and sources
    iter = store.get_iter((int(path),))
    source_entry = store.get_value(iter, STORE_SOURCE) 
    self.backend.ToggleSourceUse(str(source_entry))

  def init_keys(self):
    """Setup the user interface parts needed for the key handling"""
    self.keys_store = Gtk.ListStore(str)
    self.treeview_auth.set_model(self.keys_store)
    tr = Gtk.CellRendererText()
    keys_col = Gtk.TreeViewColumn("Key", tr, text=0)
    self.treeview_auth.append_column(keys_col)
    try:
        self.treeview_auth.enable_model_drag_dest(
          [('text/plain', 0, 0)], Gdk.DragAction.COPY)
        self.treeview_auth.connect("drag_data_received",
                                      self.on_auth_drag_data_received)
    except AttributeError:
        # Does not work with GTK 2/GI
        pass

    self.treeview_auth.connect("button-press-event",
                               self.show_auth_context_menu)

  def show_auth_context_menu(self, widget, event):
    if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
      menu = Gtk.Menu()
      item_paste = Gtk.MenuItem(label=_("_Add key from paste data"))
      item_paste.connect("activate", self.on_auth_add_key_from_paste)
      menu.add(item_paste)
      menu.popup(None, None, None, 0, event.time)
      menu.show_all()
      return True

  def on_auth_add_key_from_paste(self, widget):
    keydata = Gtk.Clipboard().wait_for_text()
    if not keydata:
      return
    if not self.add_key_from_data(keydata):
      error(self.window_main,
            _("Error importing key"),
            _("The selected data may not be a GPG key file "
              "or it might be corrupt."))
    self.show_keys()

  def on_auth_drag_data_received(self, widget, context, x, y,
                                 selection, target_type, timestamp):
      """Extract the dropped key and add it to the keyring"""
      keydata = selection.data.strip()
      if not self.add_key_from_data(keydata):
        error(self.window_main,
              _("Error importing key"),
              _("The selected data may not be a GPG key file "
                "or it might be corrupt."))
      self.show_keys()

  def on_button_revert_clicked(self, button):
      """Restore the source list from the startup of the dialog"""
      self.backend.Revert()
      if self.settings:
          self.settings.set_int("regular-auto-launch-interval", self.initial_auto_launch)
      self.show_auto_update_level()
      self.button_revert.set_sensitive(False)
      self.modified_sourceslist = False

  # dbus events
  def on_config_modified(self):
    """The config was changed and now needs to be saved and reloaded"""
    apt.apt_pkg.init_config()
    self.button_revert.set_sensitive(True)

  def on_keys_modified(self):
    """ The apt keys have changed and need to be redisplayed """
    self.show_keys()

  def on_sources_list_modified(self):
    """The sources list was changed and now needs to be saved and reloaded"""
    self.reload_sourceslist()
    self.show_distro()
    self.show_isv_sources()
    self.show_cdrom_sources()
    self.button_revert.set_sensitive(True)

  def on_auth_failed(self):
    """ send when the authentication failed """
    # reread the current config
    self.on_sources_list_modified()
    self.on_config_modified()
    self.on_keys_modified()

  def on_cdrom_scan_failed(self):
      error(self.window_main,
            _("Error scanning the CD"),
            _("Could not find a suitable CD."))

  # helpers
  def show_isv_sources(self):
    """ Show the repositories of independent software vendors in the
        third-party software tree view """
    self.source_store.clear()

    for source in self.get_isv_sources():
        contents = self.render_source(source)
        self.source_store.append([not source.disabled, contents,
                                  source, False, True])

    (path_x, path_y) = self.treeview_sources.get_cursor()
    if len(self.source_store) < 1 or path_x <0:
        self.button_remove.set_sensitive(False)
        self.button_edit.set_sensitive(False)

  def show_cdrom_sources(self):
    """ Show CD-ROM/DVD based repositories of the currently used distro in
        the CDROM based sources list """
    self.cdrom_store.clear()
    for source in self.get_cdrom_sources():
        contents = self.render_source(source)
        self.cdrom_store.append([not source.disabled, contents,
                                source, False, True])
    
  def is_separator(self, model, iter, column):
    """ Return true if the selected row is a separator """
    try:
      return model.get_value(iter, column)
    except Exception, e:
      print "is_seperator returned '%s' " % e
      return False
      
  def show_keys(self):
    self.keys_store.clear()
    for key in self.apt_key.list():
      self.keys_store.append([key])

  def on_combobox_update_interval_changed(self, widget):
    """Set the update automation interval to the chosen one"""
    i = self.combobox_update_interval.get_active()
    if i != -1:
        value = self.combobox_interval_mapping[i]
        self.backend.SetUpdateInterval(value)

  def on_add_clicked(self, widget):
    """Show a dialog that allows to enter the apt line of a to be used repo"""
    dialog = DialogAdd(self.window_main, self.sourceslist,
                       self.datadir, self.distro)
    line = dialog.run()
    if line != None:
      self.backend.AddSourceFromLine(line)

  def on_edit_clicked(self, widget):
    """Show a dialog to edit an ISV source"""
    sel = self.treeview_sources.get_selection()
    (model, iter) = sel.get_selected()
    if not iter:
      return
    old_source_entry = model.get_value(iter, LIST_ENTRY_OBJ)
    dialog = DialogEdit(self.window_main, self.sourceslist,
                        old_source_entry, self.datadir)
    if dialog.run() == Gtk.ResponseType.OK:
        self.backend.ReplaceSourceEntry(str(old_source_entry), 
                                        str(dialog.new_source_entry))

  # FIXME:outstanding from merge
  def on_isv_source_activated(self, treeview, path, column):
     """Open the edit dialog if a channel was double clicked"""
     # check if the channel can be edited
     if self.button_edit.get_property("sensitive") == True:
         self.on_edit_clicked(treeview)

  # FIXME:outstanding from merge
  def on_treeview_sources_cursor_changed(self, treeview):
    """set the sensitiveness of the edit and remove button
       corresponding to the selected channel"""
    sel = self.treeview_sources.get_selection()
    (model, iter) = sel.get_selected()
    if not iter:
        # No channel is selected, so disable edit and remove
        self.button_edit.set_sensitive(False)
        self.button_remove.set_sensitive(False)
        return
    # allow to remove the selected channel
    self.button_remove.set_sensitive(True)
    # disable editing of cdrom sources
    source_entry = model.get_value(iter, LIST_ENTRY_OBJ)
    if source_entry.uri.startswith("cdrom:"):
        self.button_edit.set_sensitive(False)
    else:
        self.button_edit.set_sensitive(True)

  def on_remove_clicked(self, widget):
    """Remove the selected source"""
    model = self.treeview_sources.get_model()
    (path, column) = self.treeview_sources.get_cursor()
    iter = model.get_iter(path)
    if iter:
        source_entry = model.get_value(iter, LIST_ENTRY_OBJ)
        self.backend.RemoveSource(str(source_entry))

  def add_key_clicked(self, widget):
    """Provide a file chooser that allows to add the gnupg of a trusted
       software vendor"""
    chooser = Gtk.FileChooserDialog(title=_("Import key"),
                                    parent=self.window_main,
                                    buttons=(Gtk.STOCK_CANCEL,
                                             Gtk.ResponseType.REJECT,
                                             Gtk.STOCK_OK,Gtk.ResponseType.ACCEPT))
    if "SUDO_USER" in os.environ:
        home = os.path.expanduser("~%s" % os.environ["SUDO_USER"])
        chooser.set_current_folder(home)
    res = chooser.run()
    chooser.hide()
    if res == Gtk.ResponseType.ACCEPT:
      if not self.backend.AddKey(chooser.get_filename()):
        error(self.window_main,
              _("Error importing selected file"),
              _("The selected file may not be a GPG key file " \
                "or it might be corrupt."))

  def remove_key_clicked(self, widget):
    """Remove a trusted software vendor key"""
    selection = self.treeview_auth.get_selection()
    (model,a_iter) = selection.get_selected()
    if a_iter == None:
        return
    key = model.get_value(a_iter,0)
    if not self.backend.RemoveKey(key[:8]):
      error(self.main,
        _("Error removing the key"),
        _("The key you selected could not be removed. "
          "Please report this as a bug."))

  def on_restore_clicked(self, widget):
    """Restore the original keys"""
    self.backend.UpdateKeys()

  def on_delete_event(self, widget, args):
    """Close the window if requested"""
    self.on_close_button(widget)

  def on_close_button(self, widget):
    """Show a dialog that a reload of the channel information is required
       only if there is no parent defined"""
    if (self.modified_sourceslist == True and
        self.options.no_update == False):
        d = DialogCacheOutdated(self.window_main,
                                self.datadir)
        res = d.run()
    self.quit()

  def on_button_add_cdrom_clicked(self, widget):
      """ when a cdrom is requested for adding """
      self.backend.AddCdromSource()
