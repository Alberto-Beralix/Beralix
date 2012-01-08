#!/usr/bin/env python

import gtk, gobject, gwui, util, actions, json, gconf
import subprocess, os, time, datetime
from microblog import config
import microblog.util
from microblog.util import resources

import gettext
from gettext import lgettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

from gwibber.microblog.util import log
from microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from microblog.util.custom import *
except:
  pass

try:
  import appindicator
except:
  appindicator = None

from dbus.mainloop.glib import DBusGMainLoop
import dbus, dbus.service

DBusGMainLoop(set_as_default=True)

class GwibberClient(gtk.Window):
  def __init__(self):
    gtk.Window.__init__(self)
    self.ui = gtk.Builder()
    self.ui.set_translation_domain ("gwibber")

    self.connection = microblog.util.getbus("Connection")
    self.connection.connect_to_signal("ConnectionOnline", self.on_connection_online)
    self.connection.connect_to_signal("ConnectionOffline", self.on_connection_offline)

    self.model = gwui.Model()

    self.service = self.model.daemon
    self.messages = self.model.messages
    self.service.connect_to_signal("LoadingStarted", self.on_loading_started)
    self.service.connect_to_signal("LoadingComplete", self.on_loading_complete)
    self.service.connect_to_signal("IndicatorInterestAdded", self.on_indicator_interest_added)
    self.service.connect_to_signal("IndicatorInterestRemoved", self.on_indicator_interest_removed)

    self.messages.connect_to_signal("Message", self.on_new_message)

    self.shortener = microblog.util.getbus("URLShorten")
    self.uploader = microblog.util.getbus("Uploader")

    self.accounts = microblog.util.getbus("Accounts")
    self.quicklist_messages = {}

    first_run = False
    # check for existing accounts
    if len(json.loads(self.accounts.List())) == 0:
      # if there are no accounts configured, prompt the user to add some
      first_run = True
      if os.path.exists(os.path.join("bin", "gwibber-accounts")):
        cmd = os.path.join("bin", "gwibber-accounts")
      else:
        cmd = "gwibber-accounts"
      ret = 1
      while ret != 0:
        ret = subprocess.call([cmd])

    self.setup_ui()

    if first_run:
      # Since we didn't have accounts configured when gwibber-service started
      # force it to refresh now that accounts have been added
      self.service.Refresh()

    # Migrate the autostart gconf key to the new location
    if config.GCONF.get("/apps/gwibber/autostart"):
      config.GCONF.set_bool("/apps/gwibber/preferences/autostart", True)
      config.GCONF.unset('/apps/gwibber/autostart')

    config.GCONF.add_dir("/desktop/gnome/interface/document_font_name", gconf.CLIENT_PRELOAD_NONE)
    config.GCONF.notify_add("/desktop/gnome/interface/document_font_name", self.on_font_changed)
    config.GCONF.add_dir("/desktop/gnome/font_rendering", gconf.CLIENT_PRELOAD_NONE)
    config.GCONF.notify_add("/desktop/gnome/font_rendering", self.on_font_changed)
    config.GCONF.add_dir("/apps/gwibber/preferences", gconf.CLIENT_PRELOAD_NONE)

    for x in ["hide_taskbar_entry", "show_tray_icon"]:
      self.model.settings.notify(x, self.on_setting_changed)

    # Only use the notification area icon if there is no interest from the 
    # messaging menu indicator
    if self.service.IndicatorInterestCheck():
      self.tray_icon.set_visible(False)
    else:
      self.tray_icon.set_visible(self.model.settings["show_tray_icon"])

    self.set_property("skip-taskbar-hint", self.model.settings["hide_taskbar_entry"])


    # set state online/offline
    if not self.connection.isConnected():
      log.logger.info("Setting to Offline")
      self.actions.get_action("refresh").set_sensitive(False)

    # Delay resizing input area or else it doesn't work
    gobject.idle_add(lambda: self.input_splitter.set_position(int(self.model.settings["window_splitter"])))

    # Delay resizing the sidebar area or else it doesn't work
    gobject.idle_add(lambda: hasattr(self.stream_view, "splitter") and self.stream_view.splitter.set_position(self.model.settings["sidebar_splitter"]))

    # Apply the user's settings 
    gobject.idle_add(lambda: self.resize(*self.model.settings["window_size"]))
    gobject.idle_add(lambda: self.move(*self.model.settings["window_position"]))

    self.connect("configure-event", self.on_configure_event)

  def on_configure_event(self, *args):
    self.save_window_settings()

  def on_new_message(self, change,  message):
    message = json.loads(message)
    if appindicator:
      if message["stream"] == "messages":
        if not message["sender"]["is_me"]:
          if not message["sender"].has_key("name"): return
          if self.quicklist_messages.has_key(message["sender"]["name"]):
            count = self.quicklist_messages[message["sender"]["name"]]["count"] + 1
            msg = "%s (%s)" % (message["sender"]["name"], count)
            self.quicklist_messages[message["sender"]["name"]]["count"] = count
            self.quicklist_messages[message["sender"]["name"]]["menu"].set_label(msg)
            self.quicklist_messages[message["sender"]["name"]]["menu"].show()
          else:
            msg = "%s" % message["sender"]["name"]
            ai_entry = gtk.MenuItem(msg)
            ai_entry.connect("activate", lambda *a: self.present_with_time(int(time.mktime(datetime.datetime.now().timetuple()))))
            self.quicklist_messages[message["sender"]["name"]] = {"count": 1, "menu": ai_entry}
            self.ai_menu.prepend(ai_entry)
            ai_entry.show()
          while len(self.quicklist_messages) >= 7:
            self.quicklist_messages.values()[-1]["menu"].destroy()
            self.quicklist_messages.pop(self.quicklist_messages.keys()[-1])

  def on_indicator_interest_added(self):
    # Hide the notification area icon if there is interest from the 
    # messaging menu indicator
    self.tray_icon.set_visible(False)

  def on_indicator_interest_removed(self):
    # Show the notification area icon if there is no interest from the 
    # messaging menu indicator
    self.tray_icon.set_visible(True)

  def on_setting_changed(self, gc, x, pref, y):
    if "show_tray_icon" in pref.key:
      self.tray_icon.set_visible(pref.value.get_bool())

    if "hide_taskbar_entry" in pref.key:
      self.set_property("skip-taskbar-hint", pref.value.get_bool())

  def on_font_changed(self, *args):
    self.update_view()

  def setup_ui(self):
    self.set_title(_("Social broadcast messages"))
    self.set_icon_from_file(resources.get_ui_asset("gwibber.svg"))
    self.connect("delete-event", self.on_window_close)

    # Load the application menu
    menu_ui = self.setup_menu()
    self.add_accel_group(menu_ui.get_accel_group())

    def on_tray_menu_popup(i, b, a):
      menu_ui.get_widget("/menu_tray").popup(None, None,
          gtk.status_icon_position_menu, b, a, self.tray_icon)

    self.tray_icon = gtk.status_icon_new_from_file(resources.get_ui_asset("gwibber.svg"))
    self.tray_icon.connect("activate", self.on_toggle_window_visibility)
    self.tray_icon.connect("popup-menu", on_tray_menu_popup)

    # Create animated loading spinner
    self.loading_spinner = gtk.Image()
    menu_spin = gtk.ImageMenuItem("")
    menu_spin.set_right_justified(True)
    menu_spin.set_sensitive(False)
    menu_spin.set_image(self.loading_spinner)

    # Force the spinner to show in newer versions of Gtk
    if hasattr(menu_spin, "set_always_show_image"):
      menu_spin.set_always_show_image(True)

    menubar = menu_ui.get_widget("/menubar_main")
    menubar.append(menu_spin)

    # Load the user's saved streams
    streams = json.loads(self.model.settings["streams"])
    streams = [dict((str(k), v) for k, v in s.items()) for s in streams]
    
    # Use the multicolumn mode if there are multiple saved streams
    view_class = getattr(gwui, "MultiStreamUi" if len(streams) > 1 else "SingleStreamUi")

    self.stream_view = view_class(self.model)
    self.stream_view.connect("action", self.on_action)
    self.stream_view.connect("search", self.on_perform_search)
    self.stream_view.connect("stream-changed", self.on_stream_changed)
    self.stream_view.connect("stream-closed", self.on_stream_closed)
    if isinstance(self.stream_view, gwui.MultiStreamUi):
      self.stream_view.connect("pane-closed", self.on_pane_closed)

    self.input = gwui.Input()
    self.input.connect("submit", self.on_input_activate)
    self.input.connect("changed", self.on_input_changed)
    self.input.connect("clear", self.on_input_cleared)

    self.input_splitter = gtk.VPaned()
    self.input_splitter.pack1(self.stream_view, resize=True)
    self.input_splitter.pack2(self.input, resize=False)

    self.input_splitter.set_focus_child(self.input)

    self.attach_image = gtk.Image()
    self.attach_image.set_from_stock(gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON)

    self.button_attach = gtk.Button()
    self.button_attach.set_image(self.attach_image)
    self.button_attach.set_tooltip_text(_("Upload image"))
    self.button_attach.connect("clicked", self.on_button_attach_clicked)

    self.button_send = gtk.Button(_("Send"))
    self.button_send.set_tooltip_text(_("Post to all enabled services"))
    self.button_send.connect("clicked", self.on_button_send_clicked)

    self.message_target = gwui.AccountTargetBar(self.model)
    self.message_target.pack_end(self.button_send, False)
    self.message_target.pack_end(self.button_attach, False)
    self.message_target.connect("canceled", self.on_reply_cancel)

    content = gtk.VBox(spacing=5)
    content.pack_start(self.input_splitter, True)
    content.pack_start(self.message_target, False)
    content.set_border_width(5)

    layout = gtk.VBox()
    layout.pack_start(menubar, False)
    layout.pack_start(content, True)

    self.add(layout)

    # Apply the user's settings 
    self.resize(*self.model.settings["window_size"])
    self.move(*self.model.settings["window_position"])
    self.input_splitter.set_position(self.model.settings["window_splitter"])
    
    if hasattr(self.stream_view, "splitter"):
      self.stream_view.splitter.set_position(
          self.model.settings["sidebar_splitter"])
    
    self.show_all()

    self.stream_view.set_state(streams)
    self.update_menu_availability()
    for stream in streams:
      if stream["stream"]:
        gobject.idle_add(lambda: self.service.UpdateIndicators(stream["stream"]))


  def on_toggle_window_visibility(self, w):
    if self.get_property("visible"):
      self.last_position = self.get_position()
      self.hide()
    else:
      self.present()
      self.move(*self.last_position)

  def set_view(self, view=None):
    state = None
    if view: self.view_class = getattr(gwui, view)
    if self.stream_view:
      state = self.stream_view.get_state()
      self.stream_view.destroy()

    self.stream_view = self.view_class(self.model)
    self.stream_view.connect("action", self.on_action)
    self.stream_view.connect("search", self.on_perform_search)
    self.stream_view.connect("stream-changed", self.on_stream_changed)
    self.stream_view.connect("stream-closed", self.on_stream_closed)

    if isinstance(self.stream_view, gwui.MultiStreamUi):
      self.stream_view.connect("pane-closed", self.on_pane_closed)

    self.input_splitter.add1(self.stream_view)
    self.stream_view.show_all()
    if state: self.stream_view.set_state(state)

  def setup_menu(self):
    ui_string = """
    <ui>
      <menubar name="menubar_main">
        <menu action="menu_gwibber">
          <menuitem action="refresh" />
          <menuitem action="search" />
          <separator/>
          <menuitem action="new_stream" />
          <menuitem action="close_window" />
          <menuitem action="close_stream" />
          <separator/>
          <menuitem action="quit" />
        </menu>

        <menu action="menu_edit">
          <menuitem action="accounts" />
          <menuitem action="preferences" />
        </menu>

        <menu action="menu_help">
          <menuitem action="help_online" />
          <menuitem action="help_translate" />
          <menuitem action="help_report" />
          <separator/>
          <menuitem action="about" />
        </menu>
      </menubar>

      <popup name="menu_tray">
        <menuitem action="refresh" />
        <separator />
        <menuitem action="accounts" />
        <menuitem action="preferences" />
        <separator />
        <menuitem action="quit" />
      </popup>
    </ui>
    """

    self.actions = gtk.ActionGroup("Actions")
    self.actions.add_actions([
      ("menu_gwibber", None, _("_Gwibber")),
      ("menu_edit", None, _("_Edit")),
      ("menu_help", None, _("_Help")),

      ("refresh", gtk.STOCK_REFRESH, _("_Refresh"), "F5", None, self.on_refresh),
      ("search", gtk.STOCK_FIND, _("_Search"), "<ctrl>F", None, self.on_search),
      ("accounts", None, _("_Accounts"), "<ctrl><shift>A", None, self.on_accounts),
      ("preferences", gtk.STOCK_PREFERENCES, _("_Preferences"), "<ctrl>P", None, self.on_preferences),
      ("about", gtk.STOCK_ABOUT, _("_About"), None, None, self.on_about),
      ("quit", gtk.STOCK_QUIT, _("_Quit"), "<ctrl>Q", None, self.on_quit),

      ("new_stream", gtk.STOCK_NEW, _("_New Stream"), "<ctrl>n", None, self.on_new_stream),
      ("close_window", gtk.STOCK_CLOSE, _("_Close Window"), "<ctrl><shift>W", None, self.on_window_close),
      ("close_stream", gtk.STOCK_CLOSE, _("_Close Stream"), "<ctrl>W", None, self.on_close_stream),

      ("help_online", None, _("Get Help Online..."), None, None, lambda *a: util.load_url(QUESTIONS_URL)),
      ("help_translate", None, _("Translate This Application..."), None, None, lambda *a: util.load_url(TRANSLATE_URL)),
      ("help_report", None, _("Report A Problem..."), None, None, lambda *a: util.load_url(BUG_URL)),
    ])

    ui = gtk.UIManager()
    ui.insert_action_group(self.actions, pos=0)
    ui.add_ui_from_string(ui_string)
    
    # Add the old CTRL+R shortcut for legacy users
    refresh = ui.get_widget('/menubar_main/menu_gwibber/refresh')
    key, mod = gtk.accelerator_parse("<ctrl>R")
    refresh.add_accelerator("activate", ui.get_accel_group(), key, mod, gtk.ACCEL_VISIBLE)

    if appindicator:
      # Use appindicators to get quicklists in unity
      self.ind = appindicator.Indicator ("Gwibber",
                                    "applications-microblogging-panel",
                                    appindicator.CATEGORY_APPLICATION_STATUS)

      # create a menu
      self.ai_menu = gtk.Menu()

      self.ai_menu.append(gtk.SeparatorMenuItem())
      ai_refresh = gtk.MenuItem(_("_Refresh"))
      ai_refresh.connect("activate", self.on_refresh)
      self.ai_menu.append(ai_refresh)

      ai_accounts = gtk.MenuItem(_("_Accounts"))
      ai_accounts.connect("activate", self.on_accounts)
      self.ai_menu.append(ai_accounts)

      ai_preferences = gtk.MenuItem(_("_Preferences"))
      ai_preferences.connect("activate", self.on_preferences)
      self.ai_menu.append(ai_preferences)

      # show the items
      self.ai_menu.show_all()

      self.ind.set_menu(self.ai_menu)

      # End use appindicators to get quicklists in unity

    return ui

  def update_menu_availability(self):
    state = self.stream_view.get_state()
    if state:
      a = self.actions.get_action("close_stream")
      a.set_visible(bool(state[0].get("transient", False)))

  def update_view(self):
    self.stream_view.update()

  def private(self, message):
    features = self.model.services[message["service"]]["features"]

    if "private" in features:
      self.message_target.set_target(message, "private")
      self.input.textview.grab_focus()
      buf = self.input.textview.get_buffer()
      buf.place_cursor(buf.get_end_iter())

  def reply(self, message):
    features = self.model.services[message["service"]]["features"]

    if "reply" in features:
      if message["sender"].get("nick", 0) and not "thread" in features:
        s = "@%s: " if self.model.settings["reply_append_colon"] else "@%s "
        self.input.set_text(s % message["sender"]["nick"])

      self.message_target.set_target(message)
      self.input.textview.grab_focus()
      buf = self.input.textview.get_buffer()
      buf.place_cursor(buf.get_end_iter())

  def on_reply_cancel(self, widget):
    self.input.clear()

  def get_message(self, id):
    data = self.messages.Get(id)
    if data: return json.loads(data)

  def on_refresh(self, *args):
    self.service.Refresh()

  def add_stream(self, data, kind=None):
    if "operation" in data:
      stream = str(self.model.features[data["operation"]]["stream"])
      obj = self.model.streams
    else:
      stream = "search"
      obj = self.model.searches

    id = obj.Create(json.dumps(data))
    self.model.refresh()
    self.stream_view.new_stream({
      "stream": stream,
      "account": data.get("account", None),
      "transient": id,
    })

    self.service.PerformOp('{"id": "%s"}' % id)
    self.update_menu_availability()

  def save_window_settings(self):
    self.model.settings["streams"] = json.dumps(self.stream_view.get_state())
    self.model.settings["window_size"] = self.get_size()
    self.model.settings["window_position"] = self.get_position()
    self.model.settings["window_splitter"] = self.input_splitter.get_position()
    
    if hasattr(self.stream_view, "splitter"):
      self.model.settings["sidebar_splitter"] = self.stream_view.splitter.get_position()

  def on_pane_closed(self, widget, count):
    if count < 2 and isinstance(self.stream_view, gwui.MultiStreamUi):
      self.set_view("SingleStreamUi")

  def on_window_close(self, *args):
    if self.model.settings["minimize_to_tray"]:
      self.on_toggle_window_visibility(self)
      return True
    else:
      self.save_window_settings()
      log.logger.info("Gwibber Client closed")
      gtk.main_quit()

  def on_quit(self, *args):
    self.service.Quit()
    self.save_window_settings()
    log.logger.info("Gwibber Client quit")
    gtk.main_quit()

  def on_search(self, *args):
    self.stream_view.set_state([{
      "stream": "search",
      "account": None,
      "transient": False,
    }])

    self.stream_view.search_box.focus()

  def on_perform_search(self, widget, query):
    self.add_stream({"name": query, "query": query})

  def on_accounts(self, *args):
    if os.path.exists(os.path.join("bin", "gwibber-accounts")):
      cmd = os.path.join("bin", "gwibber-accounts")
    else:
      cmd = "gwibber-accounts"
    return subprocess.Popen(cmd, shell=False)

  def on_preferences(self, *args):
    if os.path.exists(os.path.join("bin", "gwibber-preferences")):
      cmd = os.path.join("bin", "gwibber-preferences")
    else:
      cmd = "gwibber-preferences"
    return subprocess.Popen(cmd, shell=False)

  def on_about(self, *args):
    self.ui.add_from_file (resources.get_ui_asset("gwibber-about-dialog.ui"))
    about_dialog = self.ui.get_object("about_dialog")
    about_dialog.set_version(str(VERSION_NUMBER))
    about_dialog.set_transient_for(self)
    about_dialog.connect("response", lambda *a: about_dialog.hide())
    about_dialog.show_all()

  def on_close_stream(self, *args):
    state = self.stream_view.get_state()
    if state and state[0].get("transient", 0):
      state = state[0]
      obj = "searches" if state.get("stream", 0) == "search" else "streams"
      getattr(self.model, obj).Delete(state["transient"])
      self.stream_view.set_state([{"stream": "messages", "account": None}])

  def on_message_action_menu(self, msg, view):
    theme = gtk.icon_theme_get_default()
    menu = gtk.Menu()

    def perform_action(mi, act, widget, msg): act(widget, self, msg)

    for a in actions.MENU_ITEMS:
      if a.action.__self__.__name__ == "private" and msg["sender"].get("is_me", 0):
        continue

      if a.include(self, msg):
        image = gtk.image_new_from_icon_name(a.icon, gtk.ICON_SIZE_MENU)
        mi = gtk.ImageMenuItem()
        mi.set_label(a.label)
        mi.set_image(image)
        mi.set_property("use_underline", True)
        mi.connect("activate", perform_action, a.action, view, msg)
        menu.append(mi)

    menu.show_all()
    menu.popup(None, None, None, 3, 0)

  def on_action(self, widget, uri, cmd, query, view):
    if hasattr(actions, cmd):
      if "msg" in query:
        query["msg"] = self.get_message(query["msg"])
      getattr(actions, cmd).action(view, self, **query)

  def on_stream_closed(self, widget, id, kind):
    self.model.streams.Delete(id)
    self.model.searches.Delete(id)

  def on_stream_changed(self, widget, stream):
    self.update_menu_availability()
    if stream["stream"]:
      gobject.idle_add(lambda: self.service.UpdateIndicators(stream["stream"]))

  def on_input_changed(self, w, text, cnt):
    self.input.textview.set_overlay_text(str(MAX_MESSAGE_LENGTH - cnt))

  def on_input_cleared(self, seq):
      self.message_target.end()
      self.input.clear()

  def on_input_activate(self, w, text, cnt):
    self.send_message(text)
    self.input.clear()

  def on_button_attach_clicked(self, w):
    file_upload = gtk.FileChooserDialog(title=_("Select file to upload"),
                      action=gtk.FILE_CHOOSER_ACTION_OPEN,
                      buttons=(gtk.STOCK_CANCEL,
                          gtk.RESPONSE_CANCEL,
                          gtk.STOCK_OPEN,
                          gtk.RESPONSE_OK))
    file_upload.set_default_response(gtk.RESPONSE_OK)
    file_upload.connect("response", self.on_button_attach_file_selected)
    file_upload.show()

  def on_button_attach_file_selected(self, file_upload, response):
    attachment = None
    #import epdb;epdb.st()
    if response == gtk.RESPONSE_CANCEL:
      file_upload.destroy()
      return

    if response == gtk.RESPONSE_OK:
      attachment = file_upload.get_filename()
    file_upload.destroy()

    if attachment:
      buf = self.input.textview.get_buffer()
      # set a mark at iter, so that the callback knows where to insert
      iter = buf.get_end_iter()
      mark_start = buf.create_mark(None, iter, True)
      # insert a placeholder character
      buf.insert(iter, u"\u2328")
      # can't just get_insert() because that gets the *named* mark "insert"
      # and we want an anonymous mark so it won't get changed later
      iter_end = buf.get_iter_at_mark(buf.get_insert())
      mark_end = buf.create_mark(None, iter_end, True)
      gobject.idle_add(self.upload_attachment, attachment, iter, mark_start, mark_end)

  def upload_attachment(self, attachment, iter, mark_start, mark_end):
    buf = self.input.textview.get_buffer()

    def add_shortened(shortened_url):
      "Internal add-shortened-url-to-buffer function: a closure"
      iter_start = buf.get_iter_at_mark(mark_start)
      iter_end = buf.get_iter_at_mark(mark_end)
      buf.delete(iter_start, iter_end)
      buf.insert(iter_start, ("%s " % shortened_url))
      #buf.insert_at_cursor(" ")
    def error_shortened(dbus_exc):
      "Internal shortening-url-died function: a closure"
      iter = buf.get_iter_at_mark(mark)
      buf.insert(iter, text) # shortening failed

    text = self.uploader.Upload(attachment)

    if self.model.settings["shorten_urls"]:
      if text and text.startswith("http") and not " " in text \
          and len(text) > 30:
        self.shortener.Shorten(text,
          reply_handler=add_shortened,
          error_handler=error_shortened)
    else:
      add_shortened(text)

  def on_button_send_clicked(self, w):
    self.send_message(self.input.get_text())
    self.input.clear()

  def send_message(self, text):
    if len(text) == 0:
      return
    target = self.message_target.target
    action = self.message_target.action

    if target:
      if action == "reply":
        data = {"message": text, "target": target}
        self.service.Send(json.dumps(data))
      elif action == "repost":
        data = {"message": text, "accounts": [target["account"]]}
        self.service.Send(json.dumps(data))
      elif action == "private":
        data = {"message": text, "private": target}
        self.service.Send(json.dumps(data))
      self.message_target.end()
    else: self.service.SendMessage(text)

  def on_new_stream(self, *args):
    if isinstance(self.stream_view, gwui.MultiStreamUi):
      self.stream_view.new_stream()
    else:
      self.set_view("MultiStreamUi")
      self.stream_view.new_stream()

  def on_loading_started(self, *args):
    self.loading_spinner.set_from_animation(
      gtk.gdk.PixbufAnimation(resources.get_ui_asset("progress.gif")))

  def on_loading_complete(self, *args):
    self.loading_spinner.clear()
    self.update_view()

  def on_connection_online(self, *args):
    log.logger.info("Setting to Online")
    self.actions.get_action("refresh").set_sensitive(True)

  def on_connection_offline(self, *args):
    log.logger.info("Setting to Offline")
    self.actions.get_action("refresh").set_sensitive(False)

