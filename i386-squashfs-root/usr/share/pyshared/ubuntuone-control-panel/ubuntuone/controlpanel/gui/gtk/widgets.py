# -*- coding: utf-8 -*-

# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
# Authors: Evan Dandrea <evan.dandrea@canonical.com>
#
# Copyright 2009-2010 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A set of useful widgets."""

import gtk
import gobject
import pango

DEFAULT_PADDING = (10, 10)


class Loading(gtk.HBox):
    """A spinner and a label."""

    def __init__(self, label, fg_color=None, *args, **kwargs):
        super(Loading, self).__init__(*args, **kwargs)
        self.label = gtk.Label(label)
        self.spinner = gtk.Spinner()
        self.spinner.start()

        if fg_color is not None:
            self.spinner.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(fg_color))
            self.label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(fg_color))

        self.pack_start(self.spinner, expand=False)
        self.pack_start(self.label, expand=False)
        self.set_spacing(5)

        self.show_all()


class LabelLoading(gtk.Alignment):
    """A spinner and a label."""

    def __init__(self, loading_label, fg_color=None, *args, **kwargs):
        super(LabelLoading, self).__init__(*args, **kwargs)
        self.loading = Loading(loading_label, fg_color=fg_color)

        self.label = gtk.Label()
        self.label.set_selectable(True)
        self.label.show()
        if fg_color is not None:
            self.label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.Color(fg_color))

        self.add(self.loading)

        self.show()
        self.set(xalign=0.5, yalign=0.5, xscale=0, yscale=0)
        self.set_padding(padding_top=5, padding_bottom=0,
                         padding_left=5, padding_right=5)
        self.start()

    @property
    def active(self):
        """Whether the Loading widget is visible or not."""
        return self.get_child() is self.loading

    def start(self):
        """Show the Loading instead of the Label widget."""
        for child in self.get_children():
            self.remove(child)

        self.add(self.loading)

    def stop(self):
        """Show the label instead of the Loading widget."""
        for child in self.get_children():
            self.remove(child)

        self.add(self.label)

    def set_text(self, text):
        """Set 'text' to be the label's text."""
        self.label.set_text(text)

    def set_markup(self, text):
        """Set 'text' to be the label's markup."""
        self.label.set_markup(text)

    def get_text(self):
        """Get the label's text."""
        return self.label.get_text()

    def get_label(self):
        """Get the label's markup."""
        return self.label.get_label()


class PanelTitle(gtk.Label):
    """A box with a given color and text."""

    def __init__(self, markup='', *args, **kwargs):
        super(PanelTitle, self).__init__(*args, **kwargs)
        self.set_markup(markup)
        self.set_padding(*DEFAULT_PADDING)
        self.set_property('xalign', 0.0)
        self.set_line_wrap(True)
        self.set_line_wrap_mode(pango.WRAP_WORD)
        self.set_selectable(True)
        self.show_all()


