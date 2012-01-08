
import os, locale, re, mx.DateTime, cgi
import log, resources
import dbus
from const import *
from htmlentitydefs import name2codepoint


# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from custom import *
except:
  pass

COUNT = 200

def parsetime(t):
  locale.setlocale(locale.LC_TIME, 'C')
  result = mx.DateTime.Parser.DateTimeFromString(t)
  locale.setlocale(locale.LC_TIME, '')
  return result.ticks()

URL_SCHEMES = ('http', 'https', 'ftp', 'mailto', 'news', 'gopher',
               'nntp', 'telnet', 'wais', 'prospero', 'aim', 'webcal')

URL_FORMAT = (r'(?<!\w)(((?:%s)://|(?:www\.))' # protocol + :// or www.
    '(?!/)(?:' # get any starting /'s
    '[\w$\+\*@&=\-/]' # reserved | unreserved
    '|%%[a-fA-F0-9]{2}' # escape
    '|[\?\.:\(\),;!\'\~](?!(?:\s|$))' # punctuation
    '|(?:(?<=[^/:]{2})#)' # fragment id
    '){2,}' # at least two characters in the main url part
    ')') % ('|'.join(URL_SCHEMES),)

PARSE_LINK = re.compile(URL_FORMAT, re.U)
PARSE_NICK = re.compile("\B@([\w]+|@[\w]$)", re.UNICODE)
PARSE_HASH = re.compile("\B#([\w\-]+|@[\w\-]$)", re.UNICODE)
PARSE_URLS = re.compile(r"<[^<]*?/?>") 

def strip_urls(text):
  return PARSE_URLS.sub("", text)

def unescape(s):
  return re.sub('&(%s);' % '|'.join(name2codepoint),
    lambda m: unichr(name2codepoint[m.group(1)]), s)

def linkify(text, subs=[], escape=True):
  html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
  }
  def html_escape(text):
    return "".join(html_escape_table.get(c,c) for c in text)

  if escape: text = cgi.escape(text)
  #if escape: text = html_escape(text)
  for f, r in subs: text = f.sub(r, text)
  link = PARSE_LINK.sub('<a href="\\1">\\1</a>', text)
  # if link has www only, add http:// to the href
  return re.compile(r'"www.', re.U).sub('"http://www.', link)

def imgpreview(text):
  thumbre = {
    'twitpic': 'http://.*twitpic.com/(?!photos)([A-Za-z0-9]+)',
    'img.gd': 'http://img.gd/(?!photos)([A-Za-z0-9]+)',
    'imgur': 'http://.*imgur.com/(?!gallery)([A-Za-z0-9]+)',
    'twitgoo': 'http://.*twitgoo.com/(?!u/)([A-Za-z0-9]+)',
    'yfrog.us': 'http://.*yfrog.us/(?!froggy)([A-Za-z0-9]+)',
    'yfrog.com': 'http://.*yfrog.com/(?!froggy)([A-Za-z0-9]+)',
    'twitvid': 'http://.*twitvid.com/(?!videos)([A-Za-z0-9]+)',
    'img.ly': 'http://img.ly/(?!images)([A-Za-z0-9]+)', 
    'flic.kr': 'http://flic.kr/p/([A-Za-z0-9]+)',
    'youtu.be': 'http://youtu.be/([A-Za-z0-9-_]+)',
    'youtube.com': 'http://.*youtube.com/watch\?v=([A-Za-z0-9-_]+)',
    'tweetphoto': 'http://.*tweetphoto.com/(0-9]+)',
    'pic.gd': 'http://pic.gd/([A-Za-z0-9]+)',
    'brizzly': 'http://.*brizzly.com/pic/([A-Za-z0-9]+)',
    'twitxr': 'http://.*twitxr.com\/[^ ]+\/updates\/([0-9]+)',
    'ow.ly': 'http://ow.ly/i/([A-Za-z0-9]+)',
    'ts1.in': 'http://ts1.in/([0-9]+)',
    'twitsnaps': 'http://.*twitsnaps.com/([0-9]+)',
    'hellotext': 'http://.*hellotxt.com/i/([A-Za-z0-9]+)',
    'htxt.it': 'http://htxt.it/i/([A-Za-z0-9]+)',
    'moby.to': 'http://moby.to/([A-Za-z0-9]+)',
    'movapic': 'http://.*movapic.com/pic/([A-Za-z0-9]+)',
    'znl.me': 'http://znl.me/([A-Za-z0-9-_]+)',
    'bcphotoshare': 'http://.*bcphotoshare.com/photos/[0-9]+/([0-9]+)',
    'twitvideo.jp': 'http://.*twitvideo.jp/(?!contents)([A-Za-z0-9-_]+)'
    }
  thumburi = {
    'twitpic': 'http://twitpic.com/show/thumb/@',
    'img.gd': 'http://img.gd/show/thumb/@',
    'imgur': 'http://i.imgur.com/@s.jpg',
    'twitgoo': 'http://twitgoo.com/show/thumb/@',
    'yfrog.us': 'http://yfrog.us/@.th.jpg',
    'yfrog.com': 'http://yfrog.com/@.th.jpg',
    'twitvid': 'http://images.twitvid.com/@.jpg',
    'img.ly': 'http://img.ly/show/thumb/@',
    'flic.kr': 'http://flic.kr/p/img/@_m.jpg',
    'youtu.be': 'http://img.youtube.com/vi/@/default.jpg',
    'youtube.com': 'http://img.youtube.com/vi/@/default.jpg',
    'tweetphoto': 'http://TweetPhotoAPI.com/api/TPAPI.svc/json/imagefromurl?size=thumbnail&url=@',
    'pic.gd': 'http://TweetPhotoAPI.com/api/TPAPI.svc/json/imagefromurl?size=thumbnail&url=@',
    'brizzly': 'http://pics.brizzly.com/thumb_sm_@.jpg',
    'twitxr': 'http://twitxr.com/image/@/th/',
    'ow.ly': 'http://static.ow.ly/photos/thumb/@.jpg',
    'ts1.in': 'http://ts1.in/mini/@',
    'twitsnaps': 'http://twitsnaps.com/mini/@',
    'hellotext': 'http://hellotxt.com/image/@.s.jpg',
    'htxt.it': 'http://hellotxt.com/image/@.s.jpg',
    'moby.to': 'http://api.mobypicture.com?s=small&format=plain&k=6JQhCKX6Z9h2m9Lo&t=@',
    'movapic': 'http://image.movapic.com/pic/s_@.jpeg',
    'znl.me': 'http://app.zannel.com/content/@/Image-160x120-P-JPG.jpg',
    'bcphotoshare': 'http://images.bcphotoshare.com/storages/@/thumbnail.jpg',
    'twitvideo.jp': 'http://twitvideo.jp/img/thumb/@'
    }

  images = []
  for r, u in zip(thumbre, thumburi):
    for match in re.finditer(thumbre[r], text):
      if r == 'tweetphoto' or r == 'pic.gd' or r == 'moby.to':
        images.append({"src": thumburi[u].replace('@', match.group(0)) , "url": match.group(0)})
      else:
        images.append({"src": thumburi[u].replace('@', match.group(1)) , "url": match.group(0)})
  return images

