# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Atk, GObject, GdkPixbuf

import logging
import os

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import SimpleFileDownloader

from imagedialog import SimpleShowImageDialog

from gettext import gettext as _

LOG = logging.getLogger(__name__)


class ScreenshotThumbnail(Gtk.Alignment):

    """ Widget that displays screenshot availability, download prrogress,
        and eventually the screenshot itself.
    """

    MAX_SIZE = 300, 300
    IDLE_SIZE = 300, 150
    SPINNER_SIZE = 32, 32

    ZOOM_ICON = "stock_zoom-page"


    def __init__(self, distro, icons):
        Gtk.Alignment.__init__(self)
        self.set(0.5, 0.0, 1.0, 1.0)

        # data 
        self.distro = distro
        self.icons = icons

        self.pkgname = None
        self.appname = None
        self.thumb_url = None
        self.large_url = None

        # state tracking
        self.ready = False
        self.screenshot_pixbuf = None
        self.screenshot_available = False
        self.alpha = 0.0

        # zoom cursor
        try:
            zoom_pb = self.icons.load_icon(self.ZOOM_ICON, 22, 0)
            # FIXME
            self._zoom_cursor = Gdk.Cursor.new_from_pixbuf(
                                    Gdk.Display.get_default(),
                                    zoom_pb,
                                    0, 0)   # x, y
        except:
            self._zoom_cursor = None               

        # tip stuff
        self._hide_after = None
        self.tip_alpha = 0.0
        self._tip_fader = 0
        self._tip_layout = self.create_pango_layout("")
        #m = "<small><b>%s</b></small>"
        #~ self._tip_layout.set_markup(m % _("Click for fullsize screenshot"))
        #~ self._tip_layout.set_ellipsize(Pango.EllipsizeMode.END)

        self._tip_xpadding = 4
        self._tip_ypadding = 1

        # cache the tip dimensions
        w, h = self._tip_layout.get_pixel_size()
        self._tip_size = (w+2*self._tip_xpadding, h+2*self._tip_ypadding)

        # convienience class for handling the downloading (or not) of any screenshot
        self.loader = SimpleFileDownloader()
        self.loader.connect('error', self._on_screenshot_load_error)
        self.loader.connect('file-url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('file-download-complete', self._on_screenshot_download_complete)

        self._build_ui()
        return

    def _build_ui(self):
        self.set_redraw_on_allocate(False)
        # the frame around the screenshot (placeholder)
        self.set_border_width(3)

        # eventbox so we can connect to event signals
        event = Gtk.EventBox()
        event.set_visible_window(False)

        self.spinner_alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner_alignment.add(self.spinner)

        # the image
        self.image = Gtk.Image()
        self.image.set_redraw_on_allocate(False)
        event.add(self.image)
        self.eventbox = event

        # connect the image to our custom draw func for fading in
        self.image.connect('draw', self._on_image_draw)

        # unavailable layout
        l = Gtk.Label(label=_('No screenshot'))
        # force the label state to INSENSITIVE so we get the nice subtle etched in look
        l.set_state(Gtk.StateType.INSENSITIVE)
        # center children both horizontally and vertically
        self.unavailable = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        self.unavailable.add(l)

        # set the widget to be reactive to events
        self.set_property("can-focus", True)
        event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK|
                         Gdk.EventMask.BUTTON_RELEASE_MASK|
                         Gdk.EventMask.KEY_RELEASE_MASK|
                         Gdk.EventMask.KEY_PRESS_MASK|
                         Gdk.EventMask.ENTER_NOTIFY_MASK|
                         Gdk.EventMask.LEAVE_NOTIFY_MASK)

        # connect events to signal handlers
        event.connect('enter-notify-event', self._on_enter)
        event.connect('leave-notify-event', self._on_leave)
        event.connect('button-press-event', self._on_press)
        event.connect('button-release-event', self._on_release)

        self.connect('focus-in-event', self._on_focus_in)
