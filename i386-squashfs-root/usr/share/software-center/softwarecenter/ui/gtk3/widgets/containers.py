import cairo
import os

import softwarecenter.paths

from gi.repository import Gtk, Gdk

from buttons import MoreLink
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.drawing import rounded_rect


class FlowableGrid(Gtk.Fixed):

    MIN_HEIGHT = 100

    def __init__(self, paint_grid_pattern=True):
        Gtk.Fixed.__init__(self)
        self.set_size_request(100, -1)
        self.row_spacing = 0
        self.column_spacing = 0
        self.n_columns = 0
        self.n_rows = 0
        self.paint_grid_pattern = paint_grid_pattern
        self._cell_size = None
        return

    # private
    def _get_n_columns_for_width(self, width, cell_w, col_spacing):
        n_cols = width / (cell_w + col_spacing)
        return n_cols

    def _layout_children(self, a):
        if not self.get_visible(): return

        children = self.get_children()
        width = a.width
        #height = a.height

        col_spacing = 0
        row_spacing = 0

        cell_w, cell_h = self.get_cell_size()
        n_cols = self._get_n_columns_for_width(width, cell_w, col_spacing)

        if n_cols == 0: return
        cell_w = width / n_cols
        self.n_columns = n_cols

        #~ h_overhang = width - n_cols*cell_w - (n_cols-1)*col_spacing
        #~ if n_cols > 1:
            #~ xo = h_overhang / (n_cols-1)
        #~ else:
            #~ xo = h_overhang
        
        if len(children) % n_cols:
            self.n_rows = len(children)/n_cols + 1
        else:
            self.n_rows = len(children)/n_cols

        y = 0
        for i, child in enumerate(children):
            x = a.x + (i % n_cols) * (cell_w + col_spacing)

            #~ x = a.x + (i % n_cols) * (cell_w + col_spacing + xo)
            #~ if n_cols == 1:
                #~ x += xo/2
            if (i%n_cols) == 0:
                y = a.y + (i / n_cols) * (cell_h + row_spacing)

            child_alloc = child.get_allocation()
            child_alloc.x = x
            child_alloc.y = y
            child_alloc.width = cell_w
            child_alloc.height = cell_h
            child.size_allocate(child_alloc)
        return

    # overrides
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_height_for_width(self, width):
        old = self.get_allocation()
        if width == old.width: old.height, old.height

        cell_w, cell_h = self.get_cell_size()
        n_cols = self._get_n_columns_for_width(
                        width, cell_w, self.column_spacing)

        if not n_cols: return self.MIN_HEIGHT, self.MIN_HEIGHT

        children = self.get_children()
        n_rows = len(children) / n_cols

        # store these for use when _layout_children gets called
        if len(children) % n_cols:
            n_rows += 1

        pref_h = n_rows*cell_h + (n_rows-1)*self.row_spacing + 1
        pref_h = max(self.MIN_HEIGHT, pref_h)
        return pref_h, pref_h

    # signal handlers
    def do_size_allocate(self, allocation):
        self.set_allocation(allocation)
        self._layout_children(allocation)
        return

    def do_draw(self, cr):
        if not (self.n_columns and self.n_rows): return

        if self.paint_grid_pattern:
            self.render_grid(cr)

        for child in self: self.propagate_draw(child, cr)
        return

    # public
    def render_grid(self, cr):
        context = self.get_style_context()
        context.save()
        context.add_class("grid-lines")
        bg = context.get_border_color(self.get_state_flags())
        context.restore()

        cr.save()
        a = self.get_allocation()
        rounded_rect(cr, 0, 0, a.width, a.height-1, Frame.BORDER_RADIUS)
        cr.clip()

        Gdk.cairo_set_source_rgba(cr, bg)
        cr.set_line_width(1)

        cell_w = a.width / self.n_columns
        cell_h = self.get_cell_size()[1]

        for i in range(self.n_columns):
            for j in range(self.n_rows):
                # paint checker if need be
                #~ if not (i + j%2)%2:
                    #~ cr.save()
                    #~ cr.set_source_rgba(0.976470588, 0.956862745, 0.960784314, 0.85) #F9F4F5
                    #~ cr.rectangle(i*cell_w, j*cell_h, cell_w, cell_h)
                    #~ cr.fill()
                    #~ cr.restore()

                # paint rows
                if not j: continue
                cr.move_to(0, j*cell_h + 0.5)
                cr.rel_line_to(a.width-1, 0)
                cr.stroke()

            # paint columns
            if not i: continue
            cr.move_to(i*cell_w + 0.5, 0)
            cr.rel_line_to(0, a.height-1)
            cr.stroke()

        cr.restore()
        return

    def add_child(self, child):
        self._cell_size = None
        self.put(child, 0, 0)
        return

    def get_cell_size(self):
        if self._cell_size is not None:
            return self._cell_size

        w = h = 1
        for child in self.get_children():
            child_pref_w = child.get_preferred_width()[0]
            child_pref_h = child.get_preferred_height()[0]
            w = max(w, child_pref_w)
            h = max(h, child_pref_h)

        self._cell_size = (w, h)
        return w, h

    def set_row_spacing(self, value):
        self.row_spacing = value
        return

    def set_column_spacing(self, value):
        self.column_spacing = value
        self._layout_children(self.get_allocation())
        return

    def remove_all(self):
        self._cell_size = None
        for child in self:
            self.remove(child)
        return

