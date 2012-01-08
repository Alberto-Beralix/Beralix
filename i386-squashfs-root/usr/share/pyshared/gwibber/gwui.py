
import os, json, urlparse, util
import subprocess
import gtk, gobject, pango, webkit, time, gconf
import util
import microblog.util
from microblog.util import resources
from microblog import config


import gettext
from gettext import lgettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

from mako.template import Template
from mako.lookup import TemplateLookup

from microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from microblog.util.custom import *
except:
  pass

error_accounts = []
notified_errors = {}

gtk.gdk.threads_init()

if "gwibber" not in urlparse.uses_query:
  urlparse.uses_query.append("gwibber")

class Model(gobject.GObject):
  __gsignals__ = {
    "changed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ()),
  }
  def __init__(self):
    gobject.GObject.__init__(self)

    self.settings = config.Preferences()
    self.daemon = microblog.util.getbus("Service")
    self.messages = microblog.util.getbus("Messages")
    self.accounts = microblog.util.getbus("Accounts")
    self.streams = microblog.util.getbus("Streams")
    self.searches = microblog.util.getbus("Searches")

    self.services = json.loads(self.daemon.GetServices())
    self.features = json.loads(self.daemon.GetFeatures())

    for b in [self.accounts, self.searches, self.streams]:
      for i in ["Created", "Updated", "Deleted"]:
        b.connect_to_signal(i, self.on_stream_changed)

    self.model = None
    self.model_valid = False

  def on_stream_changed(self, id):
    self.model_valid = False
    self.emit("changed")

  @classmethod
  def to_state(self, item):
    if not item: return {}
    return dict((x, item[x]) for x in ["transient", "account", "stream"])

  @classmethod
  def match(self, d1, d2):
    return all(k in d1 and d1[k] == v for k, v in d2.items())

  def find(self, **params):
    for i in self.find_all(**params):
      return i

  def find_all(self, **params):
    for stream in self.get_streams():
      if self.match(stream, params): yield stream

      if "items" in stream:
        for stream in stream["items"]:
          if self.match(stream, params): yield stream

  def get_streams(self):
    if not self.model_valid: self.refresh()
    return self.model

  def refresh(self):
    self.model = self.generate_streams()
    self.model_valid = True

  def generate_streams(self):
    items = []
    transients = json.loads(self.streams.List())

    items.append({
      "name": _("Home"),
      "stream": "home",
      "account": None,
      "transient": False,
      "color": None,
    })

    # This list is defined just to get the strings in the template for translation
    stream_titles = [_("Messages"), _("Replies"), _("Images"), _("Links"), _("Videos"), _("Private")]

    for stream in ["messages", "replies", "images", "videos", "links", "private"]:
      items.append({
        "name": _(stream.capitalize()),
        "stream": stream,
        "account": None,
        "transient": False,
        "color": None,
      })

    items.append({
      "name": _("Sent"),
      "stream": "sent",
      "account": None,
      "transient": False,
      "color": None,
    })

    for account in json.loads(self.accounts.List()):
      aId = account["id"]

      if self.services.has_key(account["service"]) and "receive" in self.services[account["service"]]["features"]:

        item = {
            "name": account.get("username", "None"),
            "account": aId,
            "stream": None,
            "transient": False,
            "color": util.Color(account["color"]),
            "service": account["service"],
            "items": [],
        }

        default_streams = self.services[account["service"]]["default_streams"]

        if len(default_streams) > 1:
          for feature in default_streams:
            aname = self.features[feature]["stream"]
            item["items"].append({
              "name": _(aname.capitalize()),
              "account": aId,
              "stream": aname,
              "transient": False,
              "color": util.Color(account["color"]),
              "service": account["service"],
            })

          item["items"].append({
            "name": _("Sent"),
            "account": aId,
            "stream": "sent",
            "transient": False,
            "color": util.Color(account["color"]),
            "service": account["service"],
          })

        for transient in transients:
          tId = transient["id"]

          if transient["account"] == aId:
            if transient["operation"] == "user_messages" and account["service"] in ["twitter", "identica"]:
              recipient = transient["parameters"]["id"]
            else:
              recipient = False

            if transient["name"] == "Lists": transient["name"] = _("Lists")

            item["items"].append({
              "name": transient["name"],
              "account": aId,
              "stream": self.features[transient["operation"]]["stream"],
              "transient": tId,
              "recipient": recipient,
              "color": util.Color(account["color"]),
              "service": account["service"],
            })

        items.append(item)

    searches = {
        "name": _("Search"),
        "account": None,
        "stream": "search",
        "transient": False,
        "color": None,
        "items": [],
    }

    for search in json.loads(self.searches.List()):
      sId = search["id"]
      searches["items"].append({
        "name": search["name"],
        "account": None,
        "stream": "search",
        "transient": sId,
        "color": None,
      })

    items.append(searches)
    return items

