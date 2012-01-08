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
# widgets for Gwibber
#

from dbus.mainloop.glib import DBusGMainLoop
import json
import gobject, gtk
from gwibber.microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from gwibber.microblog.util.custom import *
except:
  pass

import gwibber.microblog.util
from gwibber import util
from gwibber.microblog.util import resources

import gettext
from gettext import lgettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

class GwibberPosterVBox(gtk.VBox):
  def __init__(self, content=None):
    gtk.VBox.__init__(self)
    DBusGMainLoop(set_as_default=True)
    loop = gobject.MainLoop()
    self.service = gwibber.microblog.util.getbus("Service")

    self.input = Input(content=content)
    self.input.connect("submit", self.on_input_activate)
    self.input.connect("changed", self.on_input_changed)
    self.input_splitter = gtk.VPaned()
    self.input_splitter.add1(self.input)

    self.button_send = gtk.Button(_("Send"))
    self.button_send.connect("clicked", self.on_button_send_clicked)
    self.message_target = AccountTargetBar()
    self.message_target.pack_end(self.button_send, False)

    content = gtk.VBox(spacing=5)
    content.pack_start(self.input_splitter, True)
    content.pack_start(self.message_target, False)
    content.set_border_width(5)

    layout = gtk.VBox()
    layout.pack_start(content, True)
    self.add(layout)

  def on_input_changed(self, w, text, cnt):
    self.input.textview.set_overlay_text(str(MAX_MESSAGE_LENGTH - cnt))

  def on_input_activate(self, w, text, cnt):
    self.service.SendMessage(text)
    w.clear()

  def on_button_send_clicked(self, w):
    self.service.SendMessage(self.input.get_text())
    self.input.clear()

class AccountTargetBar(gtk.HBox):
  __gsignals__ = {
      "canceled": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ())
  }

  def __init__(self):
    gtk.HBox.__init__(self, spacing=5)
    
    self.accounts = gwibber.microblog.util.getbus("Accounts")
    self.daemon = gwibber.microblog.util.getbus("Service")
    self.services = json.loads(self.daemon.GetServices())

    self.accounts.connect_to_signal("Updated", self.on_account_changed)
    self.account_list = []

    self.targetbar = gtk.HBox(False, 6)
    self.targetbar.set_size_request(0, 24)
    self.pack_start(self.targetbar, True)

    self.buttons = {}

    self.populate()

  def on_account_changed(self, acct):
    account = json.loads(acct)
    if account.has_key("send_enabled"):
      but = self.buttons[account["id"]]
      if but.get_active () != account["send_enabled"]:
        but.set_active (account["send_enabled"])
      if not account["send_enabled"]:
        but.set_tooltip_text (account["service"] + "(" + account["username"] + ") - " + _("Disabled"))
      else:
        but.set_tooltip_text (account["service"] + "(" + account["username"] + ")")

  def populate(self):
    self.account_list = []
    for account in json.loads(self.accounts.List()):
      if self.services.has_key(account["service"]) and "send" in self.services[account["service"]]["features"]:
        self.account_list.append(account)

    for account in self.account_list:
      img = gtk.Image ()
      img.set_from_file(resources.get_ui_asset("icons/breakdance/16x16/" + account["service"] + ".png"))
      img.show();
      but = gtk.ToggleButton ()
      but.set_active (account["send_enabled"])
      if not account["send_enabled"]:
        but.set_tooltip_text (account["service"] + "(" + account["username"] + ") - " + _("Disabled"))
      else:
        but.set_tooltip_text (account["service"] + "(" + account["username"] + ")")
      but.set_image(img);
      but.connect("clicked", self.on_account_toggled, account["id"])
      self.targetbar.pack_start(but, False, False, 0)
      but.show_all ()
      but.set_focus_on_click(False)
      self.buttons[account["id"]] = but

  def on_account_toggled(self, w, id):
    account = json.loads(self.accounts.Get(id))
    if account["send_enabled"] != w.get_active ():
      self.accounts.SendEnabled(id)

class Input(gtk.Frame):
  __gsignals__ = {
    "submit": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, int)),
    "changed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, int)),
    "clear": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ())
  }

  def __init__(self, content=None):
    gtk.Frame.__init__(self)

    self.textview = InputTextView(content=content)
    self.textview.connect("submit", self.do_submit_event)
    self.textview.connect("clear", self.do_clear_event)
    self.textview.get_buffer().connect("changed", self.do_changed_event)

    scroll = gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scroll.add(self.textview)
    self.add(scroll)

    self.set_focus_child(scroll)
    scroll.set_focus_child(self.textview)

  def get_text(self):
    return self.textview.get_text()

  def set_text(self, t):
    self.textview.get_buffer().set_text(t)

  def clear(self):
    self.set_text("")

  def do_clear_event(self, seq):
    self.emit("clear")

  def do_changed_event(self, tb):
    text = self.textview.get_text()
    chars = self.textview.get_char_count()
    self.emit("changed", text, chars)

  def do_submit_event(self, tv):
    text = tv.get_text()
    chars = tv.get_char_count()
    self.emit("submit", text, chars)


