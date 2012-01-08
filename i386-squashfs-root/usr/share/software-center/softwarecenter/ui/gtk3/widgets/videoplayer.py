# Copyright (C) 2011 Canonical
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

import logging
import sys

from gettext import gettext as _
from gi.repository import Gdk
from gi.repository import Gst
from gi.repository import Gtk
from gi.repository import WebKit

LOG = logging.getLogger(__name__)

class VideoPlayer(Gtk.VBox):
    def __init__(self):
        super(VideoPlayer, self).__init__()
        self.webkit = WebKit.WebView()
        self.pack_start(self.webkit, True, True, 0)
        self._uri = ""
    def _set_uri(self, v):
        self._uri = v
        self.webkit.load_uri(v)
    def _get_uri(self):
        return self._uri
    uri = property(_get_uri, _set_uri, None, "uri property")
    

# AKA the-segfault-edition-with-no-documentation
class VideoPlayerGtk3(Gtk.VBox):

    def __init__(self):
        super(VideoPlayerGtk3, self).__init__()
        self.uri = ""
        # gtk ui
        self.movie_window = Gtk.DrawingArea()
        self.pack_start(self.movie_window, True, True, 0)
        self.button = Gtk.Button(_("Play"))
        self.pack_start(self.button, False, True, 0)
        self.button.connect("clicked", self.on_play_clicked)
        # player
        self.player = Gst.ElementFactory.make("playbin2", "player")
        # bus stuff
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        # FIXME: no sync messages currently so no playing in the widget :/
        # the former appears to be not working anymore with GIR, the
        # later is not exported (introspectable=0 in the GIR)
        bus.connect("sync-message", self.on_sync_message)
        #bus.set_sync_handler(self.on_sync_message)

    def on_play_clicked(self, button):
        if self.button.get_label() == _("Play"):
            self.button.set_label("Stop")
            print(self.uri)
            self.player.set_property("uri", self.uri)
            self.player.set_state(Gst.State.PLAYING)
        else:
            self.player.set_state(Gst.State.NULL)
            self.button.set_label(_("Play"))
						
    def on_message(self, bus, message):
        print("message: %s" % bus, message)
        if message is None:
            return
        t = message.type
        print(t)
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
            self.button.set_label(_("Play"))
        elif t == Gst.MessageType.ERROR:
            self.player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            LOG.error("Error playing video: %s (%s)" % (err, debug))
            self.button.set_label(_("Play"))
            
    def on_sync_message(self, bus, message):
        print("sync: %s" % bus, message)
        if message is None or message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            Gdk.threads_enter()
            # FIXME: this is the way to do it, *but* get_xid() is not
            #        exported in the GIR
            xid = self.player.movie_window.get_window().get_xid()
            imagesink.set_xwindow_id(xid)
            Gdk.threads_leave()	


def get_test_videoplayer_window():
    win = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    win.set_default_size(500, 400)
    win.connect("destroy", Gtk.main_quit)
    player = VideoPlayer()
    win.add(player)
    if len(sys.argv) < 2:
        player.uri = "http://upload.wikimedia.org/wikipedia/commons/9/9b/Pentagon_News_Sample.ogg"
    else:
        player.uri = sys.argv[1]
    win.show_all()
    return win

if __name__ == "__main__":
    logging.basicConfig()
    Gdk.threads_init()
    Gst.init(sys.argv)

    win = get_test_videoplayer_window()
    Gtk.main()