class WebUi(webkit.WebView):
  __gsignals__ = {
    "action": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str, object)),
  }

  def __init__(self):
    webkit.WebView.__init__(self)
    self.web_settings = webkit.WebSettings()
    self.set_settings(self.web_settings)
    self.web_settings.set_property("enable-plugins", False)
    self.gc = gconf.client_get_default()

    self.connect("navigation-requested", self.on_click_link)
    self.connect("populate-popup", self.on_popup)
    self.template = None

  def on_popup(self, view, menu):
    menu.destroy()

  def on_click_link(self, view, frame, req):
    uri = req.get_uri()

    if uri.startswith("file:///"): return False
    elif uri.startswith("gwibber:"):
      url = urlparse.urlparse(uri)
      cmd = url.path.split("/")[1]
      query = urlparse.parse_qs(url.query)
      query = dict((x,y[0]) for x,y in query.items())
      self.emit("action", uri, cmd, query)
    else: util.load_url(uri)
    return True

  def render(self, theme, template, **kwargs):
    default_font = self.gc.get_string("/desktop/gnome/interface/document_font_name")
    if default_font:
      font_name, font_size = default_font.rsplit(None, 1)
      self.web_settings.set_property("sans-serif-font-family", font_name)
      self.web_settings.set_property("default-font-size", float(font_size))

    if not resources.theme_exists(theme):
      theme = "default"

    theme_path = resources.get_theme_path(theme)
    template_path = resources.get_template_path(template, theme)
    lookup_paths = list(resources.get_template_dirs()) + [theme_path]

    template = open(template_path).read()
    template = Template(template, lookup=TemplateLookup(directories=lookup_paths))
    content = template.render(theme=util.get_theme_colors(), util=util, resources=resources, _=_, **kwargs)

    # Avoid navigation redraw crashes
    if isinstance(self, Navigation) and not self.get_property("visible"):
      return content

    self.load_html_string(content, "file://%s/" % os.path.dirname(template_path))
    return content

class Navigation(WebUi):
  __gsignals__ = {
    "stream-selected": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (object,)),
    "stream-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str)),
  }

  def __init__(self, model):
    WebUi.__init__(self)

    self.model = model
    self.model.connect("changed", self.on_model_update)
    self.connect("action", self.on_perform_action)

    self.selected_stream = None
    self.tree_enabled = False
    self.small_icons = False

  def render(self):
    return WebUi.render(self, self.model.settings["theme"], "navigation.mako",
      streams=self.model.get_streams(),
      tree=self.tree_enabled,
      selected=self.selected_stream,
      small_icons=self.small_icons)

  def on_model_update(self, model):
    self.render()

  def on_perform_action(self, w, uri, cmd, query):
    if cmd == "close" and "transient" in query:
      self.emit("stream-closed", query["transient"], "transient")

    if cmd == "stream":
      query = dict((k, None if v == "None" else v) for k, v in query.items())
      target = self.model.find(**query)
      if target: self.emit("stream-selected", target)

