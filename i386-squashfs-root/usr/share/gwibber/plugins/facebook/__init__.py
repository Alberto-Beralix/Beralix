#!/usr/bin/env python

from gwibber.microblog import network, util
from gwibber.microblog.util import log, resources
import hashlib, mx.DateTime, time
from os.path import join, getmtime, exists
from gettext import lgettext as _
from gwibber.microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from gwibber.microblog.util.custom import *
except:
  pass

log.logger.name = "Facebook"

PROTOCOL_INFO = {
  "name": "Facebook",
  "version": "1.1",
  
  "config": [
    "color",
    "receive_enabled",
    "send_enabled",
    "username",
    "uid",
    "private:access_token"
  ],

  "authtype": "facebook",
  "color": "#64006C",

  "features": [
    "send",
    "reply",
    "receive",
    "thread",
    "delete",
    "send_thread",
    "like",
    "sincetime"
  ],

  "default_streams": [
    "receive",
    "images",
    "links",
    "videos",
  ]
}

URL_PREFIX = "https://graph.facebook.com/"
POST_URL = "http://www.facebook.com/profile.php?id=%s&v=feed&story_fbid=%s&ref=mf"

class Client:
  def __init__(self, acct):
    self.account = acct
    self.user_id = acct.get("uid", None)

  def _check_error(self, data):
    if isinstance(data, dict):
      if data.has_key("error"):
        log.logger.info("Facebook error %s - %s", data["error"]["type"], data["error"]["message"])
        return True
      else: 
        return False
    return True
    
  def _get(self, operation, post=False, single=False, **args):
    if not self.user_id or "access_token" not in self.account:
      logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Authentication failed"), "Auth needs updating")
      log.logger.error("%s", logstr)
      return [{"error": {"type": "auth", "account": self.account, "message": _("Authentication failed, please re-authorize")}}]

    args.update({
      "access_token": self.account["access_token"]
    })

    sig = "".join("%s=%s" % (k, v) for k, v in sorted(args.items()))
    args["sig"] = hashlib.md5(sig + self.account["access_token"]).hexdigest()
    data = network.Download((URL_PREFIX + operation), args, post).get_json()

    resources.dump(self.account["service"], self.account["id"], data)

    if isinstance(data, dict) and data.get("error_msg", 0):
      if "permission" in data["error_msg"]:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Authentication failed"), data["error_msg"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["error_msg"]}}]
      elif data["error_code"] == 102:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Session invalid"), data["error_msg"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["error_msg"]}}]
      else:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Unknown failure"), data["error_msg"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "unknown", "account": self.account, "message": data["error_msg"]}}]

    return data

  def _sender(self, data):
    sender = {
      "name": data["name"],
      "id": str(data.get("id", '')),
      "is_me": str(data.get("id", '')) == self.user_id,
      "image": URL_PREFIX + data["id"] + "/picture",
      "url": "https://www.facebook.com/profile.php?id=" + str(data.get("id", ''))
    }
    return sender
  
  def _message(self, data):
    if type(data) != dict:
      log.logger.error("Cannot parse message data: %s", str(data))
      return {}

    m = {}
    m["mid"] = str(data["id"])
    m["service"] = "facebook"
    m["account"] = self.account["id"]

    m["time"] = int(mx.DateTime.DateTimeFrom(str(data.get("updated_time", data["created_time"]))))
    m["url"] = "https://facebook.com/" + data["id"].split("_")[0] + "/posts/" + data["id"].split("_")[1]
    

    if data.get("attribution", 0):
      m["source"] = util.strip_urls(data["attribution"]).replace("via ", "")
    
    if data.has_key("message"):
      m["to_me"] = ("@%s" % self.account["username"]) in data["message"]
    if data.get("message", "").strip():
      m["text"] = data["message"]
      m["html"] = util.linkify(data["message"])
      m["content"] = m["html"]
    else:
      m["text"] = ""
      m["html"] = ""
      m["content"] = ""

    m["sender"] = self._sender(data["from"])

    m["type"] = data["type"]

    if data["type"] == "photo":
      m["photo"] = {}
      m["photo"]["picture"] = data.get("picture", None)
      m["photo"]["url"] = data.get("link", None)
      m["photo"]["name"] = data.get("name", None)
    if data["type"] == "video":
      m["video"] = {}
      m["video"]["picture"] = data.get("picture", None)
      m["video"]["source"] = data.get("source", None)
      m["video"]["url"] = data.get("link", None)
      m["video"]["name"] = data.get("name", None)
      m["video"]["icon"] = data.get("icon", None)
      m["video"]["properties"] = data.get("properties", {})
    if data["type"] == "link":
      m["link"] = {}
      m["link"]["picture"] = data.get("picture", None)
      m["link"]["name"] = data.get("name", None)
      m["link"]["description"] = data.get("description", None)
      m["link"]["url"] = data.get("link", None)
      m["link"]["icon"] = data.get("icon", None)
      m["link"]["caption"] = data.get("caption", None)
      m["link"]["properties"] = data.get("properties", {})
    
    if data.has_key("privacy"):
      m["privacy"] = {}
      m["privacy"]["description"] = data["privacy"]["description"]
      m["privacy"]["value"] = data["privacy"]["value"]

    # Handle target for wall posts with a specific recipient
    if data.has_key("to"):
      m["sender"]["name"] += u" \u25b8 %s"%(data["to"]["data"][0]["name"])

    if data.has_key("likes"):
      m["likes"] = {}
      if isinstance(data["likes"], dict):
        m["likes"]["count"] = data["likes"]["count"]
        m["likes"]["data"] = data["likes"]["data"]
      else:
        m["likes"]["count"] = data["likes"]

    if data.get("comments", 0):
      m["comments"] = []
      if data["comments"].has_key("data"):
        for item in data["comments"]["data"]:
          m["comments"].append({
              "text": item["message"],
              "time": int(mx.DateTime.DateTimeFrom(str(data.get("updated_time", data["created_time"])))),
              "sender": self._sender(item["from"]),
            })

    if data.get("attachment", 0):
      if data["attachment"].get("name", 0):
        m["content"] += "<p><b>%s</b></p>" % data["attachment"]["name"]

      if data["attachment"].get("description", 0):
        m["content"] += "<p>%s</p>" % data["attachment"]["description"]

    return m

  def __call__(self, opname, **args):
    return getattr(self, opname)(**args)

  def receive(self, since=None):
    if not since:
      since = int(mx.DateTime.DateTimeFromTicks(mx.DateTime.localtime()) - mx.DateTime.TimeDelta(hours=240.0))
    else:
      since = int(mx.DateTime.DateTimeFromTicks(since).localtime())

    data = self._get("me/home")
    
    log.logger.debug("<STATS> facebook:receive account:%s since:%s size:%s",
        self.account["id"], mx.DateTime.DateTimeFromTicks(since), len(str(data)))
    
    if not self._check_error(data):
      try:
        return [self._message(post) for post in data["data"]]
      except TypeError:
        log.logger.error("<facebook:receive> failed to parse message data")
        return data
    else: return 

  def delete(self, message):
    result = self._get("stream.remove", post_id=message["mid"])
    if not result:
      log.logger.error("<facebook:delete> failed")
      return
    return []

  def like(self, message):
    result = self._get(message["mid"] + "/likes", post=True)
    if not result:
      log.logger.error("<facebook:like> failed")
      return
    return []

  def send(self, message):
    result = self._get("me/feed", message=message, status_includes_verb=True, post=True)
    if not result:
      log.logger.error("<facebook:send> failed")
      return
    return []

  def send_thread(self, message, target):
    result = self._get(target["mid"] + "/comments", message=message, post=True)
    if not result:
      log.logger.error("<facebook:send_thread> failed")
      return
    return []