class Client(dbus.service.Object):
  __dbus_object_path__ = "/com/GwibberClient"

  def __init__(self):
    # Setup a Client dbus interface
    self.bus = dbus.SessionBus()
    self.bus_name = dbus.service.BusName("com.GwibberClient", self.bus)
    dbus.service.Object.__init__(self, self.bus_name, self.__dbus_object_path__)

    # Methods the client exposes via dbus, return from the list method
    self.exposed_methods = ["focus_client", "show_stream"]
    self.w = GwibberClient()

  @dbus.service.method("com.GwibberClient", in_signature="", out_signature="")
  def focus_client(self):
    """
    This method focuses the client UI displaying the default view.
    Currently used when the client is activated via dbus activation.
    """
    self.w.present_with_time(int(time.mktime(datetime.datetime.now().timetuple())))
    try:
      self.w.move(*self.w.model.settings["window_position"])
    except:
      pass

  @dbus.service.method("com.GwibberClient", in_signature="s", out_signature="")
  def show_stream(self, stream):
    """
    This method focuses the client UI and displays the replies view.
    Currently used when activated via the messaging indicator.
    """
    self.w.present_with_time(int(time.mktime(datetime.datetime.now().timetuple())))
    self.w.move(*self.w.model.settings["window_position"])
    stream = {'account': None, 'stream': stream, 'transient': False}
    if isinstance(self.w.stream_view, gwui.MultiStreamUi):
      streams = self.w.stream_view.get_state()
      if stream["stream"] not in str(streams):
        streams.append(stream)
        self.w.stream_view.set_state(streams)
    else:
      self.w.stream_view.set_state([stream])

  @dbus.service.method("com.GwibberClient")
  def list(self):
    """
    This method returns a list of exposed dbus methods
    """
    return self.exposed_methods