class InputTextView(gtk.TextView):
  __gsignals__ = {
    "submit": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ()),
    "clear": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ())
  }

  def __init__(self, content=None):
    gtk.TextView.__init__(self)
    self.drawable = None

    self.content = content

    self.overlay_color = util.get_theme_colors()["text"].darker(3).hex
    self.overlay_text = '<span weight="bold" size="xx-large" foreground="%s">%s</span>'

    self.shortener = gwibber.microblog.util.getbus("URLShorten")

    self.connection = gwibber.microblog.util.getbus("Connection")
    self.connection.connect_to_signal("ConnectionOnline", self.on_connection_online)
    self.connection.connect_to_signal("ConnectionOffline", self.on_connection_offline)

    self.get_buffer().connect("insert-text", self.on_add_text)
    self.get_buffer().connect("changed", self.on_text_changed)
    self.connect("expose-event", self.expose_view)
    self.connect("size-allocate", self.on_size_allocate)

    # set properties
    self.set_border_width(0)
    self.set_accepts_tab(True)
    self.set_editable(False)
    self.set_cursor_visible(True)
    self.set_wrap_mode(gtk.WRAP_WORD_CHAR)
    self.set_left_margin(2)
    self.set_right_margin(2)
    self.set_pixels_above_lines(2)
    self.set_pixels_below_lines(2)

    self.base_color = util.get_style().base[gtk.STATE_NORMAL]
    self.error_color = gtk.gdk.color_parse("indianred")

    # set state online/offline
    if not self.connection.isConnected():
      self.set_sensitive(False)

    if util.gtkspell:
      try:
        self.spell = util.gtkspell.Spell(self, None)
      except:
        pass

  def get_text(self):
    buf = self.get_buffer()
    return buf.get_text(*buf.get_bounds()).strip()

  def get_char_count(self):
    return len(unicode(self.get_text(), "utf-8"))

  def on_add_text(self, buf, iter, text, tlen):
    if text and text.startswith("http") and not " " in text \
        and len(text) > 30:

      buf = self.get_buffer()
      buf.stop_emission("insert-text")

      def add_shortened(shortened_url):
          "Internal add-shortened-url-to-buffer function: a closure"
          iter_start = buf.get_iter_at_mark(mark_start)
          iter_end = buf.get_iter_at_mark(mark_end)
          buf.delete(iter_start, iter_end)
          buf.insert(iter_start, ("%s " % shortened_url))
      def error_shortened(dbus_exc):
          "Internal shortening-url-died function: a closure"
          iter = buf.get_iter_at_mark(mark)
          buf.insert(iter, text) # shortening failed

      # set a mark at iter, so that the callback knows where to insert
      mark_start = buf.create_mark(None, iter, True)
      # insert a placeholder character
      buf.insert(iter, u"\u2328")
      # can't just get_insert() because that gets the *named* mark "insert"
      # and we want an anonymous mark so it won't get changed later
      iter_end = buf.get_iter_at_mark(buf.get_insert())
      mark_end = buf.create_mark(None, iter_end, True)
      self.shortener.Shorten(text,
          reply_handler=add_shortened,
          error_handler=error_shortened)

  def set_overlay_text(self, text):
    if not self.pango_overlay:
      self.pango_overlay = self.create_pango_layout("")
    self.pango_overlay.set_markup(self.overlay_text % (self.overlay_color, text))

  def on_size_allocate(self, *args):
    if self.drawable: self.drawable.show()

  def expose_view(self, window, event):
    if not self.drawable:
      self.drawable = self.get_window(gtk.TEXT_WINDOW_TEXT)
      self.pango_overlay = self.create_pango_layout("")
      self.set_overlay_text(MAX_MESSAGE_LENGTH)

    gc = self.drawable.new_gc()
    ww, wh = self.drawable.get_size()
    tw, th = self.pango_overlay.get_pixel_size()
    self.drawable.draw_layout(gc, ww - tw - 2, wh - th, self.pango_overlay)
    self.set_editable(True)
    if self.content:
      self.get_buffer().set_text(self.content)
      self.content = None

  def on_text_changed(self, w):
    chars = self.get_char_count()
    color = self.error_color if chars > MAX_MESSAGE_LENGTH else self.base_color
    self.modify_base(gtk.STATE_NORMAL, color)

  def on_connection_online(self, *args):
    self.set_sensitive(True)

  def on_connection_offline(self, *args):
    self.set_sensitive(False)

