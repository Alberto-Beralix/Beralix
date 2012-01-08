# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gettext
from gi.repository import GObject
from gi.repository import Gio
import logging
import math
import os
import re
import tempfile
import traceback
import time
import xml.sax.saxutils

# py3 compat
try:
    from urllib.parse import urlsplit
    urlsplit # pyflakes
except ImportError:
    from urlparse import urlsplit

from enums import Icons, APP_INSTALL_PATH_DELIMITER
from paths import SOFTWARE_CENTER_CACHE_DIR

from config import get_config

from gettext import gettext as _

# define additional entities for the unescape method, needed
# because only '&amp;', '&lt;', and '&gt;' are included by default
ESCAPE_ENTITIES = {"&apos;":"'",
                   '&quot;':'"'}
                   
LOG = logging.getLogger(__name__)

class UnimplementedError(Exception):
    pass

class ExecutionTime(object):
    """
    Helper that can be used in with statements to have a simple
    measure of the timming of a particular block of code, e.g.
    with ExecutinTime("db flush"):
        db.flush()
    """
    def __init__(self, info=""):
        self.info = info
    def __enter__(self):
        self.now = time.time()
    def __exit__(self, type, value, stack):
        logger = logging.getLogger("softwarecenter.performance")
        logger.debug("%s: %s" % (self.info, time.time() - self.now))

def utf8(s):
    """
    Takes a string or unicode object and returns a utf-8 encoded
    string, errors are ignored
    """
    if s is None:
        return None
    if isinstance(s, unicode):
        return s.encode("utf-8", "ignore")
    return unicode(s, "utf8", "ignore").encode("utf8")


def log_traceback(info):
    """
    Helper that can be used as a debug helper to show what called
    the code at this place. Logs to softwarecenter.traceback
    """
    logger = logging.getLogger("softwarecenter.traceback")
    logger.debug("%s: %s" % (info, "".join(traceback.format_stack())))
    

