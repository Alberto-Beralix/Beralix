# Copyright (C) 2009 Canonical
#
# Authors:
#  Matthew McGowan
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

import cairo
import gettext
from gi.repository import Gtk
from gi.repository import GObject
import logging
import os
import xapian

from gettext import gettext as _

import softwarecenter.paths
from softwarecenter.db.application import Application
from softwarecenter.enums import (NonAppVisibility,
                                  SortMethods,
                                  TOP_RATED_CAROUSEL_LIMIT)
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
from softwarecenter.ui.gtk3.widgets.viewport import Viewport
from softwarecenter.ui.gtk3.widgets.containers import (
     FramedHeaderBox, FramedBox, FlowableGrid)
from softwarecenter.ui.gtk3.widgets.exhibits import (
    ExhibitBanner, FeaturedExhibit)
from softwarecenter.ui.gtk3.widgets.buttons import (LabelTile,
                                                    CategoryTile,
                                                    FeaturedTile)
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.db.appfilter import AppFilter, get_global_filter
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.categories import (Category,
                                          CategoriesParser,
                                          get_category_by_name,
                                          categories_sorted_by_name)
from softwarecenter.db.utils import get_query_for_pkgnames
from softwarecenter.distro import get_distro
from softwarecenter.backend.scagent import SoftwareCenterAgent

LOG=logging.getLogger(__name__)


