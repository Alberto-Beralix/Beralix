# -*- coding: utf-8 -*-
#
# Copyright 2011 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""The GUI of the Ubuntu One Installer."""

import aptdaemon.gtk3widgets as aptgtk
import aptdaemon.client as aptclient
import gettext
import os

from gi.repository import Gtk, GObject, GLib, Gdk, Pango

# Some shenanigans to deal with pyflakes complaining
inline_callbacks = None
try:
    from defer import inline_callbacks
except ImportError:
    from aptdaemon.defer import inline_callbacks as old_callbacks

if inline_callbacks is None:
    inline_callbacks = old_callbacks

gettext.textdomain('ubuntuone-installer')
_ = gettext.gettext


class UnsupportedDistribution(BaseException):
    """Exception for when on an unsupported distribution."""


class VSeparator(Gtk.VSeparator):
    """A dotted line separator."""

    def do_draw(self, cairo_context):
        """Draw some magic."""
        sc = self.get_style_context()
        state = self.get_state_flags()
        width = self.get_allocated_width()
        height = self.get_allocated_height()

        sc.save()
        sc.set_state(state)

        y = 0
        x = width / 2
        while y < height:
            Gtk.render_activity(sc, cairo_context, float(x), float(y), 1, 1)
            y += 3

        sc.restore()
        return True


