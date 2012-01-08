# -*- coding: utf-8 -*-
# Copyright (c) 2008 Sebastian Dröge <sebastian.droege@collabora.co.uk>, GPL

import gettext
from gettext import gettext as _
import gobject
import gtk
import pango
import gst
import gst.pbutils
import apt
import apt_pkg
import os
import PackageWorker


# the list columns
(LIST_PKG_TO_INSTALL,
 LIST_PKG_NAME,
 LIST_PKG_REQUEST) = range(3)

# codecs that might be problematic for patent reasons
CODEC_WARNING_LIST = [ "gstreamer0.10-plugins-bad",
                       "gstreamer0.10-plugins-bad-multiverse",
                       "gstreamer0.10-ffmpeg",
                       "gstreamer0.10-plugins-ugly",
                     ]

class CodecDetailsView(gtk.TextView):
  " special view to display for the codec information "
  def __init__(self):
    gtk.TextView.__init__(self)
    self.set_property("editable", False)
    self.set_cursor_visible(False)
    self.set_wrap_mode(gtk.WRAP_WORD)
    self.buffer = gtk.TextBuffer()
    self.set_buffer(self.buffer)
    # tag names for the elements we insert
    self.buffer.create_tag("summary", 
                           scale=pango.SCALE_LARGE,
                           weight=pango.WEIGHT_BOLD)
    self.buffer.create_tag("homepage", 
                           weight=pango.WEIGHT_BOLD)
    self.buffer.create_tag("provides", 
                           weight=pango.WEIGHT_BOLD)
    self.buffer.create_tag("description", 
                           weight=pango.WEIGHT_BOLD)
    self.buffer.insert_with_tags_by_name(self.buffer.get_start_iter(),
                                         _("No package selected"),
                                         "summary")

  def show_codec(self, pkg=None, requests=None):
    # clear the buffer
    self.buffer.set_text("")
    iter = self.buffer.get_start_iter()
    self.buffer.place_cursor(iter)
    # if nothing is selected we are done
    if pkg is None:
      self.buffer.insert_with_tags_by_name(iter,
                                           _("No package selected"),
                                           "summary")
      return

    assert pkg.candidate
    # now format the description
    self.buffer.insert_with_tags_by_name(iter, 
                                         pkg.candidate.summary,
                                         "summary")
    self.buffer.insert(iter, "\n\n")
    if pkg.candidate.homepage:
      self.buffer.insert_with_tags_by_name(iter, 
                                           _("Homepage:")+"\n", 
                                           "homepage")
      self.buffer.insert(iter, pkg.candidate.homepage + "\n\n")
    self.buffer.insert_with_tags_by_name(iter, 
                                         _("Provides:")+"\n", 
                                         "provides")
    for request in requests:
      self.buffer.insert(iter, request.description + "\n")
    self.buffer.insert(iter, "\n")
    self.buffer.insert_with_tags_by_name(iter, 
                                         _("Long Description:")+"\n", 
                                         "description")
    self.buffer.insert(iter, pkg.candidate.description + "\n")

def set_transient_for_xid(widget, xid):
  try:
    if xid != None:
      parent = gtk.gdk.window_foreign_new(xid)
      if parent != None:
        widget.realize()
        widget.get_window().set_transient_for(parent)
  except:
    pass

