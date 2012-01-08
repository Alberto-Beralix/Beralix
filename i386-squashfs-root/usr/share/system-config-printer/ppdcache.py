#!/usr/bin/python

## Copyright (C) 2010 Red Hat, Inc.
## Authors:
##  Tim Waugh <twaugh@redhat.com>

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

import asyncconn
import cups
import gobject
import gtk
import os
import tempfile
from debug import *

class PPDCache:
    def __init__ (self, host=None, port=None, encryption=None):
        self._cups = None
        self._exc = None
        self._cache = dict()
        self._modtimes = dict()
        self._host = host
        self._port = port
        self._encryption = encryption
        self._queued = list()
        self._connecting = False
        debugprint ("+%s" % self)

    def __del__ (self):
        debugprint ("-%s" % self)
        if self._cups:
            self._cups.destroy ()

    def fetch_ppd (self, name, callback, check_uptodate=True):
        if check_uptodate and self._modtimes.has_key (name):
            # We have getPPD3 so we can check whether the PPD is up to
            # date.
            debugprint ("%s: check if %s is up to date" % (self, name))
            self._cups.getPPD3 (name,
                                modtime=self._modtimes[name],
                                reply_handler=lambda c, r:
                                    self._got_ppd3 (c, name, r, callback),
                                error_handler=lambda c, r:
                                    self._got_ppd3 (c, name, r, callback))
            return

        try:
            f = self._cache[name]
        except RuntimeError, e:
            self._schedule_callback (callback, name, None, e)
            return
        except KeyError:
            if not self._cups:
                self._queued.append ((name, callback))
                if not self._connecting:
                    self._connect ()

                return

            debugprint ("%s: fetch PPD for %s" % (self, name))
            try:
                self._cups.getPPD3 (name,
                                    reply_handler=lambda c, r:
                                        self._got_ppd3 (c, name, r, callback),
                                    error_handler=lambda c, r:
                                        self._got_ppd3 (c, name, r, callback))
            except AttributeError:
                # getPPD3 requires pycups >= 1.9.50
                self._cups.getPPD (name,
                                   reply_handler=lambda c, r:
                                       self._got_ppd (c, name, r, callback),
                                   error_handler=lambda c, r:
                                       self._got_ppd (c, name, r, callback))

            return

        # Copy from our file object to a new temporary file, create a
        # PPD object from it, then remove the file.  This way we don't
        # leave temporary files around even though we are caching...
        f.seek (0)
        (tmpfd, tmpfname) = tempfile.mkstemp ()
        tmpf = file (tmpfname, "w")
        tmpf.writelines (f.readlines ())
        del tmpf
        try:
            ppd = cups.PPD (tmpfname)
            os.unlink (tmpfname)
            self._schedule_callback (callback, name, ppd, None)
        except Exception, e:
            os.unlink (tmpfname)
            self._schedule_callback (callback, name, None, e)

    def _connect (self, callback=None):
        self._connecting = True
        asyncconn.Connection (host=self._host, port=self._port,
                              encryption=self._encryption,
                              reply_handler=self._connected,
                              error_handler=self._connected)

    def _got_ppd (self, connection, name, result, callback):
        if isinstance (result, Exception):
            self._schedule_callback (callback, name, result, None)
        else:
            debugprint ("%s: caching %s" % (self, result))
            # Store an open file object, then remove the actual file.
            # This way we don't leave temporary files around.
            self._cache[name] = file (result)
            os.unlink (result)
            self.fetch_ppd (name, callback)

    def _got_ppd3 (self, connection, name, result, callback):
        (status, modtime, filename) = result
        if status in [cups.HTTP_OK, cups.HTTP_NOT_MODIFIED]:
            if status == cups.HTTP_OK:
                debugprint ("%s: caching %s (%s) - %s" % (self,
                                                          filename,
                                                          modtime,
                                                          status))
                # Store an open file object, then remove the actual
                # file.  This way we don't leave temporary files
                # around.
                self._cache[name] = file (filename)
                os.unlink (filename)
                self._modtimes[name] = modtime

            self.fetch_ppd (name, callback, check_uptodate=False)
        else:
            self._schedule_callback (callback, name,
                                     None, cups.HTTPError (status))

    def _connected (self, connection, exc):
        self._connecting = False
        if isinstance (exc, Exception):
            self._cups = None
            self._exc = exc
        else:
            self._cups = connection

        queued = self._queued
        self._queued = list()
        for name, callback in queued:
            self.fetch_ppd (name, callback)

    def _schedule_callback (self, callback, name, result, exc):
        def cb_func (callback, name, result, exc):
            gtk.gdk.threads_enter ()
            callback (name, result, exc)
            gtk.gdk.threads_leave ()
            return False

        gobject.idle_add (cb_func, callback, name, result, exc)

if __name__ == "__main__":
    import sys
    from debug import *
    set_debugging (True)
    gobject.threads_init ()
    gtk.gdk.threads_init ()
    loop = gobject.MainLoop ()

    def signal (name, result, exc):
        debugprint ("**** %s" % name)
        debugprint (result)
        debugprint (exc)

    c = cups.Connection ()
    printers = c.getPrinters ()
    del c

    cache = PPDCache ()
    p = None
    for p in printers:
        cache.fetch_ppd (p, signal)

    if p:
        gobject.timeout_add_seconds (1, cache.fetch_ppd, p, signal)
    loop.run ()
