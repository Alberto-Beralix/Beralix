#!/usr/bin/python

## system-config-printer

## Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011 Red Hat, Inc.
## Authors:
##  Tim Waugh <twaugh@redhat.com>
##  Florian Festi <ffesti@redhat.com>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# config is generated from config.py.in by configure
import config

import authconn
import cupshelpers

import errno
import sys, os, tempfile, time, traceback, re, httplib
import locale
import string
import subprocess
import thread
from timedops import *
import dbus
import gtk

import cups

try:
    import pysmb
    PYSMB_AVAILABLE=True
except:
    PYSMB_AVAILABLE=False

import cupshelpers, options
import gobject
from gui import GtkGUI
from optionwidgets import OptionWidget
from debug import *
import probe_printer

try:
    # label_set_autowrap()
    import slip.gtk
except:
    import gtk_label_autowrap

import urllib
from smburi import SMBURI
from errordialogs import *
from PhysicalDevice import PhysicalDevice
import gtkspinner
import firewall
import asyncconn
import ppdsloader
import dnssdresolve

from gettext import gettext as _

TEXT_adjust_firewall = _("The firewall may need adjusting in order to "
                         "detect network printers.  Adjust the "
                         "firewall now?")

def validDeviceURI (uri):
    """Returns True is the provided URI is valid."""
    (scheme, rest) = urllib.splittype (uri)
    if scheme == None or scheme == '':
        return False
    return True

# Both the printer properties window and the new printer window
# need to be able to drive 'class members' selections.
def moveClassMembers(treeview_from, treeview_to):
    selection = treeview_from.get_selection()
    model_from, rows = selection.get_selected_rows()
    rows = [gtk.TreeRowReference(model_from, row) for row in rows]

    model_to = treeview_to.get_model()

    for row in rows:
        path = row.get_path()
        iter = model_from.get_iter(path)
        row_data = model_from.get(iter, 0)
        model_to.append(row_data)
        model_from.remove(iter)

def getCurrentClassMembers(treeview):
    model = treeview.get_model()
    iter = model.get_iter_root()
    result = []
    while iter:
        result.append(model.get(iter, 0)[0])
        iter = model.iter_next(iter)
    result.sort()
    return result

def checkNPName(printers, name):
    if not name: return False
    name = unicode (name.lower())
    for printer in printers.values():
        if not printer.discovered and printer.name.lower()==name:
            return False
    return True

def ready (win, cursor=None):
    try:
        gdkwin = win.window
        if gdkwin:
            gdkwin.set_cursor (cursor)
            while gtk.events_pending ():
                gtk.main_iteration ()
    except:
        nonfatalException ()

def busy (win):
    ready (win, gtk.gdk.Cursor(gtk.gdk.WATCH))

def on_delete_just_hide (widget, event):
    widget.hide ()
    return True # stop other handlers

def _singleton (x):
    """If we don't know whether getPPDs() or getPPDs2() was used, this
    function can unwrap an item from a list in either case."""
    if isinstance (x, list):
        return x[0]
    return x

