import dbus
from gwibber.microblog import util

class GwibberPublic:
    """
    GwibberPublic is the public python class which provides convience methods 
    for using Gwibber.
    """

    def __init__(self):
        self.bus = dbus.SessionBus()
        self.accounts = self.getbus("Accounts")
        self.service = self.getbus("Service")
        self.shortener = self.getbus("URLShorten")

    def getbus(self, name):
        obj = self.bus.get_object(
            "com.Gwibber.%s" % name,
            "/com/gwibber/%s" % name,
            follow_name_owner_changes=True)
        
        return dbus.Interface(obj, "com.Gwibber.%s" % name)
        
    def post(self, message):
        args = [message]
        self.microblog.operation({
          "args": args,
          "opname": "send",
          })

    def GetServices(self):
        """
        Returns a list of services available as json string
        example:
            import json, gwibber.lib
            gw = gwibber.lib.GwibberPublic()
            services = json.loads(gw.GetServices())
        """
        return self.service.GetServices()

    def GetAccounts(self):
        """
        Returns a list of services available as json string
        example:
            import json, gwibber.lib
            gw = gwibber.lib.GwibberPublic()
            accounts = json.loads(gw.GetAccounts())
        """
        return self.accounts.List()

    def SendMessage(self, message):
        """
        Posts a message/status update to all accounts with send_enabled = True.  It 
        takes one argument, which is a message formated as a string.
        example:
            import gwibber.lib
            gw = gwibber.lib.GwibberPublic()
            gw.SendMessage("This is a message")
        """
        return self.service.SendMessage(message)

    def Refresh(self):
        """
        Calls the Gwibber Service to trigger a refresh operation
        example:
            import gwibber.lib
            gw = gwibber.lib.GwibberPublic()
            gw.Refresh()
        """
        return self.service.Refresh()

    def Shorten(self, url):
        """
        Takes a long url in and returns a shortened url as a string, based on your 
        configured shortening service
        example:
            import gwibber.lib
            gw = gwibber.lib.GwibberPublic()
            gw.Shorten(url)
        """
        return self.shortener.Shorten(url)

    def MonitorAccountCreated(self, cb):
        self.accounts.connect_to_signal("AccountCreated", cb)

    def MonitorAccountChanged(self, cb):
        self.accounts.connect_to_signal("AccountChanged", cb)

    def MonitorAccountDeleted(self, cb):
        self.accounts.connect_to_signal("AccountDeleted", cb)