class Window(Gtk.Window):
    """The main dialog to use."""

    __gsignals__ = {'response': (GObject.SIGNAL_RUN_LAST,
                                 GObject.TYPE_NONE,
                                 (GObject.TYPE_INT,)),
                    }

    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_title('Ubuntu One')
        self.set_default_icon_name('ubuntuone-installer')
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER)

        vbox = Gtk.VBox()
        vbox.set_spacing(24)
        self.add(vbox)
        vbox.show()

        self.__header = Gtk.HBox()
        self.__header.set_border_width(12)
        self.__header.set_spacing(64)
        vbox.pack_start(self.__header, False, False, 0)
        self.__header.show()

        self.__hlabelbox = Gtk.VBox()
        self.__hlabelbox.set_spacing(12)
        self.__header.pack_start(self.__hlabelbox, True, True, 0)
        self.__hlabelbox.show()

        self.__hlabel = Gtk.Label((u'<span size="xx-large">{}</span>').format(
                _(u'Install Ubuntu One')))
        self.__hlabel.set_use_markup(True)
        self.__hlabel.set_alignment(0.0, 0.0)
        self.__hlabelbox.pack_start(self.__hlabel, False, False, 0)
        self.__hlabel.show()

        self.__hlabel2 = Gtk.Label((u'<span size="large">{}</span>').format(
                _(u'Discover the freedom of your personal cloud')))
        self.__hlabel2.set_use_markup(True)
        self.__hlabel2.set_alignment(0.0, 0.0)
        self.__hlabelbox.pack_start(self.__hlabel2, False, False, 0)
        self.__hlabel2.show()

        self.__hlogo = Gtk.Image()
        self.__header.pack_end(self.__hlogo, False, False, 0)
        self.__hlogo.show()

        logo = self.__find_data_file('u1logo.png')
        if logo:
            self.__hlogo.set_from_file(logo)

        self.__notebook = Gtk.Notebook()
        self.__notebook.set_show_tabs(False)
        self.__notebook.set_show_border(False)
        self.__notebook.set_scrollable(False)
        self.__notebook.popup_disable()
        #self.__notebook.set_size_request(734, 240)

        self.__info_page = self.__construct_info_page()
        self.__notebook.append_page(self.__info_page, None)
        self.__info_page.show()

        # Our progressbar widget
        self.__apt_progress = aptgtk.AptProgressBar()

        self.__progress_page = self.__construct_progress_page()
        self.__notebook.append_page(self.__progress_page, None)
        self.__progress_page.show()

        vbox.pack_start(self.__notebook, False, False, 0)
        self.__notebook.show()

        self.__action_area = Gtk.HButtonBox()
        self.__action_area.set_border_width(12)
        self.__action_area.set_spacing(12)
        self.__action_area.set_layout(Gtk.ButtonBoxStyle.END)
        vbox.pack_end(self.__action_area, False, True, 0)
        self.__action_area.show()

        self.__cancel_button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
        self.__cancel_button.connect('clicked', lambda x: self.emit(
                'response', Gtk.ResponseType.CANCEL))
        self.__action_area.add(self.__cancel_button)
        self.__cancel_button.show()

        self.__main_button = Gtk.Button.new_with_mnemonic('I_nstall')
        self.__main_button.set_image(Gtk.Image.new_from_stock(
                Gtk.STOCK_OK, Gtk.IconSize.BUTTON))
        self.__main_button.connect('clicked', lambda x: self.emit(
                'response', Gtk.ResponseType.OK))
        self.__action_area.add(self.__main_button)
        self.__main_button.grab_focus()
        self.__main_button.show()

        self.__lm_button = Gtk.LinkButton.new_with_label(
            'https://one.ubuntu.com/', 'Learn more')
        self.__action_area.add(self.__lm_button)
        self.__action_area.set_child_secondary(self.__lm_button, True)
        self.__lm_button.show()

        self.connect('destroy', self.destroyed)
        self.connect('response', self.__got_response)
        self.connect('delete-event', lambda x, y: self.emit(
                        'response', Gtk.ResponseType.DELETE_EVENT))

        self.client = aptclient.AptClient()

    def __find_data_file(self, filename):
        """Find the full path for the specified data file."""
        path = os.path.join(os.getcwd(), 'data', filename)
        if os.path.exists(path):
            return path

        path = os.path.join(os.getcwd(), os.path.pardir, 'data', filename)
        if os.path.exists(path):
            return os.path.abspath(path)

        path = os.path.join(os.getcwd(), os.path.pardir, os.path.pardir,
                            'data', filename)
        if os.path.exists(path):
            return os.path.abspath(path)

        for folder in GLib.get_system_data_dirs():
            path = os.path.join(folder, 'ubuntuone-installer', filename)
            if os.path.exists(path):
                return path

    def __got_response(self, dialog, response):
        """Handle the dialog response actions."""
        if response in [Gtk.ResponseType.CANCEL,
                        Gtk.ResponseType.DELETE_EVENT]:
            self.destroy()
            Gtk.main_quit()
            return
        elif response == Gtk.ResponseType.OK:
            self.__do_install()

    def __construct_info_page(self):
        """Build the initial info page."""
        page = Gtk.HBox()
        page.set_border_width(12)
        page.set_spacing(12)
        page.show()

        # Get the width of a larger character in pixels
        layout = page.create_pango_layout(u'W')
        (width, height) = layout.get_size()
        width = width / Pango.SCALE
        height = height / Pango.SCALE

        table = Gtk.Table(3, 5, False)
        table.set_row_spacings(12)
        table.set_col_spacings(12)
        page.pack_start(table, True, True, 24)
        table.show()

        label = Gtk.Label(u'<big>{}</big>'.format(_(u'Sync')))
        label.set_use_markup(True)
        table.attach_defaults(label, 0, 1, 0, 1)
        label.show()

        image = Gtk.Image()
        table.attach_defaults(image, 0, 1, 1, 2)
        image.show()
        path = self.__find_data_file('sync.png')
        if path:
            image.set_from_file(path)

        # Get the width in chars to set max for description labels
        width_chars = (image.get_pixbuf().get_width() / width) * 2.5

        label = Gtk.Label(u'<small>{}</small>'.format(
                _(u'Sync files across your devices.')))
        label.set_max_width_chars(width_chars)
        label.set_width_chars(width_chars)
        label.set_use_markup(True)
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.0)
        label.set_justify(Gtk.Justification.CENTER)
        table.attach_defaults(label, 0, 1, 2, 3)
        label.show()

        separator = VSeparator()
        table.attach_defaults(separator, 1, 2, 0, 3)
        separator.show()

        label = Gtk.Label(u'<big>{}</big>'.format(_(u'Stream')))
        label.set_use_markup(True)
        table.attach_defaults(label, 2, 3, 0, 1)
        label.show()

        image = Gtk.Image()
        table.attach_defaults(image, 2, 3, 1, 2)
        image.show()
        path = self.__find_data_file('stream.png')
        if path:
            image.set_from_file(path)

        label = Gtk.Label(u'<small>{}</small>'.format(
               _(u'Stream your music on the move and offline.')))
        label.set_max_width_chars(width_chars)
        label.set_width_chars(width_chars)
        label.set_use_markup(True)
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.0)
        label.set_justify(Gtk.Justification.CENTER)
        table.attach_defaults(label, 2, 3, 2, 3)
        label.show()

        separator = VSeparator()
        table.attach_defaults(separator, 3, 4, 0, 3)
        separator.show()

        label = Gtk.Label(u'<big>{}</big>'.format(_(u'Share')))
        label.set_use_markup(True)
        table.attach_defaults(label, 4, 5, 0, 1)
        label.show()

        image = Gtk.Image()
        table.attach_defaults(image, 4, 5, 1, 2)
        image.show()
        path = self.__find_data_file('share.png')
        if path:
            image.set_from_file(path)

        label = Gtk.Label(u'<small>{}</small>'.format(
                _(u'Share with colleagues, friends, and family.')))
        label.set_max_width_chars(width_chars)
        label.set_width_chars(width_chars)
        label.set_use_markup(True)
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.0)
        label.set_justify(Gtk.Justification.CENTER)
        table.attach_defaults(label, 4, 5, 2, 3)
        label.show()

        return page

    def __construct_progress_page(self):
        """Build the install progress page."""
        page = Gtk.VBox()
        page.set_border_width(24)
        page.set_spacing(6)
        page.show()

        label = Gtk.Label(_(u'Ubuntu One is installing…'))
        label.set_alignment(0.0, 0.0)
        page.pack_start(label, False, True, 0)
        label.show()

        page.pack_start(self.__apt_progress, False, True, 0)
        self.__apt_progress.show()

        return page

    def __get_series(self):
        """Get the series we're running on."""
        on_ubuntu = False
        series = None

        def get_value(keypair):
            return keypair.split('=')[1].strip()

        try:
            with open('/etc/lsb-release', 'r') as f:
                for line in f.readlines():
                    if line.startswith('DISTRIB_ID'):
                        on_ubuntu = get_value(line) == u'Ubuntu'
                    if line.startswith('DISTRIB_CODENAME'):
                        series = get_value(line)
            if not on_ubuntu or series is None:
                raise UnsupportedDistribution(
                    'This distribution is not supported by Ubuntu One.')
        except (OSError, IOError, UnsupportedDistribution), error:
            self.__got_error(error)

        return series

    def __got_error(self, error):
        """Got an error trying to set up Ubuntu One."""
        print error
        Gtk.main_quit()

    @inline_callbacks
    def __install_u1(self, *args, **kwargs):
        """Install the packages."""
        self.__apt_progress.set_fraction(0.0)

        def finished(*args, **kwargs):
            GLib.spawn_command_line_async('ubuntuone-control-panel-gtk')
            Gtk.main_quit()

        transaction = yield self.client.install_packages(
            package_names=['banshee-extension-ubuntuonemusicstore',
                           'ubuntuone-client-gnome',
                           'ubuntuone-control-panel-gtk',
                           'ubuntuone-couch',
                           ])
        transaction.connect('finished', finished)
        self.__apt_progress.set_transaction(transaction)
        transaction.run()

    @inline_callbacks
    def __update_cache(self, *args, **kwargs):
        """Update the cache."""
        self.__apt_progress.set_fraction(0.0)
        transaction = yield self.client.update_cache(
            sources_list='ubuntuone-stable-ppa.list')
        transaction.connect('finished', self.__install_u1)
        self.__apt_progress.set_transaction(transaction)
        transaction.run()

    @inline_callbacks
    def __add_stable_ppa(self):
        """Add the Ubuntu One 'stable' PPA to apt."""
        transaction = yield self.client.add_repository(
            src_type='deb',
            uri='http://ppa.launchpad.net/ubuntuone/stable/ubuntu',
            dist=self.__get_series(),
            comps=['main'],
            comment='added by Ubuntu One installer',
            sourcesfile='ubuntuone-stable-ppa.list')
        transaction.connect('finished', self.__update_cache)
        self.__apt_progress.set_transaction(transaction)
        transaction.run()

    def __do_install(self):
        """Do the install."""
        # Hide the buttons
        self.__cancel_button.hide()
        self.__main_button.hide()

        # Switch to the progress page
        self.__notebook.set_current_page(1)

        self.__update_cache()

    @property
    def active_page(self):
        """Get the active page."""
        return self.__notebook.get_current_page()

    def response(self, response):
        """Emit the response signal with the value response."""
        self.emit('response', int(response))

    def run(self):
        """Show the dialog and do what's necessary."""
        self.show()