class NewPrinterGUI(GtkGUI):

    __gsignals__ = {
        'destroy':          (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, []),
        'printer-added' :   (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                             [gobject.TYPE_STRING]),
        'printer-modified': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                             [gobject.TYPE_STRING, # printer name
                              gobject.TYPE_BOOLEAN]), # PPD modified?
        'dialog-canceled':  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, [])
        }

    new_printer_device_tabs = {
        "parallel" : 0, # empty tab
        "usb" : 0,
        "bluetooth" : 0,
        "hal" : 0,
        "beh" : 0,
        "hp" : 0,
        "hpfax" : 0,
        "dnssd" : 0,
        "socket": 2,
        "lpd" : 3,
        "scsi" : 4,
        "serial" : 5,
        "smb" : 6,
        "network": 7,
        }

    DOWNLOADABLE_ONLYPPD=True

    def __init__(self):
        gobject.GObject.__init__ (self)
        self.language = locale.getlocale (locale.LC_MESSAGES)

        self.options = {} # keyword -> Option object
        self.changed = set()
        self.conflicts = set()
        self.device = None
        self.ppd = None
        self.remotecupsqueue = False
        self.exactdrivermatch = False
        self.installable_options = False
        self.ppdsloader = None
        self.jockey_installed_files = []
        self.printers = {} # set in init()

        # Synchronisation objects.
        self.drivers_lock = thread.allocate_lock()

        self.getWidgets({"NewPrinterWindow":
                             ["NewPrinterWindow",
                              "ntbkNewPrinter",
                              "btnNPBack",
                              "btnNPForward",
                              "btnNPApply",
                              "imgProcessWorking",
                              "entNPName",
                              "entNPDescription",
                              "entNPLocation",
                              "tvNPDevices",
                              "ntbkNPType",
                              "lblNPDeviceDescription",
                              "expNPDeviceURIs",
                              "tvNPDeviceURIs",
                              "cmbNPTSerialBaud",
                              "cmbNPTSerialParity",
                              "cmbNPTSerialBits",
                              "cmbNPTSerialFlow",
                              "btnNPTLpdProbe",
                              "entNPTLpdHost",
                              "entNPTLpdQueue",
                              "entNPTJetDirectHostname",
                              "entNPTJetDirectPort",
                              "entSMBURI",
                              "btnSMBBrowse",
                              "tblSMBAuth",
                              "rbtnSMBAuthPrompt",
                              "rbtnSMBAuthSet",
                              "entSMBUsername",
                              "entSMBPassword",
                              "btnSMBVerify",
                              "entNPTNetworkHostname",
                              "btnNetworkFind",
                              "lblNetworkFindSearching",
                              "lblNetworkFindNotFound",
                              "entNPTDevice",
                              "tvNCMembers",
                              "tvNCNotMembers",
                              "btnNCAddMember",
                              "btnNCDelMember",
                              "ntbkPPDSource",
                              "rbtnNPPPD",
                              "tvNPMakes",
                              "rbtnNPFoomatic",
                              "filechooserPPD",
                              "rbtnNPDownloadableDriverSearch",
                              "entNPDownloadableDriverSearch",
                              "btnNPDownloadableDriverSearch",
                              "cmbNPDownloadableDriverFoundPrinters",
                              "tvNPModels",
                              "tvNPDrivers",
                              "rbtnChangePPDasIs",
                              "rbtnChangePPDKeepSettings",
                              "scrNPInstallableOptions",
                              "vbNPInstallOptions",
                              "tvNPDownloadableDrivers",
                              "ntbkNPDownloadableDriverProperties",
                              "lblNPDownloadableDriverSupplier",
                              "cbNPDownloadableDriverSupplierVendor",
                              "lblNPDownloadableDriverLicense",
                              "cbNPDownloadableDriverLicensePatents",
                              "cbNPDownloadableDriverLicenseFree",
                              "lblNPDownloadableDriverDescription",
                              "lblNPDownloadableDriverSupportContacts",
                              "hsDownloadableDriverPerfText",
                              "hsDownloadableDriverPerfLineArt",
                              "hsDownloadableDriverPerfGraphics",
                              "hsDownloadableDriverPerfPhoto",
                              "lblDownloadableDriverPerfTextUnknown",
                              "lblDownloadableDriverPerfLineArtUnknown",
                              "lblDownloadableDriverPerfGraphicsUnknown",
                              "lblDownloadableDriverPerfPhotoUnknown",
                              "frmNPDownloadableDriverLicenseTerms",
                              "tvNPDownloadableDriverLicense",
                              "rbtnNPDownloadLicenseYes",
                              "rbtnNPDownloadLicenseNo"],
                         "WaitWindow":
                             ["WaitWindow",
                              "lblWait"],
                         "SMBBrowseDialog":
                             ["SMBBrowseDialog",
                              "tvSMBBrowser",
                              "btnSMBBrowseOk"]},

                        domain=config.PACKAGE)

        # Fill in liststores for combo-box widgets
        for (widget,
             opts) in [(self.cmbNPTSerialBaud,
                        [[_("Default")],
                         [_("1200")],
                         [_("2400")],
                         [_("4800")],
                         [_("9600")],
                         [_("19200")],
                         [_("38400")],
                         [_("57600")],
                         [_("115200")]]),

                       (self.cmbNPTSerialParity,
                        [[_("Default")],
                         [_("None")],
                         [_("Odd")],
                         [_("Even")]]),

                       (self.cmbNPTSerialBits,
                        [[_("Default")],
                         [_("8")],
                         [_("7")]]),

                       (self.cmbNPTSerialFlow,
                        [[_("Default")],
                         [_("None")],
                         [_("XON/XOFF (Software)")],
                         [_("RTS/CTS (Hardware)")],
                         [_("DTR/DSR (Hardware)")]]),

                       ]:
            model = gtk.ListStore (gobject.TYPE_STRING)
            for row in opts:
                model.append (row=row)

            cell = gtk.CellRendererText ()
            widget.pack_start (cell, True)
            widget.add_attribute (cell, 'text', 0)
            widget.set_model (model)

        # Set up some lists
        m = gtk.SELECTION_MULTIPLE
        s = gtk.SELECTION_SINGLE
        b = gtk.SELECTION_BROWSE
        for name, model, treeview, selection_mode in (
            (_("Members of this class"), gtk.ListStore(str),
             self.tvNCMembers, m),
            (_("Others"), gtk.ListStore(str), self.tvNCNotMembers, m),
            (_("Devices"), gtk.ListStore(str), self.tvNPDevices, s),
            (_("Connections"), gtk.ListStore(str), self.tvNPDeviceURIs, s),
            (_("Makes"), gtk.ListStore(str, str), self.tvNPMakes,s),
            (_("Models"), gtk.ListStore(str, str), self.tvNPModels,s),
            (_("Drivers"), gtk.ListStore(str), self.tvNPDrivers,s),
            (_("Downloadable Drivers"), gtk.ListStore(str),
             self.tvNPDownloadableDrivers, b),
            ):

            cell = gtk.CellRendererText()
            column = gtk.TreeViewColumn(name, cell, text=0)
            treeview.set_model(model)
            treeview.append_column(column)
            treeview.get_selection().set_mode(selection_mode)

        # Since some dialogs are reused we can't let the delete-event's
        # default handler destroy them
        self.SMBBrowseDialog.connect ("delete-event", on_delete_just_hide)
        self.WaitWindow_handler = self.WaitWindow.connect ("delete-event",
                                                           on_delete_just_hide)

        try:
            slip.gtk.label_set_autowrap(self.NewPrinterWindow)
        except: # no slip.gtk module
            gtk_label_autowrap.set_autowrap(self.NewPrinterWindow)

        self.ntbkNewPrinter.set_show_tabs(False)
        self.ntbkPPDSource.set_show_tabs(False)
        self.ntbkNPType.set_show_tabs(False)
        self.ntbkNPDownloadableDriverProperties.set_show_tabs(False)

        self.spinner = gtkspinner.Spinner (self.imgProcessWorking)
        self.spinner_count = 0

        # Set up OpenPrinting widgets.
        self.openprinting = cupshelpers.openprinting.OpenPrinting ()
        self.openprinting_query_handle = None
        combobox = self.cmbNPDownloadableDriverFoundPrinters
        cell = gtk.CellRendererText()
        combobox.pack_start (cell, True)
        combobox.add_attribute(cell, 'text', 0)
        if self.DOWNLOADABLE_ONLYPPD:
            for widget in [self.cbNPDownloadableDriverLicenseFree,
                           self.cbNPDownloadableDriverLicensePatents]:
                widget.hide ()

        def protect_toggle (toggle_widget):
            active = toggle_widget.get_data ('protect_active')
            if active != None:
                toggle_widget.set_active (active)

        for widget in [self.cbNPDownloadableDriverSupplierVendor,
                       self.cbNPDownloadableDriverLicenseFree,
                       self.cbNPDownloadableDriverLicensePatents]:
            widget.connect ('clicked', protect_toggle)

        for widget in [self.hsDownloadableDriverPerfText,
                       self.hsDownloadableDriverPerfLineArt,
                       self.hsDownloadableDriverPerfGraphics,
                       self.hsDownloadableDriverPerfPhoto]:
            widget.connect ('change-value',
                            lambda x, y, z: True)

        # Device list
        slct = self.tvNPDevices.get_selection ()
        slct.set_select_function (self.device_select_function)
        self.tvNPDevices.set_row_separator_func (self.device_row_separator_fn)
        self.tvNPDevices.connect ("row-activated", self.device_row_activated)

        # Devices expander
        self.expNPDeviceURIs.connect ("notify::expanded",
                                      self.on_expNPDeviceURIs_expanded)
        self.expNPDeviceURIs.set_expanded(1)

        # SMB browser
        self.smb_store = gtk.TreeStore (gobject.TYPE_PYOBJECT)
        self.btnSMBBrowse.set_sensitive (PYSMB_AVAILABLE)
        if not PYSMB_AVAILABLE:
            self.btnSMBBrowse.set_tooltip_text (_("Browsing not available "
                                                  "(pysmbc not installed)"))

        self.tvSMBBrowser.set_model (self.smb_store)

        # SMB list columns
        col = gtk.TreeViewColumn (_("Share"))
        cell = gtk.CellRendererText ()
        col.pack_start (cell, False)
        col.set_cell_data_func (cell, self.smbbrowser_cell_share)
        self.tvSMBBrowser.append_column (col)

        col = gtk.TreeViewColumn (_("Comment"))
        cell = gtk.CellRendererText ()
        col.pack_start (cell, False)
        col.set_cell_data_func (cell, self.smbbrowser_cell_comment)
        self.tvSMBBrowser.append_column (col)

        slct = self.tvSMBBrowser.get_selection ()
        slct.set_select_function (self.smb_select_function)

        self.SMBBrowseDialog.set_transient_for(self.NewPrinterWindow)

        self.tvNPDrivers.set_has_tooltip(True)
        self.tvNPDrivers.connect("query-tooltip", self.on_NPDrivers_query_tooltip)

        ppd_filter = gtk.FileFilter()
        ppd_filter.set_name(_("PostScript Printer Description files (*.ppd, *.PPD, *.ppd.gz, *.PPD.gz, *.PPD.GZ)"))
        ppd_filter.add_pattern("*.ppd")
        ppd_filter.add_pattern("*.PPD")
        ppd_filter.add_pattern("*.ppd.gz")
        ppd_filter.add_pattern("*.PPD.gz")
        ppd_filter.add_pattern("*.PPD.GZ")
        self.filechooserPPD.add_filter(ppd_filter)

        ppd_filter = gtk.FileFilter()
        ppd_filter.set_name(_("All files (*)"))
        ppd_filter.add_pattern("*")
        self.filechooserPPD.add_filter(ppd_filter)
        debugprint ("+%s" % self)

    def __del__ (self):
        debugprint ("-%s" % self)

    def do_destroy (self):
        debugprint ("DESTROY: %s" % self)
        if self.SMBBrowseDialog:
            self.SMBBrowseDialog.destroy ()
            self.SMBBrowseDialog = None

        if self.NewPrinterWindow:
            self.NewPrinterWindow.destroy ()
            self.NewPrinterWindow = None

        if self.WaitWindow:
            self.WaitWindow.destroy ()
            self.WaitWindow = None

    def inc_spinner_task (self):
        if self.spinner_count == 0:
            self.imgProcessWorking.show ()
            self.spinner.start ()

        self.spinner_count += 1

    def dec_spinner_task (self):
        self.spinner_count -= 1
        if self.spinner_count == 0:
            self.imgProcessWorking.hide ()
            self.spinner.stop ()

    def show_IPP_Error (self, exception, message):
        return show_IPP_Error (exception, message, parent=self.NewPrinterWindow)

    def option_changed(self, option):
        if option.is_changed():
            self.changed.add(option)
        else:
            self.changed.discard(option)

        if option.conflicts:
            self.conflicts.add(option)
        else:
            self.conflicts.discard(option)
        self.setDataButtonState()

        return

    def setDataButtonState(self):
        self.btnNPForward.set_sensitive(not bool(self.conflicts))

    def makeNameUnique(self, name):
        """Make a suggested queue name valid and unique."""
        name = name.replace (" ", "-")
        name = name.replace ("/", "-")
        name = name.replace ("#", "-")
        if not checkNPName (self.printers, name):
            suffix=2
            while not checkNPName (self.printers, name + "-" + str (suffix)):
                suffix += 1
                if suffix == 100:
                    break
            name += "-" + str (suffix)
        return name

    def destroy (self):
        self.emit ('destroy')

    def init(self, dialog_mode, device_uri=None, name=None, ppd=None,
             devid="", host=None, encryption=None, parent=None, xid=0):
        if xid != 0:
            display = gtk.gdk.display_get_default ()
            parent = gtk.gdk.window_foreign_new_for_display (display, xid)
            debugprint ("Parent is %s" % parent)
            self.parent = parent
        else:
            self.parent = parent
            if not self.parent:
                self.NewPrinterWindow.set_focus_on_map (False)
            
        self.dialog_mode = dialog_mode
        self.orig_ppd = ppd
        self.devid = devid
        self._host = host
        self._encryption = encryption
        self._name = name
        if not host:
            self._host = cups.getServer ()
        if not encryption:
            self._encryption = cups.getEncryption ()

        self.options = {} # keyword -> Option object
        self.changed = set()
        self.conflicts = set()
        self.fetchDevices_conn = None
        self.ppds = None
        self.ppdsmatch_result = None
        self.printer_finder = None

        # Get a current list of printers so that we can know whether
        # the chosen name is unique.
        try:
            self.cups = authconn.Connection (parent=self.NewPrinterWindow,
                                             host=self._host,
                                             encryption=self._encryption)
        except cups.HTTPError, (s,):
            show_HTTP_Error (s, self.parent)
            return False
        except RuntimeError:
            show_HTTP_Error (-1, self.parent)
            return False
        except Exception, e:
            nonfatalException (e)
            return False

        try:
            self.printers = cupshelpers.getPrinters (self.cups)
        except cups.IPPError, (e, m):
            show_IPP_Error (e, m, parent=self.parent)
            return False

        # Initialise widgets.
        self.lblNetworkFindSearching.hide ()
        self.entNPTNetworkHostname.set_sensitive (True)
        self.entNPTNetworkHostname.set_text ('')
        self.btnNetworkFind.set_sensitive (True)
        self.lblNetworkFindNotFound.hide ()

        # Clear out any previous list of makes.
        model = self.tvNPMakes.get_model()
        model.clear()

        if device_uri == None and dialog_mode in ['printer_with_uri',
                                                  'device',
                                                  'ppd']:
            raise RuntimeError

        combobox = self.cmbNPDownloadableDriverFoundPrinters
        combobox.set_model (gtk.ListStore (str, str))
        self.entNPDownloadableDriverSearch.set_text ('')
        button = self.btnNPDownloadableDriverSearch
        label = button.get_children ()[0].get_children ()[0].get_children ()[1]
        self.btnNPDownloadableDriverSearch_label = label
        label.set_text (_("Search"))

        if self.dialog_mode in ("printer", "printer_with_uri", "class"):
            if self.dialog_mode == "class":
                name_proto = "class"
            else:
                name_proto = "printer"
            self.entNPName.set_text (self.makeNameUnique(name_proto))
            self.entNPName.grab_focus()
            for widget in [self.entNPLocation,
                           self.entNPDescription,
                           self.entSMBURI, self.entSMBUsername,
                           self.entSMBPassword]:
                widget.set_text('')

        if self.dialog_mode in ['printer_with_uri', 'ppd']:
            device_dict = { }
            self.device = cupshelpers.Device (device_uri, **device_dict)

        self.entNPTJetDirectPort.set_text('9100')
        self.rbtnSMBAuthPrompt.set_active(True)

        if xid != 0 and self.parent:
            self.NewPrinterWindow.show_now()
            self.NewPrinterWindow.window.set_transient_for (self.parent)

        if self.dialog_mode == "printer":
            self.NewPrinterWindow.set_title(_("New Printer"))
            # Start on devices page (1, not 0)
            self.ntbkNewPrinter.set_current_page(1)
            self.fillDeviceTab()
            self.rbtnNPFoomatic.set_active (True)
            self.on_rbtnNPFoomatic_toggled(self.rbtnNPFoomatic)

        elif self.dialog_mode == "class":
            self.NewPrinterWindow.set_title(_("New Class"))
            self.fillNewClassMembers()
            # Start on name page
            self.ntbkNewPrinter.set_current_page(0)
        elif self.dialog_mode == "device":
            self.NewPrinterWindow.set_title(_("Change Device URI"))
            self.ntbkNewPrinter.set_current_page(1)
            self.fillDeviceTab(device_uri)
        elif self.dialog_mode == "ppd" or \
            self.dialog_mode == "printer_with_uri":
            if self.dialog_mode == "ppd":
                self.NewPrinterWindow.set_title(_("Change Driver"))
            else:
                self.NewPrinterWindow.set_title(_("New Printer"))

            # We'll need to know the Device ID for this device.
            if self.dialog_mode == "ppd" and not self.devid:
                scheme = str(device_uri.split (":", 1)[0])
                schemes = [scheme]
                if scheme in ["socket", "lpd", "ipp"]:
                    schemes.extend (["snmp", "dnssd"])
                self.fetchDevices_conn = asyncconn.Connection ()
                self.fetchDevices_conn._begin_operation (_("fetching device "
                                                           "list"))
                self.inc_spinner_task ()
                cupshelpers.getDevices (self.fetchDevices_conn,
                                        include_schemes=schemes,
                                        reply_handler=self.change_ppd_got_devs,
                                        error_handler=self.change_ppd_got_devs)

            self.ntbkNewPrinter.set_current_page(2)
            self.rbtnNPFoomatic.set_active (True)
            self.on_rbtnNPFoomatic_toggled(self.rbtnNPFoomatic)
            self.rbtnChangePPDKeepSettings.set_active(True)

            if self.dialog_mode == "printer_with_uri":
                p = ppdsloader.PPDsLoader (device_id=devid,
                                           device_uri=device_uri,
                                           parent=self.NewPrinterWindow,
                                           host=self._host,
                                           encryption=self._encryption)
                self.ppdsloader = p
                p.connect ('finished',self.change_ppd_have_devs_and_ppds)
                p.run ()

            self.auto_make = ""
            self.auto_model = ""
            self.auto_driver = None

        if xid == 0 and self.parent:
            self.NewPrinterWindow.set_transient_for (parent)

        self.NewPrinterWindow.show()
        self.setNPButtons()
        return True

    def on_ppdsloader_finished_initial (self, ppdsloader):
        """
        This method is called when the PPDs loader has finished
        loading PPDs in preparation for the first screen the user
        sees.  We are either changing the PPD of an existing queue
        (dialog_mode=="ppd") or else we are setting up a queue for a
        given device URI (dialog_mode=="printer_with_uri").
        """

        self._getPPDs_reply (ppdsloader)
        if not self.ppds:
            return

    def change_ppd_got_devs (self, conn, result):
        self.fetchDevices_conn._end_operation ()
        self.fetchDevices_conn.destroy ()
        self.fetchDevices_conn = None
        self.dec_spinner_task ()
        if isinstance (result, Exception):
            current_devices = {}
        else:
            current_devices = result

        devid = None
        mm = None
        if self.devid != "":
            devid = self.devid
        else:
            device = current_devices.get (self.device.uri)
            if device:
                devid = device.id
                mm = device.make_and_model
                self.device = device

        # We'll also need the list of PPDs.
        self.ppdsloader = ppdsloader.PPDsLoader (device_id=devid,
                                                 device_uri=self.device.uri,
                                                 device_make_and_model=mm,
                                                 parent=self.NewPrinterWindow,
                                                 host=self._host,
                                                 encryption=self._encryption,
                                                 language=self.language[0])
        self.ppdsloader.connect ('finished',
                                 self.change_ppd_have_devs_and_ppds)
        self.ppdsloader.run ()

    def change_ppd_have_devs_and_ppds (self, ppdsloader):
        self._getPPDs_reply (ppdsloader)
        if not self.ppds:
            self.setNPButtons()
            return

        self.exactdrivermatch = False
        self.id_matched_ppdnames = []
        if self.ppdsmatch_result != None:
            try:
                (fit, ppdnamelist) = self.ppdsmatch_result
                self.id_matched_ppdnames = ppdnamelist
                ppdname = ppdnamelist[0]
                status = fit[ppdname]
                ppddict = self.ppds.getInfoFromPPDName (ppdname)
                make_model = _singleton (ppddict['ppd-make-and-model'])
                (self.auto_make, self.auto_model) = \
                    cupshelpers.ppds.ppdMakeModelSplit (make_model)
                self.auto_driver = ppdname
                if (status.startswith ("exact") and
                    self.dialog_mode == "printer_with_uri"):
                    self.exactdrivermatch = True
                    self.fillMakeList()
                    self.ntbkNewPrinter.set_current_page(6)
                    self.nextNPTab(step = 0)
            except:
                nonfatalException ()
        elif self.orig_ppd:
            attr = self.orig_ppd.findAttr("NickName")
            if not attr:
                attr = self.orig_ppd.findAttr("ModelName")

            if attr and attr.value:
                value = attr.value
                if value.endswith (" (recommended)"):
                    value = value[:-14]

                mfgmdl = cupshelpers.ppds.ppdMakeModelSplit (value)
                (self.auto_make, self.auto_model) = mfgmdl

                # Search for ppdname with that make-and-model
                ppds = self.ppds.getInfoFromModel (self.auto_make,
                                                   self.auto_model)
                for ppd, info in ppds.iteritems ():
                    if _singleton (info.
                                   get ("ppd-make-and-model")) == value:
                        self.auto_driver = ppd
                        break
        else:
            # Special CUPS names for a raw queue.
            self.auto_make = 'Generic'
            self.auto_model = 'Raw Queue'

        self.fillMakeList()

    def on_ppdsloader_finished_next (self, ppdsloader):
        """
        This method is called when the PPDs loader has finished
        loading PPDs in preparation for the next screen the user will
        see, having clicked 'Forward'.  We are creating a new queue,
        and dialog_mode is either "printer" or "printer_with_uri".
        """

        self._getPPDs_reply (ppdsloader)
        if not self.ppds:
            return

        debugprint ("Loaded PPDs this time; try nextNPTab again...")
        self.nextNPTab()

    # get PPDs

    def _getPPDs_reply (self, ppdsloader):
        exc = ppdsloader.get_error ()
        if exc:
            try:
                raise exc
            except cups.IPPError, (e, m):
                show_IPP_Error (e, m, parent=self.NewPrinterWindow)
                return

        ppds = ppdsloader.get_ppds ()
        if ppds:
            self.ppds = ppds
            self.ppdsmatch_result = ppdsloader.get_ppdsmatch_result ()
            self.jockey_installed_files = ppdsloader.get_installed_files ()
        else:
            self.ppds = None
            self.ppdsmatch_result = None

        ppdsloader.destroy ()
        self.ppdsloader = None

    # Class members

    def fillNewClassMembers(self):
        model = self.tvNCMembers.get_model()
        model.clear()
        model = self.tvNCNotMembers.get_model()
        model.clear()
        try:
            self.printers = cupshelpers.getPrinters (self.cups)
        except cups.IPPError:
            self.printers = {}

        for printer in self.printers.keys():
            model.append((printer,))

    def on_btnNCAddMember_clicked(self, button):
        moveClassMembers(self.tvNCNotMembers, self.tvNCMembers)
        self.btnNPApply.set_sensitive(
            bool(getCurrentClassMembers(self.tvNCMembers)))
        button.set_sensitive(False)

    def on_btnNCDelMember_clicked(self, button):
        moveClassMembers(self.tvNCMembers, self.tvNCNotMembers)
        self.btnNPApply.set_sensitive(
            bool(getCurrentClassMembers(self.tvNCMembers)))
        button.set_sensitive(False)

    def on_tvNCMembers_cursor_changed(self, widget):
        selection = widget.get_selection()
        model_from, rows = selection.get_selected_rows()
        self.btnNCDelMember.set_sensitive(rows != [])

    def on_tvNCNotMembers_cursor_changed(self, widget):
        selection = widget.get_selection()
        model_from, rows = selection.get_selected_rows()
        self.btnNCAddMember.set_sensitive(rows != [])

    # Navigation buttons

    def on_NPCancel(self, widget, event=None):
        if self.fetchDevices_conn:
            self.fetchDevices_conn.destroy ()
            self.fetchDevices_conn = None
            self.dec_spinner_task ()

        if self.ppdsloader:
            self.ppdsloader.destroy ()
            self.ppds_loader = None

        if self.printer_finder:
            self.printer_finder.cancel ()
            self.printer_finder = None
            self.dec_spinner_task ()

        self.NewPrinterWindow.hide()
        if self.openprinting_query_handle != None:
            self.openprinting.cancelOperation (self.openprinting_query_handle)
            self.openprinting_query_handle = None

        self.device = None
        self.printers = {}
        self.emit ('dialog-canceled')
        return True

    def on_btnNPBack_clicked(self, widget):
        self.nextNPTab(-1)

    def on_btnNPForward_clicked(self, widget):
        self.nextNPTab()

    def nextNPTab(self, step=1):
        page_nr = self.ntbkNewPrinter.get_current_page()

        if self.dialog_mode == "class":
            order = [0, 4, 5]
        elif self.dialog_mode == "printer" or \
                self.dialog_mode == "printer_with_uri":
            busy (self.NewPrinterWindow)
            if page_nr == 1: # Device (first page)
                self.auto_make, self.auto_model = "", ""
                self.auto_driver = None
                self.device.uri = self.getDeviceURI()

                # Cancel the printer finder now as the user has
                # already selected their device.
                if self.printer_finder:
                    self.printer_finder.cancel ()
                    self.printer_finder = None
                    self.dec_spinner_task ()

                if (not self.device.id and
                    self.device.type in ["socket", "lpd", "ipp"]):
                    # This is a network printer whose model we don't yet know.
                    # Try to discover it.
                    self.getNetworkPrinterMakeModel ()

                uri = self.device.uri
                if uri and uri.startswith ("smb://"):
                    uri = SMBURI (uri=uri[6:]).sanitize_uri ()

                # Try to access the PPD, in this case our detected IPP
                # printer is a queue on a remote CUPS server which is
                # not automatically set up on our local CUPS server
                # (for example DNS-SD broadcasted queue from Mac OS X)
                self.remotecupsqueue = None
                res = re.search ("ipp://(\S+?)(:\d+|)/printers/(\S+)", uri)
                if res:
                    resg = res.groups()
                    if len (resg[1]) > 0:
                        port = int (resg[1][1:])
                    else:
                        port = 631
                    try:
                        conn = httplib.HTTPConnection(resg[0], port)
                        conn.request("GET", "/printers/%s.ppd" % resg[2])
                        resp = conn.getresponse()
                        if resp.status == 200: self.remotecupsqueue = resg[2]
                    except:
                        pass

                    # We also want to fetch the printer-info and
                    # printer-location attributes, to pre-fill those
                    # fields for this new queue.
                    try:
                        encryption = cups.HTTP_ENCRYPT_IF_REQUESTED
                        c = cups.Connection (host=resg[0],
                                             port=port,
                                             encryption=encryption)

                        r = ['printer-info', 'printer-location']
                        attrs = c.getPrinterAttributes (uri=uri,
                                                        requested_attributes=r)
                        info = attrs.get ('printer-info', '')
                        location = attrs.get ('printer-location', '')
                        if len (info) > 0:
                            self.entNPDescription.set_text (info)
                        if len (location) > 0:
                            self.device.location = location
                    except RuntimeError:
                        pass
                    except:
                        nonfatalException ()
                elif ((uri.startswith ("dnssd:") or uri.startswith("mdns:")) and
                      uri.find ("/cups") != -1 and
                      self.device.info):
                    # Remote CUPS queue discovered by "dnssd" CUPS backend
                    self.remotecupsqueue = self.device.info

                if not self.remotecupsqueue:
                    if self.ppds == None:
                        devid = self.device.id # ID of selected device
                        if not devid:
                            devid = self.devid # ID supplied at init()
                        if not devid:
                            devid = None

                        debugprint ("nextNPTab: need PPDs loaded")
                        p = ppdsloader.PPDsLoader (device_id=devid,
                                                   device_uri=uri,
                                                   parent=self.NewPrinterWindow,
                                                   host=self._host,
                                                   encryption=self._encryption)
                        self.ppdsloader = p
                        p.connect ('finished',self.on_ppdsloader_finished_next)
                        p.run ()
                        ready (self.NewPrinterWindow)
                        return

                if (hasattr (self.device, 'hp_scannable') and
                    self.device.hp_scannable and
                    not os.access ("/etc/sane.d/dll.d/hpaio", os.R_OK)):
                    try:
                        pk = installpackage.PackageKit ()
                        xid = self.NewPrinterWindow.window.xid
                        pk.InstallPackageName (xid, 0, "libsane-hpaio")
                    except:
                        pass

                ppdname = None
                self.id_matched_ppdnames = []
                try:
                    if self.remotecupsqueue:
                        # We have a remote CUPS queue, let the client queue
                        # stay raw so that the driver on the server gets used
                        ppdname = 'raw'
                        self.ppd = ppdname
                        name = self.remotecupsqueue
                        name = self.makeNameUnique (name)
                        self.entNPName.set_text (name)
                    elif (self.device.id or
                          (self.device.make_and_model and
                           self.device.make_and_model != "Unknown")):
                        if self.device.id:
                            id_dict = self.device.id_dict
                        else:
                            id_dict = {}
                            (id_dict["MFG"],
                             id_dict["MDL"]) = cupshelpers.ppds.\
                                 ppdMakeModelSplit (self.device.make_and_model)
                            id_dict["DES"] = ""
                            id_dict["CMD"] = []

                        fit = self.ppds.\
                            getPPDNamesFromDeviceID (id_dict["MFG"],
                                                     id_dict["MDL"],
                                                     id_dict["DES"],
                                                     id_dict["CMD"],
                                                     self.device.uri,
                                                     self.device.make_and_model)
                        ppdnamelist = self.ppds.\
                            orderPPDNamesByPreference (fit.keys (),
                                                       self.jockey_installed_files,
                                                       devid=id_dict, fit=fit)
                        self.id_matched_ppdnames = ppdnamelist
                        ppdname = ppdnamelist[0]
                        status = fit[ppdname]
                    else:
                        (status, ppdname) = self.ppds.\
                            getPPDNameFromDeviceID ("Generic",
                                                    "Printer",
                                                    "Generic Printer",
                                                    [],
                                                    self.device.uri)
                        status = "generic"

                    if ppdname and not self.remotecupsqueue:
                        ppddict = self.ppds.getInfoFromPPDName (ppdname)
                        make_model = _singleton (ppddict['ppd-make-and-model'])
                        (make, model) = \
                            cupshelpers.ppds.ppdMakeModelSplit (make_model)
                        self.auto_make = make
                        self.auto_model = model
                        self.auto_driver = ppdname
                        if (status == "exact" and \
                            self.dialog_mode != "ppd"):
                            self.exactdrivermatch = True
                        else:
                            self.exactdrivermatch = False
                except:
                    nonfatalException ()

                if not self.remotecupsqueue:
                    self.fillMakeList()
            elif page_nr == 3: # Model has been selected
                if not self.device.id:
                    # Choose an appropriate name when no Device ID
                    # is available, based on the model the user has
                    # selected.
                    try:
                        model, iter = self.tvNPModels.get_selection ().\
                                      get_selected ()
                        name = model.get(iter, 0)[0]
                        name = self.makeNameUnique (name)
                        self.entNPName.set_text (name)
                    except:
                        nonfatalException ()

            ready (self.NewPrinterWindow)
            if self.dialog_mode == "printer":
                if self.remotecupsqueue:
                    order = [1, 0]
                elif self.exactdrivermatch:
                    order = [1, 6, 0]
                elif self.rbtnNPFoomatic.get_active():
                    order = [1, 2, 3, 6, 0]
                elif self.rbtnNPPPD.get_active():
                    order = [1, 2, 6, 0]
                else:
                    # Downloadable driver
                    order = [1, 2, 7, 6, 0]
            else:
                if self.remotecupsqueue:
                    order = [0]
                elif self.exactdrivermatch:
                    order = [6, 0]
                elif self.rbtnNPFoomatic.get_active():
                    order = [2, 3, 6, 0]
                elif self.rbtnNPPPD.get_active():
                    order = [2, 6, 0]
                else:
                    # Downloadable driver
                    order = [2, 7, 6, 0]
        elif self.dialog_mode == "device":
            order = [1]
        elif self.dialog_mode == "ppd":
            if self.rbtnNPFoomatic.get_active():
                order = [2, 3, 5, 6]
            elif self.rbtnNPPPD.get_active():
                order = [2, 5, 6]
            else:
                # Downloadable driver
                order = [2, 7, 5, 6]

        next_page_nr = order[order.index(page_nr)+step]

        # fill Installable Options tab
        fetch_ppd = False
        try:
            if order.index (5) > -1:
                # There is a copy settings page in this set
                fetch_ppd = next_page_nr == 5 and step >= 0
        except ValueError:
            fetch_ppd = next_page_nr == 6 and step >= 0

        debugprint ("Will fetch ppd? %d" % fetch_ppd)
        if fetch_ppd:
            self.ppd = self.getNPPPD()
            self.installable_options = False
            if self.ppd == None:
                return

            # Prepare Installable Options screen.
            if isinstance(self.ppd, cups.PPD):
                self.fillNPInstallableOptions()
            else:
                # Put a label there explaining why the page is empty.
                ppd = self.ppd
                self.ppd = None
                self.fillNPInstallableOptions()
                self.ppd = ppd

            if not self.installable_options:
                if next_page_nr == 6:
                    # step over if empty
                    next_page_nr = order[order.index(next_page_nr)+1]

        # Step over empty Installable Options tab when moving backwards.
        if next_page_nr == 6 and not self.installable_options and step<0:
            next_page_nr = order[order.index(next_page_nr)-1]

        if step >= 0 and next_page_nr == 7: # About to show downloadable drivers
            if self.drivers_lock.locked ():
                # Still searching for drivers.
                self.lblWait.set_markup ('<span weight="bold" size="larger">' +
                                         _('Searching') + '</span>\n\n' +
                                         _('Searching for drivers'))
                self.WaitWindow.set_transient_for (self.NewPrinterWindow)
                self.WaitWindow.show ()
                busy (self.WaitWindow)
                busy (self.NewPrinterWindow)

                # Keep the UI refreshed while we wait for the drivers
                # query to complete.
                while self.drivers_lock.locked ():
                    while gtk.events_pending ():
                        gtk.main_iteration ()
                    time.sleep (0.1)

                ready (self.NewPrinterWindow)
                self.WaitWindow.hide ()

            self.fillDownloadableDrivers()

        if step >= 0 and next_page_nr == 0: # About to choose a name.
            # Suggest an appropriate name.
            name = None
            descr = None

            try:
                if (self.device.id and
                    not self.device.type in ("socket", "lpd", "ipp",
                                             "http", "https", "bluetooth")):
                    name = "%s %s" % (self.device.id_dict["MFG"], 
                                      self.device.id_dict["MDL"])
            except:
                nonfatalException ()

            try:
                if name == None and isinstance (self.ppd, cups.PPD):
                    mname = self.ppd.findAttr ("modelName").value
                    make, model = cupshelpers.ppds.ppdMakeModelSplit (mname)
                    if make and model:
                        name = "%s %s" % (make, model)
                    elif make or model:
                        name = "%s%s" % (make, model)
            except:
                nonfatalException ()

            if name:
                descr = name
            else:
                name = 'printer'

            name = self.makeNameUnique (name)
            self.entNPName.set_text (name)

            if self.entNPDescription.get_text () == '' and descr:
                self.entNPDescription.set_text (descr)

        self.ntbkNewPrinter.set_current_page(next_page_nr)

        self.setNPButtons()

    def setNPButtons(self):
        nr = self.ntbkNewPrinter.get_current_page()

        if self.dialog_mode == "device":
            self.btnNPBack.hide()
            self.btnNPForward.hide()
            self.btnNPApply.show()
            try:
                uri = self.getDeviceURI ()
                valid = validDeviceURI (uri)
            except AttributeError:
                # No device selected yet.
                valid = False
            self.btnNPApply.set_sensitive (valid)
            return

        if self.dialog_mode == "ppd":
            if nr == 5: # Apply
                if not self.installable_options:
                    # There are no installable options, so this is the
                    # last page.
                    debugprint ("No installable options")
                    self.btnNPForward.hide ()
                    self.btnNPApply.show ()
                else:
                    self.btnNPForward.show ()
                    self.btnNPApply.hide ()
                return
            elif nr == 6:
                self.btnNPForward.hide()
                self.btnNPApply.show()
                return
            else:
                self.btnNPForward.show()
                self.btnNPApply.hide()
            if nr == 2:
                self.btnNPBack.hide()
                self.btnNPForward.show()
                downloadable_selected = False
                if self.rbtnNPDownloadableDriverSearch.get_active ():
                    combobox = self.cmbNPDownloadableDriverFoundPrinters
                    iter = combobox.get_active_iter ()
                    if iter and combobox.get_model ().get_value (iter, 1):
                        downloadable_selected = True

                self.btnNPForward.set_sensitive(bool(
                        (self.rbtnNPFoomatic.get_active() and
                         self.tvNPMakes.get_cursor()[0] != None) or
                        self.filechooserPPD.get_filename() or
                        downloadable_selected))
                return
            else:
                self.btnNPBack.show()

        # class/printer

        if nr == 1: # Device
            valid = False
            try:
                uri = self.getDeviceURI ()
                valid = validDeviceURI (uri)
            except:
                pass
            self.btnNPForward.set_sensitive(valid)
            self.btnNPBack.hide ()
        else:
            self.btnNPBack.show()

        self.btnNPForward.show()
        self.btnNPApply.hide()

        if nr == 0: # Name
            self.btnNPBack.show()
            if self.dialog_mode == "printer" or \
                    self.dialog_mode == "printer_with_uri":
                self.btnNPForward.hide()
                self.btnNPApply.show()
                self.btnNPApply.set_sensitive(
                    checkNPName(self.printers, self.entNPName.get_text()))
            if self.dialog_mode == "class":
                # This is the first page for the New Class dialog, so
                # hide the Back button.
                self.btnNPBack.hide ()
            if self.dialog_mode == "printer_with_uri" and \
                    (self.remotecupsqueue or \
                         (self.exactdrivermatch and \
                              not self.installable_options)):
                self.btnNPBack.hide ()
        if nr == 2: # Make/PPD file
            downloadable_selected = False
            if self.rbtnNPDownloadableDriverSearch.get_active ():
                combobox = self.cmbNPDownloadableDriverFoundPrinters
                iter = combobox.get_active_iter ()
                if iter and combobox.get_model ().get_value (iter, 1):
                    downloadable_selected = True

            self.btnNPForward.set_sensitive(bool(
                self.rbtnNPFoomatic.get_active() or
                self.filechooserPPD.get_filename() or
                downloadable_selected))
            # If we have an auto-detected printer for which there was no
            # driver found, we have already the URI and so this step is
            # not needed in the wizard. This makes manufacturer?PPD selection
            # the firts step
            if self.dialog_mode == "printer_with_uri":
                self.btnNPBack.hide()
        if nr == 3: # Model/Driver
            model, iter = self.tvNPDrivers.get_selection().get_selected()
            self.btnNPForward.set_sensitive(bool(iter))
        if nr == 4: # Class Members
            self.btnNPForward.hide()
            self.btnNPApply.show()
            self.btnNPApply.set_sensitive(
                bool(getCurrentClassMembers(self.tvNCMembers)))
        if nr == 6: # Installable options
            if self.dialog_mode == "printer_with_uri" and \
                    self.exactdrivermatch:
                self.btnNPBack.hide ()
        if nr == 7: # Downloadable drivers
            if self.ntbkNPDownloadableDriverProperties.get_current_page() == 1:
                accepted = self.rbtnNPDownloadLicenseYes.get_active ()
            else:
                treeview = self.tvNPDownloadableDrivers
                model, iter = treeview.get_selection ().get_selected ()
                accepted = (iter != None)

            self.btnNPForward.set_sensitive(accepted)

    def on_entNPName_changed(self, widget):
        # restrict
        text = unicode (widget.get_text())
        new_text = text
        new_text = new_text.replace("/", "")
        new_text = new_text.replace("#", "")
        new_text = new_text.replace(" ", "")
        if text!=new_text:
            widget.set_text(new_text)
        if self.dialog_mode == "printer":
            self.btnNPApply.set_sensitive(
                checkNPName(self.printers, new_text))
        else:
            self.btnNPForward.set_sensitive(
                checkNPName(self.printers, new_text))

    def fetchDevices(self, network=False, current_uri=None):
        debugprint ("fetchDevices")
        self.inc_spinner_task ()

        # Search for Bluetooth printers together with the network printers
        # as the Bluetooth search takes rather long time
        network_schemes = ["dnssd", "snmp", "bluetooth"]
        error_handler = self.error_getting_devices
        if network == False:
            reply_handler = (lambda x, y:
                                 self.local_devices_reply (x, y,
                                                           current_uri))
            cupshelpers.getDevices (self.fetchDevices_conn,
                                    exclude_schemes=network_schemes,
                                    reply_handler=reply_handler,
                                    error_handler=error_handler)
        else:
            reply_handler = (lambda x, y:
                                 self.network_devices_reply (x, y,
                                                             current_uri))
            cupshelpers.getDevices (self.fetchDevices_conn,
                                    include_schemes=network_schemes,
                                    reply_handler=reply_handler,
                                    error_handler=error_handler)

    def error_getting_devices (self, conn, exc):
        # Just ignore the error.
        debugprint ("Error fetching devices: %s" % repr (exc))
        self.dec_spinner_task ()
        self.fetchDevices_conn._end_operation ()
        self.fetchDevices_conn.destroy ()
        self.fetchDevices_conn = None

    def local_devices_reply (self, conn, result, current_uri):
        self.dec_spinner_task ()

        # Now we've got the local devices, start a request for the
        # network devices.
        self.fetchDevices (network=True, current_uri=current_uri)

        # Add the local devices to the list.
        self.add_devices (result, current_uri)

    def network_devices_reply (self, conn, result, current_uri):
        self.dec_spinner_task ()
        self.fetchDevices_conn._end_operation ()
        self.fetchDevices_conn.destroy ()
        self.fetchDevices_conn = None

        # Add the network devices to the list.
        no_more = True
        need_resolving = {}
        for uri, device in result.iteritems ():
            if uri.startswith ("dnssd://"):
                need_resolving[uri] = device
                no_more = False

        for uri in need_resolving.keys ():
            del result[uri]

        self.add_devices (result, current_uri, no_more=no_more)

        if len (need_resolving) > 0:
            resolver = dnssdresolve.DNSSDHostNamesResolver (need_resolving)
            resolver.resolve (reply_handler=lambda devices:
                                  self.dnssd_resolve_reply (current_uri,
                                                            devices))

    def dnssd_resolve_reply (self, current_uri, devices):
        self.add_devices (devices, current_uri, no_more=True)

    def get_hpfax_device_id(self, faxuri):
        os.environ["URI"] = faxuri
        cmd = 'LC_ALL=C DISPLAY= hp-info -x -i -d"${URI}"'
        debugprint (faxuri + ": " + cmd)
        try:
            p = subprocess.Popen (cmd, shell=True, close_fds=True,
                                  stdin=file("/dev/null"),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            (stdout, stderr) = p.communicate ()
        except:
            # Problem executing command.
            return None

        faxtype = -1
        for line in stdout.split ("\n"):
            if line.find ("fax-type") == -1:
                continue
            res = re.search ("(\d+)", line)
            if res:
                resg = res.groups()
                faxtype = resg[0]
            if faxtype >= 0:
                break
        if faxtype <= 0:
            return None
        elif faxtype == 4:
            return 'MFG:HP;MDL:Fax 2;DES:HP Fax 2;'
        else:
            return 'MFG:HP;MDL:Fax;DES:HP Fax;'

    def get_hplip_scan_type_for_uri(self, uri):
        os.environ["URI"] = uri
        cmd = 'hp-query -k scan-type -d "${URI}"'
        debugprint (uri + ": " + cmd)
        try:
            p = subprocess.Popen (cmd, shell=True, close_fds=True,
                                  stdin=file("/dev/null"),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            (stdout, stderr) = p.communicate ()
            if p.returncode != 0:
                return None
        except:
            # Problem executing command.
            return None

        scan_type = stdout.strip ()
        fields = scan_type.split ("=", 1)
        if len (fields) < 2:
            return None

        value = fields[1]
        if value == '0':
            return None

        return value

    def get_hplip_uri_for_network_printer(self, host, mode):
        os.environ["HOST"] = host
        if mode == "print": mod = "-c"
        elif mode == "fax": mod = "-f"
        else: mod = "-c"
        cmd = 'hp-makeuri ' + mod + ' "${HOST}"'
        debugprint (host + ": " + cmd)
        uri = None
        try:
            p = subprocess.Popen (cmd, shell=True, close_fds=True,
                                  stdin=file("/dev/null"),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            (stdout, stderr) = p.communicate ()
            if p.returncode != 0:
                return None
        except:
            # Problem executing command.
            return None

        uri = stdout.strip ()
        return uri

    def getNetworkPrinterMakeModel(self, host=None, device=None):
        """
        Try to determine the make and model for the currently selected
        network printer, and store this in the data structure for the
        printer.
        Returns (hostname or None, uri or None).
        """
        uri = None
        if device == None:
            device = self.device
        # Determine host name/IP
        if host == None:
            s = device.uri.find ("://")
            if s != -1:
                s += 3
                e = device.uri[s:].find (":")
                if e == -1: e = device.uri[s:].find ("/")
                if e == -1: e = device.uri[s:].find ("?")
                if e == -1: e = len (device.uri)
                host = device.uri[s:s+e]
        # Try to get make and model via SNMP
        if host:
            os.environ["HOST"] = host
            cmd = '/usr/lib/cups/backend/snmp "${HOST}"'
            debugprint (host + ": " + cmd)
            stdout = None
            try:
                p = subprocess.Popen (cmd, shell=True, close_fds=True,
                                      stdin=file("/dev/null"),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
                (stdout, stderr) = p.communicate ()
                if p.returncode != 0:
                    stdout = None
            except:
                # Problem executing command.
                pass

            if stdout != None:
                line = stdout.strip ()
                words = probe_printer.wordsep (line)
                n = len (words)
                if n < 4:
                    words.extend (['','','',''])
                    words = words[:4]
                    n = 4
                elif n > 6:
                    words = words[:6]
                    n = 6

                if n == 6:
                    (device_class, uri, make_and_model,
                     info, device_id, device_location) = words
                elif n == 5:
                    (device_class, uri, make_and_model,
                     info, device_id) = words
                elif n == 4:
                    (device_class, uri, make_and_model, info) = words

                if n == 4:
                    # No Device ID given so we'll have to make one
                    # up.
                    debugprint ("No Device ID from snmp backend")
                    (mk, md) = cupshelpers.ppds.\
                        ppdMakeModelSplit (make_and_model)
                    device.id = "MFG:%s;MDL:%s;DES:%s %s;" % (mk, md,
                                                              mk, md)
                else:
                    debugprint ("Got Device ID: %s" % device_id)
                    device.id = device_id

                device.id_dict = cupshelpers.parseDeviceID (device.id)
                device.make_and_model = make_and_model
                device.info = info
                if n == 6:
                    device.location = device_location

        return (host, uri)

    def fillDeviceTab(self, current_uri=None):
        self.device_selected = -1
        model = gtk.TreeStore (gobject.TYPE_STRING,   # device-info
                               gobject.TYPE_PYOBJECT, # PhysicalDevice obj
                               gobject.TYPE_BOOLEAN)  # Separator?
        other = cupshelpers.Device('', **{'device-info' :_("Enter URI")})
        physother = PhysicalDevice (other)
        self.devices = [physother]
        uri_iter = model.append (None, row=[physother.get_info (),
                                            physother, False])
        network_iter = model.append (None, row=[_("Network Printer"),
                                                None,
                                                False])
        network_dict = { 'device-class': 'network',
                         'device-info': _("Find Network Printer") }
        network = cupshelpers.Device ('network', **network_dict)
        find_nw_iter = model.append (network_iter,
                                     row=[network_dict['device-info'],
                                          PhysicalDevice (network), False])
        model.insert_after (network_iter, find_nw_iter, row=['', None, True])
        self.devices_uri_iter = uri_iter
        self.devices_find_nw_iter = find_nw_iter
        self.devices_network_iter = network_iter
        self.devices_network_fetched = False
        self.tvNPDevices.set_model (model)
        self.entNPTDevice.set_text ('')
        self.expNPDeviceURIs.hide ()
        column = self.tvNPDevices.get_column (0)
        self.tvNPDevices.set_cursor ((0,), column)

        allowed = True
        self.current_uri = current_uri
        try:
            if (self._host == 'localhost' or
                self._host[0] == '/'):
                self.firewall = firewall.Firewall ()
                debugprint ("Examining firewall")
                self.firewall.read (reply_handler=self.on_firewall_read,
                                    error_handler=lambda x:
                                        self.start_fetching_devices())
                allowed = False
            else:
                # This is a remote server.  Nothing we can do about
                # the firewall there.
                allowed = True
        except (dbus.DBusException, Exception):
            nonfatalException ()

        if allowed:
            debugprint ("Fetching devices (no firewall service")
            self.start_fetching_devices ()

    def on_firewall_read (self, data):
        f = self.firewall
        allowed = True
        try:
            ipp_allowed = f.check_ipp_client_allowed ()
            mdns_allowed = f.check_mdns_allowed ()
            allowed = (ipp_allowed and mdns_allowed)

            secondary_text = TEXT_adjust_firewall + "\n\n"
            if not ipp_allowed:
                secondary_text += ("- " +
                                   _("Allow all incoming IPP Browse packets") +
                                   "\n")
                f.add_rule (f.ALLOW_IPP_CLIENT)
            if not mdns_allowed:
                secondary_text += ("- " +
                                   _("Allow all incoming mDNS traffic") + "\n")
                f.add_rule (f.ALLOW_MDNS)

            if not allowed:
                debugprint ("Asking for permission to adjust firewall:\n%s" %
                            secondary_text)
                dialog = gtk.MessageDialog (self.NewPrinterWindow,
                                            gtk.DIALOG_MODAL |
                                            gtk.DIALOG_DESTROY_WITH_PARENT,
                                            gtk.MESSAGE_QUESTION,
                                            gtk.BUTTONS_NONE,
                                            _("Adjust Firewall"))
                dialog.format_secondary_markup (secondary_text)
                dialog.add_buttons (_("Do It Later"), gtk.RESPONSE_NO,
                                    _("Adjust Firewall"), gtk.RESPONSE_YES)
                dialog.connect ('response', self.adjust_firewall_response)
                dialog.show ()
        except (dbus.DBusException, Exception):
            nonfatalException ()

        if allowed:
            debugprint ("Firewall all OK; fetching devices")
            self.start_fetching_devices ()

    def adjust_firewall_response (self, dialog, response):
        dialog.destroy ()
        if response == gtk.RESPONSE_YES:
            self.firewall.add_rule (self.firewall.ALLOW_IPP_SERVER)
            self.firewall.write ()

        debugprint ("Fetching devices after firewall dialog response")
        self.start_fetching_devices ()

    def start_fetching_devices (self):
        self.fetchDevices_conn = asyncconn.Connection ()
        self.fetchDevices_conn._begin_operation (_("fetching device list"))
        self.fetchDevices (network=False, current_uri=self.current_uri)
        del self.current_uri

    def add_devices (self, devices, current_uri, no_more=False):
        if current_uri:
            if devices.has_key (current_uri):
                current = devices.pop(current_uri)
            elif devices.has_key (current_uri.replace (":9100", "")):
                current_uri = current_uri.replace (":9100", "")
                current = devices.pop(current_uri)
            elif no_more:
                current = cupshelpers.Device (current_uri)
                current.info = "Current device"
            else:
                current_uri = None

        devices = devices.values()

        for device in devices:
            if device.type == "socket":
                # Remove default port to more easily find duplicate URIs
                device.uri = device.uri.replace (":9100", "")

        # Map generic URIs to something canonical
        def replace_generic (device):
            if device.uri == "hp:/no_device_found":
                device.uri = "hp"
            elif device.uri == "hpfax:/no_device_found":
                device.uri = "hpfax"
            return device

        devices = map (replace_generic, devices)

        # Mark duplicate URIs for deletion
        for i in range (len (devices) - 1):
            for j in range (i + 1, len (devices)):
                device1 = devices[i]
                device2 = devices[j]
                if device1.uri == "delete" or device2.uri == "delete":
                    continue
                if device1.uri == device2.uri:
                    # Keep the one with the longer (better) device ID
                    if (not device1.id):
                        device1.uri = "delete"
                    elif (not device2.id):
                        device2.uri = "delete"
                    elif (len (device1.id) < len (device2.id)):
                        device1.uri = "delete"
                    else:
                        device2.uri = "delete"
        devices = filter(lambda x: x.uri not in ("hp", "hpfax",
                                                 "hal", "beh",
                                                 "scsi", "http", "delete"),
                         devices)
        newdevices = []
        for device in devices:
            physicaldevice = PhysicalDevice (device)
            try:
                i = self.devices.index (physicaldevice)
                self.devices[i].add_device (device)
            except ValueError:
                self.devices.append (physicaldevice)
                newdevices.append (physicaldevice)

        self.devices.sort()
        if current_uri:
            current_device = PhysicalDevice (current)
            try:
                i = self.devices.index (current_device)
                self.devices[i].add_device (current)
                current_device = self.devices[i]
            except ValueError:
                self.devices.append (current_device)
                newdevices.append (current_device)
        else:
            current_device = None

        model = self.tvNPDevices.get_model ()

        network_iter = self.devices_network_iter
        find_nw_iter = self.devices_find_nw_iter
        for device in newdevices:
            devs = device.get_devices ()
            network = devs[0].device_class == 'network'
            info = device.get_info ()
            if device == current_device:
                info += _(" (Current)")
            row=[info, device, False]
            if network:
                if devs[0].uri != devs[0].type:
                    # An actual network printer device.  Put this at the top.
                    iter = model.insert_before (network_iter, find_nw_iter,
                                                row=row)

                    # If this is the currently selected device we need
                    # to expand the "Network Printer" row so that it
                    # is visible.
                    if device == current_device:
                        network_path = model.get_path (network_iter)
                        self.tvNPDevices.expand_row (network_path, False)
                else:
                    # Just a method of finding one.
                    iter = model.append (network_iter, row=row)
            else:
                # Insert this local device in order.
                network_path = model.get_path (network_iter)
                iter = model.get_iter_first ()
                while model.get_path (iter) != network_path:
                    physdev = model.get_value (iter, 1)
                    if physdev > device:
                        break

                    iter = model.iter_next (iter)

                iter = model.insert_before (None, iter, row=row)

            if device == current_device:
                device_select_path = model.get_path (iter)
                self.tvNPDevices.scroll_to_cell (device_select_path,
                                                 row_align=0.5)
                column = self.tvNPDevices.get_column (0)
                self.tvNPDevices.set_cursor (device_select_path, column)

        connection_select_path = 0
        if current_uri:
            model = self.tvNPDeviceURIs.get_model ()
            iter = model.get_iter_first ()
            i = 0
            while iter:
                dev = model.get_value (iter, 1)
                if current_uri == dev.uri:
                    connection_select_path = i
                    break

                iter = model.iter_next (iter)
                i += 1
        elif not self.device_selected:
            # Select the device.
            column = self.tvNPDevices.get_column (0)
            self.tvNPDevices.set_cursor ((0,), column)

            # Select the connection.
            column = self.tvNPDeviceURIs.get_column (0)
            self.tvNPDeviceURIs.set_cursor (connection_select_path, column)

    ## SMB browsing

    def browse_smb_hosts(self):
        """Initialise the SMB tree store."""
        store = self.smb_store
        store.clear ()
        busy(self.SMBBrowseDialog)
        class X:
            pass
        dummy = X()
        dummy.smbc_type = pysmb.smbc.PRINTER_SHARE
        dummy.name = _('Scanning...')
        dummy.comment = ''
        store.append(None, [dummy])
        while gtk.events_pending ():
            gtk.main_iteration ()

        debug = 0
        if get_debugging ():
            debug = 10
        smbc_auth = pysmb.AuthContext (self.SMBBrowseDialog)
        ctx = pysmb.smbc.Context (debug=debug,
                                  auth_fn=smbc_auth.callback)
        entries = None
        try:
            while smbc_auth.perform_authentication () > 0:
                try:
                    entries = ctx.opendir ("smb://").getdents ()
                except Exception, e:
                    smbc_auth.failed (e)
        except RuntimeError, (e, s):
            if e != errno.ENOENT:
                debugprint ("Runtime error: %s" % repr ((e, s)))
        except:
            nonfatalException ()

        store.clear ()
        if entries:
            for entry in entries:
                if entry.smbc_type in [pysmb.smbc.WORKGROUP,
                                       pysmb.smbc.SERVER]:
                    iter = store.append (None, [entry])
                    i = store.append (iter)

        specified_uri = SMBURI (uri=self.entSMBURI.get_text ())
        (group, host, share, user, password) = specified_uri.separate ()
        if len (host) > 0:
            # The user has specified a server before clicking Browse.
            # Append the server as a top-level entry.
            class FakeEntry:
                pass
            toplevel = FakeEntry ()
            toplevel.smbc_type = pysmb.smbc.SERVER
            toplevel.name = host
            toplevel.comment = ''
            iter = store.append (None, [toplevel])
            i = store.append (iter)

            # Now expand it.
            path = store.get_path (iter)
            self.tvSMBBrowser.expand_row (path, 0)

        ready(self.SMBBrowseDialog)

        if store.get_iter_first () == None:
            self.SMBBrowseDialog.hide ()
            show_info_dialog (_("No Print Shares"),
                              _("There were no print shares found.  "
                                "Please check that the Samba service is "
                                "marked as trusted in your firewall "
                                "configuration."),
                              parent=self.NewPrinterWindow)

    def smb_select_function (self, path):
        """Don't allow this path to be selected unless it is a leaf."""
        iter = self.smb_store.get_iter (path)
        return not self.smb_store.iter_has_child (iter)

    def smbbrowser_cell_share (self, column, cell, model, iter):
        entry = model.get_value (iter, 0)
        share = ''
        if entry != None:
            share = entry.name
        cell.set_property ('text', share)

    def smbbrowser_cell_comment (self, column, cell, model, iter):
        entry = model.get_value (iter, 0)
        comment = ''
        if entry != None:
            comment = entry.comment
        cell.set_property ('text', comment)

    def on_tvSMBBrowser_row_activated (self, view, path, column):
        """Handle double-clicks in the SMB tree view."""
        store = self.smb_store
        iter = store.get_iter (path)
        entry = store.get_value (iter, 0)
        if entry and entry.smbc_type == pysmb.smbc.PRINTER_SHARE:
            # This is a share, not a host.
            self.btnSMBBrowseOk.clicked ()
            return

        if view.row_expanded (path):
            view.collapse_row (path)
        else:
            self.on_tvSMBBrowser_row_expanded (view, iter, path)

    def on_tvSMBBrowser_row_expanded (self, view, iter, path):
        """Handler for expanding a row in the SMB tree view."""
        model = view.get_model ()
        entry = model.get_value (iter, 0)
        if entry == None:
            return

        if entry.smbc_type == pysmb.smbc.WORKGROUP:
            # Workgroup
            # Be careful though: if there is a server with the
            # same name as the workgroup we will get a list of its
            # shares, not the workgroup's servers.
            try:
                if self.expanding_row:
                    return
            except:
                self.expanding_row = 1

            busy (self.SMBBrowseDialog)
            uri = "smb://%s/" % entry.name
            debug = 0
            if get_debugging ():
                debug = 10
            smbc_auth = pysmb.AuthContext (self.SMBBrowseDialog)
            ctx = pysmb.smbc.Context (debug=debug,
                                      auth_fn=smbc_auth.callback)
            entries = []
            try:
                while smbc_auth.perform_authentication () > 0:
                    try:
                        entries = ctx.opendir (uri).getdents ()
                    except Exception, e:
                        smbc_auth.failed (e)
            except RuntimeError, (e, s):
                if e != errno.ENOENT:
                    debugprint ("Runtime error: %s" % repr ((e, s)))
            except:
                nonfatalException()

            while model.iter_has_child (iter):
                i = model.iter_nth_child (iter, 0)
                model.remove (i)

            for entry in entries:
                if entry.smbc_type in [pysmb.smbc.SERVER,
                                       pysmb.smbc.PRINTER_SHARE]:
                    i = model.append (iter, [entry])
                if entry.smbc_type == pysmb.smbc.SERVER:
                    n = model.append (i)

            view.expand_row (path, 0)
            del self.expanding_row
            ready (self.SMBBrowseDialog)

        elif entry.smbc_type == pysmb.smbc.SERVER:
            # Server
            try:
                if self.expanding_row:
                    return
            except:
                self.expanding_row = 1

            busy (self.SMBBrowseDialog)
            uri = "smb://%s/" % entry.name
            debug = 0
            if get_debugging ():
                debug = 10
            smbc_auth = pysmb.AuthContext (self.SMBBrowseDialog)
            ctx = pysmb.smbc.Context (debug=debug,
                                      auth_fn=smbc_auth.callback)
            shares = []
            try:
                while smbc_auth.perform_authentication () > 0:
                    try:
                        shares = ctx.opendir (uri).getdents ()
                    except Exception, e:
                        smbc_auth.failed (e)
            except RuntimeError, (e, s):
                if e != errno.EACCES and e != errno.EPERM:
                    debugprint ("Runtime error: %s" % repr ((e, s)))
            except:
                nonfatalException()

            while model.iter_has_child (iter):
                i = model.iter_nth_child (iter, 0)
                model.remove (i)

            for share in shares:
                if share.smbc_type == pysmb.smbc.PRINTER_SHARE:
                    i = model.append (iter, [share])
                    debugprint (repr (share))

            view.expand_row (path, 0)
            del self.expanding_row
            ready (self.SMBBrowseDialog)

    def on_entSMBURI_changed (self, ent):
        allowed_chars = string.letters+string.digits+'_-./:@%'
        self.entry_changed(ent, allowed_chars)
        uri = ent.get_text ()
        (group, host, share, user, password) = SMBURI (uri=uri).separate ()
        if user:
            self.entSMBUsername.set_text (user)
        if password:
            self.entSMBPassword.set_text (password)
        if user or password:
            uri = SMBURI (group=group, host=host, share=share).get_uri ()
            ent.set_text(uri)
            self.rbtnSMBAuthSet.set_active(True)
        elif self.entSMBUsername.get_text () == '':
            self.rbtnSMBAuthPrompt.set_active(True)

        self.btnSMBVerify.set_sensitive(bool(uri))
        self.setNPButtons ()

    def on_tvSMBBrowser_cursor_changed(self, widget):
        store, iter = self.tvSMBBrowser.get_selection().get_selected()
        is_share = False
        if iter:
            entry = store.get_value (iter, 0)
            if entry:
                is_share = entry.smbc_type == pysmb.smbc.PRINTER_SHARE

        self.btnSMBBrowseOk.set_sensitive(iter != None and is_share)

    def on_btnSMBBrowse_clicked(self, button):
        self.btnSMBBrowseOk.set_sensitive(False)

        try:
            # Note: we do the browsing from *this* machine, regardless
            # of which CUPS server we are connected to.
            f = firewall.Firewall ()
            allowed = f.check_samba_client_allowed ()
            secondary_text = TEXT_adjust_firewall + "\n\n"
            if not allowed:
                dialog = gtk.MessageDialog (self.NewPrinterWindow,
                                            gtk.DIALOG_MODAL |
                                            gtk.DIALOG_DESTROY_WITH_PARENT,
                                            gtk.MESSAGE_QUESTION,
                                            gtk.BUTTONS_NONE,
                                            _("Adjust Firewall"))
                secondary_text += ("- " +
                                   _("Allow all incoming SMB/CIFS "
                                     "browse packets"))
                dialog.format_secondary_markup (secondary_text)
                dialog.add_buttons (_("Do It Later"), gtk.RESPONSE_NO,
                                    _("Adjust Firewall"), gtk.RESPONSE_YES)
                response = dialog.run ()
                dialog.destroy ()

                if response == gtk.RESPONSE_YES:
                    f.add_rule (f.ALLOW_SAMBA_CLIENT)
                    f.write ()
        except (dbus.DBusException, Exception):
            nonfatalException ()

        self.SMBBrowseDialog.show()
        self.browse_smb_hosts()

    def on_btnSMBBrowseOk_clicked(self, button):
        store, iter = self.tvSMBBrowser.get_selection().get_selected()
        is_share = False
        if iter:
            entry = store.get_value (iter, 0)
            if entry:
                is_share = entry.smbc_type == pysmb.smbc.PRINTER_SHARE

        if not iter or not is_share:
            self.SMBBrowseDialog.hide()
            return

        parent_iter = store.iter_parent (iter)
        domain_iter = store.iter_parent (parent_iter)
        share = store.get_value (iter, 0)
        host = store.get_value (parent_iter, 0)
        if domain_iter:
            group = store.get_value (domain_iter, 0).name
        else:
            group = ''
        uri = SMBURI (group=group,
                      host=host.name,
                      share=share.name).get_uri ()

        self.entSMBUsername.set_text ('')
        self.entSMBPassword.set_text ('')
        self.entSMBURI.set_text (uri)

        self.SMBBrowseDialog.hide()

    def on_btnSMBBrowseCancel_clicked(self, widget, *args):
        self.SMBBrowseDialog.hide()

    def on_btnSMBBrowseRefresh_clicked(self, button):
        self.browse_smb_hosts()

    def on_rbtnSMBAuthSet_toggled(self, widget):
        self.tblSMBAuth.set_sensitive(widget.get_active())

    def on_btnSMBVerify_clicked(self, button):
        uri = self.entSMBURI.get_text ()
        (group, host, share, u, p) = SMBURI (uri=uri).separate ()
        user = ''
        passwd = ''
        reason = None
        auth_set = self.rbtnSMBAuthSet.get_active()
        if auth_set:
            user = self.entSMBUsername.get_text ()
            passwd = self.entSMBPassword.get_text ()

        accessible = False
        canceled = False
        busy (self.NewPrinterWindow)
        try:
            debug = 0
            if get_debugging ():
                debug = 10

            if auth_set:
                # No prompting.
                def do_auth (svr, shr, wg, un, pw):
                    return (group, user, passwd)
                ctx = pysmb.smbc.Context (debug=debug, auth_fn=do_auth)
                try:
                    ctx.optionUseKerberos = True
                except AttributeError:
                    # requires pysmbc >= 1.0.12
                    pass

                f = ctx.open ("smb://%s/%s" % (host, share),
                              os.O_RDWR, 0777)
                accessible = True
            else:
                # May need to prompt.
                smbc_auth = pysmb.AuthContext (self.NewPrinterWindow,
                                               workgroup=group,
                                               user=user,
                                               passwd=passwd)
                ctx = pysmb.smbc.Context (debug=debug,
                                          auth_fn=smbc_auth.callback)
                while smbc_auth.perform_authentication () > 0:
                    try:
                        f = ctx.open ("smb://%s/%s" % (host, share),
                                      os.O_RDWR, 0777)
                        accessible = True
                    except Exception, e:
                        smbc_auth.failed (e)

                if not accessible:
                    canceled = True
        except RuntimeError, (e, s):
            debugprint ("Error accessing share: %s" % repr ((e, s)))
            reason = s
        except:
            nonfatalException()
        ready (self.NewPrinterWindow)

        if accessible:
            show_info_dialog (_("Print Share Verified"),
                              _("This print share is accessible."),
                              parent=self.NewPrinterWindow)
            return

        if not canceled:
            text = _("This print share is not accessible.")
            if reason:
                text = reason
            show_error_dialog (_("Print Share Inaccessible"), text,
                               parent=self.NewPrinterWindow)

    def entry_changed(self, entry, allowed_chars):
        "Remove all chars from entry's text that are not in allowed_chars."
        try:
            allowed_chars = unicode (allowed_chars, locale.getpreferredencoding())
        except UnicodeDecodeError:
            allowed_chars = unicode (allowed_chars)
        origtext = unicode (entry.get_text())
        new_text = origtext
        for char in origtext:
            if char not in allowed_chars:
                new_text = new_text.replace(char, "")
                debugprint ("removed disallowed character %s" % char)
        if origtext!=new_text:
            entry.set_text(new_text)

    def on_entNPTDevice_changed(self, ent):
        allowed_chars = string.letters+string.digits+'_-./:%()@?=&'
        self.entry_changed(ent, allowed_chars)
        self.setNPButtons()

    def on_entNPTJetDirectHostname_changed(self, ent):
        allowed_chars = string.letters+string.digits+'_-.'
        self.entry_changed(ent, allowed_chars)
        self.setNPButtons()

    def on_entNPTJetDirectPort_changed(self, ent):
        self.entry_changed(ent, string.digits)
        self.setNPButtons()

    def on_expNPDeviceURIs_expanded (self, widget, UNUSED):
        # When the expanded is not expanded we want its packing to be
        # 'expand = false' so that it aligns at the bottom (it packs
        # to the end of its vbox).  But when it is expanded we'd like
        # it to expand with the window.
        #
        # Adjust its 'expand' packing state depending on whether the
        # widget is expanded.

        parent = widget.get_parent ()
        (expand, fill,
         padding, pack_type) = parent.query_child_packing (widget)
        expand = widget.get_expanded ()
        parent.set_child_packing (widget, expand, fill,
                                  padding, pack_type)

    def device_row_separator_fn (self, model, iter):
        return model.get_value (iter, 2)

    def device_row_activated (self, view, path, column):
        if view.row_expanded (path):
            view.collapse_row (path)
        else:
            view.expand_row (path, False)

    def device_select_function (self, path):
        """
        Allow this path to be selected as long as there
        is a device associated with it.  Otherwise, expand or collapse it.
        """
        model = self.tvNPDevices.get_model ()
        iter = model.get_iter (path)
        if model.get_value (iter, 1) != None:
            return True

        self.device_row_activated (self.tvNPDevices, path, None)
        return False

    def on_tvNPDevices_cursor_changed(self, widget):
        self.device_selected += 1
        path, column = widget.get_cursor ()
        if path == None:
            return

        model = widget.get_model ()
        iter = model.get_iter (path)
        physicaldevice = model.get_value (iter, 1)
        if physicaldevice == None:
            return
        for device in physicaldevice.get_devices ():
            if device.type == "parallel":
                device.menuentry = _("Parallel Port")
            elif device.type == "serial":
                device.menuentry = _("Serial Port")
            elif device.type == "usb":
                device.menuentry = _("USB")
            elif device.type == "bluetooth":
                device.menuentry = _("Bluetooth")
            elif device.type == "hp":
                device.menuentry = _("HP Linux Imaging and Printing (HPLIP)")
            elif device.type == "hpfax":
                device.menuentry = _("Fax") + " - " + \
                    _("HP Linux Imaging and Printing (HPLIP)")
            elif device.type == "hal":
                device.menuentry = _("Hardware Abstraction Layer (HAL)")
            elif device.type == "socket":
                device.menuentry = _("AppSocket/HP JetDirect")
            elif device.type == "lpd":
                (scheme, rest) = urllib.splittype (device.uri)
                (hostport, rest) = urllib.splithost (rest)
                (queue, rest) = urllib.splitquery (rest)
                if queue != '':
                    if queue[0] == '/':
                        queue = queue[1:]

                    device.menuentry = _("LPD/LPR queue '%s'") % queue
                else:
                    device.menuentry = _("LPD/LPR queue")

            elif device.type == "smb":
                device.menuentry = _("Windows Printer via SAMBA")
            elif device.type == "ipp":
                (scheme, rest) = urllib.splittype (device.uri)
                (hostport, rest) = urllib.splithost (rest)
                (queue, rest) = urllib.splitquery (rest)
                if queue != '':
                    if queue[0] == '/':
                        queue = queue[1:]
                    if queue.startswith("printers/"):
                        queue = queue[9:]
                if queue != '':
                    device.menuentry = _("IPP") + " (%s)" % queue
                else:
                    device.menuentry = _("IPP")
            elif device.type == "http" or device.type == "https":
                device.menuentry = _("HTTP")
            elif device.type == "dnssd" or device.type == "mdns":
                (scheme, rest) = urllib.splittype (device.uri)
                (name, rest) = urllib.splithost (rest)
                (cupsqueue, rest) = urllib.splitquery (rest)
                if cupsqueue[0] == '/':
                    cupsqueue = cupsqueue[1:]
                if cupsqueue == 'cups':
                    device.menuentry = _("Remote CUPS printer via DNS-SD")
                    if device.info != '':
                         device.menuentry += " (%s)" % device.info
                else:
                    protocol = None
                    if name.find("._ipp") != -1:
                        protocol = "IPP"
                    elif name.find("._printer") != -1:
                        protocol = "LPD"
                    elif name.find("._pdl-datastream") != -1:
                        protocol = "AppSocket/JetDirect"
                    if protocol != None:
                        device.menuentry = \
                            _("%s network printer via DNS-SD") % protocol
                    else:
                        device.menuentry = \
                            _("Network printer via DNS-SD")
            else:
                device.menuentry = device.uri

        model = gtk.ListStore (str,                    # URI description
                               gobject.TYPE_PYOBJECT)  # cupshelpers.Device
        self.tvNPDeviceURIs.set_model (model)

        # If this is a network device, check whether HPLIP can drive it.
        if physicaldevice.get_data ('checked-hplip') != True:
            hp_drivable = False
            hp_scannable = False
            is_network = False
            remotecups = False
            host = None
            device_dict = { 'device-class': 'network' }
            if physicaldevice._network_host:
                host = physicaldevice._network_host
            for device in physicaldevice.get_devices ():
                if device.type == "hp":
                    # We already know that HPLIP can drive this device.
                    hp_drivable = True

                    # But can we scan using it?
                    if self.get_hplip_scan_type_for_uri (device.uri):
                        hp_scannable = True

                    break
                elif device.type in ["socket", "lpd", "ipp", "dnssd", "mdns"]:
                    # This is a network printer.
                    if host == None and device.type in ["socket", "lpd", "ipp"]:
                        (scheme, rest) = urllib.splittype (device.uri)
                        (hostport, rest) = urllib.splithost (rest)
                        if hostport != None:
                            (host, port) = urllib.splitport (hostport)
                    if host:
                        is_network = True
                        remotecups = ((device.uri.startswith('dnssd:') or \
                                       device.uri.startswith('mdns:')) and \
                                      device.uri.endswith('/cups'))
                        if (not device.make_and_model or \
                            device.make_and_model == "Unknown") and not \
                           remotecups:
                            self.getNetworkPrinterMakeModel(host=host,
                                                            device=device)
                        device_dict['device-info'] = device.info
                        device_dict['device-make-and-model'] = (device.
                                                                make_and_model)
                        device_dict['device-id'] = device.id
                        device_dict['device-location'] = device.location

            if not hp_drivable and is_network and not remotecups:
                if (hasattr (physicaldevice, "dnssd_hostname") and \
                    physicaldevice.dnssd_hostname):
                    hpliphost = physicaldevice.dnssd_hostname
                else:
                    hpliphost = host
                hplipuri = self.get_hplip_uri_for_network_printer (hpliphost,
                                                                   "print")
                if hplipuri:
                    dev = cupshelpers.Device (hplipuri, **device_dict)
                    dev.menuentry = "HP Linux Imaging and Printing (HPLIP)"
                    physicaldevice.add_device (dev)

                    # Now check to see if we can also send faxes using
                    # this device.
                    faxuri = self.get_hplip_uri_for_network_printer (hpliphost,
                                                                     "fax")
                    if faxuri:
                        faxdevid = self.get_hpfax_device_id (faxuri)
                        device_dict['device-id'] = faxdevid
                        device_dict['device-info'] = _("Fax")
                        faxdev = cupshelpers.Device (faxuri, **device_dict)
                        faxdev.menuentry = _("Fax") + " - " + \
                            "HP Linux Imaging and Printing (HPLIP)"
                        physicaldevice.add_device (faxdev)

            physicaldevice.set_data ('hp-scannable', True)
            physicaldevice.set_data ('checked-hplip', True)

        device.hp_scannable = physicaldevice.get_data ('hp-scannable')

        # Fill the list of connections for this device.
        n = 0
        for device in physicaldevice.get_devices ():
            model.append ((device.menuentry, device))
            n += 1
        column = self.tvNPDeviceURIs.get_column (0)
        self.tvNPDeviceURIs.set_cursor (0, column)
        if n > 1:
            self.expNPDeviceURIs.show_all ()
        else:
            self.expNPDeviceURIs.hide ()

    def on_tvNPDeviceURIs_cursor_changed(self, widget):
        path, column = widget.get_cursor ()
        if path == None:
            return

        model = widget.get_model ()
        iter = model.get_iter (path)
        device = model.get_value(iter, 1)
        self.device = device
        self.lblNPDeviceDescription.set_text ('')
        page = self.new_printer_device_tabs.get(device.type, 1)
        self.ntbkNPType.set_current_page(page)

        location = ''
        type = device.type
        url = device.uri.split(":", 1)[-1]
        if page == 0:
            # This is the "no options" page, with just a label to describe
            # the selected device.
            if device.type == "parallel":
                text = _("A printer connected to the parallel port.")
            elif device.type == "usb":
                text = _("A printer connected to a USB port.")
            elif device.type == "bluetooth":
                text = _("A printer connected via Bluetooth.")
            elif device.type == "hp":
                text = _("HPLIP software driving a printer, "
                         "or the printer function of a multi-function device.")
            elif device.type == "hpfax":
                text = _("HPLIP software driving a fax machine, "
                         "or the fax function of a multi-function device.")
            elif device.type == "hal":
                text = _("Local printer detected by the "
                         "Hardware Abstraction Layer (HAL).")
            elif device.type == "dnssd" or device.type == "mdns":
                (scheme, rest) = urllib.splittype (device.uri)
                (name, rest) = urllib.splithost (rest)
                (cupsqueue, rest) = urllib.splitquery (rest)
                if cupsqueue[0] == '/':
                    cupsqueue = cupsqueue[1:]
                if cupsqueue == 'cups':
                    text = _("Remote CUPS printer via DNS-SD")
                else:
                    protocol = None
                    if name.find("._ipp") != -1:
                        protocol = "IPP"
                    elif name.find("._printer") != -1:
                        protocol = "LPD"
                    elif name.find("._pdl-datastream") != -1:
                        protocol = "AppSocket/JetDirect"
                    if protocol != None:
                        text = _("%s network printer via DNS-SD") % protocol
                    else:
                        text = _("Network printer via DNS-SD")
            else:
                text = device.uri

            self.lblNPDeviceDescription.set_text (text)
        elif device.type=="socket":
            (scheme, rest) = urllib.splittype (device.uri)
            host = ''
            port = 9100
            if scheme == "socket":
                (hostport, rest) = urllib.splithost (rest)
                (host, port) = urllib.splitnport (hostport, defport=port)
                debugprint ("socket: host is %s, port is %s" % (host,
                                                                repr (port)))
                if device.location != '':
                    location = device.location
                else:
                    location = host
            self.entNPTJetDirectHostname.set_text (host)
            self.entNPTJetDirectPort.set_text (str (port))
        elif device.type=="serial":
            if not device.is_class:
                options = device.uri.split("?")[1]
                options = options.split("+")
                option_dict = {}
                for option in options:
                    name, value = option.split("=")
                    option_dict[name] = value

                for widget, name, optionvalues in (
                    (self.cmbNPTSerialBaud, "baud", None),
                    (self.cmbNPTSerialBits, "bits", None),
                    (self.cmbNPTSerialParity, "parity",
                     ["none", "odd", "even"]),
                    (self.cmbNPTSerialFlow, "flow",
                     ["none", "soft", "hard", "hard"])):
                    if option_dict.has_key(name): # option given in URI?
                        if optionvalues is None: # use text in widget
                            model = widget.get_model()
                            iter = model.get_iter_first()
                            nr = 0
                            while iter:
                                value = model.get(iter,0)[0]
                                if value == option_dict[name]:
                                    widget.set_active(nr)
                                    break
                                iter = model.iter_next(iter)
                                nr += 1

                            if not iter:
                                widget.set_active (0)
                        else: # use optionvalues
                            nr = optionvalues.index(
                                option_dict[name])
                            widget.set_active(nr+1) # compensate "Default"
                    else:
                        widget.set_active(0)

        # XXX FILL TABS FOR VALID DEVICE URIs
        elif device.type=="lpd":
            self.entNPTLpdHost.set_text ('')
            self.entNPTLpdQueue.set_text ('')
            self.entNPTLpdQueue.set_completion (None)
            self.btnNPTLpdProbe.set_sensitive (False)
            if len (device.uri) > 6:
                host = device.uri[6:]
                i = host.find ("/")
                if i != -1:
                    printer = host[i + 1:]
                    host = host[:i]
                else:
                    printer = ""
                self.entNPTLpdHost.set_text (host)
                self.entNPTLpdQueue.set_text (printer)
                location = host
                self.btnNPTLpdProbe.set_sensitive (True)
        elif device.uri == "smb":
            self.entSMBURI.set_text('')
            self.btnSMBVerify.set_sensitive(False)
        elif device.type == "smb":
            self.entSMBUsername.set_text ('')
            self.entSMBPassword.set_text ('')
            self.entSMBURI.set_text(device.uri[6:])
            self.btnSMBVerify.set_sensitive(True)
        else:
            if device.uri:
                self.entNPTDevice.set_text(device.uri)

        try:
            if len (location) == 0 and self.device.device_class == "direct":
                # Set location to the name of this host.
                if (self._host == 'localhost' or
                    self._host[0] == '/'):
                    u = os.uname ()
                    location = u[1]
                else:
                    location = self._host

            # Pre-fill location field.
            self.entNPLocation.set_text (location)
        except:
            nonfatalException ()

        self.setNPButtons()

    def on_entNPTLpdHost_changed(self, ent):
        hostname = ent.get_text()
        self.btnNPTLpdProbe.set_sensitive (len (hostname) > 0)
        self.setNPButtons()

    def on_entNPTLpdQueue_changed(self, ent):
        self.setNPButtons()

    def on_btnNPTLpdProbe_clicked(self, button):
        # read hostname, probe, fill printer names
        hostname = self.entNPTLpdHost.get_text()
        server = probe_printer.LpdServer(hostname)

        self.lblWait.set_markup ('<span weight="bold" size="larger">' +
                                 _('Searching') + '</span>\n\n' +
                                 _('Searching for printers'))
        self.WaitWindow.set_transient_for (self.NewPrinterWindow)
        self.WaitWindow.show_now ()
        busy (self.WaitWindow)
        def stop (widget, event):
            server.destroy ()
            return True

        self.WaitWindow.disconnect (self.WaitWindow_handler)
        signal = self.WaitWindow.connect ("delete-event", stop)
        printers = server.probe()
        self.WaitWindow.disconnect (signal)
        self.WaitWindow_handler = self.WaitWindow.connect ("delete-event",
                                                           on_delete_just_hide)
        self.WaitWindow.hide ()

        model = gtk.ListStore (gobject.TYPE_STRING)
        for printer in printers:
            model.append ([printer])

        completion = gtk.EntryCompletion ()
        completion.set_model (model)
        completion.set_text_column (0)
        completion.set_minimum_key_length (0)
        self.entNPTLpdQueue.set_completion (completion)

    ### Find Network Printer
    def on_entNPTNetworkHostname_changed(self, ent):
        text = ent.get_text ()
        if text.find (":") != -1:
            # The user is typing in a URI.  In that case, switch to URI entry.
            ent.set_text ('')
            debugprint ("URI detected (%s) -> Enter URI" % text)
            self.entNPTDevice.set_text (text)
            model = self.tvNPDevices.get_model ()
            path = model.get_path (self.devices_uri_iter)
            self.tvNPDevices.set_cursor (path)
            self.entNPTDevice.select_region (0, 0)
            self.entNPTDevice.set_position (-1)
            return

        allowed_chars = string.letters+string.digits+'_-.'
        self.entry_changed(ent, allowed_chars)
        s = ent.get_text ()
        self.btnNetworkFind.set_sensitive (len (s) > 0)
        self.lblNetworkFindNotFound.hide ()
        self.setNPButtons ()

    def on_btnNetworkFind_clicked(self, button):
        host = self.entNPTNetworkHostname.get_text ()

        def found_callback (new_device):
            if self.printer_finder == None:
                return

            gobject.idle_add (self.found_network_printer_callback, new_device)

        self.btnNetworkFind.set_sensitive (False)
        self.entNPTNetworkHostname.set_sensitive (False)
        self.network_found = 0
        self.lblNetworkFindNotFound.hide ()
        self.lblNetworkFindSearching.show_all ()
        finder = probe_printer.PrinterFinder ()
        self.inc_spinner_task ()
        finder.find (host, found_callback)
        self.printer_finder = finder

    def found_network_printer_callback (self, new_device):
        gtk.gdk.threads_enter ()
        if new_device:
            self.network_found += 1
            dev = PhysicalDevice (new_device)
            try:
                i = self.devices.index (dev)

                # Adding a new URI to an existing physical device.
                self.devices[i].add_device (new_device)

                (path, column) = self.tvNPDevices.get_cursor ()
                if path:
                    model = self.tvNPDevices.get_model ()
                    iter = model.get_iter (path)
                    if model.get_value (iter, 1) == self.devices[i]:
                        self.on_tvNPDevices_cursor_changed (self.tvNPDevices)
            except ValueError:
                # New physical device.
                dev.set_data ('checked-hplip', True)
                self.devices.append (dev)
                self.devices.sort ()
                model = self.tvNPDevices.get_model ()
                iter = model.insert_before (None, self.devices_find_nw_iter,
                                            row=[dev.get_info (), dev, False])

                # If this is the first one we've found, select it.
                if self.network_found == 1:
                    path = model.get_path (iter)
                    self.tvNPDevices.set_cursor (path)
        else:
            self.printer_finder = None
            self.dec_spinner_task ()
            self.lblNetworkFindSearching.hide ()
            self.entNPTNetworkHostname.set_sensitive (True)
            self.btnNetworkFind.set_sensitive (True)
            if self.network_found == 0:
                self.lblNetworkFindNotFound.set_markup ('<i>' +
                                                        _("No printer was "
                                                          "found at that "
                                                          "address.") + '</i>')
                self.lblNetworkFindNotFound.show ()

        gtk.gdk.threads_leave ()
    ###

    def getDeviceURI(self):
        type = self.device.type
        page = self.new_printer_device_tabs.get (type, 1)
        device = type
        if page == 0:
            # The "no options page".  We already have the URI.
            device = self.device.uri
        elif type == "socket": # JetDirect
            host = self.entNPTJetDirectHostname.get_text()
            port = self.entNPTJetDirectPort.get_text()
            if host:
                device += "://" + host
                if port:
                    device += ":" + port
        elif type in ("ipp", "http", "https"): # IPP
            try:
                if self.lblIPPURI.get_property('visible'):
                    device = self.lblIPPURI.get_text()
            except:
                device = self.entNPTDevice.get_text()
        elif type == "lpd": # LPD
            host = self.entNPTLpdHost.get_text()
            printer = self.entNPTLpdQueue.get_text()
            if host:
                device += "://" + host
                if printer:
                    device += "/" + printer
        elif type == "serial": # Serial
            options = []
            for widget, name, optionvalues in (
                (self.cmbNPTSerialBaud, "baud", None),
                (self.cmbNPTSerialBits, "bits", None),
                (self.cmbNPTSerialParity, "parity",
                 ("none", "odd", "even")),
                (self.cmbNPTSerialFlow, "flow",
                 ("none", "soft", "hard", "hard"))):
                nr = widget.get_active()
                if nr:
                    if optionvalues is not None:
                        option = optionvalues[nr-1]
                    else:
                        option = widget.get_active_text()
                    options.append(name + "=" + option)
            options = "+".join(options)
            device =  self.device.uri.split("?")[0] #"serial:/dev/ttyS%s"
            if options:
                device = device + "?" + options
        elif type == "smb":
            uri = self.entSMBURI.get_text ()
            (group, host, share, u, p) = SMBURI (uri=uri).separate ()
            user = ''
            password = ''
            if self.rbtnSMBAuthSet.get_active ():
                user = self.entSMBUsername.get_text ()
                password = self.entSMBPassword.get_text ()
            uri = SMBURI (group=group, host=host, share=share,
                          user=user, password=password).get_uri ()
            if uri:
                device += "://" + uri
        else:
            device = self.entNPTDevice.get_text()
        return device

    # PPD

    def on_rbtnNPFoomatic_toggled(self, widget):
        rbtn1 = self.rbtnNPFoomatic.get_active()
        rbtn2 = self.rbtnNPPPD.get_active()
        rbtn3 = self.rbtnNPDownloadableDriverSearch.get_active()
        self.tvNPMakes.set_sensitive(rbtn1)
        self.filechooserPPD.set_sensitive(rbtn2)

        if rbtn1:
            page = 0
        if rbtn2:
            page = 1
        if rbtn3:
            page = 2
        self.ntbkPPDSource.set_current_page (page)

        if not rbtn3 and self.openprinting_query_handle:
            # Need to cancel a search in progress.
            self.openprinting.cancelOperation (self.openprinting_query_handle)
            self.openprinting_query_handle = None
            self.btnNPDownloadableDriverSearch_label.set_text (_("Search"))
            # Clear printer list.
            model = gtk.ListStore (str, str)
            combobox = self.cmbNPDownloadableDriverFoundPrinters
            combobox.set_model (model)
            combobox.set_sensitive (False)

        for widget in [self.entNPDownloadableDriverSearch,
                       self.cmbNPDownloadableDriverFoundPrinters]:
            widget.set_sensitive(rbtn3)
        self.btnNPDownloadableDriverSearch.\
            set_sensitive (rbtn3 and (self.openprinting_query_handle == None))

        self.setNPButtons()

    def on_filechooserPPD_selection_changed(self, widget):
        self.setNPButtons()

    def on_btnNPDownloadableDriverSearch_clicked(self, widget):
        if self.openprinting_query_handle != None:
            self.openprinting.cancelOperation (self.openprinting_query_handle)
            self.openprinting_query_handle = None

        widget.set_sensitive (False)
        label = self.btnNPDownloadableDriverSearch_label
        label.set_text (_("Searching"))
        searchterm = self.entNPDownloadableDriverSearch.get_text ()
        debugprint ('Searching for "%s"' % searchterm)
        self.drivers_lock.acquire (0)
        self.openprinting_query_handle = \
            self.openprinting.searchPrinters (searchterm,
                                              self.openprinting_printers_found)
        self.cmbNPDownloadableDriverFoundPrinters.set_sensitive (False)

    def openprinting_printers_found (self, status, user_data, printers):
        self.openprinting_query_handle = None
        self.downloadable_printers_unchecked = map (lambda x:
                                                        (x, printers[x]),
                                                    printers)
        self.downloadable_printers = []
        self.downloadable_drivers = dict() # by printer id of dict
        if status != 0:
            # Should report error.
            print printers
            print traceback.extract_tb(printers[2], limit=None)
            self.drivers_lock.release ()
            return

        # Kick off a search for drivers for each model.
        self.openprinting_query_next_printer ()

    def openprinting_query_next_printer (self):
        """
        If there are more printers to query, kick off a query and
        return True.

        Otherwise return False.
        """

        try:
            a = self.downloadable_printers_unchecked.pop ()
            (printer_id, printer_name) = a
        except IndexError:
            debugprint ("All printer driver queries finished")
            return False

        extra_options = dict()
        if self.DOWNLOADABLE_ONLYPPD:
            extra_options['onlyppdfiles'] = '1'

        debugprint ("Querying drivers for %s" % printer_id)
        self.openprinting_query_handle = \
            self.openprinting.listDrivers (printer_id,
                                           self.openprinting_printer_drivers_found,
                                           user_data=(printer_id, printer_name),
                                           extra_options=extra_options)

        return True

    def openprinting_printer_drivers_found (self, status, user_data, drivers):
        self.openprinting_query_handle = None
        if status != 0:
            print drivers
            print traceback.extract_tb(drivers[2], limit=None)
            self.drivers_lock.release ()
            return

        if drivers:
            debugprint (" - drivers found")
            (printer_id, printer_name) = user_data
            self.downloadable_drivers[printer_id] = drivers
            self.downloadable_printers.append (user_data)

        if not self.openprinting_query_next_printer ():
            self.drivers_lock.release ()
            self.openprinting_drivers_found ()

    def openprinting_drivers_found (self):
        button = self.btnNPDownloadableDriverSearch
        label = self.btnNPDownloadableDriverSearch_label
        gtk.gdk.threads_enter ()
        try:
            label.set_text (_("Search"))
            button.set_sensitive (True)
            model = gtk.ListStore (str, str)
            if len (self.downloadable_printers) != 1:
                if len (self.downloadable_printers) > 1:
                    first = _("-- Select from search results --")
                else:
                    first = _("-- No matches found --")

                iter = model.append (None)
                model.set_value (iter, 0, first)
                model.set_value (iter, 1, None)

            sorted_list = []
            for printer_id, printer_name in self.downloadable_printers:
                sorted_list.append ((printer_id, printer_name))

            sorted_list.sort (lambda x, y: cups.modelSort (x[1], y[1]))
            sought = self.entNPDownloadableDriverSearch.get_text ().lower ()
            select_index = 0
            for id, name in sorted_list:
                iter = model.append (None)
                model.set_value (iter, 0, name)
                model.set_value (iter, 1, id)
                if name.lower () == sought:
                    select_index = model.get_path (iter)[0]
            combobox = self.cmbNPDownloadableDriverFoundPrinters
            combobox.set_model (model)
            combobox.set_active (select_index)
            combobox.set_sensitive (True)
            self.setNPButtons ()
        except:
            nonfatalException()
        gtk.gdk.threads_leave ()

    def on_cmbNPDownloadableDriverFoundPrinters_changed(self, widget):
        self.setNPButtons ()

        if self.openprinting_query_handle != None:
            self.openprinting.cancelOperation (self.openprinting_query_handle)
            self.openprinting_query_handle = None
            self.drivers_lock.release()

    def fillDownloadableDrivers(self):
        # Clear out the properties.
        self.lblNPDownloadableDriverSupplier.set_text ('')
        self.lblNPDownloadableDriverLicense.set_text ('')
        self.lblNPDownloadableDriverDescription.set_text ('')
        self.lblNPDownloadableDriverSupportContacts.set_text ('')
        self.rbtnNPDownloadLicenseNo.set_active (True)
        self.frmNPDownloadableDriverLicenseTerms.hide ()

        widget = self.cmbNPDownloadableDriverFoundPrinters
        model = widget.get_model ()
        iter = widget.get_active_iter ()
        if iter:
            printer_id = model.get_value (iter, 1)
        else:
            printer_id = None

        if printer_id == None:
            return

        drivers = self.downloadable_drivers[printer_id]
        model = gtk.ListStore (str,                     # driver name
                               gobject.TYPE_PYOBJECT)   # driver data
        recommended_iter = None
        first_iter = None
        for driver in drivers.values ():
            iter = model.append (None)
            if first_iter == None:
                first_iter = iter

            model.set_value (iter, 0, driver['name'])
            model.set_value (iter, 1, driver)

            if driver['recommended']:
                recommended_iter = iter

        if recommended_iter == None:
            recommended_iter = first_iter

        treeview = self.tvNPDownloadableDrivers
        treeview.set_model (model)
        if recommended_iter != None:
            treeview.get_selection ().select_iter (recommended_iter)

    def on_rbtnNPDownloadLicense_toggled(self, widget):
        self.setNPButtons ()

    # PPD from foomatic

    def fillMakeList(self):
        self.recommended_make_selected = False
        makes = self.ppds.getMakes()
        model = self.tvNPMakes.get_model()
        model.clear()
        found = False
        if self.auto_make:
            auto_make_norm = cupshelpers.ppds.normalize (self.auto_make)
        else:
            auto_make_norm = None

        for make in makes:
            recommended = (auto_make_norm and
                           cupshelpers.ppds.normalize (make) == auto_make_norm)
            if self.device and self.device.make_and_model and recommended:
                text = make + _(" (recommended)")
            else:
                text = make

            iter = model.append((text, make,))
            if recommended:
                path = model.get_path(iter)
                self.tvNPMakes.set_cursor (path)
                self.tvNPMakes.scroll_to_cell(path, None,
                                              True, 0.5, 0.5)
                found = True

        if not found:
            self.tvNPMakes.set_cursor (0,)
            self.tvNPMakes.scroll_to_cell(0, None, True, 0.0, 0.0)

        # Also pre-fill the OpenPrinting.org search box.
        search = ''
        if self.device and self.device.id_dict:
            devid_dict = self.device.id_dict
            if devid_dict["MFG"] and devid_dict["MDL"]:
                search = devid_dict["MFG"] + " " + devid_dict["MDL"]
            elif devid_dict["DES"]:
                search = devid_dict["DES"]
            elif devid_dict["MFG"]:
                search = devid_dict["MFG"]
        if search == '' and self.auto_make != None:
            search += self.auto_make
            if self.auto_model != None:
                search += " " + self.auto_model
        self.entNPDownloadableDriverSearch.set_text (search)

    def on_tvNPMakes_cursor_changed(self, tvNPMakes):
        path, column = tvNPMakes.get_cursor()
        if path != None:
            model = tvNPMakes.get_model ()
            iter = model.get_iter (path)
            self.NPMake = model.get(iter, 1)[0]
            recommended_make = (self.auto_make and
                                cupshelpers.ppds.normalize (self.auto_make) ==
                                cupshelpers.ppds.normalize (self.NPMake))
            self.recommended_make_selected = recommended_make
            self.fillModelList()

    def fillModelList(self):
        self.recommended_model_selected = False
        models = self.ppds.getModels(self.NPMake)
        model = self.tvNPModels.get_model()
        model.clear()
        selected = False
        is_auto_make = (cupshelpers.ppds.normalize (self.NPMake) ==
                        cupshelpers.ppds.normalize (self.auto_make))
        if is_auto_make:
            auto_model_norm = cupshelpers.ppds.normalize (self.auto_model)

        for pmodel in models:
            recommended = (is_auto_make and
                           cupshelpers.ppds.normalize (pmodel) ==
                           auto_model_norm)
            if self.device and self.device.make_and_model and recommended:
                text = pmodel + _(" (recommended)")
            else:
                text = pmodel

            iter = model.append((text, pmodel,))
            if recommended:
                path = model.get_path(iter)
                self.tvNPModels.set_cursor (path)
                self.tvNPModels.scroll_to_cell(path, None,
                                               True, 0.5, 0.5)
                selected = True
        if not selected:
            self.tvNPModels.set_cursor (0,)
            self.tvNPModels.scroll_to_cell(0, None, True, 0.0, 0.0)
        self.tvNPModels.columns_autosize()

    def fillDriverList(self, pmake, pmodel):
        self.NPModel = pmodel
        model = self.tvNPDrivers.get_model()
        model.clear()

        if self.device:
            devid = self.device.id_dict
        else:
            devid = None

        if (self.device and self.device.make_and_model and
            self.recommended_model_selected and
            self.id_matched_ppdnames):
            # Use the actual device-make-and-model string.
            make_and_model = self.device.make_and_model

            # and the ID-matched list of PPDs.
            self.NPDrivers = self.id_matched_ppdnames
            debugprint ("ID matched PPDs: %s" % repr (self.NPDrivers))
        elif self.ppds:
            # Use a generic make and model string for generating the
            # driver preference list.
            make_and_model = pmake + " " + pmodel
            ppds = self.ppds.getInfoFromModel(pmake, pmodel)
            ppdnames = ppds.keys ()

            files = self.jockey_installed_files
            try:
                self.NPDrivers = self.ppds.orderPPDNamesByPreference(ppdnames,
                                                                     files,
                                                                     make_and_model,
                                                                     devid)
            except:
                nonfatalException ()
                self.NPDrivers = ppdnames

            # Put the current driver first.
            if self.auto_driver and self.device:
                drivers = []
                for driver in self.NPDrivers:
                    if driver == self.auto_driver:
                        drivers.insert (0, driver)
                    else:
                        drivers.append (driver)

                self.NPDrivers = drivers
        else:
            # No available PPDs for some reason(!)
            debugprint ("No PPDs available?")
            self.NPDrivers = []

        driverlist = []
        NPDrivers = []
        i = 0
        for ppdname in self.NPDrivers:
            ppd = self.ppds.getInfoFromPPDName (ppdname)
            driver = _singleton (ppd["ppd-make-and-model"])
            driver = driver.replace(" (recommended)", "")

            try:
                lpostfix = " [%s]" % _singleton (ppd["ppd-natural-language"])
                driver += lpostfix
            except KeyError:
                pass

            duplicate = driver in driverlist

            if (not (self.device and self.device.make_and_model) and
                self.auto_driver == ppdname):
                driverlist.append (driver)
                NPDrivers.append (ppdname)
                i += 1
                iter = model.append ((driver + _(" (Current)"),))
                path = model.get_path (iter)
                self.tvNPDrivers.get_selection().select_path(path)
                self.tvNPDrivers.scroll_to_cell(path, None, True, 0.5, 0.0)
            elif self.device and i == 0:
                driverlist.append (driver)
                NPDrivers.append (ppdname)
                i += 1
                iter = model.append ((driver + _(" (recommended)"),))
                path = model.get_path (iter)
                self.tvNPDrivers.get_selection().select_path(path)
                self.tvNPDrivers.scroll_to_cell(path, None, True, 0.5, 0.0)
            else:
                if duplicate:
                    continue
                driverlist.append (driver)
                NPDrivers.append (ppdname)
                i += 1
                model.append((driver, ))

        self.NPDrivers = NPDrivers
        self.tvNPDrivers.columns_autosize()

    def on_NPDrivers_query_tooltip(self, tv, x, y, keyboard_mode, tooltip):
        if keyboard_mode:
            path = tv.get_cursor()[0]
            if path is None:
                return False
        else:
            bin_x, bin_y = tv.convert_widget_to_bin_window_coords(x, y)
            ret = tv.get_path_at_pos (bin_x, bin_y)
            if ret is None:
                return False
            path = ret[0]

        drivername = self.NPDrivers[path[0]]
        ppddict = self.ppds.getInfoFromPPDName(drivername)
        markup = _singleton (ppddict['ppd-make-and-model'])
        if (drivername.startswith ("foomatic:")):
            markup += " "
            markup += _("This PPD is generated by foomatic.")
        tooltip.set_markup(markup)
        return True

    def on_tvNPModels_cursor_changed(self, widget):
        path, column = widget.get_cursor()
        if path != None:
            model = widget.get_model ()
            iter = model.get_iter (path)
            pmodel = model.get(iter, 1)[0]

            # Find out if this is the auto-detected make and model
            recommended_model = (self.recommended_make_selected and
                                 self.auto_model and
                                 self.auto_model.lower () == pmodel.lower ())
            self.recommended_model_selected = recommended_model
            self.fillDriverList(self.NPMake, pmodel)
            self.on_tvNPDrivers_cursor_changed(self.tvNPDrivers)

    def on_tvNPDrivers_cursor_changed(self, widget):
        self.setNPButtons()

    def on_tvNPDownloadableDrivers_cursor_changed(self, widget):
        model, iter = widget.get_selection ().get_selected ()
        if not iter:
            path, column = widget.get_cursor()
            iter = model.get_iter (path)
        driver = model.get_value (iter, 1)
        import pprint
        pprint.pprint (driver)
        self.ntbkNPDownloadableDriverProperties.set_current_page(1)
        supplier = driver.get('supplier', _("OpenPrinting"))
        vendor = self.cbNPDownloadableDriverSupplierVendor
        active = driver['manufacturersupplied']

        def set_protect_active (widget, active):
            widget.set_active (active)
            widget.set_data ('protect_active', active)

        set_protect_active (vendor, active)
        self.lblNPDownloadableDriverSupplier.set_text (supplier)

        license = driver.get('license', _("Distributable"))
        patents = self.cbNPDownloadableDriverLicensePatents
        free = self.cbNPDownloadableDriverLicenseFree
        set_protect_active (patents, driver['patents'])
        set_protect_active (free, driver['freesoftware'])
        self.lblNPDownloadableDriverLicense.set_text (license)

        description = driver.get('shortdescription', _("None"))
        self.lblNPDownloadableDriverDescription.set_markup (description)

        functionality = driver['functionality']
        for field in ["Graphics", "LineArt", "Photo", "Text"]:
            key = field.lower ()
            value = None
            hs = self.__dict__.get ("hsDownloadableDriverPerf%s" % field)
            unknown = self.__dict__.get ("lblDownloadableDriverPerf%sUnknown"
                                         % field)
            if functionality.has_key (key):
                if hs:
                    try:
                        value = int (functionality[key])
                        hs.set_value (value)
                        hs.show_all ()
                        unknown.hide ()
                    except:
                        pass

            if value == None:
                hs.hide ()
                unknown.show_all ()
        supportcontacts = ""
        if driver.has_key ('supportcontacts'):
            for supportentry in driver['supportcontacts']:
                if supportentry['name']:
                    supportcontact = " - " + supportentry['name']
                    supportcontact_extra = ""
                    if supportentry['url']:
                        supportcontact_extra = supportcontact_extra + \
                            supportentry['url']
                    if supportentry['level']:
                        if supportcontact_extra:
                            supportcontact_extra = supportcontact_extra + _(", ")
                        supportcontact_extra = supportcontact_extra + \
                            supportentry['level']
                    if supportcontact_extra:
                        supportcontact = supportcontact + \
                            _("\n(%s)") % supportcontact_extra
                        if supportcontacts:
                            supportcontacts = supportcontacts + "\n"
                        supportcontacts = supportcontacts + supportcontact
        if not supportcontacts:
            supportcontacts = _("No support contacts known")
        self.lblNPDownloadableDriverSupportContacts.set_text (supportcontacts)
        if driver.has_key ('licensetext'):
            self.frmNPDownloadableDriverLicenseTerms.show ()
            terms = driver.get('licensetext', _("Not specified."))
            self.tvNPDownloadableDriverLicense.get_buffer ().set_text (terms)
        else:
            self.frmNPDownloadableDriverLicenseTerms.hide ()
        if not driver['nonfreesoftware'] and not driver['patents']:
            self.rbtnNPDownloadLicenseYes.set_active (True)
            self.rbtnNPDownloadLicenseYes.hide ()
            self.rbtnNPDownloadLicenseNo.hide ()
        else:
            self.rbtnNPDownloadLicenseNo.set_active (True)
            self.rbtnNPDownloadLicenseYes.show ()
            self.rbtnNPDownloadLicenseNo.show ()
            self.frmNPDownloadableDriverLicenseTerms.show ()
            terms = driver.get('licensetext', _("Not specified."))
            self.tvNPDownloadableDriverLicense.get_buffer ().set_text (terms)

        self.setNPButtons()

    def getNPPPD(self):
        try:
            if self.rbtnNPFoomatic.get_active():
                model, iter = self.tvNPDrivers.get_selection().get_selected()
                nr = model.get_path(iter)[0]
                ppd = self.NPDrivers[nr]
            elif self.rbtnNPPPD.get_active():
                ppd = cups.PPD(self.filechooserPPD.get_filename())
            else:
                # PPD of the driver downloaded from OpenPrinting XXX
                treeview = self.tvNPDownloadableDrivers
                model, iter = treeview.get_selection ().get_selected ()
                driver = model.get_value (iter, 1)
                if driver.has_key ('ppds'):
                    # Only need to download a PPD.
                    if (len(driver['ppds']) > 0):
                        file_to_download = driver['ppds'][0]
                        debugprint ("ppd file to download [" + file_to_download+ "]")
                        file_to_download = file_to_download.strip()
                        if (len(file_to_download) > 0):
                            ppdurlobj = urllib.urlopen(file_to_download)
                            ppdcontent = ppdurlobj.read()
                            ppdurlobj.close()
                            (tmpfd, ppdname) = tempfile.mkstemp()
                            debugprint(ppdname)
                            ppdfile = os.fdopen(tmpfd, 'w')
                            ppdfile.write(ppdcontent)
                            ppdfile.close()
                            ppd = cups.PPD(ppdname)
                            os.unlink(ppdname)

        except RuntimeError, e:
            debugprint ("RuntimeError: " + str(e))
            if self.rbtnNPFoomatic.get_active():
                # Foomatic database problem of some sort.
                err_title = _('Database error')
                err_text = _("The '%s' driver cannot be "
                             "used with printer '%s %s'.")
                model, iter = (self.tvNPDrivers.get_selection().
                               get_selected())
                nr = model.get_path(iter)[0]
                driver = self.NPDrivers[nr]
                if driver.startswith ("gutenprint"):
                    # This printer references some XML that is not
                    # installed by default.  Point the user at the
                    # package they need to install.
                    err = _("You will need to install the '%s' package "
                            "in order to use this driver.") % \
                            "gutenprint-foomatic"
                else:
                    err = err_text % (driver, self.NPMake, self.NPModel)
            elif self.rbtnNPPPD.get_active():
                # This error came from trying to open the PPD file.
                err_title = _('PPD error')
                filename = self.filechooserPPD.get_filename()
                err = _('Failed to read PPD file.  Possible reason '
                        'follows:') + '\n'
                try:
                    # We want this to be in the current natural language,
                    # so we intentionally don't set LC_ALL=C here.
                    p = subprocess.Popen (['/usr/bin/cupstestppd',
                                           '-rvv', filename],
                                          close_fds=True,
                                          stdin=file("/dev/null"),
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
                    (stdout, stderr) = p.communicate ()
                    err += stdout
                except:
                    # Problem executing command.
                    raise
            else:
                # Failed to get PPD downloaded from OpenPrinting XXX
                err_title = _('Downloadable drivers')
                err = _("Failed to download PPD.")

            show_error_dialog (err_title, err, self.NewPrinterWindow)
            return None

        debugprint("ppd: " + repr(ppd))
        if isinstance(ppd, str) or isinstance(ppd, unicode):
            self.cups._begin_operation (_("fetching PPD"))
            try:
                if ppd != "raw":
                    f = self.cups.getServerPPD(ppd)
                    ppd = cups.PPD(f)
                    os.unlink(f)
            except RuntimeError:
                nonfatalException()
                debugprint ("libcups from CUPS 1.3 not available: never mind")
            except cups.IPPError:
                nonfatalException()
                debugprint ("CUPS 1.3 server not available: never mind")

            self.cups._end_operation ()

        return ppd

    # Installable Options

    def fillNPInstallableOptions(self):
        debugprint ("Examining installable options")
        self.installable_options = False
        self.options = { }

        container = self.vbNPInstallOptions
        for child in container.get_children():
            container.remove(child)

        if not self.ppd:
            l = gtk.Label(_("No Installable Options"))
            container.add(l)
            l.show()
            debugprint ("No PPD so no installable options")
            return

        # build option tabs
        for group in self.ppd.optionGroups:
            if group.name != "InstallableOptions":
                continue
            self.installable_options = True

            table = gtk.Table(1, 3, False)
            table.set_col_spacings(6)
            table.set_row_spacings(6)
            container.add(table)
            rows = 0

            for nr, option in enumerate(group.options):
                if option.keyword == "PageRegion":
                    continue
                rows += 1
                table.resize (rows, 3)
                o = OptionWidget(option, self.ppd, self)
                table.attach(o.conflictIcon, 0, 1, nr, nr+1, 0, 0, 0, 0)

                hbox = gtk.HBox()
                if o.label:
                    a = gtk.Alignment (0.5, 0.5, 1.0, 1.0)
                    a.set_padding (0, 0, 0, 6)
                    a.add (o.label)
                    table.attach(a, 1, 2, nr, nr+1, gtk.FILL, 0, 0, 0)
                    table.attach(hbox, 2, 3, nr, nr+1, gtk.FILL, 0, 0, 0)
                else:
                    table.attach(hbox, 1, 3, nr, nr+1, gtk.FILL, 0, 0, 0)
                hbox.pack_start(o.selector, False)
                self.options[option.keyword] = o
        if not self.installable_options:
            l = gtk.Label(_("No Installable Options"))
            container.add(l)
            l.show()
        self.scrNPInstallableOptions.hide()
        self.scrNPInstallableOptions.show_all()


    # Create new Printer
    def on_btnNPApply_clicked(self, widget):
        if self.fetchDevices_conn:
            self.fetchDevices_conn.destroy ()
            self.fetchDevices_conn = None
            self.dec_spinner_task ()

        if self.ppdsloader:
            self.ppdsloader.destroy ()
            self.ppdsloader = None

        if self.printer_finder:
            self.printer_finder.cancel ()
            self.printer_finder = None
            self.dec_spinner_task ()

        if self.dialog_mode in ("class", "printer", "printer_with_uri"):
            name = unicode (self.entNPName.get_text())
            location = unicode (self.entNPLocation.get_text())
            info = unicode (self.entNPDescription.get_text())
        else:
            name = self._name

        # Whether to check for missing drivers.
        check = False
        checkppd = None
        ppd = self.ppd

        if self.dialog_mode == "class":
            members = getCurrentClassMembers(self.tvNCMembers)
            try:
                for member in members:
                    self.cups.addPrinterToClass(member, name)
            except cups.IPPError, (e, msg):
                self.show_IPP_Error(e, msg)
                return
        elif self.dialog_mode == "printer" or \
                self.dialog_mode == "printer_with_uri":
            uri = None
            if self.device.uri:
                uri = self.device.uri
            else:
                uri = self.getDeviceURI()
            if not self.ppd: # XXX needed?
                # Go back to previous page to re-select driver.
                self.nextNPTab(-1)
                return

            # write Installable Options to ppd
            for option in self.options.itervalues():
                option.writeback()

            busy (self.NewPrinterWindow)
            while gtk.events_pending ():
                gtk.main_iteration ()
            self.cups._begin_operation (_("adding printer %s") % name)
            try:
                if isinstance(ppd, str) or isinstance(ppd, unicode):
                    self.cups.addPrinter(name, ppdname=ppd,
                         device=uri, info=info, location=location)
                    check = True
                elif ppd is None: # raw queue
                    self.cups.addPrinter(name, device=uri,
                                         info=info, location=location)
                else:
                    cupshelpers.setPPDPageSize(ppd, self.language[0])
                    self.cups.addPrinter(name, ppd=ppd, device=uri,
                                         info=info, location=location)
                    check = True
                    checkppd = ppd
            except cups.IPPError, (e, msg):
                ready (self.NewPrinterWindow)
                self.show_IPP_Error(e, msg)
                self.cups._end_operation()
                return
            except:
                ready (self.NewPrinterWindow)
                self.cups._end_operation()
                fatalException (1)
            self.cups._end_operation()
            ready (self.NewPrinterWindow)
        if self.dialog_mode in ("class", "printer", "printer_with_uri"):
            self.cups._begin_operation (_("modifying printer %s") % name)
            try:
                cupshelpers.activateNewPrinter (self.cups, name)
                self.cups.setPrinterLocation(name, location)
                self.cups.setPrinterInfo(name, info)
            except cups.IPPError, (e, msg):
                self.show_IPP_Error(e, msg)
                self.cups._end_operation ()
                return
            self.cups._end_operation ()
        elif self.dialog_mode == "device":
            self.cups._begin_operation (_("modifying printer %s") % name)
            try:
                uri = self.getDeviceURI()
                self.cups.addPrinter(name, device=uri)
            except cups.IPPError, (e, msg):
                self.show_IPP_Error(e, msg)
                self.cups._end_operation ()
                return
            self.cups._end_operation ()
        elif self.dialog_mode == "ppd":
            if not ppd:
                ppd = self.ppd = self.getNPPPD()
                if not ppd:
                    # Go back to previous page to re-select driver.
                    self.nextNPTab(-1)
                    return

            self.cups._begin_operation (_("modifying printer %s") % name)
            # set ppd on server and retrieve it
            # cups doesn't offer a way to just download a ppd ;(=
            raw = False
            if isinstance(ppd, str) or isinstance(ppd, unicode):
                if self.rbtnChangePPDasIs.get_active():
                    # To use the PPD as-is we need to prevent CUPS copying
                    # the old options over.  Do this by setting it to a
                    # raw queue (no PPD) first.
                    try:
                        self.cups.addPrinter(name, ppdname='raw')
                    except cups.IPPError, (e, msg):
                        self.show_IPP_Error(e, msg)
                try:
                    self.cups.addPrinter(name, ppdname=ppd)
                except cups.IPPError, (e, msg):
                    self.show_IPP_Error(e, msg)
                    self.cups._end_operation ()
                    return

                try:
                    filename = self.cups.getPPD(name)
                    ppd = cups.PPD(filename)
                    os.unlink(filename)
                except cups.IPPError, (e, msg):
                    if e == cups.IPP_NOT_FOUND:
                        raw = True
                    else:
                        self.show_IPP_Error(e, msg)
                        self.cups._end_operation ()
                        return
            else:
                # We have an actual PPD to upload, not just a name.
                if ((not self.rbtnChangePPDasIs.get_active()) and
                    isinstance (self.orig_ppd, cups.PPD)):
                    cupshelpers.copyPPDOptions(self.orig_ppd, ppd)
                else:
                    cupshelpers.setPPDPageSize(ppd, self.language[0])

                # write Installable Options to ppd
                for option in self.options.itervalues():
                    option.writeback()

                try:
                    self.cups.addPrinter(name, ppd=ppd)
                except cups.IPPError, (e, msg):
                    self.show_IPP_Error(e, msg)
                    self.cups._end_operation ()
                    return

            self.cups._end_operation ()

            if not raw:
                check = True
                checkppd = ppd

        self.NewPrinterWindow.hide()
        if self.dialog_mode in ["printer", "printer_with_uri", "class"]:
            self.emit ('printer-added', name)
        else:
            self.emit ('printer-modified', name, self.orig_ppd != self.ppd)

        self.device = None
        del self.printers

def show_help():
    print ("\nThis is the test/debug mode of the new-printer dialog of " \
           "system-config-printer.\n\n"
           "Options:\n\n"
           "  --setup-printer URI\n"
           "            Select the (detected) CUPS device URI on start up\n"
           "            and run the new-printer wizard for it.\n\n"
           "  --devid   Supply a device ID which should be used for the\n"
           "            setup of the new printer with \"--setup-printer\".\n"
           "            This can be any printer's ID, so that driver \n"
           "            selection can be tested for printers which are not\n"
           "            physically available.\n")

gobject.type_register (NewPrinterGUI)

if __name__ == '__main__':
    import getopt
    try:
        opts, args = getopt.gnu_getopt (sys.argv[1:], '',
                                        ['setup-printer=',
                                         'devid='])
    except getopt.GetoptError:
        show_help ()
        sys.exit (1)

    setup_printer = None
    devid = ""
    for opt, optarg in opts:
        if opt == '--setup-printer':
            setup_printer = optarg
        elif opt == '--devid':
            devid = optarg

    os.environ["SYSTEM_CONFIG_PRINTER_UI"] = "ui"
    import ppdippstr
    import locale
    locale.setlocale (locale.LC_ALL, "")
    ppdippstr.init ()
    gobject.threads_init ()
    set_debugging (True)

    n = NewPrinterGUI ()
    def on_signal (*args):
        gtk.main_quit ()

    n.connect ("printer-added", on_signal)
    n.connect ("printer-modified", on_signal)
    n.connect ("dialog-canceled", on_signal)
    if setup_printer != None:
        n.init ("printer_with_uri", device_uri=setup_printer, devid=devid)
    else:
        n.init ("printer")
    gtk.main ()
