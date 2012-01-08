from gwibber.microblog import network, util
import re
import gnomekeyring
from oauth import oauth
from gwibber.microblog.util import log, resources
from gettext import lgettext as _
log.logger.name = "Twitter"

PROTOCOL_INFO = {
  "name": "Twitter",
  "version": "1.0",
  
  "config": [
    "private:secret_token",
    "access_token",
    "username",
    "color",
    "receive_enabled",
    "send_enabled",
  ],
 
  "authtype": "oauth1a",
  "color": "#729FCF",

  "features": [
    "send",
    "receive",
    "search",
    "tag",
    "reply",
    "responses",
    "private",
    "public",
    "delete",
    "follow",
    "unfollow",
    "profile",
    "retweet",
    "like",
    "send_thread",
    "send_private",
    "user_messages",
    "sinceid",
    "lists",
    "list",
  ],

  "default_streams": [
    "receive",
    "images",
    "responses",
    "private",
    "lists",
  ],
}

URL_PREFIX = "https://twitter.com"
API_PREFIX = "https://api.twitter.com/1"

class Client:
  def __init__(self, acct):
    self.service = util.getbus("Service")
    if acct.has_key("secret_token") and acct.has_key("password"): acct.pop("password")
    self.account = acct

    if not acct.has_key("access_token") and not acct.has_key("secret_token"):
      return [{"error": {"type": "auth", "account": self.account, "message": _("Failed to find credentials")}}]

    self.sigmethod = oauth.OAuthSignatureMethod_HMAC_SHA1()
    self.consumer = oauth.OAuthConsumer(*util.resources.get_twitter_keys())
    self.token = oauth.OAuthToken(acct["access_token"], acct["secret_token"])

  def _common(self, data):
    m = {};
    try:

      m["mid"] = str(data["id"])
      m["service"] = "twitter"
      m["account"] = self.account["id"]
      if data.has_key("created_at"):
        m["time"] = util.parsetime(data["created_at"])
      m["text"] = util.unescape(data["text"])
      m["to_me"] = ("@%s" % self.account["username"]) in data["text"]

      m["html"] = util.linkify(m["text"],
        ((util.PARSE_HASH, '#<a class="hash" href="%s#search?q=\\1">\\1</a>' % URL_PREFIX),
        (util.PARSE_NICK, '@<a class="nick" href="%s/\\1">\\1</a>' % URL_PREFIX)), escape=False)

      m["content"] = util.linkify(m["text"],
        ((util.PARSE_HASH, '#<a href="gwibber:/tag?acct=%s&query=\\1">\\1</a>' % m["account"]),
        (util.PARSE_NICK, '@<a href="gwibber:/user?acct=%s&name=\\1">\\1</a>' % m["account"])), escape=True)

      m["favorited"] = data.get("favorited", False)

      images = util.imgpreview(m["text"])
      if images:
        m["images"] = images
        m["type"] = "photo"
    except: 
      log.logger.error("%s failure - %s", PROTOCOL_INFO["name"], data)
      return {}
 
    return m

  def _user(self, user):
    return {
        "name": user.get("name", None),
        "nick": user.get("screen_name", None),
        "id": user.get("id", None),
        "location": user.get("location", None),
        "followers": user.get("followers_count", None),
        "friends": user.get("friends_count", None),
        "description": user.get("description", None),
        "following": user.get("following", None),
        "protected": user.get("protected", None),
        "statuses": user.get("statuses_count", None),
        "image": user.get("profile_image_url", None),
        "website": user.get("url", None),
        "url": "/".join((URL_PREFIX, user.get("screen_name", ""))) or None,
        "is_me": user.get("screen_name", None) == self.account["username"],
    }
    
  def _message(self, data):
    if type(data) != dict:
      log.logger.error("Cannot parse message data: %s", str(data))
      return {}

    n = {}
    if data.has_key("retweeted_status"):
      n["retweeted_by"] = self._user(data["user"] if "user" in data else data["sender"])
      if data.has_key("created_at"):
        n["time"] = util.parsetime(data["created_at"])
      data = data["retweeted_status"]
    else:
      n["retweeted_by"] = None
      if data.has_key("created_at"):
        n["time"] = util.parsetime(data["created_at"])

    m = self._common(data)
    for k in n:
      m[k] = n[k]

    m["source"] = data.get("source", False)
    
    if data.has_key("in_reply_to_status_id"):
      if data["in_reply_to_status_id"]:
        m["reply"] = {}
        m["reply"]["id"] = data["in_reply_to_status_id"]
        m["reply"]["nick"] = data["in_reply_to_screen_name"]
        if m["reply"]["id"] and m["reply"]["nick"]:
          m["reply"]["url"] = "/".join((URL_PREFIX, m["reply"]["nick"], "statuses", str(m["reply"]["id"])))
        else:
          m["reply"]["url"] = None

    m["sender"] = self._user(data["user"] if "user" in data else data["sender"])
    m["url"] = "/".join((m["sender"]["url"], "statuses", str(m["mid"])))

    return m

  def _private(self, data):
    m = self._message(data)
    m["private"] = True

    m["recipient"] = {}
    m["recipient"]["name"] = data["recipient"]["name"]
    m["recipient"]["nick"] = data["recipient"]["screen_name"]
    m["recipient"]["id"] = data["recipient"]["id"]
    m["recipient"]["image"] = data["recipient"]["profile_image_url"]
    m["recipient"]["location"] = data["recipient"]["location"]
    m["recipient"]["url"] = "/".join((URL_PREFIX, m["recipient"]["nick"]))
    m["recipient"]["is_me"] = m["recipient"]["nick"] == self.account["username"]
    m["to_me"] = m["recipient"]["is_me"]

    return m

  def _result(self, data):
    m = self._common(data)
    
    if data["to_user_id"]:
      m["reply"] = {}
      m["reply"]["id"] = data["to_user_id"]
      m["reply"]["nick"] = data["to_user"]

    m["sender"] = {}
    m["sender"]["nick"] = data["from_user"]
    m["sender"]["id"] = data["from_user_id"]
    m["sender"]["image"] = data["profile_image_url"]
    m["sender"]["url"] = "/".join((URL_PREFIX, m["sender"]["nick"]))
    m["sender"]["is_me"] = m["sender"]["nick"] == self.account["username"]
    m["url"] = "/".join((m["sender"]["url"], "statuses", str(m["mid"])))
    return m

  def _profile(self, data):
    if "error" in data:
      return {
          "error": data["error"]
        }
    return {
        "name": data.get("name", data["screen_name"]),
        "service": "twitter",
        "stream": "profile",
        "account": self.account["id"],
        "mid": data["id"],
        "text": data.get("description", ""),
        "nick": data["screen_name"],
        "url": data.get("url", ""),
        "protected": data.get("protected", False),
        "statuses": data.get("statuses_count", 0),
        "followers": data.get("followers_count", 0),
        "friends": data.get("friends_count", 0),
        "following": data.get("following", 0),
        "favourites": data.get("favourites_count", 0),
        "image": data["profile_image_url"],
        "utc_offset": data.get("utc_offset", 0),
        "id": data["id"],
        "lang": data.get("lang", "en"),
        "verified": data.get("verified", False),
        "geo_enabled": data.get("geo_enabled", False),
        "time_zone": data.get("time_zone", "")
    }

  def _list(self, data):
    return {
        "mid": data["id"],
        "service": "twitter",
        "account": self.account["id"],
        "time": 0,
        "text": data["description"],
        "html": data["description"],
        "content": data["description"],
        "url": "/".join((URL_PREFIX, data["uri"])),
        "sender": self._user(data["user"]),
        "name": data["name"],
        "nick": data["slug"],
        "key": data["slug"],
        "full": data["full_name"],
        "uri": data["uri"],
        "mode": data["mode"],
        "members": data["member_count"],
        "followers": data["subscriber_count"],
        "kind": "list",
    }

  def _get(self, path, parse="message", post=False, single=False, **args):
    url = "/".join((API_PREFIX, path))

    request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, self.token,
        http_method=post and "POST" or "GET", http_url=url, parameters=util.compact(args))
    request.sign_request(self.sigmethod, self.consumer, self.token)
    
    if post:
      data = network.Download(request.to_url(), util.compact(args), post).get_json()
    else:
      data = network.Download(request.to_url(), None, post).get_json()

    resources.dump(self.account["service"], self.account["id"], data)

    if isinstance(data, dict) and data.get("errors", 0):
      if "authenticate" in data["errors"][0]["message"]:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Authentication failed"), error["message"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["errors"][0]["message"]}}]
      else:
        for error in data["errors"]:
          logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Unknown failure"), error["message"])
          return [{"error": {"type": "unknown", "account": self.account, "message": error["message"]}}]
    elif isinstance(data, dict) and data.get("error", 0):
      if "Incorrect signature" in data["error"]:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Request failed"), data["error"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["error"]}}]
    elif isinstance(data, str):
      logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Request failed"), data)
      log.logger.error("%s", logstr)
      return [{"error": {"type": "request", "account": self.account, "message": data}}]

    if parse == "follow" or parse == "unfollow":
      if isinstance(data, dict) and data.get("error", 0):
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Unable to %s user" % parse), data["error"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["error"]}}]
      else:
        return [["friendships", {"type": parse, "account": self.account["id"], "service": self.account["service"],"user_id": data["id"], "nick": data["screen_name"]}]]
    
    if parse == "profile":
      return self._profile(data)

    if parse == "list":
      return [self._list(l) for l in data["lists"]]

    if single: return [getattr(self, "_%s" % parse)(data)]
    if parse: return [getattr(self, "_%s" % parse)(m) for m in data]
    else: return []

  def _search(self, **args):
    data = network.Download("http://search.twitter.com/search.json", util.compact(args))
    data = data.get_json()["results"]

    if type(data) != list:
      log.logger.error("Cannot parse search data: %s", str(data))
      return []

    return [self._result(m) for m in data]

  def __call__(self, opname, **args):
    return getattr(self, opname)(**args)
  
  def receive(self, count=util.COUNT, since=None):
    return self._get("statuses/home_timeline.json", count=count, since_id=since)

  def responses(self, count=util.COUNT, since=None):
    return self._get("statuses/mentions.json", count=count, since_id=since)

  def private(self, count=util.COUNT, since=None):
    private = self._get("direct_messages.json", "private", count=count, since_id=since) or []
    private_sent = self._get("direct_messages/sent.json", "private", count=count, since_id=since) or []
    return private + private_sent

  def public(self):
    return self._get("statuses/public_timeline.json")

  def lists(self, **args):
    following = self._get("%s/lists/subscriptions.json" % self.account["username"], "list") or []
    lists = self._get("%s/lists.json" % self.account["username"], "list") or []
    return following + lists

  def list(self, user, id, count=util.COUNT, since=None):
    return self._get("%s/lists/%s/statuses.json" % (user, id), per_page=count, since_id=since)

  def search(self, query, count=util.COUNT, since=None):
    return self._search(q=query, rpp=count, since_id=since)

  def tag(self, query, count=util.COUNT, since=None):
    return self._search(q="#%s" % query, count=count, since_id=since)

  def delete(self, message):
    return self._get("statuses/destroy/%s.json" % message["mid"], None, post=True, do=1)

  def like(self, message):
    return self._get("favorites/create/%s.json" % message["mid"], None, post=True, do=1)

  def send(self, message):
    return self._get("statuses/update.json", post=True, single=True,
        status=message)
  
  def send_private(self, message, private):
    return self._get("direct_messages/new.json", "private", post=True, single=True,
        text=message, screen_name=private["sender"]["nick"])

  def send_thread(self, message, target):
    return self._get("statuses/update.json", post=True, single=True,
        status=message, in_reply_to_status_id=target["mid"])

  def retweet(self, message):
    return self._get("statuses/retweet/%s.json" % message["mid"], None, post=True, do=1)

  def follow(self, screen_name):
    return self._get("friendships/create.json", screen_name=screen_name, post=True, parse="follow")

  def unfollow(self, screen_name):
    return self._get("friendships/destroy.json", screen_name=screen_name, post=True, parse="unfollow")

  def profile(self, id=None, count=None, since=None):
    return self._get("users/show.json", screen_name=id, count=count, since_id=since, parse="profile")

  def user_messages(self, id=None, count=util.COUNT, since=None):
    profiles = [self.profile(id)] or []
    messages = self._get("statuses/user_timeline.json", id=id, count=count, since_id=since) or []
    return messages + profiles