class MainWindow(object):

  def __init__(self,requests,xid):
    self._requests = requests
    self._window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    self._window.set_title(_("Install Multimedia Plugins"))
    self._window.set_property("default_width", 600)
    self._window.set_property("default_height", 500)
    self._window.set_border_width(10)
    self._window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

    self._return_code = gst.pbutils.INSTALL_PLUGINS_NOT_FOUND

    self._window.connect("delete_event", self._delete_event)
    self._window.connect("destroy", self._destroy)
    set_transient_for_xid(self._window, xid)

    vbox_window = gtk.VBox()
    vbox_packages = gtk.VBox(homogeneous=False)

    label = gtk.Label()
    label.set_line_wrap(True)
    label.set_justify(gtk.JUSTIFY_LEFT)
    label.set_alignment(0.0, 0.0)

    plugins = ""
    for request in self._requests:
      plugins += "\n- " + request.description
    label.set_markup(_("<b><big>Please select the packages for installation "
                       "to provide the following plugins:</big></b>\n") + plugins)
    vbox_packages.pack_start(label, False, False, 10)

    self._package_list_model = gtk.ListStore(gobject.TYPE_BOOLEAN, 
                                             gobject.TYPE_STRING, 
                                             gobject.TYPE_PYOBJECT)

    self._package_list = gtk.TreeView(self._package_list_model)
    self._package_list.set_headers_visible(True)
    self._package_list.connect("cursor-changed", self._package_cursor_changed)
    
    toggle_renderer = gtk.CellRendererToggle()
    toggle_renderer.connect("toggled", self._toggle_install)
    self._package_list.append_column(gtk.TreeViewColumn(None, toggle_renderer, active=0))
    text_renderer = gtk.CellRendererText()
    text_renderer.set_data("column", 1)
    self._package_list.append_column(gtk.TreeViewColumn(_("Package"), text_renderer, text=1))

    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    #scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.add(self._package_list)

    vbox_packages.pack_start(scrolled_window, True, True, 10)

    expander = gtk.Expander(_("Details") + ":")
    expander.connect("notify::expanded", self._package_details_expanded)

    self._package_details = CodecDetailsView()
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    #scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.add_with_viewport(self._package_details)

    expander.add(scrolled_window)
    vbox_packages.pack_start(expander, False, False, 10)
    
    vbox_window.pack_start(vbox_packages, True, True, 0)

    button_box = gtk.HButtonBox()
    button_box.set_layout(gtk.BUTTONBOX_END)
    button_box.set_spacing(5)

    #TODO integrate help by calling yelp
    #btn = gtk.Button(_("Help"), gtk.STOCK_HELP)
    #button_box.add(btn)
    #button_box.set_child_secondary(btn, True)

    btn = gtk.Button(_("Cancel"), gtk.STOCK_CANCEL)
    btn.connect("clicked", self._canceled)
    button_box.add(btn)

    btn = gtk.Button(_("Install"), None)
    btn.connect("clicked", self._install_selection)
    button_box.add(btn)

    vbox_window.pack_start(button_box, False, False, 0)    
    self._window.add(vbox_window)

    self._window.show_all()


  def modal_dialog(self, type, primary, secondary=""):
    " helper that shows a modal dialog of the given type "
    dlg = gtk.MessageDialog(self._window, 
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, 
                            type,
                            gtk.BUTTONS_OK, 
                            primary)
    dlg.set_title(primary)
    dlg.format_secondary_text(secondary)
    res = dlg.run()
    dlg.destroy()
    return res

  def _package_cursor_changed(self, treeview, data=None):
    selection = treeview.get_selection()
    (model, iter) = selection.get_selected()
    if iter:
      pkgname = model.get_value(iter, LIST_PKG_NAME)
      requests = model.get_value(iter, LIST_PKG_REQUEST)
      self._package_details.show_codec(self.cache[pkgname], requests)
    else:
      self._package_details.show_codec(None)

  def _package_details_expanded(self, expander, param_spec, data=None):
    if expander.get_expanded():
      expander.get_child().show_all()
      expander.set_size_request(-1, 120)
    else:
      expander.set_size_request(-1, -1)
      expander.get_child().hide_all()

  def _confirm_codec_install(self, install_list):
    " helper that shows a codec warning dialog "
    for pkgname in CODEC_WARNING_LIST:
      if pkgname in install_list:
        break
    else:
      return
    dia = gtk.MessageDialog(parent=self._window,
                            type=gtk.MESSAGE_WARNING,
                            buttons=gtk.BUTTONS_CANCEL)
    header = _("Confirm installation of restricted software")
    body = _("The use of this software may be "
             "restricted in some countries. You "
             "must verify that one of the following is true:\n\n"
             "* These restrictions do not apply in your country "
             "of legal residence\n"
             "* You have permission to use this software (for "
             "example, a patent license)\n"
             "* You are using this software for research "
             "purposes only")
    dia.set_markup("<big><b>%s</b></big>\n\n%s" % (header,body))
    dia.add_button(_("C_onfirm"), gtk.RESPONSE_OK)
    res = dia.run()
    dia.hide()
    if res != gtk.RESPONSE_OK:
      return False
    return True

  def _toggle_install(self, cell, path, data=None):
    iter = self._package_list_model.get_iter((int(path),))
    enabled = self._package_list_model.get_value(iter, LIST_PKG_TO_INSTALL)
    enabled = not enabled
    self._package_list_model.set(iter, LIST_PKG_TO_INSTALL, enabled)

  def _populate_list(self):
    dlg = gtk.Dialog(_("Searching Plugin Packages"), self._window, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, None)
    dlg.set_has_separator(False)
    dlg.set_deletable(False)
    dlg.set_border_width(5)

    label = gtk.Label()
    label.set_markup("<b><big>" + _("Searching Plugin Packages") + "</big></b>\n" + 
                     _("This might take up to one or two minutes."))

    dlg.vbox.pack_start(label, True, True, 5)

    progressbar = gtk.ProgressBar()
    progressbar.set_fraction(0.0)
    dlg.vbox.pack_start(progressbar, True, True, 5)

    dlg.show_all()

    self.update_ui()

    progressbar.set_text(_("Loading package cache..."))
    self.cache = apt.Cache(PackageWorker.GtkOpProgress())
    
    self.update_ui()
    
    npackages = 0

    package_count = len(self.cache)
    
    progressbar.set_text(_("Searching for requested plugins..."))

    # maps request to pkgrecord entry and provide information if
    # gst caps must be used or the string needs to be split 
    requests_map = [
      #  request    pkgrecord             caps  split
      ("decoder", "Gstreamer-Decoders", True, False),
      ("encoder", "Gstreamer-Encoders", True, False),
      ("urisource", "Gstreamer-Uri-Sources", False, True),
      ("urisink", "Gstreamer-Uri-Sinks", False, True),
      ("element", "Gstreamer-Elements", False, True),
    ]

    # iterate all the packages
    for (cur_package, pkg) in enumerate(self.cache):

      if cur_package % 500 == 0:
        progressbar.set_fraction(float(cur_package) / package_count)

      self.update_ui()
      if pkg.is_installed and not pkg.is_upgradable:
        continue

      # prefer native versions on a multiarch system
      if ":" in pkg.name and pkg.name.split(":")[0] in self.cache:
        continue
      
      try:
        record = pkg.candidate.record
      except AttributeError:
        continue
      try:
        major, minor = record["Gstreamer-Version"].split(".")
      except KeyError:
        continue

      if (int(major) != self._requests[0].major or 
          int(minor) != self._requests[0].minor):
        continue

      add_pkg = False
      pkg_requests = []

      # check requests
      for request in self._requests:
        self.update_ui()

        for (request_str, pkgrecord_str, check_caps, do_split) in requests_map:
          if request.gstkind == request_str:
            if not pkgrecord_str in record:
              continue
            if check_caps:
              caps = gst.Caps(record[pkgrecord_str])
              if request.caps.intersect(caps):
                add_pkg = True
                pkg_requests.append(request)
                break
            if do_split:
              elms = record[pkgrecord_str].split(",")
              if request.feature in elms:
                add_pkg = True
                pkg_requests.append(request)
                break

      if add_pkg:
        npackages += 1
        iter = self._package_list_model.append()
        self._package_list_model.set(iter,
                                     LIST_PKG_TO_INSTALL, True,
                                     LIST_PKG_NAME, pkg.name,
                                     LIST_PKG_REQUEST, pkg_requests)
    
    self._package_list_model.set_sort_column_id(LIST_PKG_NAME, gtk.SORT_ASCENDING)
    self.update_ui()

    dlg.destroy()
    return npackages