class SingleStreamUi(gtk.VBox):
  __gsignals__ = {
    "action": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str, object, object)),
    "stream-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str)),
    "stream-changed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (object,)),
    "search": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str,)),
  }
  def __init__(self, model):
    gtk.VBox.__init__(self)
    self.model = model

    self.gc = gconf.client_get_default()

    # Build the side navigation bar
    self.navigation = Navigation(self.model)
    self.navigation.connect("stream-selected", self.on_stream_change)
    self.navigation.connect("stream-closed", self.on_stream_closed)
    self.navigation.render()

    self.navigation_scroll = gtk.ScrolledWindow()
    self.navigation_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
    self.navigation_scroll.add(self.navigation)

    self.messages = MessageStream(self.model)
    self.messages.message_view.connect("action", self.on_action)
    
    self.search_box = GwibberSearch()
    self.search_box.connect("search", self.on_search)

    
    layout = gtk.VBox(spacing=5)
    layout.pack_start(self.search_box, False)
    if hasattr(gtk, "InfoBar"): 
      self.infobox = GwibberInfoBox()
      layout.pack_start(self.infobox, False, True, 0)
    layout.pack_start(self.messages, True)

    # Build the pane layout
    self.splitter = gtk.HPaned()
    self.splitter.add1(self.navigation_scroll)
    self.splitter.add2(layout)

    self.splitter.connect("notify", self.on_splitter_drag)
    self.pack_start(self.splitter, True)

  def handle_splitter_position_change(self, pos):
    if pos < 70 and self.navigation.tree_enabled:
      #self.navigation_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
      self.navigation_scroll.set_shadow_type(gtk.SHADOW_NONE)
      self.navigation.tree_enabled = False
      self.navigation.render()

    if pos > 70 and not self.navigation.tree_enabled:
      #self.navigation_scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
      self.navigation_scroll.set_shadow_type(gtk.SHADOW_IN)
      self.navigation.tree_enabled = True
      self.navigation.render()

    if pos < 30 and not self.navigation.small_icons:
      self.navigation.small_icons = True
      self.navigation.render()

    if pos > 30 and self.navigation.small_icons:
      self.navigation.small_icons = False
      self.navigation.render()

    if pos < 25:
      self.splitter.set_position(25)

  def on_splitter_drag(self, pane, ev):
    if ev.name == 'position':
      pos = pane.get_position()
      self.handle_splitter_position_change(pos)

  def on_stream_closed(self, widget, id, kind):
    self.emit("stream-closed", id, kind)

  def on_stream_change(self, widget, stream):
    self.navigation.selected_stream = stream
    self.emit("stream-changed", stream)
    self.update_search_visibility()
    self.update()

  def update_search_visibility(self):
    stream = self.navigation.selected_stream
    if stream is not None:
      is_search = stream["stream"] == "search" and not stream["transient"] 
      self.search_box.set_visible(not is_search)

  def on_action(self, widget, uri, cmd, query):
    self.emit("action", uri, cmd, query, self)

  def on_search(self, widget, query):
    self.emit("search", query)

  def update(self, *args):
    self.messages.update(self.navigation.selected_stream)
    
  def get_state(self):
    return [self.model.to_state(self.navigation.selected_stream)]

  def new_stream(self, state=None):
    if state: self.set_state([state])

  def set_state(self, streams):
    if streams:
      self.navigation.selected_stream = self.model.find(**streams[0]) or self.model.find(stream="home", account=None)
      self.navigation.render()
      self.update_search_visibility()
      self.update()


class MultiStreamUi(gtk.HBox):
  __gsignals__ = {
    "action": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str, object, object)),
    "stream-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str)),
    "stream-changed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (object,)),
    "pane-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (int,)),
    "search": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str,)),
  }
  def __init__(self, model):
    gtk.HBox.__init__(self)
    self.model = model

    self.container = gtk.HBox(spacing=5)
    self.container.set_border_width(5)

    self.scroll = gtk.ScrolledWindow()
    self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
    self.scroll.add_with_viewport(self.container)

    self.pack_start(self.scroll, True)

  def on_stream_closed(self, widget, id, kind):
    self.emit("stream-closed", id, kind)

  def on_pane_closed(self, widget):
    widget.destroy()
    self.emit("pane-closed", len(self.container))

  def on_search(self, widget, query):
    self.emit("search", query)

  def on_action(self, widget, uri, cmd, query):
    self.emit("action", uri, cmd, query, widget)

  def new_stream(self, state={"stream": "messages", "account": None}):
    item = MultiStreamPane(self.model)
    item.set_property("width-request", 350)
    item.connect("search", self.on_search)
    item.connect("action", self.on_action)
    item.connect("stream-closed", self.on_stream_closed)
    item.connect("pane-closed", self.on_pane_closed)
    item.show_all()

    item.search_box.hide()
    if state: item.set_state(state)
    self.container.pack_start(item)
    return item

  def set_state(self, state):
    for item in self.container: item.destroy()
    for item in state: self.new_stream(item)

  def get_state(self):
    return [pane.get_state() for pane in self.container]

  def update(self):
    for stream in self.container:
      stream.update()

