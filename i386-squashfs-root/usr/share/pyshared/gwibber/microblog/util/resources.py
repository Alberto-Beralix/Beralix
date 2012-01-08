
"""
Paths to various Gwibber files and resources
SegPhault (Ryan Paul) - 11/22/2008
"""

import os, sys
from os.path import join, isdir, realpath, exists
from os import makedirs, remove
from os import environ
import Image
import log
import mx.DateTime
from gwibber.microblog import network
from const import *
import inspect

# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from custom import *
except:
  pass

log.logger.name = "Gwibber Dispatcher Resources"

PROGRAM_NAME = "gwibber"
UI_DIR_NAME = "ui"
THEME_DIR_NAME = os.path.join(UI_DIR_NAME, "themes")
LAUNCH_DIR = os.path.abspath(sys.path[0])
DATA_DIRS = [LAUNCH_DIR]
THEME_NAME = "default"

# Minimum theme version, this is a serial to ensure themes are compatible
# with current version of the client.  This serial is set in the theme 
# dir in a file named theme.version 
THEME_MIN_VERSION = 2

try:
  import xdg
  DATA_BASE_DIRS = xdg.BaseDirectory.xdg_data_dirs
  CACHE_BASE_DIR = xdg.BaseDirectory.xdg_cache_home
except:
  DATA_BASE_DIRS = [
    os.path.join(os.path.expanduser("~"), ".local", "share"),
    "/usr/local/share", "/usr/share"]
  CACHE_BASE_DIR = os.path.join(os.path.expanduser("~"), ".cache")

DATA_DIRS += [os.path.join(d, PROGRAM_NAME) for d in DATA_BASE_DIRS]

def get_plugin_dirs():
  PLUGINS = []
  PLUGINS_DIRS = []
  PLUGINS_DIRS += [os.path.join(d, "gwibber", "plugins") for d in DATA_BASE_DIRS]

  if exists(os.path.join("gwibber", "microblog", "plugins")):
    PLUGINS_DIRS.insert(0, os.path.realpath(os.path.join("gwibber", "microblog", "plugins")))

  if exists(os.path.join("gwibber", "plugins")):
    PLUGINS_DIRS.insert(0, os.path.realpath(os.path.join("gwibber", "plugins")))

  if environ.has_key("GWIBBER_PLUGIN_DIR"):
    GWIBBER_PLUGIN_DIR = environ["GWIBBER_PLUGIN_DIR"]
    if exists(os.path.realpath(GWIBBER_PLUGIN_DIR)):
      PLUGINS_DIRS.insert(0, os.path.realpath(GWIBBER_PLUGIN_DIR))

  PLUGINS_DIRS.reverse()

  for p in PLUGINS_DIRS:
    if exists(p):
      sys.path.insert(0, p)
      for d in os.listdir(p):
        if os.path.isdir(os.path.join(p, d)):
          if d not in PLUGINS:
            PLUGINS.append(d)
  return [PLUGINS,PLUGINS_DIRS] 

def get_twitter_keys():
  # Distros should register their own keys and not rely on the defaults
  return TWITTER_OAUTH_KEY, TWITTER_OAUTH_SECRET

def get_avatar_path(url):
  avatar_cache_dir = realpath(join(CACHE_BASE_DIR, "gwibber", "avatars"))
  if not isdir(avatar_cache_dir):
    makedirs(avatar_cache_dir)
  avatar_cache_image = join(avatar_cache_dir, url.replace("/",""))

  if not exists(avatar_cache_image) or len(open(avatar_cache_image, "r").read()) < 1:
    log.logger.debug("Downloading avatar %s", url)
    f = file(avatar_cache_image, "w")
    data = network.Download(url)
    f.write(data.get_string())
    f.close()
    img_resize(avatar_cache_image, 48)

  if len(open(avatar_cache_image, "r").read()) > 0:
    return avatar_cache_image
  return None