# first tier of caching, cache component assets from which frames are
# rendered
_frame_asset_cache = {}
class Frame(Gtk.Alignment):

    BORDER_RADIUS = 8
    ASSET_TAG = "default"
    BORDER_IMAGE = os.path.join(
        softwarecenter.paths.datadir, "ui/gtk3/art/frame-border-image.png")
    #~ CORNER_LABEL = os.path.join(
        #~ softwarecenter.paths.datadir, "ui/gtk3/art/corner-label.png")

    def __init__(self, padding=0):
        Gtk.Alignment.__init__(self)
        # set padding + some additional padding in the bottom, left and
        # right edges to factor in the dropshadow width, and ensure even
        # visual border
        self.set_padding(padding, padding+2, padding+1, padding+1)

        # corner lable jazz
        #~ self.show_corner_label = False
        #~ self.layout = self.create_pango_layout("")
        #~ self.layout.set_width(40960)
        #~ self.layout.set_ellipsize(Pango.EllipsizeMode.END)

        #~ assets = self._cache_art_assets()
        self._cache_art_assets()
        # second tier of caching, cache resultant surface of
        # fully composed and rendered frame
        self._frame_surface_cache = None
        #~ self.connect_after("draw", self.on_draw_after,
                           #~ assets, self.layout)
        self._allocation = Gdk.Rectangle()
        self.connect("size-allocate", self.on_size_allocate)
        self.connect("style-updated", self.on_style_updated)
        return

    def on_style_updated(self, widget):
        self._frame_surface_cache = None
        return

    def on_size_allocate(self, *args):
        old = self._allocation
        cur = self.get_allocation()
        if cur.width != old.width or cur.height != old.height:
            self._frame_surface_cache = None
            self._allocation = cur
            return
        return True

    def _cache_art_assets(self):
        global _frame_asset_cache
        at = self.ASSET_TAG
        assets = _frame_asset_cache
        if at in assets: return assets

        def cache_corner_surface(tag, xo, yo):
            sw = sh = cnr_slice
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
            cr = cairo.Context(surf)
            cr.set_source_surface(border_image, xo, yo)
            cr.paint()
            assets[tag] = surf
            del cr
            return

        def cache_edge_pattern(tag, xo, yo, sw, sh):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
            cr = cairo.Context(surf)
            cr.set_source_surface(border_image, xo, yo)
            cr.paint()
            ptrn = cairo.SurfacePattern(surf)
            ptrn.set_extend(cairo.EXTEND_REPEAT)
            assets[tag] = ptrn
            del cr
            return

        # register the asset tag within the asset_cache
        assets[at] = 'loaded'

        # the basic stuff
        border_image = cairo.ImageSurface.create_from_png(self.BORDER_IMAGE)
        assets["corner-slice"] = cnr_slice = 10
        w = border_image.get_width()
        h = border_image.get_height()

        # caching ....
        # north-west corner of border image
        cache_corner_surface("%s-nw" % at, 0, 0)
        # northern edge pattern
        cache_edge_pattern("%s-n" % at,
                           -cnr_slice, 0,
                           w-2*cnr_slice, cnr_slice)
        # north-east corner
        cache_corner_surface("%s-ne" % at, -(w-cnr_slice), 0)
        # eastern edge pattern
        cache_edge_pattern("%s-e" % at,
                           -(w-cnr_slice), -cnr_slice,
                           cnr_slice, h-2*cnr_slice)
        # south-east corner
        cache_corner_surface("%s-se" % at, -(w-cnr_slice), -(h-cnr_slice))
        # southern edge pattern
        cache_edge_pattern("%s-s" % at,
                           -cnr_slice, -(h-cnr_slice),
                           w-2*cnr_slice, cnr_slice)
        # south-west corner
        cache_corner_surface("%s-sw" % at, 0, -(h-cnr_slice))
        # western edge pattern
        cache_edge_pattern("%s-w" % at, 0, -cnr_slice,
                           cnr_slice, h-2*cnr_slice)
        # all done!
        return assets

    def do_draw(self, cr):
        cr.save()
        self.on_draw(cr)
        cr.restore()
        return

    def on_draw(self, cr):
        a = self.get_allocation()
        self.render_frame(cr, a, self.BORDER_RADIUS, _frame_asset_cache)

        for child in self: self.propagate_draw(child, cr)
        return

    #~ def on_draw_after(self, widget, cr, assets, layout):
        #~ if not self.show_corner_label: return
        #~ cr.save()
        #~ surf = assets["corner-label"]
        #~ w = surf.get_width()
        #~ h = surf.get_height()
        #~ cr.reset_clip()
        #~ # the following arbitrary adjustments are specific to the
        #~ # corner-label.png image...

        #~ # alter the to allow drawing outside of the widget bounds
        #~ cr.rectangle(-10, -10, w+4, h+4)
        #~ cr.clip()
        #~ cr.set_source_surface(surf, -7, -8)
        #~ cr.paint()
        #~ # render label
        #~ ex = layout.get_pixel_extents()[1]
        #~ # transalate to the visual center of the corner-label
        #~ cr.translate(19, 18)
        #~ # rotate counter-clockwise
        #~ cr.rotate(-pi*0.25)
        #~ # paint normal markup
        #~ Gtk.render_layout(widget.get_style_context(),
                          #~ cr, -ex.width/2, -ex.height/2, layout)
        #~ cr.restore()
        #~ return

    def set_show_corner_label(self, show_label):
        if (not self.layout.get_text() and
            self.show_corner_label == show_label): return
        global _frame_asset_cache
        assets = _frame_asset_cache

        if "corner-label" not in assets:
            # cache corner label
            surf = cairo.ImageSurface.create_from_png(self.CORNER_LABEL)
            assets["corner-label"] = surf

        self.show_corner_label = show_label
        self.queue_draw()
        return

    #~ def set_corner_label(self, markup):
        #~ markup = '<span font_desc="12" color="white"><b>%s</b></span>' % markup
        #~ self.set_show_corner_label(True)
        #~ self.layout.set_markup(markup, -1)
        #~ self.queue_draw()
        #~ return

    def render_frame(self, cr, a, border_radius, assets):
        # we cache as much of the drawing as possible
        # store a copy of the rendered frame surface, so we only have to
        # do a full redraw if the widget dimensions change
        if self._frame_surface_cache is None:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, a.width, a.height)
            _cr = cairo.Context(surf)

            at = self.ASSET_TAG

            width = a.width
            height = a.height
            cnr_slice = assets["corner-slice"]

            # paint north-west corner
            _cr.set_source_surface(assets["%s-nw" % at], 0, 0)
            _cr.paint()

            # paint north length
            _cr.save()
            _cr.set_source(assets["%s-n" % at])
            _cr.rectangle(cnr_slice, 0, width-2*cnr_slice, cnr_slice)
            _cr.clip()
            _cr.paint()
            _cr.restore()

            # paint north-east corner
            _cr.set_source_surface(assets["%s-ne" % at],
                                   width-cnr_slice, 0)
            _cr.paint()

            # paint east length
            _cr.save()
            _cr.translate(width-cnr_slice, cnr_slice)
            _cr.set_source(assets["%s-e" % at])
            _cr.rectangle(0, 0, cnr_slice, height-2*cnr_slice)
            _cr.clip()
            _cr.paint()
            _cr.restore()

            # paint south-east corner
            _cr.set_source_surface(assets["%s-se" % at],
                                   width-cnr_slice,
                                   height-cnr_slice)
            _cr.paint()

            # paint south length
            _cr.save()
            _cr.translate(cnr_slice, height-cnr_slice)
            _cr.set_source(assets["%s-s" % at])
            _cr.rectangle(0, 0, width-2*cnr_slice, cnr_slice)
            _cr.clip()
            _cr.paint()
            _cr.restore()

            # paint south-west corner
            _cr.set_source_surface(assets["%s-sw" % at],
                                   0, height-cnr_slice)
            _cr.paint()

            # paint west length
            _cr.save()
            _cr.translate(0, cnr_slice)
            _cr.set_source(assets["%s-w" % at])
            _cr.rectangle(0, 0, cnr_slice, height-2*cnr_slice)
            _cr.clip()
            _cr.paint()
            _cr.restore()

            # fill interior
            rounded_rect(_cr, 3, 2, a.width-6, a.height-6, border_radius)
            context = self.get_style_context()
            bg = context.get_background_color(self.get_state_flags())
            Gdk.cairo_set_source_rgba(_cr, bg)
            _cr.fill()

            self._frame_surface_cache = surf
            del _cr

        # paint the cached surface and apply a rounded rect clip to
        # child draw ops
        A = self.get_allocation()
        xo, yo = a.x-A.x, a.y-A.y

        cr.set_source_surface(self._frame_surface_cache, xo, yo)
        cr.paint()

        rounded_rect(cr, xo+3, yo+2, a.width-6, a.height-6, border_radius)
        cr.clip()
        return