class MultiStreamPane(gtk.VBox):
  __gsignals__ = {
    "action": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str, object)),
    "stream-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str, str)),
    "pane-closed": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ()),
    "search": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str,)),
  }

  def __init__(self, model):
    gtk.VBox.__init__(self, spacing = 2)
    self.model = model
    self.selected_stream = None

    # Build the top navigation bar
    close_icon = gtk.image_new_from_stock("gtk-close", gtk.ICON_SIZE_MENU)
    down_arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_NONE)

    btn_arrow = gtk.Button()
    btn_arrow.set_relief(gtk.RELIEF_NONE)
    btn_arrow.add(down_arrow)
    btn_arrow.connect("clicked", self.on_dropdown)

    self.arrow = gtk.EventBox()
    self.arrow.add(btn_arrow)

    btn_close = gtk.Button()
    btn_close.set_relief(gtk.RELIEF_NONE)
    btn_close.set_image(close_icon)
    btn_close.connect("clicked", self.on_close)

    self.icon_protocol = gtk.Image()
    self.icon_stream = gtk.Image()
    self.nav_label = gtk.Label()

    self.search_box = GwibberSearch()
    self.search_box.connect("search", self.on_search)

    self.navigation_bar = gtk.HBox(spacing=5)
    self.navigation_bar.pack_start(self.arrow, False)
    self.navigation_bar.pack_start(self.icon_protocol, False)
    self.navigation_bar.pack_start(self.icon_stream, False)
    self.navigation_bar.pack_start(self.nav_label, False)
    self.navigation_bar.pack_end(btn_close, False)

    # Build the main message view

    self.messages = MessageStream(self.model)
    self.messages.message_view.connect("action", self.on_action)

    self.pack_start(self.navigation_bar, False)
    self.pack_start(self.search_box, False)
    self.pack_start(self.messages, True)

  def on_close(self, *args):
    self.emit("pane-closed")

  def on_dropdown(self, button):
    w, h = self.arrow.window.get_geometry()[2:4]
    x, y = self.arrow.window.get_origin()

    window = gtk.Window()
    window.move(x, y + h)
    window.set_decorated(False)
    window.set_property("skip-taskbar-hint", True)
    window.set_property("skip-pager-hint", True)
    window.set_events(gtk.gdk.FOCUS_CHANGE_MASK)
    window.connect("focus-out-event", lambda w,x: w.destroy())

    def on_change(widget, stream):
      self.set_stream(stream)
      self.update()
      window.destroy()

    def on_stream_close(widget, id, kind):
      self.emit("stream-closed", id, kind)

    navigation = Navigation(self.model)
    navigation.connect("stream-selected", on_change)
    navigation.connect("stream-closed", on_stream_close)
    navigation.selected_stream = self.selected_stream
    navigation.tree_enabled = True
    navigation.small_icons = True
    navigation.show()
    navigation.render()

    window.add(navigation)
    window.show_all()
    window.grab_focus()

  def set_stream(self, stream):
    self.selected_stream = stream
    self.nav_label.set_text(stream["name"])

    is_search = stream["stream"] == "search" and not stream["transient"]
    self.search_box.set_visible(not is_search)

    if stream["account"]:
      fname = resources.get_ui_asset("icons/breakdance/16x16/%s.png" % stream["service"])
      self.icon_protocol.set_from_file(fname)
    else: self.icon_protocol.clear()

    if stream["stream"]:
      fname = resources.get_ui_asset("icons/streams/16x16/%s.png" % stream["stream"])
      self.icon_stream.set_from_file(fname)
    else: self.icon_stream.clear()

  def on_search(self, widget, query):
    self.emit("search", query)

  def on_action(self, widget, uri, cmd, query):
    self.emit("action", uri, cmd, query)

  def update(self, *args):
    if self.selected_stream:
      self.messages.update(self.selected_stream)

  def get_state(self):
    return self.model.to_state(self.selected_stream)

  def set_state(self, stream):
    self.set_stream(self.model.find(**stream) or self.model.find(stream="home", account=None))
    self.update()

