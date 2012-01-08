# -*- coding: utf-8 -*-
# Copyright (c) 2008 Sebastian Dröge <sebastian.droege@collabora.co.uk>, GPL

import sys
import gtk
import gettext
from gettext import gettext as _
import re

# from gst.pbutils - copied to avoid overhead of the import
(INSTALL_PLUGINS_SUCCESS,
 INSTALL_PLUGINS_NOT_FOUND,
 INSTALL_PLUGINS_ERROR,
 INSTALL_PLUGINS_PARTIAL_SUCCESS,
 INSTALL_PLUGINS_USER_ABORT) = range(5)

class Request(object):
  def __init__(self, major, minor, app, descr, kind, caps=None, feature=None):
    self.major = major
    self.minor = minor
    self.application = app
    self.description = descr
    self.gstkind = kind      # decoder, encoder, urisink, urisource, ...
    self.caps = caps
    self.feature = feature

def parse_arguments(args):
  regex = re.compile("^gstreamer\|([0-9])+\.([0-9]+)\|(.+)\|(.+)\|([a-z]+)-(.*)[|]?")
  requests = []
  xid = None
  gst_init = False
  major = 0
  minor = 0
  for arg in args:
    if arg[0:16] == "--transient-for=":
      try:
        xid = int(arg[16:])
      except:
        pass
      continue
    elif arg[0:2] == "--":
      continue

    match = regex.search(arg)
    if not match:
      continue
    try:
      r_major = int(match.group(1))
      r_minor = int(match.group(2))
      if not gst_init:
        import pygst
        pygst.require("%d.%d" % (r_major, r_minor))
        import gst
        gst_init = True
        major = r_major
        minor = r_minor
      elif r_major != major or r_minor != minor:
        return None
    except ValueError:
      continue

    if match.group(5) == "decoder" or match.group(5) == "encoder":
      try:
        requests.append(Request(major, minor, match.group(3), match.group(4), match.group(5), caps=gst.Caps(match.group(6))))
      except TypeError:
        continue
    elif match.group(5) == "urisource" or match.group(5) == "urisink" or match.group(5) == "element":
      requests.append(Request(major, minor, match.group(3), match.group(4), match.group(5), feature=match.group(6)))
    else:
      continue
  return (requests, xid)

def set_transient_for_xid(widget, xid):
  try:
    if xid != None:
      parent = gtk.gdk.window_foreign_new(xid)
      if parent != None:
        widget.realize()
        widget.get_window().set_transient_for(parent)
  except:
    pass

def main(args):
  gettext.textdomain("gnome-codec-install")
  gettext.bindtextdomain("gnome-codec-install")

  (requests, xid) = parse_arguments(args)

  try:
    icon = gtk.icon_theme_get_default().load_icon("gnome-codec-install", 32, 0)
  except:
    icon = None
  if icon:
    gtk.window_set_default_icon(icon)

  if requests == None or len(requests) == 0:
    sys.stderr.write("invalid commandline '%s'\n" % (args))
    dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                            gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                            _("Invalid commandline"))
    dlg.format_secondary_text(_("The parameters passed to the application "
                                "had an invalid format. Please file a bug!\n\n"
                                "The parameters were:\n%s") % ("\n".join(map(str, args))))
    dlg.set_title(_("Invalid commandline"))
    set_transient_for_xid(dlg, xid)
    dlg.run()
    dlg.destroy()
    exit(INSTALL_PLUGINS_ERROR)
  else:
    dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                            gtk.MESSAGE_QUESTION, gtk.BUTTONS_CANCEL,
                            _("Search for suitable plugin?"))
    dlg.format_secondary_text(_("The required software to play this "
                              "file is not installed. You need to install "
                              "suitable plugins to play "
                              "media files. Do you want to search for a plugin "
                              "that supports the selected file?\n\n"
                              "The search will also include software which is not "
                              "officially supported."))
    btn = dlg.add_button(_("_Search"), gtk.RESPONSE_YES)
    btn.grab_focus()
    dlg.set_title(_("Search for suitable plugin?"))
    set_transient_for_xid(dlg, xid)
    res = dlg.run()
    dlg.destroy()
    while gtk.events_pending():
      gtk.main_iteration()
    if res != gtk.RESPONSE_YES:
      exit(INSTALL_PLUGINS_USER_ABORT)
    import MainWindow
    window = MainWindow.MainWindow(requests, xid)
    exit(window.main())

