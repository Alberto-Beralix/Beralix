# Copyright (C) 2010 Canonical
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

from gi.repository import Gtk
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.dialogs import SimpleGtkbuilderDialog

from softwarecenter.db.application import Application
from softwarecenter.distro import get_distro
from softwarecenter.enums import Icons
from softwarecenter.ui.gtk3.views.pkgnamesview import PackageNamesView
import softwarecenter.ui.gtk3.dialogs

LOG = logging.getLogger(__name__)

#FIXME: These need to come from the main app
ICON_SIZE = 24

def confirm_install(parent, datadir, app, db, icons):
    """Confirm install of the given app
       
       (currently only shows a dialog if a installed app needs to be removed
        in order to install the application)
    """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)

    if not appdetails.pkg:
        return True
    depends = cache.get_packages_removed_on_install(appdetails.pkg)
    if not depends:
        return True
    (primary, button_text) = distro.get_install_warning_text(cache, appdetails.pkg, app.name, depends)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache)

def confirm_remove(parent, datadir, app, db, icons):
    """ Confirm removing of the given app """
    cache = db._aptcache
    distro = get_distro()
    appdetails = app.get_details(db)
    # FIXME: use 
    #  backend = get_install_backend()
    #  backend.simulate_remove(app.pkgname)
    # once it works
    if not appdetails.pkg:
        return True
    depends = cache.get_packages_removed_on_remove(appdetails.pkg)
    if not depends:
        return True
    (primary, button_text) = distro.get_removal_warning_text(
        db._aptcache, appdetails.pkg, app.name, depends)
    return _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache)

def _confirm_remove_internal(parent, datadir, app, db, icons, primary, button_text, depends, cache):
    glade_dialog = SimpleGtkbuilderDialog(datadir, domain="software-center")
    dialog = glade_dialog.dialog_dependency_alert
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_default_size(360, -1)

    # get icon for the app
    appdetails = app.get_details(db)
    icon_name = appdetails.icon
    if (icon_name is None or
        not icons.has_icon(icon_name)):
        icon_name = Icons.MISSING_APP
    glade_dialog.image_package_icon.set_from_icon_name(icon_name, 
                                                       Gtk.IconSize.DIALOG)

    # set the texts
    glade_dialog.label_dependency_primary.set_text("<span font_weight=\"bold\" font_size=\"large\">%s</span>" % primary)
    glade_dialog.label_dependency_primary.set_use_markup(True)
    glade_dialog.button_dependency_do.set_label(button_text)

    # add the dependencies
    view = PackageNamesView(_("Dependency"), cache, depends, icons, ICON_SIZE, db)
    view.set_headers_visible(False)
    # FIXME: work out how not to select?/focus?/activate? first item
    glade_dialog.scrolledwindow_dependencies.add(view)
    glade_dialog.scrolledwindow_dependencies.show_all()
        
    result = dialog.run()
    dialog.hide()
    if result == Gtk.ResponseType.ACCEPT:
        return True
    return False


if __name__ == "__main__":
    import sys, os

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"


    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    Gtk.Window.set_default_icon_name("softwarecenter")

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    # xapian
    import xapian
    from softwarecenter.paths import XAPIAN_BASE_PATH
    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    try:
        db = StoreDatabase(pathname, cache)
        db.open()
    except xapian.DatabaseOpeningError:
        # Couldn't use that folder as a database
        # This may be because we are in a bzr checkout and that
        #   folder is empty. If the folder is empty, and we can find the
        # script that does population, populate a database in it.
        if os.path.isdir(pathname) and not os.listdir(pathname):
            from softwarecenter.db.update import rebuild_database
            logging.info("building local database")
            rebuild_database(pathname)
            db = StoreDatabase(pathname, cache)
            db.open()
    except xapian.DatabaseCorruptError as e:
        logging.exception("xapian open failed")
        softwarecenter.ui.gtk3.dialogs.error(None, 
                           _("Sorry, can not open the software database"),
                           _("Please re-install the 'software-center' "
                             "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)

    confirm_install(None, 
                   "./data", 
                   Application("", "gourmet"),
                   db,
                   icons)

    confirm_remove(None, 
                   "./data", 
                   Application("", "p7zip-full"),
                   db,
                   icons)