class AccountTargetBar(gtk.HBox):
  __gsignals__ = {
      "canceled": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, ())
  }

  def __init__(self, model):
    gtk.HBox.__init__(self, spacing=5)
    self.model = model
    self.model.connect("changed", self.on_account_changed)
    self.accounts = []

    self.target = None
    self.action = None

    self.targetbar = WebUi()
    self.targetbar.connect("action", self.on_action)
    self.targetbar.set_size_request(0, 24)
    self.pack_start(self.targetbar, True)

    self.populate()
    self.render()

  def set_target(self, message, action="reply"):
    self.target = message
    self.target["account_data"] = json.loads(self.model.accounts.Get(message["account"]))
    self.action = action
    self.render()

  def end(self):
    self.emit("canceled")
    self.target = None
    self.action = None
    self.render()

  def on_action(self, w, uri, cmd, query):
    if cmd == "cancel": return self.end()
    if cmd == "account" and "id" in query:
      acct = self.model.accounts.Get(query["id"])
      if acct and "send_enabled" in query:
        acct = json.loads(acct)
        acct["send_enabled"] = bool(query["send_enabled"] == "true")
        self.model.accounts.Update(json.dumps(acct))

  def on_account_changed(self, id):
    self.populate()
    self.render()

  def populate(self):
    self.accounts = []
    for account in json.loads(self.model.accounts.List()):
      if self.model.services.has_key(account["service"]) and "send" in self.model.services[account["service"]]["features"]:
        self.accounts.append(account)

  def render(self):
    return self.targetbar.render(self.model.settings["theme"], "targetbar.mako",
        services=self.model.services,
        target=self.target,
        action=self.action,
        accounts=self.accounts)

class MessageStream(gtk.HBox):
  def __init__(self, model):
    gtk.HBox.__init__(self, spacing=5)

    self.previous_threshold = 100
    self.previous_position = 0
    self.previous_stream = None
    self.messages = None

    self.add_events(gtk.gdk.KEY_PRESS_MASK | gtk.gdk.SCROLL_MASK)
    self.connect("scroll-event", self.on_viewport_scroll)
    self.connect("key-press-event", self.on_viewport_key)

    self.message_view = MessageStreamView(model)
    self.message_view.connect("load-finished", self.on_scroll)

    self.message_scroll = gtk.ScrolledWindow()
    self.message_scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
    self.message_scroll.set_shadow_type(gtk.SHADOW_IN)
    self.message_scroll.add(self.message_view)

    self.scrollbar = gtk.VScrollbar()
    self.scrollbar.set_range(0, 100)
    self.scrollbar.set_increments(1, 10)
    self.scrollbar.connect("value-changed", self.on_scroll)

    self.pack_start(self.message_scroll, True, True)
    self.pack_start(self.scrollbar, False)

  def on_viewport_key(self, widget, event):
    if not event.state & gtk.gdk.SHIFT_MASK: return
    if 'Down' == gtk.gdk.keyval_name(event.keyval):
        value = int(self.scrollbar.get_value()) + 1
        self.scrollbar.set_value(value)
    elif 'Page_Down' == gtk.gdk.keyval_name(event.keyval):
        value = int(self.scrollbar.get_value()) + 3
        self.scrollbar.set_value(value)
    elif 'Up' == gtk.gdk.keyval_name(event.keyval):
        value = int(self.scrollbar.get_value()) - 1
        self.scrollbar.set_value(value)
    elif 'Page_Up' == gtk.gdk.keyval_name(event.keyval):
        value = int(self.scrollbar.get_value()) - 3
        self.scrollbar.set_value(value)
    elif 'Home' == gtk.gdk.keyval_name(event.keyval):
        self.scrollbar.set_value(0)
    elif 'End' == gtk.gdk.keyval_name(event.keyval):
        self.scrollbar.set_value(100)
        
  def on_viewport_scroll(self, widget, event):
    value = int(self.scrollbar.get_value())

    if event.direction == gtk.gdk.SCROLL_DOWN: value += 1
    elif event.direction == gtk.gdk.SCROLL_UP: value -= 1

    self.scrollbar.set_value(value)

  def on_scroll(self, *args):
    self.handle_scroll(int(self.scrollbar.get_value()))

  def handle_scroll(self, value):
    if value > len(self.messages):
      value = len(self.messages)
    elif value < 0:
      value = 0
    self.message_view.execute_script("""
    document.location.hash = "";
    document.location.hash = "msg-%s"
    """ % value)

    self.previous_position = value

    return

    ### Experimenting with infinite scrolling

    threshold = len(self.messages) - 6

    if value > threshold and len(self.messages) < self.previous_threshold:
      print "Loading more messages"
      self.previous_threshold  += 100
      self.update(self.previous_stream, self.previous_threshold)

    self.previous_position = value

  def update(self, selected_stream, count=100):
    id = None
    
    if selected_stream:
      same_stream = selected_stream == self.previous_stream
      self.previous_stream = selected_stream 
      
      if self.messages and same_stream:
        index = int(self.scrollbar.get_value())
        if index < len(self.messages) and index > 0:
          id = self.messages[index]

      self.messages = self.message_view.render([selected_stream], count)
      pos = self.messages.index(id) if id and id in self.messages else 0
      self.scrollbar.set_range(0, len(self.messages) - 1)
      self.scrollbar.set_value(pos)

