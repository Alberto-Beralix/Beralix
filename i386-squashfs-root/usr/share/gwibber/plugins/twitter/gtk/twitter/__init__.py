import gtk, pango, webkit, gnomekeyring
import urllib, urllib2, json, urlparse, uuid
from oauth import oauth

from gtk import Builder
from gwibber.microblog.util import resources
import gettext
from gettext import gettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

gtk.gdk.threads_init()

sigmeth = oauth.OAuthSignatureMethod_HMAC_SHA1()

class AccountWidget(gtk.VBox):
  """AccountWidget: A widget that provides a user interface for configuring twitter accounts in Gwibber
  """
  
  def __init__(self, account=None, dialog=None):
    """Creates the account pane for configuring Twitter accounts"""
    gtk.VBox.__init__( self, False, 20 )
    self.ui = gtk.Builder()
    self.ui.set_translation_domain ("gwibber")
    self.ui.add_from_file (resources.get_ui_asset("gwibber-accounts-twitter.ui"))
    self.ui.connect_signals(self)
    self.vbox_settings = self.ui.get_object("vbox_settings")
    self.pack_start(self.vbox_settings, False, False)
    self.show_all()

    self.account = account or {}
    self.dialog = dialog
    has_secret_key = True
    if self.account.has_key("id"):
      try:
        value = gnomekeyring.find_items_sync(gnomekeyring.ITEM_GENERIC_SECRET, {"id": str("%s/%s" % (self.account["id"], "secret_token"))})[0].secret
      except gnomekeyring.NoMatchError:
        has_secret_key = False

    try:
      if self.account.has_key("access_token") and self.account.has_key("secret_token") and self.account.has_key("username") and has_secret_key and not self.dialog.condition:
        self.ui.get_object("hbox_twitter_auth").hide()
        self.ui.get_object("twitter_auth_done_label").set_label(_("%s has been authorized by Twitter") % self.account["username"])
        self.ui.get_object("hbox_twitter_auth_done").show()
      else:
        self.ui.get_object("hbox_twitter_auth_done").hide()
        if self.dialog.ui:
          self.dialog.ui.get_object('vbox_create').hide()
    except:
      self.ui.get_object("hbox_twitter_auth_done").hide()
      if self.dialog.ui:
        self.dialog.ui.get_object("vbox_create").hide()


  def on_twitter_auth_clicked(self, widget, data=None):
    self.winsize = self.window.get_size()

    web = webkit.WebView()
    web.get_settings().set_property("enable-plugins", False)
    web.load_html_string(_("<p>Please wait...</p>"), "file:///")

    self.consumer = oauth.OAuthConsumer(*resources.get_twitter_keys())

    request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_method="POST",
        callback="http://gwibber.com/0/auth.html",
        http_url="https://api.twitter.com/oauth/request_token")

    request.sign_request(sigmeth, self.consumer, token=None)

    tokendata = urllib2.urlopen(request.http_url, request.to_postdata()).read()
    self.token = oauth.OAuthToken.from_string(tokendata)

    url = "http://api.twitter.com/oauth/authorize?oauth_token=" + self.token.key

    web.load_uri(url)
    web.set_size_request(550, 450)
    web.connect("title-changed", self.on_twitter_auth_title_change)

    self.scroll = gtk.ScrolledWindow()
    self.scroll.add(web)

    self.pack_start(self.scroll, True, True, 0)
    self.show_all()

    self.ui.get_object("vbox1").hide()
    self.ui.get_object("vbox_advanced").hide()
    self.dialog.infobar.set_message_type(gtk.MESSAGE_INFO)

  def on_twitter_auth_title_change(self, web=None, title=None, data=None):
    saved = False
    if title.get_title() == "Success":

      if hasattr(self.dialog, "infobar_content_area"):
        for child in self.dialog.infobar_content_area.get_children(): child.destroy()
      self.dialog.infobar_content_area = self.dialog.infobar.get_content_area()
      self.dialog.infobar_content_area.show()
      self.dialog.infobar.show()

      message_label = gtk.Label(_("Verifying"))
      message_label.set_use_markup(True)
      message_label.set_ellipsize(pango.ELLIPSIZE_END)
      self.dialog.infobar_content_area.add(message_label)
      self.dialog.infobar.show_all()
      self.scroll.hide()
      url = web.get_main_frame().get_uri()
      data = urlparse.parse_qs(url.split("?", 1)[1])

      self.ui.get_object("vbox1").show()
      self.ui.get_object("vbox_advanced").show()

      token = data["oauth_token"][0]
      verifier = data["oauth_verifier"][0]

      request = oauth.OAuthRequest.from_consumer_and_token(
        self.consumer, self.token,
        http_url="https://api.twitter.com/oauth/access_token",
        parameters={"oauth_verifier": str(verifier)})
      request.sign_request(sigmeth, self.consumer, self.token)

      tokendata = urllib2.urlopen(request.http_url, request.to_postdata()).read()
      data = urlparse.parse_qs(tokendata)

      atok = oauth.OAuthToken.from_string(tokendata)

      self.account["access_token"] = data["oauth_token"][0]
      self.account["secret_token"] = data["oauth_token_secret"][0]
      self.account["username"] = data["screen_name"][0]
      self.account["user_id"] = data["user_id"][0]

      apireq = oauth.OAuthRequest.from_consumer_and_token(
        self.consumer, atok,
        http_method="GET",
        http_url="http://api.twitter.com/1/account/verify_credentials.json", parameters=None)

      apireq.sign_request(sigmeth, self.consumer, atok)

      account_data = json.loads(urllib2.urlopen(apireq.to_url()).read())

      if isinstance(account_data, dict):
        if account_data.has_key("id"):
          saved = self.dialog.on_edit_account_save()
        else:
          print "Failed"
          self.dialog.infobar.set_message_type(gtk.MESSAGE_ERROR)
          message_label.set_text(_("Authorization failed. Please try again.")) 
      else:
        print "Failed"
        self.dialog.infobar.set_message_type(gtk.MESSAGE_ERROR)
        message_label.set_text(_("Authorization failed. Please try again."))

      if saved: 
        message_label.set_text(_("Successful"))
        self.dialog.infobar.set_message_type(gtk.MESSAGE_INFO)
        #self.dialog.infobar.hide()

      self.ui.get_object("hbox_twitter_auth").hide()
      self.ui.get_object("twitter_auth_done_label").set_label(_("%s has been authorized by Twitter") % str(self.account["username"]))
      self.ui.get_object("hbox_twitter_auth_done").show()
      if self.dialog.ui and self.account.has_key("id") and not saved:
        self.dialog.ui.get_object("vbox_save").show()
      elif self.dialog.ui and not saved:
        self.dialog.ui.get_object("vbox_create").show()

    self.window.resize(*self.winsize)

    if title.get_title() == "Failure":
      web.hide()
      self.dialog.infobar.set_message_type(gtk.MESSAGE_ERROR)
      message_label.set_text(_("Authorization failed. Please try again."))
      self.dialog.infobar.show_all()

      self.ui.get_object("vbox1").show()
      self.ui.get_object("vbox_advanced").show()
      self.window.resize(*self.winsize)
