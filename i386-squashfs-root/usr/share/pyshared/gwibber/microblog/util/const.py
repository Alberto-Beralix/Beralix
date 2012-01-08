import xdg.BaseDirectory
from os.path import join, isdir, realpath
from os import mkdir, environ

CACHE_DIR = realpath(join(xdg.BaseDirectory.xdg_cache_home, "gwibber"))
if not isdir(CACHE_DIR):
  mkdir(CACHE_DIR)

from os import environ
if environ.has_key("FB_APP_KEY"):
  FB_APP_KEY = environ["FB_APP_KEY"]
else:
  FB_APP_KEY = "71b85c6d8cb5bbb9f1a3f8bbdcdd4b05"

TWITTER_OAUTH_KEY = "VDOuA5qCJ1XhjaSa4pl76g"
TWITTER_OAUTH_SECRET = "BqHlB8sMz5FhZmmFimwgiIdB0RiBr72Y0bio49IVJM"

# Gwibber
MAX_MESSAGE_LENGTH = 140
MAX_MESSAGE_COUNT = 20000

cache_dir = realpath(join(xdg.BaseDirectory.xdg_cache_home, "gwibber"))
config_dir = realpath(join(xdg.BaseDirectory.xdg_config_home, "gwibber"))
SQLITE_DB_FILENAME = "%s/gwibber.sqlite" % config_dir
if not isdir(cache_dir): mkdir(cache_dir)
if not isdir(config_dir): mkdir(config_dir)

GWIBBER_TEST_DUMP = None
if environ.has_key("GWIBBER_TEST_DUMP"):
  GWIBBER_TEST_DUMP = environ["GWIBBER_TEST_DUMP"]

DEFAULT_SETTINGS = {
  "interval": 15,
  "view": "SingleStreamUi",
  "streams": '[{"stream": "messages", "account": null}]',
  "show_notifications": True,
  "notify_mentions_only": True,
  "presence_check": True,
  "show_fullname": True,
  "shorten_urls": True,
  "urlshorter": "is.gd",
  "imageuploader": "imageshack",
  "reply_append_colon": True,
  "retweet_style": "recycle",
  "global_retweet": False,
  "theme": "default",
  "window_size":  (500, 580),
  "window_position": (0, 24),
  "window_splitter": 450,
  "sidebar_splitter": 40,
  "minimize_to_tray": False,
  "hide_taskbar_entry": False,
  "show_tray_icon": True,
}

RETWEET_FORMATS = {
  "via": "{text} (via @{nick})",
  "RT": "RT @{nick}: {text}",
  "RD": "RD @{nick}: {text}",
  "/via": "{text} /via @{nick}",
  "/by": "{text} /by @{nick}",
  "recycle": u"\u267a @{nick}: {text}",
  "service": "{R} @{nick}: {text}",
}

VERSION_NUMBER = "3.2.0.1"
GCONF_CLIENT_DIR = "/apps/gwibber/client/"

BUG_URL = "https://bugs.launchpad.net/gwibber/+filebug"
QUESTIONS_URL = "https://answers.launchpad.net/gwibber"
TRANSLATE_URL = "https://translations.launchpad.net/gwibber"

GWIBBER_OPERATIONS = """
{
  "delete": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "favorites": {
    "account_tree": true,
    "dynamic": true,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "favorites",
    "transient": false
  },

  "group": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "group",
    "transient": true
  },

  "like": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "lists": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "lists",
    "transient": true,
    "interval": 20
  },

  "list": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "list",
    "transient": true
  },

  "private": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "private",
    "transient": false
  },
  
  "public": {
    "account_tree": true,
    "dynamic": true,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "public",
    "transient": false
  },
 
  "receive": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "messages",
    "transient": false
  },

  "images": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "images",
    "transient": false 
  },

  "links": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "links",
    "transient": false 
  },

  "videos": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "videos",
    "transient": false 
  },

  "reply": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": true,
    "function": "send",
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "responses": {
    "account_tree": true,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "replies",
    "transient": false
  },

  "retweet": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },
 
  "follow": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "unfollow": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "search": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "search",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": true,
    "stream": "search",
    "transient": true
  },
  
  "search_url": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "search",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": true,
    "stream": "search",
    "transient": true
  },

  "send": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "send",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "messages",
    "transient": false
  },

  "send_thread": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "send",
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },

  "send_private": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "send",
    "first_only": false,
    "function": null,
    "return_value": false,
    "search": false,
    "stream": null,
    "transient": false
  },
  
  "tag": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": null,
    "transient": false
  },

  "thread": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "thread",
    "transient": true
  },
  
  "user_messages": {
    "account_tree": false,
    "dynamic": false,
    "enabled": "receive",
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "user",
    "transient": true
  },
  
  "profile": {
    "account_tree": false,
    "dynamic": false,
    "enabled": null,
    "first_only": false,
    "function": null,
    "return_value": true,
    "search": false,
    "stream": "profile",
    "transient": true
  }
}
"""
