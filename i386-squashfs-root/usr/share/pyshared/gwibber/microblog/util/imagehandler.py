#!/usr/bin/env python

import os, hashlib, urllib2, Image

DEFAULT_AVATAR = 'http://digg.com/img/udl.png'

try:
  import xdg
  CACHE_BASE_DIR = xdg.BaseDirectory.xdg_cache_home
except:
  CACHE_BASE_DIR = os.path.join(os.path.expanduser("~"), ".cache")

CACHE_DIR = os.path.join(CACHE_BASE_DIR, "gwibber", "images")

class ImageHandler:
  def __init__(self, cache_dir=CACHE_DIR):
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    self.cache_dir = cache_dir
    print cache_dir

  def get_path(self, url):
    urlhash = hashlib.sha1(url).hexdigest()
    if len(urlhash) > 200: urlhash = urlhash[::-1][:200]
    suffix = "jpg" if "friendfeed" in url else url.split(".")[-1]
    return os.path.join(self.cache_dir, "%s.%s" % (urlhash, suffix)).replace("\n", "")

  def resize(self, img_path, size):
    try:
      image = Image.open(img_path)
      x, y = image.size
      if x != size or y != size: 
        # need to upsample limited palette images before resizing
        if image.mode == 'P': image = image.convert('RGBA') 
        image.resize((size, size), Image.ANTIALIAS).save(img_path)
    except Exception, e:
      from traceback import format_exc
      print(format_exc())

  def download(self, url, img_path):
    if not os.path.exists(img_path):
      print img_path
      output = open(img_path, "w+")
      try:
        image_data = urllib2.urlopen(url).read()
        if image_data.startswith("<?xml"): raise IOError()
        output.write(urllib2.urlopen(url).read())
        output.close()
        self.resize(img_path, 48)
      except IOError, e:
        if hasattr(e, 'reason'): # URLError
          print('image_cache URL Error: %s whilst fetching %s' % (e.reason, url))
        elif hasattr(e, 'code') and hasattr(e, 'msg') and hasattr(e, 'url'): # HTTPError
          print('image_cache HTTP Error %s: %s whilst fetching %s' % (e.code, e.msg, e.url))
        else: print(e)
        # if there were any problems getting the avatar img replace it with default
        output.write(urllib2.urlopen(DEFAULT_AVATAR).read())
      finally: output.close()


