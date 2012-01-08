#
# Copyright (C) 2010 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2010 Ken VanDine <ken.vandine@canonical.com>
#
# Preferences interface for Gwibber
#

import pygtk
try:
  pygtk.require("2.0") 
except:
  print "Requires pygtk 2.0 or later"
  exit

import gtk, gconf
from gwibber import util
from microblog.util import resources
from microblog import config

import gettext
from gettext import lgettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
  gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

from microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from microblog.util.custom import *
except:
  pass

from microblog.urlshorter import PROTOCOLS as urlshorters

from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)

class GwibberPreferences(object):
  def __init__(self):
    self.ui = gtk.Builder()
    self.ui.set_translation_domain("gwibber")
    self.ui.add_from_file(resources.get_ui_asset("gwibber-preferences-dialog.ui"))
    self.ui.connect_signals(self)
    self.gc = gconf.client_get_default()
    dialog = self.ui.get_object("prefs_dialog")
    dialog.set_icon_from_file(resources.get_ui_asset("gwibber.svg"))

    self.settings = config.Preferences()
    
    setting_keys = [
      "autostart",
      "show_notifications",
      "notify_mentions_only",
      "no_notifications",
      "show_fullname",
      "shorten_urls",
      "reply_append_colon",
      "global_retweet",
      "interval",
      "minimize_to_tray",
      "hide_taskbar_entry",
      "show_tray_icon",
    ]

    for key in setting_keys:
      self.settings.bind(self.ui.get_object(key), key)

    self.populate_settings_widgets()

    for key in ["theme", "urlshorter", "retweet_style"]:
      # Don't blow up if these values aren't set to something expected
      # just reset to the default and carry on
      try:
        self.settings.bind(getattr(self, key + "_selector"), key)
      except:
        config.GCONF.set_value(config.GCONF_PREFERENCES_DIR + "/" + key, self.settings.defaults[key])
        self.settings.bind(getattr(self, key + "_selector"), key)

    dialog.show_all()

  def populate_settings_widgets(self):
    self.theme_selector = gtk.combo_box_new_text()
    for theme in sorted(resources.get_themes()): self.theme_selector.append_text(theme)
    self.ui.get_object("theme_container").pack_start(self.theme_selector, True, True)
    self.theme_selector.set_active_iter(dict([(x[0].strip(), x.iter) for x in self.theme_selector.get_model()]).get(
      self.settings["theme"], self.theme_selector.get_model().get_iter_root()))
    self.theme_selector.show_all()
    self.urlshorter_selector = gtk.combo_box_new_text()
    for urlshorter in urlshorters.keys(): self.urlshorter_selector.append_text(urlshorter)
    self.ui.get_object("urlshorter_container").pack_start(self.urlshorter_selector, True, True)

    self.urlshorter_selector.set_active_iter(dict([(x[0].strip(), x.iter) for x in self.urlshorter_selector.get_model()]).get(
      self.settings["urlshorter"], self.urlshorter_selector.get_model().get_iter_root()))
    self.urlshorter_selector.show_all()

    self.retweet_style_selector = gtk.combo_box_new_text()
    for format in RETWEET_FORMATS: self.retweet_style_selector.append_text(format)
    self.ui.get_object("retweet_style_container").pack_start(self.retweet_style_selector, True, True)
    self.retweet_style_selector.set_active_iter(dict([(x[0].strip(), x.iter) for x in self.retweet_style_selector.get_model()]).get(
      self.settings["retweet_style"], self.retweet_style_selector.get_model().get_iter_root()))
    self.retweet_style_selector.show_all()

  def on_close_button_clicked(self, widget, data=None):
    gtk.main_quit()
    
  def on_prefs_dialog_destroy_event(self, widget, data=None):
    gtk.main_quit()