#  def _on_button_help_clicked(self, widget):
#      if os.path.exists("/usr/bin/yelp"):
#          subprocess.Popen(["/usr/bin/yelp", "ghelp:gnome-codec-install"])
#      else:
#          d = gtk.MessageDialog(parent=self.window_main,
#                                flags=gtk.DIALOG_MODAL,
#                                type=gtk.MESSAGE_ERROR,
#                                buttons=gtk.BUTTONS_CLOSE)
#          header = _("No help available")
#          msg = _("To display the help, you need to install the "
#                  "\"yelp\" application.")
#          d.set_title("")
#          d.set_markup("<big><b>%s</b></big>\n\n%s" % (header, msg))
#          d.run()
#          d.destroy()

  def _delete_event(self, widget, event, data=None):
    return False

  def _destroy(self, widget, data=None):
    gtk.main_quit()

  def _canceled(self, widget, data=None):
    self._return_code = gst.pbutils.INSTALL_PLUGINS_USER_ABORT
    gtk.main_quit()

  def update_ui(self):
    " helper that processes all pending events "
    while gtk.events_pending():
      gtk.main_iteration()

  def _install_selection(self, widget, data=None):
    iter = self._package_list_model.get_iter_first()
    packages = []

    while iter:
      if self._package_list_model.get_value(iter, LIST_PKG_TO_INSTALL):
        packages.append((self._package_list_model.get_value(iter, LIST_PKG_NAME), 
                         self._package_list_model.get_value(iter, LIST_PKG_REQUEST)))
      iter = self._package_list_model.iter_next(iter)

    if not packages or len(packages) == 0:
      self.modal_dialog(gtk.MESSAGE_WARNING,
                        _("No packages selected"))
      self._return_code = gst.pbutils.INSTALL_PLUGINS_NOT_FOUND
      return

    # check codec install message
    if not self._confirm_codec_install(set([package[LIST_PKG_TO_INSTALL] for package in packages])):
      return

    worker = PackageWorker.get_worker()
    install_success = worker.perform_action(self._window, set([package[LIST_PKG_TO_INSTALL] for package in packages]), set())

    if install_success:
      if not self._requests or len(self._requests) == 0:
        self.modal_dialog(gtk.MESSAGE_INFO,
                          _("Packages successfully installed"),
                          _("The selected packages were successfully "
                            "installed and provided all requested plugins"))
        self._return_code = gst.pbutils.INSTALL_PLUGINS_SUCCESS
      else:
        self.modal_dialog(gtk.MESSAGE_INFO,
                          _("Packages successfully installed"),
                          _("The selected packages were successfully "
                            "installed but did not provide all requested "
                            "plugins"))
        self._return_code = gst.pbutils.INSTALL_PLUGINS_PARTIAL_SUCCESS
    else:
      self.modal_dialog(gtk.MESSAGE_ERROR,
                        _("No packages installed"),
                        _("None of the selected packages were installed."))
      self._return_code = gst.pbutils.INSTALL_PLUGINS_ERROR
    gtk.main_quit()

  def _apt_lists_dir_has_missing_files(self):
    """ check if sources.list contains entries that are not in
        /var/lib/apt/lists - this can happen if the lists/ dir
        is not fresh

        Returns True if there is a file missing
    """
    for metaindex in self.cache._list.list:
      for m in metaindex.index_files:
        if m.label == "Debian Package Index" and not m.exists:
          print "Missing package list: ", m
          return True
    return False
          
  def _ask_perform_update(self):
    dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION, gtk.BUTTONS_CANCEL,
                            _("Update package list?"))
    dlg.format_secondary_text(_("The package information is incomplete "
                                "and needs to be updated."))
    btn = dlg.add_button(_("_Update"), gtk.RESPONSE_YES)
    btn.grab_focus()
    dlg.set_title("")
    dlg.set_transient_for(self._window)
    res = dlg.run()
    dlg.destroy()
    return res == gtk.RESPONSE_YES

  def _show_no_codecs_error(self):
    plugins = ""
    for request in self._requests:
      plugins += "\n" + request.description
    self.modal_dialog(gtk.MESSAGE_WARNING,
                      _("No packages with the requested plugins found"),
                      _("The requested plugins are:\n") + plugins)

  def main(self):
    npackages = self._populate_list()
    if npackages == 0:
      if self._apt_lists_dir_has_missing_files():
        if self._ask_perform_update():
          worker = PackageWorker.get_worker()
          worker.perform_update(self._window)
          npackages = self._populate_list()
          if npackages == 0:
            self._show_no_codecs_error()
            return gst.pbutils.INSTALL_PLUGINS_NOT_FOUND
      else:
        self._show_no_codecs_error()
        return gst.pbutils.INSTALL_PLUGINS_NOT_FOUND
    gtk.main()
    return self._return_code

