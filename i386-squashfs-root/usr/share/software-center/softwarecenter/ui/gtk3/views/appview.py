# Copyright (C) 2009,2010 Canonical
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

#~ from __future__ import with_statement



from gi.repository import Gtk, GObject
from gettext import gettext as _
#~ import gettext

from softwarecenter.enums import SortMethods
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.models.appstore2 import AppTreeStore
from softwarecenter.ui.gtk3.widgets.apptreeview import AppTreeView
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
#~ from softwarecenter.ui.gtk3.widgets.containers import FlowableGrid


class AppView(Gtk.VBox):

    __gsignals__ = {
        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (GObject.SignalFlags.RUN_LAST,
                                        None,
                                        (GObject.TYPE_PYOBJECT,
                                         GObject.TYPE_PYOBJECT, 
                                         GObject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }
    
    (INSTALLED_MODE, AVAILABLE_MODE, DIFF_MODE) = range(3)

    _SORT_METHOD_INDEX = (SortMethods.BY_ALPHABET,
                          SortMethods.BY_TOP_RATED,
                          SortMethods.BY_SEARCH_RANKING,
                          SortMethods.BY_CATALOGED_TIME)
    # indices that relate to the above tuple
    _SORT_BY_ALPHABET = 0
    _SORT_BY_TOP_RATED = 1
    _SORT_BY_SEARCH_RANKING = 2
    _SORT_BY_NEWEST_FIRST = 3

    def __init__(self, db, cache, icons, show_ratings):
        Gtk.VBox.__init__(self)
        self.set_name("app-view")
        # app properties helper
        self.helper = AppPropertiesHelper(db, cache, icons)
        # misc internal containers
        self.header_hbox = Gtk.HBox()
        self.header_hbox.set_border_width(StockEms.MEDIUM)
        self.pack_start(self.header_hbox, False, False, 0)
        self.tree_view_scroll = Gtk.ScrolledWindow()
        self.pack_start(self.tree_view_scroll, True, True, 0)

        # category label
        self.header_label = Gtk.Label()
        self.header_label.set_use_markup(True)
        self.header_hbox.pack_start(self.header_label, False, False, 0)

        # sort methods combobox
        self.sort_methods_combobox = self._get_sort_methods_combobox()
        alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)
        alignment.add(self.sort_methods_combobox)
        self.header_hbox.pack_end(alignment, False, False, 0)

        # content views
        self.tree_view = AppTreeView(self, icons,
                                     show_ratings, store=None)
        self.tree_view_scroll.add(self.tree_view)

        self.appcount = None

        self.user_defined_sort_method = False
        self._handler_changed = self.sort_methods_combobox.connect(
                                    "changed",
                                    self.on_sort_method_changed)
        return

    #~ def on_draw(self, w, cr):
        #~ cr.set_source_rgb(1,1,1)
        #~ cr.paint()

    def _append_appcount(self, appcount, mode=AVAILABLE_MODE):
#~ 
        #~ if mode == self.INSTALLED_MODE:
            #~ text = gettext.ngettext("%(amount)s item installed",
                                    #~ "%(amount)s items installed",
                                    #~ appcount) % { 'amount' : appcount, }
        #~ elif mode == self.DIFF_MODE:
            #~ text = gettext.ngettext("%(amount)s item",
                                    #~ "%(amount)s items",
                                    #~ appcount) % { 'amount' : appcount, }        
        #~ else:
            #~ text = gettext.ngettext("%(amount)s item available",
                                    #~ "%(amount)s items available",
                                    #~ appcount) % { 'amount' : appcount, }
#~ 
        #~ if not self.appcount:
            #~ self.appcount = Gtk.Label()
            #~ self.appcount.set_alignment(0.5, 0.5)
            #~ self.appcount.set_margin_top(4)
            #~ self.appcount.set_margin_bottom(3)
            #~ self.appcount.connect("draw", self.on_draw)
            #~ self.vbox.pack_start(self.appcount, False, False, 0)
        #~ self.appcount.set_text(text)
        #~ self.appcount.show()
        return

    def on_sort_method_changed(self, *args):
        self.user_defined_sort_method = True
        return

    def _get_sort_methods_combobox(self):
        combo = Gtk.ComboBoxText.new()
        combo.append_text(_("By Name"))
        combo.append_text(_("By Top Rated"))
        combo.append_text(_("By Relevance"))
        combo.append_text(_("By Newest First"))
        combo.set_active(self._SORT_BY_TOP_RATED)
        return combo

    def set_sort_method_with_no_signal(self, sort_method):
        combo = self.sort_methods_combobox
        combo.handler_block(self._handler_changed)
        combo.set_active(sort_method)
        combo.handler_unblock(self._handler_changed)
        return

    def set_allow_user_sorting(self, do_allow):
        if do_allow:
            self.sort_methods_combobox.show()
        else:
            self.sort_methods_combobox.hide()

    def set_header_labels(self, first_line, second_line):
        if second_line:
            markup = '%s\n<big><b>%s</b></big>' % (first_line, second_line)
        else:
            markup = "<big><b>%s</b></big>" % first_line
        return self.header_label.set_markup(markup)

    def set_model(self, model):
        self.tree_view.set_model(model)
        return

    def display_matches(self, matches, sort_by_relevance=False):
        # FIXME: installedpane handles display of the trees intimately,
        # so for the time being lets just return None in the case of our
        # TreeView displaying an AppTreeStore ...    ;(
        # ... also we dont currently support user sorting in the
        # installedview, so issue is somewhat moot for the time being...
        if isinstance(self.tree_view.appmodel, AppTreeStore):
            return

        if sort_by_relevance:
            self.set_sort_method_with_no_signal(self._SORT_BY_SEARCH_RANKING)
        else:
            #~ combo.remove(-1)
            if (self.get_sort_mode() == SortMethods.BY_SEARCH_RANKING and\
                not self.user_defined_sort_method):
                self.set_sort_method_with_no_signal(self._SORT_BY_TOP_RATED)
        model = self.tree_view.appmodel
        if model:
            model.set_from_matches(matches)
        self.user_defined_sort_method = False
        return

    def clear_model(self):
        return self.tree_view.clear_model()

    def get_sort_mode(self):
        active_index = self.sort_methods_combobox.get_active()
        return self._SORT_METHOD_INDEX[active_index]



def get_test_window():
    from softwarecenter.testutils import (
        get_test_db, get_test_pkg_info, get_test_gtk3_icon_cache)
    from softwarecenter.db.enquire import AppEnquire
    from softwarecenter.ui.gtk3.models.appstore2 import AppListStore
    import xapian

    db = get_test_db()
    cache = get_test_pkg_info()
    icons = get_test_gtk3_icon_cache()

    # create the view
    appview = AppView(db, cache, icons, show_ratings=True)
    liststore = AppListStore(db, cache, icons)
    appview.set_model(liststore)

    # do a simple query and display that
    enquirer = AppEnquire(cache, db)
    enquirer.set_query(xapian.Query(""),
                       sortmode=SortMethods.BY_CATALOGED_TIME,
                       limit=20,
                       nonblocking_load=False)
    appview.display_matches(enquirer.matches)

    # and put it in the window
    win = Gtk.Window()
    win.add(appview)
    win.set_data("appview", appview)

    win.connect("destroy", lambda x: Gtk.main_quit())
    win.set_size_request(600, 400)
    win.show_all()

    return win

if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