_asset_cache = {}
class CategoriesViewGtk(Viewport, CategoriesParser):

    __gsignals__ = {
        "category-selected" : (GObject.SignalFlags.RUN_LAST,
                               None, 
                               (GObject.TYPE_PYOBJECT, ),
                              ),
                              
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT, ),
                                 ),

        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
                                  
        "show-category-applist" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (),)
        }

    SPACING = PADDING = 3

    # art stuff
    STIPPLE = os.path.join(softwarecenter.paths.datadir,
                           "ui/gtk3/art/stipple.png")

    def __init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit=0):

        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        db - a Database object
        icons - a Gtk.IconTheme
        apps_filter - ?
        apps_limit - the maximum amount of items to display to query for
        """

        self.cache = cache
        self.db = db
        self.icons = icons
        self.section = None

        Viewport.__init__(self)
        CategoriesParser.__init__(self, db)

        self.set_name("category-view")

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        # setup widgets

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # appstore stuff
        self.categories = []
        self.header = ""
        #~ self.apps_filter = apps_filter
        self.apps_limit = apps_limit
        # for comparing on refreshes
        self._supported_only = False

        # more stuff
        self._poster_sigs = []
        self._allocation = None

        self._cache_art_assets()
        #~ assets = self._cache_art_assets()
        #~ self.vbox.connect("draw", self.on_draw, assets)
        self._prev_alloc = None
        self.connect("size-allocate", self.on_size_allocate)
        return

    def _add_tiles_to_flowgrid(self, docs, flowgrid, amount):
        '''Adds application tiles to a FlowableGrid:
           docs = xapian documents (apps)
           flowgrid = the FlowableGrid to add tiles to
           amount = number of tiles to add from start of doc range'''
        amount = min(len(docs), amount)
        for doc in docs[0:amount]:
            tile = FeaturedTile(self.helper, doc)
            tile.connect('clicked', self.on_app_clicked,
                         self.helper.get_application(doc))
            flowgrid.add_child(tile)
        return

    def on_size_allocate(self, widget, _):
        a = widget.get_allocation()
        prev = self._prev_alloc
        if prev is None or a.width != prev.width or a.height != prev.height:
            self._prev_alloc = a
            self.queue_draw()
        return

    def _cache_art_assets(self):
        global _asset_cache
        if _asset_cache: return _asset_cache
        assets = _asset_cache
        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.STIPPLE)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["stipple"] = ptrn
        return assets

    def on_app_clicked(self, btn, app):
        """emit the category-selected signal when a category was clicked"""
        def timeout_emit():
            self.emit("application-selected", app)
            self.emit("application-activated", app)
            return False

        GObject.timeout_add(50, timeout_emit)
        return

    def on_category_clicked(self, btn, cat):
        """emit the category-selected signal when a category was clicked"""
        def timeout_emit():
            self.emit("category-selected", cat)
            return False

        GObject.timeout_add(50, timeout_emit)
        return

    def build(self, desktopdir):
        pass

    def do_draw(self, cr):
        cr.set_source(_asset_cache["stipple"])
        cr.paint_with_alpha(0.5)
        for child in self: self.propagate_draw(child, cr)
        return

    def set_section(self, section):
        self.section = section

    def refresh_apps(self):
        raise NotImplemented


class LobbyViewGtk(CategoriesViewGtk):

    def __init__(self, datadir, desktopdir, cache, db, icons,
                 apps_filter, apps_limit=0):
        CategoriesViewGtk.__init__(self, datadir, desktopdir, cache, db, icons,
                                   apps_filter, apps_limit=0)

        # sections
        self.departments = None
        self.appcount = None

        # this means that the departments don't jump down once the cache loads
        # it doesn't look odd if the recommends are never loaded
        #~ self.recommended = Gtk.Label()
        #~ self.vbox.pack_start(self.recommended, False, False, 0)

        self.build(desktopdir)
        return

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        #~ self._append_recommendations()
        self._append_banner_ads()

        self.top_hbox = Gtk.HBox(spacing=StockEms.SMALL)
        top_hbox_alignment = Gtk.Alignment()
        top_hbox_alignment.set_padding(0, 0, StockEms.MEDIUM-2, StockEms.MEDIUM-2)
        top_hbox_alignment.add(self.top_hbox)
        self.vbox.pack_start(top_hbox_alignment, False, False, 0)

        self._append_departments()

        self.right_column = Gtk.Box.new(Gtk.Orientation.VERTICAL, self.SPACING)
        self.top_hbox.pack_start(self.right_column, True, True, 0)

        self._append_new()
        #~ self._append_recommendations()
        self._append_top_rated()

        self._append_appcount()

        #self._append_video_clips()
        #self._append_top_of_the_pops
        return

    #~ def _append_top_of_the_pops(self):
        #~ self.totp_hbox = Gtk.HBox(spacing=self.SPACING)
#~ 
        #~ alignment = Gtk.Alignment()
        #~ alignment.set_padding(0, 0, self.PADDING, self.PADDING)
        #~ alignment.add(self.totp_hbox)
#~ 
        #~ frame = FramedHeaderBox()
        #~ frame.header_implements_more_button()
        #~ frame.set_header_label(_("Most Popular"))
#~ 
        #~ label = Gtk.Label.new("Soda pop!!!")
        #~ label.set_name("placeholder")
        #~ label.set_size_request(-1, 200)
#~ 
        #~ frame.add(label)
        #~ self.totp_hbox.add(frame)
#~ 
        #~ frame = FramedHeaderBox()
        #~ frame.header_implements_more_button()
        #~ frame.set_header_label(_("Top Rated"))
#~ 
        #~ label = Gtk.Label.new("Demos ftw(?)")
        #~ label.set_name("placeholder")
        #~ label.set_size_request(-1, 200)
#~ 
        #~ frame.add(label)
        #~ self.totp_hbox.add(frame)
#~ 
        #~ self.vbox.pack_start(alignment, False, False, 0)
        #~ return

    #~ def _append_video_clips(self):
        #~ frame = FramedHeaderBox()
        #~ frame.set_header_expand(False)
        #~ frame.set_header_position(HeaderPosition.LEFT)
        #~ frame.set_header_label(_("Latest Demo Videos"))
#~ 
        #~ label = Gtk.Label.new("Videos go here")
        #~ label.set_name("placeholder")
        #~ label.set_size_request(-1, 200)
#~ 
        #~ frame.add(label)
#~ 
        #~ alignment = Gtk.Alignment()
        #~ alignment.set_padding(0, 0, self.PADDING, self.PADDING)
        #~ alignment.add(frame)
#~ 
        #~ self.vbox.pack_start(alignment, False, False, 0)
        #~ return

    def _on_show_exhibits(self, exhibit_banner, exhibit):
        pkgs = exhibit.package_names.split(",")
        if len(pkgs) == 1:
            app = Application("", pkgs[0])
            self.emit("application-activated", app)
        else:
            query = get_query_for_pkgnames(pkgs)
            title = exhibit.title_translated
            untranslated_name = exhibit.package_names
            # create a temp query
            cat = Category(untranslated_name, title, None, query,
                           flags=['nonapps-visible'])
            self.emit("category-selected", cat)

    def _append_banner_ads(self):
        exhibit_banner = ExhibitBanner()
        exhibit_banner.set_exhibits([FeaturedExhibit(),
                                    ])
        exhibit_banner.connect("show-exhibits-clicked", self._on_show_exhibits)

        # query using the agent
        scagent = SoftwareCenterAgent()
        scagent.connect(
            "exhibits", lambda sca,l: exhibit_banner.set_exhibits(l))
        scagent.query_exhibits()

        a = Gtk.Alignment()
        a.set_padding(0,StockEms.SMALL,0,0)
        a.add(exhibit_banner)

        self.vbox.pack_start(a, False, False, 0)
        return

    def _append_departments(self):
        # set the departments section to use the label markup we have just defined
        cat_vbox = FramedBox(Gtk.Orientation.VERTICAL)
        self.top_hbox.pack_start(cat_vbox, False, False, 0)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        mrkup = "<small>%s</small>"
        for cat in sorted_cats:
            if 'carousel-only' in cat.flags: continue
            category_name = mrkup % GObject.markup_escape_text(cat.name)
            label = LabelTile(category_name, None)
            label.label.set_margin_left(StockEms.SMALL)
            label.label.set_margin_right(StockEms.SMALL)
            label.label.set_alignment(0.0, 0.5)
            label.label.set_use_markup(True)
            label.connect('clicked', self.on_category_clicked, cat)
            cat_vbox.pack_start(label, False, False, 0)
        return

    def _get_toprated_category_content(self):
        toprated_cat = get_category_by_name(self.categories, 
                                            u"Top Rated")  # unstranslated name
        if toprated_cat is None:
            LOG.warn("No 'toprated' category found!!")
            return None, []

        enq = AppEnquire(self.cache, self.db)
        app_filter = AppFilter(self.db, self.cache)
        enq.set_query(toprated_cat.query,
                      limit=TOP_RATED_CAROUSEL_LIMIT,
                      sortmode=toprated_cat.sortmode,
                      filter=app_filter,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=False)

        if not hasattr(self, "helper"):
            self.helper = AppPropertiesHelper(self.db,
                                              self.cache,
                                              self.icons)

        return toprated_cat, enq.get_documents()

    def _update_toprated_content(self):
        # remove any existing children from the grid widget
        self.toprated.remove_all()
        # get toprated category and docs
        toprated_cat, docs = self._get_toprated_category_content()
        # display docs
        self._add_tiles_to_flowgrid(docs, self.toprated,
                                    TOP_RATED_CAROUSEL_LIMIT)
        self.toprated.show_all()
        return toprated_cat

    def _append_top_rated(self):
        self.toprated = FlowableGrid()
        #~ self.featured.row_spacing = StockEms.SMALL
        frame = FramedHeaderBox()
        frame.set_header_label(_("Top Rated"))
        frame.add(self.toprated)
        self.toprated_frame = frame
        self.right_column.pack_start(frame, True, True, 0)

        toprated_cat = self._update_toprated_content()
        # only display the 'More' LinkButton if we have toprated content
        if toprated_cat is not None:
            frame.header_implements_more_button()
            frame.more.connect('clicked', self.on_category_clicked, toprated_cat) 
        return

    def _get_new_category_content(self):
        whatsnew_cat = get_category_by_name(self.categories, 
                                            u"What\u2019s New") # unstranslated name
        if whatsnew_cat is None:
            LOG.warn("No 'new' category found!!")
            return None, []

        enq = AppEnquire(self.cache, self.db)
        app_filter = AppFilter(self.db, self.cache)
        app_filter.set_available_only(True)
        app_filter.set_not_installed_only(True)
        enq.set_query(whatsnew_cat.query,
                      limit=8,
                      filter=app_filter,
                      sortmode=SortMethods.BY_CATALOGED_TIME,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=False)

        if not hasattr(self, "helper"):
            self.helper = AppPropertiesHelper(self.db,
                                              self.cache,
                                              self.icons)

        return whatsnew_cat, enq.get_documents()

    def _update_new_content(self):
        # remove any existing children from the grid widget
        self.featured.remove_all()
        # get toprated category and docs
        whatsnew_cat, docs = self._get_new_category_content()
        # display docs
        self._add_tiles_to_flowgrid(docs, self.featured, 8)
        self.featured.show_all()
        return whatsnew_cat

    def _append_new(self):
        self.featured = FlowableGrid()
        frame = FramedHeaderBox()
        frame.set_header_label(_(u"What\u2019s New"))
        frame.add(self.featured)
        self.new_frame = frame

        whatsnew_cat = self._update_new_content()
        if whatsnew_cat is not None:
            # only add to the visible right_frame if we actually have it
            self.right_column.pack_start(frame, True, True, 0)
            frame.header_implements_more_button()
            frame.more.connect('clicked', self.on_category_clicked, whatsnew_cat) 
        return

    #~ def _append_recommendations(self):
        #~ featured_cat = get_category_by_name(self.categories, 
                                            #~ u"Featured")  # unstranslated name
#~ 
        #~ enq = AppEnquire(self.cache, self.db)
        #~ app_filter = AppFilter(self.db, self.cache)
        #~ enq.set_query(featured_cat.query,
                      #~ limit=12,
                      #~ filter=app_filter,
                      #~ nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      #~ nonblocking_load=False)
#~ 
        #~ self.featured = FlowableGrid()
        #~ frame = FramedHeaderBox(Gtk.Orientation.VERTICAL)
        #~ frame.add(self.featured)
        #~ frame.set_header_label(_("Recommended For You"))
        #~ frame.header_implements_more_button()
        #~ self.right_column.pack_start(frame, True, True, 0)
#~ 
        #~ self.helper = AppPropertiesHelper(self.db, self.cache, self.icons)
        #~ docs = enq.get_documents()
        #~ self._add_tiles_to_flowgrid(docs, self.featured, 12)
        #~ return

    def _update_appcount(self):
        enq = AppEnquire(self.cache, self.db)

        distro = get_distro()
        if get_global_filter().supported_only:
            query = distro.get_supported_query()
        else:
            query = xapian.Query('')

        enq.set_query(query,
                      limit=0,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=True)

        length = len(enq.matches)
        text = gettext.ngettext("%(amount)s item", "%(amount)s items", length
                                ) % { 'amount' : length, }
        self.appcount.set_text(text)

    def _append_appcount(self):
        self.appcount = Gtk.Label()
        self.appcount.set_alignment(0.5, 0.5)
        self.appcount.set_margin_top(1)
        self.appcount.set_margin_bottom(4)
        self.vbox.pack_start(self.appcount, False, True, 0)
        self._update_appcount()
        return

    def build(self, desktopdir):
        self.categories = self.parse_applications_menu(desktopdir)
        self.header = _('Departments')
        self._build_homepage_view()
        self.show_all()
        return

    def refresh_apps(self):
        supported_only = get_global_filter().supported_only
        if (self._supported_only == supported_only):
            return
        self._supported_only = supported_only

        self._update_toprated_content()
        self._update_new_content()
        self._update_appcount()
        return

    # stubs for the time being, we may reuse them if we get dynamic content 
    # again
    def stop_carousels(self):
        pass

    def start_carousels(self):
        pass

class SubCategoryViewGtk(CategoriesViewGtk):

    def __init__(self, datadir, desktopdir, cache, db, icons,
                 apps_filter, apps_limit=0, root_category=None):
        CategoriesViewGtk.__init__(self, datadir, desktopdir, cache, db, icons,
                                   apps_filter, apps_limit)
        # state
        self._built = False
        # data
        self.root_category = root_category
        self.enquire = AppEnquire(self.cache, self.db)
        self.helper = AppPropertiesHelper(self.db,
                                          self.cache,
                                          self.icons)

        # sections
        self.current_category = None
        self.departments = None
        self.toprated = None
        self.appcount = None

        # widgetry
        self.vbox.set_margin_left(StockEms.MEDIUM-2)
        self.vbox.set_margin_right(StockEms.MEDIUM-2)
        self.vbox.set_margin_top(StockEms.MEDIUM)
        return

    def _get_sub_toprated_content(self, category):
        app_filter = AppFilter(self.db, self.cache)
        self.enquire.set_query(category.query,
                               limit=TOP_RATED_CAROUSEL_LIMIT,
                               sortmode=SortMethods.BY_TOP_RATED,
                               filter=app_filter,
                               nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                               nonblocking_load=False)
        return self.enquire.get_documents()

    @wait_for_apt_cache_ready # be consistent with new apps
    def _update_sub_toprated_content(self, category):
        self.toprated.remove_all()
        # FIXME: should this be m = "%s %s" % (_(gettext text), header text) ??
        m = _('Top Rated %s') % GObject.markup_escape_text(self.header)
        self.toprated_frame.set_header_label(m)
        docs = self._get_sub_toprated_content(category)
        self._add_tiles_to_flowgrid(docs, self.toprated, TOP_RATED_CAROUSEL_LIMIT)
        return

    def _append_sub_toprated(self):
        self.toprated = FlowableGrid()
        self.toprated.set_row_spacing(6)
        self.toprated.set_column_spacing(6)
        self.toprated_frame = FramedHeaderBox()
        self.toprated_frame.pack_start(self.toprated, True, True, 0)
        self.vbox.pack_start(self.toprated_frame, False, True, 0)
        return

    def _update_subcat_departments(self, category, num_items):
        self.departments.remove_all()

        # set the subcat header
        m = "<b><big>%s</big></b>"
        self.subcat_label.set_markup(m % GObject.markup_escape_text(self.header))

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)
        enquire = xapian.Enquire(self.db.xapiandb)
        app_filter = AppFilter(self.db, self.cache)
        for cat in sorted_cats:
            # add the subcategory if and only if it is non-empty
            enquire.set_query(cat.query)

            if len(enquire.get_mset(0,1)):
                tile = CategoryTile(cat.name, cat.iconname)
                tile.connect('clicked', self.on_category_clicked, cat)
                self.departments.add_child(tile)

        # partialy work around a (quite rare) corner case
        if num_items == 0:
            enquire.set_query(xapian.Query(xapian.Query.OP_AND, 
                                category.query,
                                xapian.Query("ATapplication")))
            # assuming that we only want apps is not always correct ^^^
            tmp_matches = enquire.get_mset(0, len(self.db), None, app_filter)
            num_items = tmp_matches.get_matches_estimated()

        # append an additional button to show all of the items in the category
        all_cat = Category("All", _("All"), "category-show-all", category.query)
        name = GObject.markup_escape_text('%s %s' % (_("All"), num_items))
        tile = CategoryTile(name, "category-show-all")
        tile.connect('clicked', self.on_category_clicked, all_cat)
        self.departments.add_child(tile)
        self.departments.queue_draw()
        return num_items

    def _append_subcat_departments(self):
        self.subcat_label = Gtk.Label()
        self.subcat_label.set_alignment(0, 0.5)
        self.departments = FlowableGrid(paint_grid_pattern=False)
        self.departments.set_row_spacing(StockEms.SMALL)
        self.departments.set_column_spacing(StockEms.SMALL)
        frame = FramedBox(spacing=StockEms.MEDIUM,
                          padding=StockEms.MEDIUM)
        # set x/y-alignment and x/y-expand
        frame.set(0.5, 0.0, 1.0, 1.0)
        frame.pack_start(self.subcat_label, False, False, 0)
        frame.pack_start(self.departments, True, True, 0)
        # append the departments section to the page
        self.vbox.pack_start(frame, False, True, 0)
        return

    def _update_appcount(self, appcount):
        text = gettext.ngettext("%(amount)s item available",
                                "%(amount)s items available",
                                appcount) % { 'amount' : appcount, }
        self.appcount.set_text(text)
        return

    def _append_appcount(self):
        self.appcount = Gtk.Label()
        self.appcount.set_alignment(0.5, 0.5)
        self.appcount.set_margin_top(1)
        self.appcount.set_margin_bottom(4)
        self.vbox.pack_end(self.appcount, False, False, 0)
        return

    def _build_subcat_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments()
        self._append_sub_toprated()
        self._append_appcount()
        self._built = True
        return

    def _update_subcat_view(self, category, num_items=0):
        num_items = self._update_subcat_departments(category, num_items)
        self._update_sub_toprated_content(category)
        self._update_appcount(num_items)
        self.show_all()
        return

    def set_subcategory(self, root_category, num_items=0, block=False):
        # nothing to do
        if (root_category is None or
            self.categories == root_category.subcategories):
            return

        self.current_category = root_category
        self.header = root_category.name
        self.categories = root_category.subcategories

        if not self._built: self._build_subcat_view()
        self._update_subcat_view(root_category, num_items)

        GObject.idle_add(self.queue_draw)
        return

    def refresh_apps(self):
        supported_only = get_global_filter().supported_only
        if (self.current_category is None or
            self._supported_only == supported_only):
            return
        self._supported_only = supported_only

        if not self._built: self._build_subcat_view()
        self._update_subcat_view(self.current_category)
        GObject.idle_add(self.queue_draw)
        return

    #def build(self, desktopdir):
        #self.in_subsection = True
        #self.set_subcategory(self.root_category)
        #return

def get_test_window_catview():

    def on_category_selected(view, cat):
        print("on_category_selected %s %s" % view, cat)

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    import softwarecenter.paths
    datadir = softwarecenter.paths.datadir

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    apps_filter = AppFilter(db, cache)

    # gui
    win = Gtk.Window()
    n = Gtk.Notebook()

    from softwarecenter.paths import APP_INSTALL_PATH
    view = LobbyViewGtk(datadir, APP_INSTALL_PATH,
                        cache, db, icons, distro, apps_filter)
    win.set_data("lobby", view)

    scroll = Gtk.ScrolledWindow()
    scroll.add(view)
    n.append_page(scroll, Gtk.Label(label="Lobby"))

    # find a cat in the LobbyView that has subcategories
    subcat_cat = None
    for cat in reversed(view.categories):
        if cat.subcategories:
            subcat_cat = cat
            break

    view = SubCategoryViewGtk(datadir, APP_INSTALL_PATH, cache, db, icons,
                              apps_filter)
    view.connect("category-selected", on_category_selected)
    view.set_subcategory(subcat_cat)
    win.set_data("subcat", view)

    scroll = Gtk.ScrolledWindow()
    scroll.add(view)
    n.append_page(scroll, Gtk.Label(label="Subcats"))

    win.add(n)
    win.set_size_request(800,600)
    win.show_all()
    win.connect('destroy', Gtk.main_quit)
    return win

if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG)

    win = get_test_window_catview()

    # run it
    Gtk.main()