# Modified from John Stowers' client-side-windows demo.
class GreyableBin(gtk.Bin):
    """A greyable bin.

    Provides a 'greyed' boolean property that, when set, the bin gets greyed
    out.

    """

    # Invalid name, Missing docstring, do not list fix-mes
    # pylint: disable=C0103,C0111,W0511

    __gsignals__ = {
        "damage_event": "override",
    }
    __gproperties__ = {
        'greyed': (gobject.TYPE_BOOLEAN,
                   'Greyed', 'greyed', False, gobject.PARAM_READWRITE),
    }
    __gtype_name__ = 'GreyableBin'

    def __init__(self):
        gtk.Bin.__init__(self)

        self.child = None
        self.offscreen_window = None
        self.greyed = False

        self.unset_flags(gtk.NO_WINDOW)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def _to_child(self, widget_x, widget_y):
        return widget_x, widget_y

    def _to_parent(self, offscreen_x, offscreen_y):
        return offscreen_x, offscreen_y

    def _pick_offscreen_child(self, offscreen_window, widget_x, widget_y):
        if self.child and self.child.flags() & gtk.VISIBLE:
            x, y = self._to_child(widget_x, widget_y)
            ca = self.child.allocation
            if (x >= 0 and x < ca.width and y >= 0 and y < ca.height):
                return self.offscreen_window
        return None

    def _offscreen_window_to_parent(self, offscreen_window, offscreen_x,
                                    offscreen_y, parent_x, parent_y):
        # Unused variable 'y', Unused variable 'x'
        # pylint: disable=W0612
        x, y = self._to_parent(offscreen_x, offscreen_y)
        offscreen_x = parent_x
        offscreen_y = offscreen_x

    def _offscreen_window_from_parent(self, parent_window, parent_x, parent_y,
                                      offscreen_x, offscreen_y):
        # Unused variable 'y', Unused variable 'x'
        # pylint: disable=W0612
        x, y = self._to_child(parent_x, parent_y)
        offscreen_x = parent_x
        offscreen_y = offscreen_x

    def do_realize(self):
        self.set_flags(gtk.REALIZED)

        border_width = self.border_width

        w = self.allocation.width - 2 * border_width
        h = self.allocation.height - 2 * border_width

        self.window = gtk.gdk.Window(
                self.get_parent_window(),
                x=self.allocation.x + border_width,
                y=self.allocation.y + border_width,
                width=w,
                height=h,
                window_type=gtk.gdk.WINDOW_CHILD,
                event_mask=self.get_events()
                        | gtk.gdk.EXPOSURE_MASK
                        | gtk.gdk.POINTER_MOTION_MASK
                        | gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.BUTTON_RELEASE_MASK
                        | gtk.gdk.SCROLL_MASK
                        | gtk.gdk.ENTER_NOTIFY_MASK
                        | gtk.gdk.LEAVE_NOTIFY_MASK,
                visual=self.get_visual(),
                colormap=self.get_colormap(),
                wclass=gtk.gdk.INPUT_OUTPUT)

        self.window.set_user_data(self)
        self.window.connect("pick-embedded-child", self._pick_offscreen_child)

        if self.child and self.child.flags() & gtk.VISIBLE:
            w = self.child.allocation.width
            h = self.child.allocation.height

        self.offscreen_window = gtk.gdk.Window(
                self.get_root_window(),
                x=self.allocation.x + border_width,
                y=self.allocation.y + border_width,
                width=w,
                height=h,
                window_type=gtk.gdk.WINDOW_OFFSCREEN,
                event_mask=self.get_events()
                        | gtk.gdk.EXPOSURE_MASK
                        | gtk.gdk.POINTER_MOTION_MASK
                        | gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.BUTTON_RELEASE_MASK
                        | gtk.gdk.SCROLL_MASK
                        | gtk.gdk.ENTER_NOTIFY_MASK
                        | gtk.gdk.LEAVE_NOTIFY_MASK,
                visual=self.get_visual(),
                colormap=self.get_colormap(),
                wclass=gtk.gdk.INPUT_OUTPUT)
        self.offscreen_window.set_user_data(self)

        if self.child:
            self.child.set_parent_window(self.offscreen_window)

        gtk.gdk.offscreen_window_set_embedder(self.offscreen_window,
                                              self.window)
        self.offscreen_window.connect("to-embedder",
                                      self._offscreen_window_to_parent)
        self.offscreen_window.connect("from-embedder",
                                      self._offscreen_window_from_parent)

        self.style.attach(self.window)
        self.style.set_background(self.window, gtk.STATE_NORMAL)
        self.style.set_background(self.offscreen_window, gtk.STATE_NORMAL)

        self.offscreen_window.show()

    def do_child_type(self):
        #FIXME: This never seems to get called...
        if self.child:
            return None
        return gtk.Widget.__gtype__

    def do_unrealize(self):
        self.offscreen_window.set_user_data(None)
        self.offscreen_window = None

    def do_add(self, widget):
        if not self.child:
            widget.set_parent_window(self.offscreen_window)
            widget.set_parent(self)
            self.child = widget
        else:
            print "Cannot have more than one child"

    def do_remove(self, widget):
        was_visible = widget.flags() & gtk.VISIBLE
        if self.child == widget:
            widget.unparent()
            self.child = None
            if was_visible and (self.flags() & gtk.VISIBLE):
                self.queue_resize()

    def do_forall(self, internal, callback, data):
        if self.child:
            callback(self.child, data)

    def do_size_request(self, r):
        cw, ch = 0, 0
        if self.child and (self.child.flags() & gtk.VISIBLE):
            cw, ch = self.child.size_request()

        r.width = self.border_width + cw
        r.height = self.border_width + ch

    def do_size_allocate(self, allocation):
        self.allocation = allocation

        border_width = self.border_width
        w = self.allocation.width - border_width
        h = self.allocation.height - border_width

        if self.flags() & gtk.REALIZED:
            self.window.move_resize(
                            allocation.x + border_width,
                            allocation.y + border_width,
                            w, h)

        if self.child and self.child.flags() & gtk.VISIBLE:
            ca = gtk.gdk.Rectangle(x=0, y=0, width=w, height=h)

            if self.flags() & gtk.REALIZED:
                self.offscreen_window.move_resize(
                            allocation.x + border_width,
                            allocation.y + border_width,
                            w, h)

            self.child.size_allocate(ca)

    # FIXME this does not play well with the automatic partitioning page
    # (expose events to the max, causes lockup)
    def do_damage_event(self, eventexpose):
        # invalidate the whole window
        self.window.invalidate_rect(None, False)
        return True

    def do_expose_event(self, event):
        if self.flags() & gtk.VISIBLE and self.flags() & gtk.MAPPED:
            if event.window == self.window:
                pm = gtk.gdk.offscreen_window_get_pixmap(self.offscreen_window)
                w, h = pm.get_size()

                cr = event.window.cairo_create()
                if self.greyed:
                    cr.save()
                cr.rectangle(0, 0, w, h)
                cr.clip()

                # paint the offscreen child
                cr.set_source_pixmap(pm, 0, 0)
                cr.paint()

                if self.greyed:
                    cr.restore()
                    cr.set_source_rgba(0, 0, 0, 0.5)
                    cr.rectangle(0, 0, *event.window.get_geometry()[2:4])
                    cr.paint()

            elif event.window == self.offscreen_window:
                self.style.paint_flat_box(
                                event.window,
                                gtk.STATE_NORMAL, gtk.SHADOW_NONE,
                                event.area, self, "blah",
                                0, 0, -1, -1)
                if self.child:
                    self.propagate_expose(self.child, event)

        return False

gobject.type_register(GreyableBin)