class MessageStreamView(WebUi):
  def __init__(self, model):
    WebUi.__init__(self)
    self.model = model

  def render(self, streams, count = 100):
    accounts = json.loads(self.model.accounts.List())
    accounts = dict((a["id"], a) for a in accounts)
    messages = []
    seen = {}
    time = 0
    orderby = "time"
    order = "desc"
    limit = 50

    if len(streams) == 1:
      # get message data for selected stream
      # stream, account, time, transient, recipient, orderby, order, limit
      msgs = json.loads(self.model.streams.Messages(streams[0]["stream"] or "all", streams[0]["account"] or "all", time, streams[0]["transient"] or "0", streams[0].has_key("recipient") and streams[0]["recipient"] or "0", orderby, order, limit))
     
      for item in msgs:
        message = item
        message["dupes"] = []
        message["txtid"] = util.remove_urls(message["text"]).strip()[:MAX_MESSAGE_LENGTH] or None
        message["color"] = util.Color(accounts.get(message["account"], {"color": "#5A5A5A"})["color"])
        message["time_string"] = util.generate_time_string(message["time"])
        try:
          message["sender"]["image"] = resources.get_avatar_path(message["sender"]["image"])
        except:
          pass
        messages.append(message)

    def dupematch(item, message):
      if item["service"] == message["service"] and item["mid"] == message["mid"]:
        return True

      for item in item["dupes"]:
        if item["service"] == message["service"] and item["mid"] == message["mid"]:
          return True

    # Detect duplicates
    for n, message in enumerate(messages):
      message["is_dupe"] = message["txtid"] in seen
      if message["is_dupe"]:
        item = messages[seen[message["txtid"]]]
        if not dupematch(item, message):
          item["dupes"].append(message)
      else:
        if message["txtid"]:
          seen[message["txtid"]] = n

    messages = [m for m in messages if not m["is_dupe"]]

    WebUi.render(self, self.model.settings["theme"], "template.mako",
        message_store=messages,
        preferences=self.model.settings,
        services=self.model.services,
        accounts=accounts)

    return [m["txtid"] for m in messages]

class GwibberInfoBox(gtk.VBox):
  def __init__(self, error=None):
    gtk.VBox.__init__(self, spacing=2)
    self.service = microblog.util.getbus("Service")
    self.service.connect_to_signal("Error", self.add_info_bar)
    self.show()

  def add_info_bar(self, data):
    data = json.loads(data)
    if data.has_key("error"):
      if data["error"]["account"]["id"] in error_accounts:
        return
      if notified_errors.has_key(data["error"]["account"]["id"]):
        if data["error"]["type"] in notified_errors[data["error"]["account"]["id"]]:
          return
        else:
          notified_errors[data["error"]["account"]["id"]].append(data["error"]["type"])
      print notified_errors
      error_accounts.append(data["error"]["account"]["id"])
      bar = GwibberInfoBar(data=data)
      self.show()
      bar.connect("destroy", self.on_close)
      self.pack_end(bar, True)

  def on_close(self, *args):
    if len(self.children()) < 1:
      self.hide()


# FIXME    if hasattr(gtk, "InfoBar"):

