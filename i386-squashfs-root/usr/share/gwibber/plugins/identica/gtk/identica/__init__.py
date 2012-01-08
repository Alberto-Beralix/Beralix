import gtk, webkit, gnomekeyring
import urllib, urllib2, json, urlparse, uuid
from oauth import oauth

from gtk import Builder
import gwibber.microblog
from gwibber.microblog.util import resources
import gettext
from gettext import gettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

gtk.gdk.threads_init()

sigmeth = oauth.OAuthSignatureMethod_HMAC_SHA1()


class AccountWidget(gtk.VBox):
  """AccountWidget: A widget that provides a user interface for configuring identi.ca accounts in Gwibber
  """
  
  def __init__(self, account=None, dialog=None):
    """Creates the account pane for configuring identi.ca accounts"""
    gtk.VBox.__init__( self, False, 20 )
    self.ui = gtk.Builder()
    self.ui.set_translation_domain ("gwibber")
    self.ui.add_from_file (resources.get_ui_asset("gwibber-accounts-identica.ui"))
    self.ui.connect_signals(self)
    self.vbox_settings = self.ui.get_object("vbox_settings")
    self.pack_start(self.vbox_settings, False, False)
    self.show_all()

    self.account = account or {}
    self.dialog = dialog
    self.url_prefix = "https://identi.ca"
    has_secret_key = True
    if self.account.has_key("id"):
      try:
        value = gnomekeyring.find_items_sync(gnomekeyring.ITEM_GENERIC_SECRET, {"id": str("%s/%s" % (self.account["id"], "secret_token"))})[0].secret
      except gnomekeyring.NoMatchError:
        has_secret_key = False

    try:
      if self.account.has_key("access_token") and self.account.has_key("secret_token") and self.account.has_key("username") and has_secret_key:
        self.ui.get_object("hbox_statusnet_auth").hide()
        self.ui.get_object("statusnet_auth_done_label").set_label(_("%s has been authorized by %s") % (self.account["username"]))
        self.ui.get_object("hbox_statusnet_auth_done").show()
      else:
        self.ui.get_object("hbox_statusnet_auth_done").hide()
        if self.dialog.ui:
          self.dialog.ui.get_object('vbox_create').hide()
    except:
      self.ui.get_object("hbox_statusnet_auth_done").hide()
      if self.dialog.ui:
        self.dialog.ui.get_object("vbox_create").hide()

  def on_statusnet_auth_clicked(self, widget, data=None):
    self.winsize = self.window.get_size()

    web = webkit.WebView()
    web.get_settings().set_property("enable-plugins", False)
    web.load_html_string(_("<p>Please wait...</p>"), "file:///")

    self.consumer = oauth.OAuthConsumer("anonymous", "anonymous")

    request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_method="POST",
        callback="http://gwibber.com/0/auth.html",
        parameters={"source": "Gwibber"},
        http_url=self.url_prefix +  "/api/oauth/request_token")
    request.sign_request(sigmeth, self.consumer, token=None)

    tokendata = urllib2.urlopen(request.http_url, request.to_postdata()).read()
    self.token = oauth.OAuthToken.from_string(tokendata)

    url = self.url_prefix + "/api/oauth/authorize?mode=desktop&oauth_token=" + self.token.key

    web.load_uri(url)
    #web.set_size_request(500, 420)
    web.set_size_request(550, 400)

    web.connect("title-changed", self.on_statusnet_auth_title_change)

    scroll = gtk.ScrolledWindow()
    scroll.add(web)

    self.pack_start(scroll, True, True, 0)
    self.show_all()

    self.ui.get_object("vbox1").hide()
    self.ui.get_object("vbox_advanced").hide()

  def on_statusnet_auth_title_change(self, web=None, title=None, data=None):
    saved = False
    if title.get_title() == "Success":
      try:
        url = web.get_main_frame().get_uri()
        data = urlparse.parse_qs(url.split("?", 1)[1])

        rtok = oauth.OAuthToken(self.token.key, self.token.secret)

        request = oauth.OAuthRequest.from_consumer_and_token(oauth_consumer=self.consumer, 
          token=rtok,  
          http_method="POST",
          callback="http://gwibber.com/0/auth.html",
          parameters={"oauth_verifier": str(data["oauth_verifier"][0]), "source": "Gwibber"},
          http_url=self.url_prefix + "/api/oauth/access_token")

        request.sign_request(sigmeth, self.consumer, rtok)

        tokendata = urllib2.urlopen(request.http_url, request.to_postdata()).read()

        atok = oauth.OAuthToken.from_string(tokendata)

        """
        # TESTING
        print "Access token"
        print "     oauth_token       : " + atok.key
        print "     oauth_token_secret: " + atok.secret + "\n"

        # GET protected resource

        print "verifying your credentials..."
        """

        apireq = oauth.OAuthRequest.from_consumer_and_token(oauth_consumer=self.consumer, token=atok,
            verifier=None,
            http_method="GET",
            http_url=self.url_prefix + "/api/account/verify_credentials.json", parameters=None)

        apireq.sign_request(sigmeth, self.consumer, atok)

        account_data = json.loads(urllib2.urlopen(apireq.to_url()).read())
        """
        print "### account_data ###"
        print account_data

        # TESTING

        """
        sitereq = oauth.OAuthRequest.from_consumer_and_token(oauth_consumer=self.consumer, token=atok,
            verifier=None,
            http_method="GET",
            http_url=self.url_prefix + "/api/statusnet/config.json", parameters=None)
        sitereq.sign_request(sigmeth, self.consumer, atok)
        site_data = json.loads(urllib2.urlopen(sitereq.to_url()).read())
        """
        print "### site_data ###"
        print site_data

        version_req = oauth.OAuthRequest.from_consumer_and_token(oauth_consumer=self.consumer, token=atok,
            verifier=None,
            http_method="GET",
            http_url=self.url_prefix + "/api/statusnet/version.json", parameters=None)
        version_req.sign_request(sigmeth, self.consumer, atok)
        version_data = json.loads(urllib2.urlopen(version_req.to_url()).read())
        print "### version_data ###"
        print version_data

        """
        """ SAVING CODE
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

        """
 
        if isinstance(account_data, dict) and isinstance(site_data, dict):
          if account_data.has_key("screen_name") and site_data.has_key("site"):
            self.account["access_token"] = atok.key
            self.account["secret_token"] = atok.secret
            self.account["username"] = account_data["screen_name"]
            saved = self.dialog.on_edit_account_save()
          else:
            print "Failed"
        else:
          print "Failed"

        self.ui.get_object("hbox_statusnet_auth").hide()
        self.ui.get_object("statusnet_auth_done_label").set_label(_("%s has been authorized by Identi.ca") % (str(self.account["username"])))
        self.ui.get_object("hbox_statusnet_auth_done").show()
        if self.dialog.ui and self.account.has_key("id") and not saved:
          self.dialog.ui.get_object("vbox_save").show()
        elif self.dialog.ui and not saved:
          self.dialog.ui.get_object("vbox_create").show()
      except:
        pass

      web.hide()
      self.window.resize(*self.winsize)
      self.ui.get_object("vbox1").show()
      self.ui.get_object("vbox_advanced").show()

    if title.get_title() == "Failure":
      d = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
        gtk.BUTTONS_OK, _("Authorization failed. Please try again."))
      if d.run(): d.destroy()

      web.hide()
      self.window.resize(*self.winsize)