def del_avatar(avatar):
  if exists(avatar):
    try:
      remove(avatar)
    except:
      log.logger.error("Failed to remove avatar from cache: %s", avatar)

def img_resize(img_path, size):
  try:
    image = Image.open(img_path)
    x, y = image.size
    if x != size or y != size:
      # need to upsample limited palette images before resizing
      if image.mode == 'P': image = image.convert('RGBA')
      image.resize((size, size), Image.ANTIALIAS).save(img_path, format="jpeg")
  except Exception, e:
    from traceback import format_exc
    log.logger.error("Image resizing failed:\n%s", format_exc())

def get_desktop_file():
  p = os.path.join(LAUNCH_DIR, "gwibber.desktop")
  if os.path.exists(p): return p
  
  for base in DATA_BASE_DIRS:
    p = os.path.join(base, "applications", "gwibber.desktop")
    if os.path.exists(p): return p

def get_theme_paths():
  for base in DATA_DIRS:
    theme_root = os.path.join(base, THEME_DIR_NAME)
    if os.path.exists(theme_root):
      for f in sorted(os.listdir(theme_root)):
        if not f.startswith('.'):
          theme_dir = os.path.join(theme_root, f)
          if os.path.isdir(theme_dir) and \
            os.path.exists(os.path.join(theme_dir, "theme.version")):
            with open(os.path.join(theme_dir, "theme.version")) as f:
              for line in f:
                if "theme_version" in line:
                  theme_version = int(line.split("=")[1])
                  if theme_version >= THEME_MIN_VERSION:
                    yield theme_dir

def get_theme_path(name):
  for path in get_theme_paths():
    if name == os.path.basename(path):
      return path

def theme_exists(theme):
  return bool(get_theme_path(theme))

def get_themes():
  themes = {}
  for path in get_theme_paths():
    if not os.path.basename(path) in themes:
      themes[os.path.basename(path)] = path
  return themes

def get_ui_asset(asset_name):
  # Look for UI assets in PLUGINS_DIRS first, then fallback to DATA_DIRS
  PLUGINS_DIRS = get_plugin_dirs()[1]
  PLUGINS_DIRS.reverse()
  for p in PLUGINS_DIRS:
    if exists(p):
      for d in os.listdir(p):
        if os.path.isdir(os.path.join(p, d, UI_DIR_NAME)):
          asset_path = os.path.join(p, d, UI_DIR_NAME, asset_name)
          if os.path.exists(asset_path):
            return asset_path

  for base in DATA_DIRS:
    asset_path = os.path.join(base, UI_DIR_NAME, asset_name)
    if os.path.exists(asset_path):
      return asset_path
  return None

def get_template_dirs():
  for base in DATA_DIRS:
    p = os.path.join(base, UI_DIR_NAME, "templates")
    if os.path.exists(p):
      yield p

def get_theme_asset(asset_name, theme="default"):
  theme_path = get_theme_path(theme)
  if theme_path:
    fname = os.path.join(theme_path, asset_name)
    if os.path.exists(fname):
      return fname

def get_template_path(template, theme="default"):
  theme_template = get_theme_asset(template, theme)
  if theme_template: return theme_template
  for d in get_template_dirs():
    template_path = os.path.join(d, template)
    if template_path: return template_path

def dump(service, aid, data):
  if GWIBBER_TEST_DUMP and len(data) > 0:
    operation = inspect.stack()[2][3]
    dump_cache_dir = realpath(join(CACHE_BASE_DIR, "gwibber", "dump", service))
    if not isdir(dump_cache_dir):
      makedirs(dump_cache_dir)
    dump_cache_file = join(dump_cache_dir, (aid + "." + str(mx.DateTime.now()) + "." + operation))

    if not exists(dump_cache_file) or len(open(dump_cache_file, "r").read()) < 1:
      log.logger.debug("Dumping test data %s - %s - %s", service, aid, operation)
      f = file(dump_cache_file, "w")
      f.write(str(data))
      f.close()
