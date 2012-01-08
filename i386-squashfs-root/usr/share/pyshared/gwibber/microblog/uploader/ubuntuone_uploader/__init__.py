"Ubuntu One uploader and publisher"

import dbus, gio, os
try:
    from ubuntuone.platform.tools import SyncDaemonTool, DBusClient, DBUS_IFACE_STATUS_NAME
except ImportError:
    SyncDaemonTool = None

class Uploader(object):
    def __init__(self, success_callback, failure_callback):
        self.success_callback = success_callback
        self.failure_callback = failure_callback
        self.path = None
        if SyncDaemonTool:
            self.sd = SyncDaemonTool(bus=dbus.SessionBus())

    def uploadFile(self, path):
        self.path = path
        if not SyncDaemonTool:
            failure_callback(path, "Could not find Ubuntu One library (python-ubuntuone-client)")
            return
        
        # First, confirm Ubuntu One is connected
        d = self.sd.get_status()
        d.addErrback(self.__failure)
        d.addCallback(self.__got_status)

    def __failure(self, *args):
        self.failure_callback(self.path, "Problem uploading to Ubuntu One: %s" % str(args))

    def __got_status(self, state):
        if state["is_online"]:
            self.__copy_file()
        else:
            # not online, so try to connect
            self.sig_status_changed = self.sd.bus.add_signal_receiver(
                handler_function=self.__status_changed, signal_name="StatusChanged",
                dbus_interface=DBUS_IFACE_STATUS_NAME, path='/status')
            d = self.sd.connect()
            d.addErrback(self.__failure)

    def __status_changed(self, status):
        if status["is_online"]:
            # We are connected; continue
            self.sig_status_changed.remove()
            self.__copy_file()
            return
        if status["is_error"]:
            # We are not connected, and not going to be without user fixes
            self.sig_status_changed.remove()
            self.__failure("Could not connect to Ubuntu One")
            return

    def __copy_file(self):
        # First, create a folder to put the copy of the specified file in
        fol = os.path.expanduser("~/Ubuntu One/Gwibber Uploads")
        try:
            os.makedirs(fol)
        except OSError:
            if not os.path.isdir(fol):
                self.__failure("Could not create Gwibber Uploads folder in Ubuntu One")
                return
            # OSError is OK if the folder already existed
        fdir, ffullname = os.path.split(self.path)
        fname, fext = os.path.splitext(ffullname)
        src = gio.File(self.path)
        dest = gio.File(os.path.join(fol, ffullname))
        
        # We connect to the UploadFinished signal from syncdaemon here,
        # before we even copy the file, so we know that it's right.
        self.sig_upload_finished = self.sd.bus.add_signal_receiver(
            handler_function=self.__file_uploaded, signal_name="UploadFinished",
            dbus_interface=DBUS_IFACE_STATUS_NAME, path='/status')
        
        try:
            src.copy(dest)
        except gio.Error:
            # file with this name exists. Try creating a file with a number in
            differentiator = 1
            while 1:
                try:
                    dest = gio.File(os.path.join(fol, "%s (%s)%s" % (fname, differentiator, fext)))
                    src.copy(dest)
                except gio.Error:
                    differentiator += 1
                else:
                    break
        self.u1path = dest.get_path() # the actual path in ~/Ubuntu One

    def __file_uploaded(self, path, info):
        if path == self.u1path:
            # stop listening to the signal
            self.sig_upload_finished.remove()
            # publish the file
            d = self.sd.change_public_access(path, True)
            d.addCallback(self.__published)
            d.addErrback(self.__failure)

    def __published(self, info):
        self.success_callback(self.path, info["public_url"])