def compact(data):
  if isinstance(data, dict):
    return dict([(x, y) for x,y in data.items() if y])
  elif isinstance(data, list):
    return [i for i in data if i]
  else: return data

first = lambda fn, lst: next((x for x in i if fn(x)))

def isRTL(s):
	""" is given text a RTL content? """
	if len(s)==0 :
		return False
	cc = ord(s[0]) # character code
	if cc>=1536 and cc<=1791 : # arabic, persian, ...
		return True
	if cc>=65136 and cc<=65279 : # arabic peresent 2
		return True
	if cc>=64336 and cc<=65023 : # arabic peresent 1
		return True
	if cc>=1424 and cc<=1535 : # hebrew
		return True
	if cc>=64256 and cc<=64335 : # hebrew peresent
		return True
	if cc>=1792 and cc<=1871 : # Syriac
		return True
	if cc>=1920 and cc<=1983 : # Thaana
		return True
	if cc>=1984 and cc<=2047 : # NKo
		return True
	if cc>=11568 and cc<=11647 : # Tifinagh
		return True
	return False

try:
  import pynotify
  import gtk, gtk.gdk, glib
  pynotify.init("Gwibber")

  def notify(title, text, icon = None, timeout = None, iconsize = 48):
    if icon is None:
      icon = resources.get_ui_asset("gwibber.svg")
    
    caps = pynotify.get_server_caps()
    
    notification = pynotify.Notification(title, text)

    try:
      pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(icon, iconsize, iconsize)
      notification.set_icon_from_pixbuf(pixbuf)
    except glib.GError as e:
      log.logger.error("Avatar failure - %s - %s", icon, e.message)
      resources.del_avatar(icon)

    if timeout:
      notification.set_timeout(timeout)

    if "x-canonical-append" in caps:
      notification.set_hint('x-canonical-append', 'allowed')

    try:
      notification.show ()
    except:
      log.logger.error("Notification failed")
    return

  can_notify = True
except:
  can_notify = False


def getbus(path, address="com.Gwibber"):
  if not path.startswith("/"):
    path = "/com/gwibber/%s" % path
    if len(path.split('gwibber/')[1]) > 1:
      address = "com.Gwibber.%s" % path.split('wibber/')[1]
  bus = dbus.SessionBus()
  obj = bus.get_object(address, path,
      follow_name_owner_changes = True)
  return dbus.Interface(obj, address)

def service_is_running(name):
  return name in dbus.Interface(dbus.SessionBus().get_object(
    "org.freedesktop.DBus", "/org/freedesktop/DBus"),
      "org.freedesktop.DBus").ListNames()