class GwibberInfoBar(hasattr(gtk, "InfoBar") and gtk.InfoBar or gtk.VBox):
  def __init__(self, data=None):
    gtk.InfoBar.__init__(self)
    self.service = microblog.util.getbus("Service")
    self.set_message_type(gtk.MESSAGE_ERROR)
    #self.set_no_show_all(True)

    self.account = data["error"]["account"]
    content_area = self.get_content_area()
    
    #if not account.has_key("service"):
    #  icon = gtk.image_new_from_file(resources.get_ui_asset("gwibber.png"))
    #else:
    icon = gtk.image_new_from_file(resources.get_ui_asset("icons/breakdance/16x16/%s.png" % data["error"]["account"]["service"]))
    
    label = gtk.Label(data["error"]["message"])

    label.set_use_markup(True)
    label.set_ellipsize(pango.ELLIPSIZE_END)

    content_area.pack_start(icon, False, False, 0)
    content_area.pack_start(label, True, True, 0)
    self.pack_start(content_area, False)

    close_button = gtk.Button()
    close_button.set_image(gtk.image_new_from_stock (gtk.STOCK_CLOSE, gtk.ICON_SIZE_BUTTON))
    close_button.set_tooltip_text(_("Close"))
    close_button.connect("clicked", self.on_error_close_clicked_cb)
    self.pack_end(close_button, False)

    if data["error"]["type"] == "auth":
      edit_button = gtk.Button()
      edit_button.set_image(gtk.image_new_from_stock (gtk.STOCK_EDIT, gtk.ICON_SIZE_BUTTON))
      edit_button.set_tooltip_text(_("Edit Account"))
      edit_button.connect("clicked", self.on_error_edit_clicked_cb, data["error"]["account"]["id"], data["error"]["message"])
      self.pack_end(edit_button, False)

    retry_button = gtk.Button()
    retry_button.set_image(gtk.image_new_from_stock (gtk.STOCK_REFRESH, gtk.ICON_SIZE_BUTTON))
    retry_button.set_tooltip_text(_("Retry"))
    retry_button.connect("clicked", self.on_error_retry_clicked_cb, data["error"]["account"]["id"])
    self.pack_end(retry_button, False)

    self.show_all()

  def on_error_edit_clicked_cb(self, w, account, message, *args):
    util.show_accounts_dialog(account, message, self, self.clear)

  def on_error_close_clicked_cb(self, *args):
    self.clear()

  def on_error_retry_clicked_cb(self, w, account, *args):
    self.service.PerformOp(json.dumps({
      "account": account,
      "operation": "receive",
      "args": {},
      "transient": False,
    }))
    self.clear()

  def clear(self):
    for child in self.children(): child.destroy()
    self.destroy()
    error_accounts.remove(self.account["id"])
     
  
class GwibberSearch(gtk.HBox):
  __gsignals__ = {
    "search": (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION, None, (str,)),
  }

  def __init__(self):
    gtk.HBox.__init__(self, spacing=2)

    self.entry = gtk.Entry()
    self.entry.connect("activate", self.on_search)
    self.entry.connect("changed", self.on_changed)

    self.button = gtk.Button(_("Search"))
    self.button.connect("clicked", self.on_search)

    self.pack_start(self.entry, True)
    self.pack_start(self.button, False)

    try:
      self.entry.set_property("primary-icon-stock", gtk.STOCK_FIND)
      self.entry.connect("icon-press", self.on_icon_press)
    except: pass

  def on_search(self, *args):
    self.emit("search", self.entry.get_text())
    self.clear()

  def clear(self):
    self.entry.set_text("")

  def on_icon_press(self, w, pos, e):
    if pos == 1: return self.clear()

  def on_changed(self, widget):
    self.entry.set_property("secondary-icon-stock",
      gtk.STOCK_CLEAR if self.entry.get_text().strip() else None)

  def set_visible(self, value):
    if value: self.hide()
    else: self.show_all()

  def focus(self):
    self.entry.grab_focus()

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
    self.model = Model()

    self.content = content

    self.overlay_color = util.get_theme_colors()["text"].darker(3).hex
    self.overlay_text = '<span weight="bold" size="xx-large" foreground="%s">%s</span>'

    self.shortener = microblog.util.getbus("URLShorten")

    self.connection = microblog.util.getbus("Connection")
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
    if self.model.settings["shorten_urls"]:
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

gtk.binding_entry_add_signal(InputTextView, gtk.keysyms.Return, 0, "submit")
gtk.binding_entry_add_signal(InputTextView, gtk.keysyms.KP_Enter, 0, "submit")
gtk.binding_entry_add_signal(InputTextView, gtk.keysyms.Escape, 0, "clear")