def wait_for_apt_cache_ready(f):
    """ decorator that ensures that self.cache is ready using a
        gtk idle_add - needs a cache as argument
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        # check if the cache is ready and 
        window = None
        if hasattr(self, "app_view"):
            window =  self.app_view.get_window()
        if not self.cache.ready:
            if window:
                window.set_cursor(self.busy_cursor)
            GObject.timeout_add(500, lambda: wrapper(*args, **kwargs))
            return False
        # cache ready now
        if window:
            window.set_cursor(None)
        f(*args, **kwargs)
        return False
    return wrapper

def normalize_package_description(desc):
    """ this takes a package description and normalizes it
        so that all uneeded \n are stripped away and all
        enumerations are at the start of the line and start with a "*"
        E.g.:
        Some potentially very long paragrah that is in a single line.
        A new paragrpah.
        A list:
        * item1
        * item2 that may again be very very long
    """

    def get_indent(part, whitespace=" "):
        i = 0
        for i, char in enumerate(part):
            if char != whitespace:
                break
        return i

    BULLETS = ('- ', '* ', 'o ')
    norm_description = ""
    in_blist = False
    # process it
    for i, part in enumerate(desc.split("\n")):
        indent = get_indent(part)
        part = part.strip()

        # explicit newline
        if not part:
            norm_description += '\n'
            continue
        # check if in a enumeration
        if part[:2] in BULLETS:
            in_blist = True
            norm_description += "\n" + indent*' ' + "* " + part[2:]
        elif in_blist and indent > 0:
            norm_description += " " + part
        elif part.endswith('.') or part.endswith(':'):
            if in_blist:
                in_blist = False
                norm_description += '\n'
            norm_description += part + '\n'
        else:
            in_blist = False
            if not norm_description.endswith("\n"):
                norm_description += " "
            norm_description += part
    return norm_description.strip()

def get_title_from_html(html):
    """ takes a html string and returns the document title,
        if the document has no title it uses the first h1
        (but only if that has no further html tags)
        
        returns "" if it can't find anything or can't parse the html
    """
    import xml.etree.ElementTree
    try:
        root = xml.etree.ElementTree.fromstring(html)
    except Exception as e:
        logging.warn("failed to parse: '%s' (%s)" % (html, e))
        return ""
    title = root.findall(".//title")
    if title:
        text = title[0].text
        return text
    all_h1 = root.findall(".//h1")
    if all_h1:
        h1 = all_h1[0]
        # we don't support any sub html in the h1 when 
        if len(h1) == 0:
            return h1.text
    return ""

def htmlize_package_description(desc):
    html = ""
    inside_li = False
    for part in normalize_package_description(desc).split("\n"):
        stripped_part = part.strip()
        if not stripped_part: continue
        if stripped_part.startswith("* "):
            if not inside_li:
                html += "<ul>"
                inside_li = True
            html += '<li>%s</li>' % stripped_part[2:]
        else:
            if inside_li:
                html += "</ul>"
            html += '<p tabindex="0">%s</p>' % part
            inside_li = False
    if inside_li:
        html += "</ul>"
    return html

def get_parent_xid(widget):
    while widget.get_parent():
        widget = widget.get_parent()
    window = widget.get_window()
    #print dir(window)
    if hasattr(window, 'xid'):
        return window.xid
    return 0    # cannot figure out how to get the xid of gdkwindow under pygi

def get_language():
    """Helper that returns the current language
    """
    import locale
    # fallback if locale parsing fails
    FALLBACK = "en"
    # those languages need the full language-code, the other ones
    # can be abbreved
    FULL = ["pt_BR", 
            "zh_CN", "zh_TW"]
    try:
        language = locale.getdefaultlocale(('LANGUAGE','LANG','LC_CTYPE','LC_ALL'))[0]
    except Exception as e:
        LOG.warn("Failed to get language: '%s'" % e)
        language = "C"
    # use fallback if we can't determine the language
    if language is None or language == "C":
        return FALLBACK
    if language in FULL:
        return language
    return language.split("_")[0]

def get_http_proxy_string_from_libproxy(url):
    """Helper that uses libproxy to get the http proxy for the given url """
    import libproxy
    pf = libproxy.ProxyFactory()
    proxies = pf.getProxies(url)
    # FIXME: how to deal with multiple proxies?
    proxy = proxies[0]
    if proxy == "direct://":
        return ""
    else:
        return proxy

def get_http_proxy_string_from_gsettings():
    """Helper that gets the http proxy from gsettings

    Returns: string with http://auth:pw@proxy:port/ or None
    """
    try:
        # check if this is actually available and usable. if not
        # well ... it segfaults (thanks pygi)
        key = "org.gnome.system.proxy.http"
        if not key in Gio.Settings.list_schemas():
            return None
        settings = Gio.Settings.new(key)
        if settings.get_boolean("enabled"):
            authentication = ""
            if settings.get_boolean("use-authentication"):
                user = settings.get_string("authentication-user")
                password = settings.get_string("authentication-password")
                authentication = "%s:%s@" % (user, password)
            host = settings.get_string("host")
            port = settings.get_int("port")
            http_proxy = "http://%s%s:%s/" %  (authentication, host, port)
            if host:
                return http_proxy
    except Exception:
        logging.exception("failed to get proxy from gconf")

def encode_for_xml(unicode_data, encoding="ascii"):
    """ encode a given string for xml """
    return unicode_data.encode(encoding, 'xmlcharrefreplace')

def decode_xml_char_reference(s):
    """ takes a string like 
        'Search&#x2026;' 
        and converts it to
        'Search...'
    """
    p = re.compile("\&\#x(\d\d\d\d);")
    return p.sub(r"\u\1", s).decode("unicode-escape")
    
def unescape(text):
    """
    unescapes the given text
    """
    return xml.sax.saxutils.unescape(text, ESCAPE_ENTITIES)

def uri_to_filename(uri):
    try:
        import apt_pkg
        return apt_pkg.uri_to_filename(uri)
    except ImportError:
        return uri

def human_readable_name_from_ppa_uri(ppa_uri):
    """ takes a PPA uri and returns a human readable name for it """
    name = urlsplit(ppa_uri).path
    if name.endswith("/ubuntu"):
        return name[0:-len("/ubuntu")]
    return name

def sources_filename_from_ppa_entry(entry):
    """ 
    takes a PPA SourceEntry and returns a filename suitable for sources.list.d
    """
    import apt_pkg
    name = "%s.list" % apt_pkg.URItoFileName(entry.uri)
    return name
    
def obfuscate_private_ppa_details(text):
    """
    hides any private PPA details that may be found in the given text
    """
    result = text
    s = text.split()
    for item in s:
        if "private-ppa.launchpad.net" in item:
            url_parts = urlsplit(item)
            if url_parts.username:
                result = result.replace(url_parts.username, "hidden")
            if url_parts.password:
                result = result.replace(url_parts.password, "hidden")
    return result

def release_filename_in_lists_from_deb_line(debline):
    """
    takes a debline and returns the filename of the Release file
    in /var/lib/apt/lists
    """
    import aptsources.sourceslist
    entry = aptsources.sourceslist.SourceEntry(debline)
    name = "%s_dists_%s_Release" % (uri_to_filename(entry.uri), entry.dist)
    return name
    
def is_unity_running():
    """
    return True if Unity is currently running
    """
    import dbus
    unity_running = False
    try:
        bus = dbus.SessionBus()
        unity_running = bus.name_has_owner("com.canonical.Unity")
    except:
        LOG.exception("could not check for Unity dbus service")
    return unity_running
    
def get_icon_from_theme(icons, iconname=None, iconsize=Icons.APP_ICON_SIZE, missingicon=Icons.MISSING_APP):
    """
    return the icon in the theme that corresponds to the given iconname
    """    
    if not iconname:
        iconname = missingicon
    try:
        icon = icons.load_icon(iconname, iconsize, 0)
    except Exception as e:
        LOG.warning(utf8("could not load icon '%s', displaying missing icon instead: %s "
                        ) % (utf8(iconname), utf8(e.message)))
        icon = icons.load_icon(missingicon, iconsize, 0)
    return icon
    
def get_file_path_from_iconname(icons, iconname=None, iconsize=Icons.APP_ICON_SIZE):
    """
    return the file path of the icon in the theme that corresponds to the
    given iconname, or None if it cannot be determined
    """
    if (not iconname or
        not icons.has_icon(iconname)):
        iconname = Icons.MISSING_APP
    try:
        icon_info = icons.lookup_icon(iconname, iconsize, 0)
    except Exception:
        icon_info = icons.lookup_icon(Icons.MISSING_APP, iconsize, 0)
    if icon_info is not None:
        icon_file_path = icon_info.get_filename()
        icon_info.free()
        return icon_file_path
        
def convert_desktop_file_to_installed_location(app_install_data_file_path, pkgname):
    """ returns the installed desktop file path that corresponds to the
        given app-install-data file path, and will also check directly for
        the desktop file that corresponds to a given pkgname.
    """
    if app_install_data_file_path and pkgname:
        # "normal" case
        installed_desktop_file_path = app_install_data_file_path.replace("app-install/desktop/"
                                                                         + pkgname + ":",
                                                                         "applications/")
        if os.path.exists(installed_desktop_file_path):
            return installed_desktop_file_path  
        # next, try case where a subdirectory is encoded in the app-install
        # desktop filename, e.g. kde4_soundkonverter.desktop
        installed_desktop_file_path = installed_desktop_file_path.replace(APP_INSTALL_PATH_DELIMITER, "/")
        if os.path.exists(installed_desktop_file_path):
            return installed_desktop_file_path
    # lastly, just try checking directly for the desktop file based on the pkgname itself
    if pkgname:
        installed_desktop_file_path =  "/usr/share/applications/%s.desktop" % pkgname
        if os.path.exists(installed_desktop_file_path):
            return installed_desktop_file_path
    LOG.warn("Could not determine the installed desktop file path for app-install desktop file: '%s'" % app_install_data_file_path)
    return ""

def clear_token_from_ubuntu_sso(appname):
    """ send a dbus signal to the com.ubuntu.sso service to clear 
        the credentials for the given appname, e.g. _("Ubuntu Software Center")
    """
    import dbus
    bus = dbus.SessionBus()
    proxy = bus.get_object('com.ubuntu.sso', '/credentials')
    proxy.clear_token(appname)

def get_nice_date_string(cur_t):
    """ return a "nice" human readable date, like "2 minutes ago"  """
    import datetime

    dt = datetime.datetime.utcnow() - cur_t
    days = dt.days
    secs = dt.seconds

    if days < 1:

        if secs < 120:   # less than 2 minute ago
            s = _('a few minutes ago')   # dont be fussy

        elif secs < 3600:   # less than an hour ago
            s = gettext.ngettext("%(min)i minute ago",
                                 "%(min)i minutes ago",
                                 (secs/60)) % { 'min' : (secs/60) }

        else:   # less than a day ago
            s = gettext.ngettext("%(hours)i hour ago",
                                 "%(hours)i hours ago",
                                 (secs/3600)) % { 'hours' : (secs/3600) }

    elif days <= 5: # less than a week ago
        s = gettext.ngettext("%(days)i day ago",
                             "%(days)i days ago",
                             days) % { 'days' : days }

    else:   # any timedelta greater than 5 days old
        # YYYY-MM-DD
        s = cur_t.isoformat().split('T')[0]

    return s

def _get_from_desktop_file(desktop_file, key):
    import ConfigParser
    config = ConfigParser.ConfigParser()
    config.read(desktop_file)
    try:
        return config.get("Desktop Entry", key)
    except ConfigParser.NoOptionError:
        return None

def get_exec_line_from_desktop(desktop_file):
    return _get_from_desktop_file(desktop_file, "Exec")

def is_no_display_desktop_file(desktop_file):
    nd =  _get_from_desktop_file(desktop_file, "NoDisplay")
    # desktop spec says the booleans are always either "true" or "false
    if nd == "true":
        return True
    return False

def get_nice_size(n_bytes):
    nice_size = lambda s:[(s%1024**i and "%.1f"%(s/1024.0**i) or \
        str(s/1024**i))+x.strip() for i,x in enumerate(' KMGTPEZY') \
        if s<1024**(i+1) or i==8][0]
    return nice_size(n_bytes)
            
def save_person_to_config(username):
    """ save the specified username value for Ubuntu SSO to the config file
    """
    # FIXME: ideally this would be stored in ubuntu-sso-client
    #        but it doesn't so we store it here
    curr_name = get_person_from_config()
    if curr_name != username:
        config = get_config()
        if not config.has_section("reviews"):
            config.add_section("reviews")
        config.set("reviews", "username", username)
        config.write()
        # refresh usefulness cache in the background once we know
        # the person 
        from backend.reviews import UsefulnessCache
        UsefulnessCache(True)
    return
            
def get_person_from_config():
    """ get the username value for Ubuntu SSO from the config file
    """
    cfg = get_config()
    if cfg.has_option("reviews", "username"):
        return cfg.get("reviews", "username")
    return None

def pnormaldist(qn):
    '''Inverse normal distribution, based on the Ruby statistics2.pnormaldist'''
    b = [1.570796288, 0.03706987906, -0.8364353589e-3,
         -0.2250947176e-3, 0.6841218299e-5, 0.5824238515e-5,
         -0.104527497e-5, 0.8360937017e-7, -0.3231081277e-8,
         0.3657763036e-10, 0.6936233982e-12]
        
    if qn < 0 or qn > 1:
        raise ValueError("qn must be between 0.0 and 1.0")
    if qn == 0.5:
        return 0.0
    
    w1 = qn
    if qn > 0.5:
        w1 = 1.0 - w1
    w3 = -math.log(4.0 * w1 * (1.0 - w1))
    w1 = b[0]
    for i in range (1,11):
        w1 = w1 + (b[i] * math.pow(w3, i))
        
    if qn > 0.5:
        return math.sqrt(w1*w3)
    else:
        return -math.sqrt(w1*w3)

def wilson_score(pos, n, power=0.2):
    if n == 0:
        return 0
    z = pnormaldist(1-power/2)
    phat = 1.0 * pos / n
    return (phat + z*z/(2*n) - z * math.sqrt((phat*(1-phat)+z*z/(4*n))/n))/(1+z*z/n)

def calc_dr(ratings, power=0.1):
    '''Calculate the dampened rating for an app given its collective ratings'''
    if not len(ratings) == 5:
        raise AttributeError('ratings argument must be a list of 5 integers')
   
    tot_ratings = 0
    for i in range (0,5):
        tot_ratings = ratings[i] + tot_ratings
      
    sum_scores = 0.0
    for i in range (0,5):
        ws = wilson_score(ratings[i], tot_ratings, power)
        sum_scores = sum_scores + float((i+1)-3) * ws
   
    return sum_scores + 3


class SimpleFileDownloader(GObject.GObject):

    LOG = logging.getLogger("softwarecenter.simplefiledownloader")

    __gsignals__ = {
        "file-url-reachable"      : (GObject.SIGNAL_RUN_LAST,
                                     GObject.TYPE_NONE,
                                     (bool,),),

        "file-download-complete"  : (GObject.SIGNAL_RUN_LAST,
                                     GObject.TYPE_NONE,
                                     (str,),),

        "error"                   : (GObject.SIGNAL_RUN_LAST,
                                     GObject.TYPE_NONE,
                                     (GObject.TYPE_PYOBJECT,
                                      GObject.TYPE_PYOBJECT,),),
        }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.tmpdir = None
        self._cancellable = None

    def download_file(self, url, dest_file_path=None, use_cache=False,
                      simple_quoting_for_webkit=False):
        """ Download a url and emit the file-download-complete 
            once the file is there. Note that calling this twice
            will cancel the previous pending operation.
            If dest_file_path is given, download to that specific
            local filename.
            If use_cache is given it will not use a tempdir, but
            instead a permanent cache dir - no etag or timestamp
            checks are performed.
        """
        self.LOG.debug("download_file: %s %s %s" % (
                url, dest_file_path, use_cache))

        # cancel anything pending to avoid race conditions
        # like bug #839462
        if self._cancellable:
            self._cancellable.cancel()
        self._cancellable = Gio.Cancellable()

        # no need to cache file urls and no need to really download
        # them, its enough to adjust the dest_file_path
        if url.startswith("file:"):
            dest_file_path = url[len("file:"):]
            use_cache = False

        # if the cache is used, we use that as the dest_file_path
        if use_cache:
            cache_path = os.path.join(
                SOFTWARE_CENTER_CACHE_DIR, "download-cache")
            if not os.path.exists(cache_path):
                os.makedirs(cache_path)
            dest_file_path = os.path.join(cache_path, uri_to_filename(url))
            if simple_quoting_for_webkit:
                dest_file_path = dest_file_path.replace("%", "")
                dest_file_path = dest_file_path.replace("?", "")

        # no cache and no dest_file_path, use tempdir
        if dest_file_path is None:
            if self.tmpdir is None:
                self.tmpdir = tempfile.mkdtemp(prefix="software-center-")
            dest_file_path = os.path.join(self.tmpdir, uri_to_filename(url))

        self.url = url
        self.dest_file_path = dest_file_path

        # FIXME: we actually need to do etag based checking here to see
        #        if the source needs refreshing
        if os.path.exists(self.dest_file_path):
            self.emit('file-url-reachable', True)
            self.emit("file-download-complete", self.dest_file_path)
            return

        f = Gio.File.new_for_uri(url)
        # first check if the url is reachable
        f.query_info_async(Gio.FILE_ATTRIBUTE_STANDARD_SIZE, 0, 0, 
                           self._cancellable,
                           self._check_url_reachable_and_then_download_cb,
                           None)
                           
    def _check_url_reachable_and_then_download_cb(self, f, result, user_data=None):
        self.LOG.debug("_check_url_reachable_and_then_download_cb: %s" % f)
        try:
            info = f.query_info_finish(result)
            etag = info.get_etag()
            self.emit('file-url-reachable', True)
            self.LOG.debug("file reachable %s %s %s" % (self.url,
                                                        info, 
                                                        etag))
            # url is reachable, now download the file
            f.load_contents_async(
                self._cancellable, self._file_download_complete_cb, None)
        except GObject.GError as e:
            self.LOG.debug("file *not* reachable %s" % self.url)
            self.emit('file-url-reachable', False)
            self.emit('error', GObject.GError, e)
        del f

    def _file_download_complete_cb(self, f, result, path=None):
        self.LOG.debug("file download completed %s" % self.dest_file_path)
        # The result from the download is actually a tuple with three 
        # elements (content, size, etag?)
        # The first element is the actual content so let's grab that
        try:
            res, content, etag = f.load_contents_finish(result)
        except Exception as e:
            # i witnissed a strange error[1], so make the loader robust in this
            # situation
            # 1. content = f.load_contents_finish(result)[0]
            #    Gio.Error: DBus error org.freedesktop.DBus.Error.NoReply
            self.LOG.debug(e)
            self.emit('error', Exception, e)
            return
        # write out the data
        outputfile = open(self.dest_file_path, "w")
        outputfile.write(content)
        outputfile.close()
        self.emit('file-download-complete', self.dest_file_path)





# those helpers are packaging system specific
from softwarecenter.db.pkginfo import get_pkg_info
# do not call here get_pkg_info, since package switch may not have been set
# instead use an anonymous function delay
upstream_version_compare = lambda v1, v2: get_pkg_info().upstream_version_compare(v1, v2)
upstream_version = lambda v: get_pkg_info().upstream_version(v)
version_compare = lambda v1, v2: get_pkg_info().version_compare(v1, v2)

# only when needed
try:
    import apt_pkg
    size_to_str = apt_pkg.size_to_str
except ImportError:
    def size_to_str(size):
        return str(size)
        
if __name__ == "__main__":
    s = decode_xml_char_reference('Search&#x2026;')
    print(s)
    print(type(s))
    print(unicode(s))
