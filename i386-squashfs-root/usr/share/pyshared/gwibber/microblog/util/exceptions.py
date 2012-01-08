import log
import os, subprocess
import xdg, time

import gettext
from gettext import lgettext as _
if hasattr(gettext, 'bind_textdomain_codeset'):
    gettext.bind_textdomain_codeset('gwibber','UTF-8')
gettext.textdomain('gwibber')

class GwibberError(Exception):
    """Base class for exceptions in gwibber."""
    pass

class GwibberServiceError(GwibberError):
    """Exception raised for errors from services.

    Attributes:
        service
        username
        message
        kind
    """
    def __init__(self, kind="UNKNOWN", service="UNKNOWN", username="UNKNOWN", message="UNKNOWN"):
        if kind == "keyring" or kind == "auth":
            log.logger.error("Failed to find credentials in the keyring")
            accounts_error = os.path.join(xdg.BaseDirectory.xdg_cache_home, "gwibber", ".accounts_error")
            if os.path.exists(accounts_error) and os.path.getmtime(accounts_error) > time.time()-600:
                log.logger.info("gwibber-accounts was raised less than 600 seconds")
                return
            else:
                open(accounts_error, 'w').close() 
        else:
            log.logger.error("%s failure: %s:%s - %s", kind, service, username, message)

        display_message = _("There was an %(kind)s failure from %(service)s for account %(account)s, error was %(error)s") % {
          "kind": kind, 
          "service": service, 
          "account": username,
          "error": message
        }
        title = _("Gwibber")
        level = "info"
        if kind == "auth":
            display_message = _("Authentication error from %(service)s for account %(account)s") % {
            "service": service,
            "account": username
            }
            title = _("Gwibber Authentication Error")
            level = "error"
        if kind == "network":
            display_message = _("There was a network error communicating with %(message)s") % { "message": message}
            title = _("Gwibber Network Error")
            level = "error"

        if os.path.exists(os.path.join("bin", "gwibber-error")):
            cmd = os.path.join("bin", "gwibber-error")
        else:
            cmd = "gwibber-error"
        ret = subprocess.Popen([cmd, '-m', display_message, '-t', title, '-c', level, '-s', service, '-u', username, '-e', kind], shell=False)