class SmallBorderRadiusFrame(Frame):

    BORDER_RADIUS = 3
    ASSET_TAG = "small"
    BORDER_IMAGE = os.path.join(
        softwarecenter.paths.datadir, "ui/gtk3/art/frame-border-image-2px-border-radius.png")

    def __init__(self, padding=3):
        Frame.__init__(self, padding)
        return


class FramedBox(Frame):

    def __init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=0, padding=0):
        Frame.__init__(self, padding)
        self.box = Gtk.Box.new(orientation, spacing)
        Gtk.Alignment.add(self, self.box)
        return

    def add(self, *args, **kwargs):
        return self.box.add(*args, **kwargs)

    def pack_start(self, *args, **kwargs):
        return self.box.pack_start(*args, **kwargs)

    def pack_end(self, *args, **kwargs):
        return self.box.pack_end(*args, **kwargs)


class HeaderPosition:
    LEFT = 0.0
    CENTER = 0.5
    RIGHT = 1.0


class FramedHeaderBox(FramedBox):

    MARKUP = '<b>%s</b>'

    def __init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=0, padding=0):
        FramedBox.__init__(self, Gtk.Orientation.VERTICAL, spacing, padding)
        self.header = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, spacing)
        self.header_alignment = Gtk.Alignment()
        self.header_alignment.add(self.header)
        self.box.pack_start(self.header_alignment, False, False, 0)
        self.content_box = Gtk.Box.new(orientation, spacing)
        self.box.add(self.content_box)
        return

    def on_draw(self, cr):
        a = self.get_allocation()
        self.render_frame(cr, a, Frame.BORDER_RADIUS, _frame_asset_cache)
        a = self.header_alignment.get_allocation()
        self.render_header(cr, a, Frame.BORDER_RADIUS, _frame_asset_cache)

        for child in self: self.propagate_draw(child, cr)
        return

    def add(self, *args, **kwargs):
        return self.content_box.add(*args, **kwargs)

    def pack_start(self, *args, **kwargs):
        return self.content_box.pack_start(*args, **kwargs)

    def pack_end(self, *args, **kwargs):
        return self.content_box.pack_end(*args, **kwargs)

    # XXX: non-functional with current code...
    #~ def set_header_expand(self, expand):
        #~ alignment = self.header_alignment
        #~ if expand:
            #~ expand = 1.0
        #~ else:
            #~ expand = 0.0
        #~ alignment.set(alignment.get_property("xalign"),
                      #~ alignment.get_property("yalign"),
                      #~ expand, 1.0)

    def set_header_position(self, position):
        alignment = self.header_alignment
        alignment.set(position, 0.5,
                      alignment.get_property("xscale"),
                      alignment.get_property("yscale"))

    def set_header_label(self, label):
        if not hasattr(self, "title"):
            self.title = Gtk.Label()
            self.title.set_padding(StockEms.MEDIUM, StockEms.SMALL)
            context = self.title.get_style_context()
            context.add_class("frame-header-title")
            self.header.pack_start(self.title, False, False, 0)
            self.title.show()

        self.title.set_markup(self.MARKUP % label)
        return

    def header_implements_more_button(self, callback=None):
        if not hasattr(self, "more"):
            self.more = MoreLink()
            self.header.pack_end(self.more, False, False, 0)
        return
    
    def render_header(self, cr, a, border_radius, assets):
        context = self.get_style_context()
        Gtk.render_background(context, cr,
                              0, 0, a.width, a.height)

        cr.save()
        lin = cairo.LinearGradient(0, 0, 0, a.height)
        lin.add_color_stop_rgba(0, 1,1,1, 0.5)
        lin.add_color_stop_rgba(1, 1,1,1, 0.0)
        cr.set_source(lin)
        cr.rectangle(0, 0, a.width, a.height)
        cr.fill()

        # gridline color
        context.save()
        context.add_class("grid-lines")
        bc = context.get_border_color(self.get_state_flags())
        Gdk.cairo_set_source_rgba(cr, bc)
        context.restore()

        cr.move_to(0, a.height-0.5)
        cr.rel_line_to(a.width, 0)
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

        if hasattr(self, "more"):
            # set the arrow fill color
            context = self.more.get_style_context()
            cr.save()

            bg = context.get_background_color(self.get_state_flags())
            Gdk.cairo_set_source_rgba(cr, bg)

            # the arrow shape stuff
            ta = self.more.get_allocation()
            cr.move_to(ta.x-a.x-StockEms.MEDIUM, 0)
            cr.rel_line_to(ta.width+StockEms.MEDIUM, 0)
            cr.rel_line_to(0, a.height)
            cr.rel_line_to(-(ta.width+StockEms.MEDIUM), 0)
            cr.rel_line_to(StockEms.MEDIUM, -(a.height)*0.5)
            cr.close_path()
            cr.clip_preserve()
            cr.fill_preserve()

            bc = context.get_border_color(self.get_state_flags())
            Gdk.cairo_set_source_rgba(cr, bc)
            cr.stroke()

            cr.restore()

        # paint the containers children
        for child in self: self.propagate_draw(child, cr)
        return


# this is used in the automatic tests
def get_test_container_window():
    win = Gtk.Window()
    win.set_size_request(500, 300)
    f = FlowableGrid()

    import buttons

    for i in range(10):
        t = buttons.CategoryTile("test", "folder")
        f.add_child(t)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(f)

    win.add(scroll)
    win.show_all()

    win.connect("destroy", lambda x: Gtk.main_quit())
    return win

if __name__ == '__main__':
    win = get_test_container_window()
    win.show_all()
    Gtk.main()
