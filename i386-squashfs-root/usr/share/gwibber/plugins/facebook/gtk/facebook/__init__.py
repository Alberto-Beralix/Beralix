#
# Copyright (C) 2010 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2010 Ken VanDine <ken.vandine@canonical.com>
#
# facebook widgets for Gwibber
#

import gtk
import urllib
import webkit
import string

from gtk import Builder
from gwibber.microblog.util import facelib
from gwibber.microblog.util import resources
from gwibber.microblog.util.const import *
# Try to import * from custom, install custom.py to include packaging 
# customizations like distro API keys, etc
try:
  from gwibber.microblog.util.custom import *
except:
  pass

import json, urlparse, gnomekeyring, uuid
import gettext
from gettext import gettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

"""
gtk.gdk.threads_init()

APP_KEY = "71b85c6d8cb5bbb9f1a3f8bbdcdd4b05"
"""

class AccountWidget(gtk.VBox):
  """AccountWidget: A widget that provides a user interface for configuring facebook accounts in Gwibber
  """
  
  def __init__(self, account=None, dialog=None):
    """Creates the account pane for configuring facebook accounts"""
    gtk.VBox.__init__( self, False, 20 )
    self.ui = gtk.Builder()
    self.ui.set_translation_domain ("gwibber")
    self.ui.add_from_file (resources.get_ui_asset("gwibber-accounts-facebook.ui"))
    self.ui.connect_signals(self)
    self.vbox_settings = self.ui.get_object("vbox_settings")
    self.pack_start(self.vbox_settings, False, False)
    self.show_all()
    if account:
      self.account = account
    else:
      self.account = {}
    self.dialog = dialog
    has_access_token = True
    if self.account.has_key("id"):
      try:
        value = gnomekeyring.find_items_sync(gnomekeyring.ITEM_GENERIC_SECRET, {"id": str("%s/%s" % (self.account["id"], "access_token"))})[0].secret
      except gnomekeyring.NoMatchError:
        has_access_token = False
    try:
      if self.account["access_token"] and self.account["username"] and has_access_token and not self.dialog.condition:
        self.ui.get_object("hbox_facebook_auth").hide()
        self.ui.get_object("fb_auth_done_label").set_label(_("%s has been authorized by Facebook") % str(self.account["username"]))
        self.ui.get_object("hbox_facebook_auth_done").show()
      else:
        self.ui.get_object("hbox_facebook_auth_done").hide()
        if self.dialog.ui:
          self.dialog.ui.get_object('vbox_create').hide()
    except:
      self.ui.get_object("hbox_facebook_auth_done").hide()
      if self.dialog.ui:
        self.dialog.ui.get_object("vbox_create").hide()

  def on_facebook_auth_clicked(self, widget, data=None):
    (self.win_w, self.win_h) = self.window.get_size()

    web = webkit.WebView()
    web.get_settings().set_property("enable-plugins", False)
    web.load_html_string(_("<p>Please wait...</p>"), "file:///")

    url = urllib.urlencode({
      "client_id": FB_APP_KEY,
      "display": "popup",
      "type": "user_agent",
      "scope": "publish_stream,read_stream,status_update,offline_access,user_photos,friends_photos",
      "redirect_uri": "http://www.facebook.com/connect/login_success.html",
    })
    web.set_size_request(450, 340)
    web.load_uri("https://graph.facebook.com/oauth/authorize?" + url)
    web.connect("title-changed", self.on_facebook_auth_title_change)

    scroll = gtk.ScrolledWindow()
    scroll.add(web)

    self.pack_start(scroll, True, True, 0)
    self.show_all()
    self.ui.get_object("vbox1").hide()
    self.ui.get_object("vbox_advanced").hide()

  def on_facebook_auth_title_change(self, web=None, title=None, data=None):
    saved = False
    url = web.get_main_frame().get_uri()
    if title.get_title() == "Success":
      url = web.get_main_frame().get_uri()
      self.account["access_token"] = str(urlparse.parse_qs(url.split("#", 1)[1])["access_token"][0])
      data = json.loads(urllib.urlopen("https://graph.facebook.com/me?access_token=" + self.account["access_token"]).read())
      if isinstance(data, dict):
        if data.has_key("id") and data.has_key("name"):
          self.account["username"] = data["name"]
          self.account["uid"] = data["id"]
          saved = self.dialog.on_edit_account_save() 
      else:
        # Make a desparate attempt to guess the id from the url
        uid = url.split('-')[1].split('%7C')[0]
        if isinstance(uid, int) and len(uid) > 2:
          acct = json.loads(urllib.urlopen("https://graph.facebook.com/" + str(uid)).read())
          if isinstance(acct, dict):
            if acct.has_key("id") and acct.has_key("name"):
              self.account["uid"] = acct["id"]
              self.account["username"] = acct["name"]
              saved = self.dialog.on_edit_account_save()
          else:
            print "Failed"

     
        

      self.ui.get_object("hbox_facebook_auth").hide()
      self.ui.get_object("fb_auth_done_label").set_label(_("%s has been authorized by Facebook") % str(self.account["username"]))
      self.ui.get_object("hbox_facebook_auth_done").show()
      if self.dialog.ui and self.account.has_key("id") and not saved:
        self.dialog.ui.get_object("vbox_save").show()
      elif self.dialog.ui and not saved:
        self.dialog.ui.get_object("vbox_create").show()

      web.hide()
      self.window.resize(self.win_w, self.win_h)
      self.ui.get_object("vbox1").show()
      self.ui.get_object("vbox_advanced").show()

    if title.get_title() == "Failure":
      gtk.gdk.threads_enter()
      d = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_OK, _("Facebook authorization failed. Please try again."))
      if d.run(): d.destroy()
      gtk.gdk.threads_leave()

      web.hide()
      self.window.resize(self.win_w, self.win_h)