#        self.connect('focus-out-event', self._on_focus_out)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)

    # signal handlers
    def _on_enter(self, widget, event):
        if not self.get_is_actionable(): return

        self.get_window().set_cursor(self._zoom_cursor)
        self.show_tip(hide_after=3000)
        return

    def _on_leave(self, widget, event):
        self.get_window().set_cursor(None)
        self.hide_tip()
        return

    def _on_press(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(Gtk.StateType.ACTIVE)
        return

    def _on_release(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(Gtk.StateType.NORMAL)
        self._show_image_dialog()
        return

    def _on_focus_in(self, widget, event):
        self.show_tip(hide_after=3000)
        return

#    def _on_focus_out(self, widget, event):
#        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (Gdk.KEY_space, 
                            Gdk.KEY_Return, 
                            Gdk.KEY_KP_Enter) and self.get_is_actionable():
            self.set_state(Gtk.StateType.ACTIVE)
        return

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (Gdk.KEY_space,
                            Gdk.KEY_Return, 
                            Gdk.KEY_KP_Enter) and self.get_is_actionable():
            self.set_state(Gtk.StateType.NORMAL)
            self._show_image_dialog()
        return

    def _on_image_draw(self, widget, cr):
        """ If the alpha value is less than 1, we override the normal draw
            for the GtkImage so we can draw with transparencey.
        """
#~ 
        #~ if widget.get_storage_type() != Gtk.ImageType.PIXBUF:
            #~ return
#~ 
        #~ pb = widget.get_pixbuf()
        #~ if not pb: return True
#~ 
        #~ a = widget.get_allocation()
        #~ cr.rectangle(a.x, a.y, a.width, a.height)
        #~ cr.clip()
#~ 
        #~ # draw the pixbuf with the current alpha value
        #~ cr.set_source_pixbuf(pb, a.x, a.y)
        #~ cr.paint_with_alpha(self.alpha)
        #~ 
        #~ if not self.tip_alpha: return True
#~ 
        #~ tw, th = self._tip_size
        #~ if a.width > tw:
            #~ self._tip_layout.set_width(-1)
        #~ else:
            #~ # tip is image width
            #~ tw = a.width
            #~ self._tip_layout.set_width(1024*(tw-2*self._tip_xpadding))
#~ 
        #~ tx, ty = a.x+a.width-tw, a.y+a.height-th
#~ 
        #~ rr = mkit.ShapeRoundedRectangleIrregular()
        #~ rr.layout(cr, tx, ty, tx+tw, ty+th, radii=(6, 0, 0, 0))
#~ 
        #~ cr.set_source_rgba(0,0,0,0.85*self.tip_alpha)
        #~ cr.fill()
#~ 
        #~ cr.move_to(tx+self._tip_xpadding, ty+self._tip_ypadding)
        #~ cr.layout_path(self._tip_layout)
        #~ cr.set_source_rgba(1,1,1,self.tip_alpha)
        #~ cr.fill()

        #~ return True
        return

    def _fade_in(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.alpha += 0.05
        if self.alpha >= 1.0:
            self.alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _tip_fade_in(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.tip_alpha += 0.1
        #ia = self.image.get_allocation()
        tw, th = self._tip_size

        if self.tip_alpha >= 1.0:
            self.tip_alpha = 1.0
            self.image.queue_draw()
#            self.image.queue_draw_area(ia.x+ia.width-tw,
#                                       ia.y+ia.height-th,
#                                       tw, th)
            return False

        self.image.queue_draw()
#        self.image.queue_draw_area(ia.x+ia.width-tw,
#                                   ia.y+ia.height-th,
#                                   tw, th)
        return True

    def _tip_fade_out(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.tip_alpha -= 0.1
        #ia = self.image.get_allocation()
        tw, th = self._tip_size

        if self.tip_alpha <= 0.0:
            self.tip_alpha = 0.0
#            self.image.queue_draw_area(ia.x+ia.width-tw,
#                                       ia.y+ia.height-th,
#                                       tw, th)
            self.image.queue_draw()
            return False

        self.image.queue_draw()
#        self.image.queue_draw_area(ia.x+ia.width-tw,
#                                   ia.y+ia.height-th,
#                                   tw, th)
        return True

    def _show_image_dialog(self):
        """ Displays the large screenshot in a seperate dialog window """

        if self.screenshot_pixbuf:
            title = _("%s - Screenshot") % self.appname
            toplevel = self.get_toplevel()
            d = SimpleShowImageDialog(title, self.screenshot_pixbuf, toplevel)
            d.run()
            d.destroy()
        return

    def _on_screenshot_load_error(self, loader, err_type, err_message):
        self.set_screenshot_available(False)
        self.ready = True
        return

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable: self.ready = True
        return

    def _downsize_pixbuf(self, pb, target_w, target_h):
        w = pb.get_width()
        h = pb.get_height()

        if w > h:
            sf = float(target_w) / w
        else:
            sf = float(target_h) / h

        sw = int(w*sf)
        sh = int(h*sf)

        return pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)

    def _on_screenshot_download_complete(self, loader, screenshot_path):

        def setter_cb(path):
            try:
                self.screenshot_pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            except Exception, e:
                LOG.exception("Pixbuf.new_from_file() failed")
                self.loader.emit('error', GObject.GError, e)
                return False

            # remove the spinner
            if self.spinner_alignment.get_parent():
                self.spinner.stop()
                self.spinner.hide()
                self.remove(self.spinner_alignment)

            pb = self._downsize_pixbuf(self.screenshot_pixbuf, *self.MAX_SIZE)

            if not self.eventbox.get_parent():
                self.add(self.eventbox)
                if self.get_property("visible"):
                    self.show_all()

            self.image.set_size_request(-1, -1)
            self.image.set_from_pixbuf(pb)

            # queue parent redraw if height of new pb is less than idle height
            if pb.get_height() < self.IDLE_SIZE[1]:
                if self.get_parent():
                    self.get_parent().queue_draw()

            # start the fade in
            GObject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        GObject.timeout_add(500, setter_cb, screenshot_path)
        return

    def show_tip(self, hide_after=0):
        if (not self.image.get_property('visible') or
            self.tip_alpha >= 1.0): 
            return

        if self._tip_fader: GObject.source_remove(self._tip_fader)
        self._tip_fader = GObject.timeout_add(25, self._tip_fade_in)

        if hide_after:
            if self._hide_after: 
                GObject.source_remove(self._hide_after)
            self._hide_after = GObject.timeout_add(hide_after, self.hide_tip)
        return

    def hide_tip(self):
        if (not self.image.get_property('visible') or
            self.tip_alpha <= 0.0):
            return

        if self._tip_fader: 
            GObject.source_remove(self._tip_fader)
        self._tip_fader = GObject.timeout_add(25, self._tip_fade_out)
        return

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and
            the download has completed 
        """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):
        """ Configures the ScreenshotView depending on whether there
            is a screenshot available.
        """
        if not available:
            if not self.eventbox.get_parent():
                self.remove(self.spinner_alignment)
                self.spinner.stop()
                self.add(self.eventbox)

            if self.image.get_parent():
                self.image.hide()
                self.eventbox.remove(self.image)
                self.eventbox.add(self.unavailable)
                # set the size of the unavailable placeholder
                # 160 pixels is the fixed width of the thumbnails
                self.unavailable.set_size_request(*self.IDLE_SIZE)
            acc = self.get_accessible()
            acc.set_name(_('No screenshot available'))
            acc.set_role(Atk.Role.LABEL)
        else:
            if self.unavailable.get_parent():
                self.unavailable.hide()
                self.eventbox.remove(self.unavailable)
                self.eventbox.add(self.image)
            acc = self.get_accessible()
            acc.set_name(_('Screenshot'))
            acc.set_role(Atk.Role.PUSH_BUTTON)

        if self.get_property("visible"):
            self.show_all()
        self.screenshot_available = available
        return
 
    def configure(self, app_details):

        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """

        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))

        self.clear()
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname
#        self.thumbnail_url = app_details.thumbnail
        self.thumbnail_url = app_details.screenshot
        self.large_url = app_details.screenshot
        return

    def clear(self):

        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """

        self.screenshot_available = True
        self.ready = False
        self.alpha = 0.0

        if self.eventbox.get_parent():
            self.eventbox.hide()
            self.remove(self.eventbox)

        if not self.spinner_alignment.get_parent():
            self.add(self.spinner_alignment)

        self.spinner_alignment.set_size_request(*self.IDLE_SIZE)

        self.spinner.start()

        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its 
            reachable, if so it downloads the thumbnail.
            If not, it emits "file-url-reachable" False, then exits.
        """

        self.loader.download_file(self.thumbnail_url)
        # show it
        if self.get_property('visible'):
            self.show_all()

        return

    def draw(self, widget, cr):
        """ Draws the thumbnail frame """
        #~ if not self.get_property("visible"): return
#~ 
        #~ if self.eventbox.get_property('visible'):
            #~ ia = self.eventbox.get_allocation()
        #~ else:
            #~ ia = self.spinner_alignment.get_allocation()
#~ 
        #~ a = widget.get_allocation()
#~ 
        #~ x = a.x
        #~ y = a.y
#~ 
        #~ if self.has_focus() or self.get_state() == Gtk.StateType.ACTIVE:
            #~ cr.rectangle(x-2, y-2, ia.width+4, ia.height+4)
            #~ cr.set_source_rgb(1,1,1)
            #~ cr.fill_preserve()
            #~ if self.get_state() == Gtk.StateType.ACTIVE:
                #~ color = mkit.floats_from_gdkcolor(self.style.mid[self.get_state()])
            #~ else:
                #~ color = mkit.floats_from_gdkcolor(self.style.dark[Gtk.StateType.SELECTED])
            #~ cr.set_source_rgb(*color)
            #~ cr.stroke()
        #~ else:
        #~ cr.rectangle(x-3, y-3, ia.width+6, ia.height+6)
        #~ cr.set_source_rgb(1,1,1)
        #~ cr.fill()
        #~ cr.save()
        #~ cr.translate(0.5, 0.5)
        #~ cr.set_line_width(1)
        #~ cr.rectangle(x-3, y-3, ia.width+5, ia.height+5)
#~ 
        #~ # FIXME: color
        #~ dark = color_floats("#000")
        #~ cr.set_source_rgb(*dark)
        #~ cr.stroke()
        #~ cr.restore()
#~ 
        #~ if not self.screenshot_available:
            #~ cr.rectangle(x, y, ia.width, ia.height)
            #~ cr.set_source_rgb(1,0,0)
            #~ cr.fill()
        return

def get_test_screenshot_thumbnail_window():

    icons = Gtk.IconTheme.get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    win = Gtk.Window()
    win.set_border_width(10)

    t = ScreenshotThumbnail(distro, icons)
    t.connect('draw', t.draw)
    win.set_data("screenshot_thumbnail_widget", t)

    vb = Gtk.VBox(spacing=6)
    win.add(vb)

    vb.pack_start(Gtk.Button('A button for focus testing'), True, True, 0)
    vb.pack_start(t, True, True, 0)

    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    from mock import Mock
    app_details = Mock()
    app_details.display_name = "display name"
    app_details.pkgname = "pkgname"
    url = "http://www.ubuntu.com/sites/default/themes/ubuntu10/images/footer_logo.png"
    app_details.thumbnail = url
    app_details.screenshot = url

    t.configure(app_details)
    t.download_and_display()

    return win

if __name__ == '__main__':

    def testing_cycle_apps(thumb, apps, db):

        if not thumb.pkgname or thumb.pkgname == "uace":
            d = apps[0].get_details(db)
        else:
            d = apps[1].get_details(db)

        thumb.configure(d)
        thumb.download_and_display()
        return True

    logging.basicConfig(level=logging.DEBUG)

    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()
   
    w = get_test_screenshot_thumbnail_window()
    t = w.get_data("screenshot_thumbnail_widget")

    from softwarecenter.db.application import Application
    apps = [Application("Movie Player", "totem"),
            Application("ACE", "uace")]

    GObject.timeout_add_seconds(6, testing_cycle_apps, t, apps, db)

    Gtk.main()
