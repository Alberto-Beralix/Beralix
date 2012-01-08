import gtk, gwui, microblog, util, json
from microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from microblog.util.custom import *
except:
  pass

import gwibber.microblog.util
from gwibber.microblog.util import resources
import mx.DateTime
import re

from gettext import lgettext as _

class MessageAction:
  icon = None
  label = None

  @classmethod
  def get_icon_path(self, size=16, use_theme=True):
    return util.icon(self.icon, size, use_theme)
    
  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False
    return self.__name__ in client.model.services[msg["service"]]["features"]

  @classmethod
  def action(self, w, client, msg):
    pass

class reply(MessageAction):
  icon = "mail-reply-sender"
  label = _("_Reply")

  @classmethod
  def action(self, w, client, msg):
    if msg.get("private", 0):
      client.private(msg)
    else:
      client.reply(msg)

  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False
    if "reply" in client.model.services[msg["service"]]["features"]:
      if not msg.get("sender", {}).get("is_me", 0):
        return True
    
class thread(MessageAction):
  icon = "mail-reply-all"
  label = _("View reply t_hread")

  @classmethod
  def action(self, w, client, msg):
    tab_label = msg["original_title"] if msg.has_key("original_title") else msg["text"]
    client.add_transient_stream(msg.account, "thread",
        "message:/" + msg.gwibber_path, "Thread")

class retweet(MessageAction):
  icon = "mail-forward"
  label = _("R_etweet")
  PARSE_GROUP = re.compile("\B!([A-Za-z0-9_\-]+|@[A-Za-z0-9_\-]$)")

  @classmethod
  def action(self, w, client, msg):
    if "retweet" in client.model.services[msg["service"]]["features"]:
      text = RETWEET_FORMATS[client.model.settings["retweet_style"]]
      symbol = "RD" if msg["service"] == "identica" else "RT"
      text = text.format(text=msg["text"], nick=msg["sender"]["nick"], R=symbol)
      #replace ! with # if identica service
      if msg["service"] == "identica" and client.model.settings["global_retweet"]:
          text = self.PARSE_GROUP.sub('#\\1', text)

      if not client.model.settings["global_retweet"]:
        client.message_target.set_target(msg, "repost")
        
      client.input.set_text(text)
      client.input.textview.grab_focus()
      buf = client.input.textview.get_buffer()
      buf.place_cursor(buf.get_end_iter())

  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False

    if "retweet" in client.model.services[msg["service"]]["features"]:
      if not msg.get("sender", {}).get("is_me", 0) and not msg.get("private", 0):
        return True

class private(MessageAction):
  icon = "mail-reply-sender"
  label = _("_Direct Message")

  @classmethod
  def action(self, w, client, msg):
    client.private(msg)

  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False
    if "private" in client.model.services[msg["service"]]["features"]:
      if not msg.get("sender", {}).get("is_me", 0) and not msg.get("private", 0):
        return True

class like(MessageAction):
  icon = "bookmark_add"
  label = _("_Like this message")

  @classmethod
  def action(self, w, client, msg):
    client.service.PerformOp(json.dumps({
      "account": msg["account"],
      "operation": "like",
      "args": {"message": msg},
      "transient": False,
    }))
    
    image = resources.get_ui_asset("gwibber.svg")
    expire_timeout = 5000
    n = gwibber.microblog.util.notify(_("Liked"), _("You have marked this message as liked."), image, expire_timeout)
  
  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False
    if "like" in client.model.services[msg["service"]]["features"]:
      if not msg.get("sender", {}).get("is_me", 0) and not msg.get("private", 0):
        return True

class delete(MessageAction):
  icon = "gtk-delete"
  label = _("_Delete this message")

  @classmethod
  def action(self, w, client, msg):
    client.service.PerformOp(json.dumps({
      "account": msg["account"],
      "operation": "delete",
      "args": {"message": msg},
      "transient": False,
    }))

    image = resources.get_ui_asset("gwibber.svg")
    expire_timeout = 5000
    n = gwibber.microblog.util.notify(_("Deleted"), _("The message has been deleted."), image, expire_timeout)

  @classmethod
  def include(self, client, msg):
    if not client.model.services.has_key(msg["service"]):
      return False
    if "delete" in client.model.services[msg["service"]]["features"]:
      if msg.get("sender", {}).get("is_me", 0):
        return True

class search(MessageAction):
  icon = "gtk-find"
  label = _("_Search for a query")

  @classmethod
  def action(self, w, client, query=None):
    pass

class read(MessageAction):
  icon = "mail-read"
  label = _("View _Message")

  @classmethod
  def action(self, w, client, msg):
    if msg.has_key("url"):
      util.load_url(msg["url"])
    elif msg.has_key("images"):
      util.load_url(msg["images"][0]["url"])

  @classmethod
  def include(self, client, msg):
    if not msg.get("private", 0):
      return "url" in msg

class list(MessageAction):
  @classmethod
  def action(self, w, client, acct=None, user=None, id=None, name=None):
    if acct and user and id and name:
      client.add_stream({
        "name": name,
        "account": acct,
        "operation": "list",
        "parameters": {"user": user, "id": id},
      })

class user(MessageAction):
  icon = "face-monkey"
  label = _("View user _Profile")
  
  @classmethod
  def action(self, w, client, acct=None, name=None):
    client.add_stream({
      "name": name,
      "account": acct,
      "operation": "user_messages",
      "parameters": {"id": name, "count": 50},
    })

class menu(MessageAction):
  @classmethod
  def action(self, w, client, msg):
    client.on_message_action_menu(msg, w)

class tag(MessageAction):
  @classmethod
  def action(self, w, client, acct, query):
    client.add_stream({
      "name": "#%s" % query,
      "query": "#%s" % query,
    })

class translate(MessageAction):
  icon = "config-language"
  label = _("Tra_nslate")

  @classmethod
  def action(self, w, client, msg):
    ## Need to figure out the user's language instead of default to EN
    script = """document.getElementById("text-%s").innerHTML = %s"""
    text = gwibber.microblog.util.getbus("Translate").Translate(msg["text"], "", "en")
    if isinstance(w.messages.message_view, gwui.WebUi):
      w.messages.message_view.execute_script(script % (msg["id"], json.dumps(text)))

  @classmethod
  def include(self, client, msg):
    return True

class group(MessageAction):
  icon = "face-monkey"

  @classmethod
  def action(self, w, client, acct, query):
    client.add_transient_stream(acct, "group", query)
    print "Searching for group", query

class tomboy(MessageAction):
  icon = "tomboy"
  label = _("Save to _Tomboy")

  @classmethod
  def action(self, w, client, msg):
    util.create_tomboy_note(
      _("%(service_name)s message from %(sender)s at %(time)s\n\n%(message)s\n\nSource: %(url)s") % {
        "service_name": client.model.services[msg["service"]]["name"],
        "sender": msg["sender"]["name"],
        "time": mx.DateTime.DateTimeFromTicks(msg["time"]).localtime().strftime(),
        "message": msg["text"],
        "url": msg["url"]
    })

  @classmethod
  def include(self, client, msg):
    return gwibber.microblog.util.service_is_running("org.gnome.Tomboy")

MENU_ITEMS = [reply, retweet, private, read, user, like, delete, tomboy, translate]
