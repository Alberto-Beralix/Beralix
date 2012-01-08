# UnitySupport.py 
#  
#  Copyright (c) 2011 Canonical
#  
#  Author: Robert Roth <robert.roth.off@gmail.com>
#          Bilal Akhtar <bilalakhtar@ubuntu.com>
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU General Public License as 
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

import logging

HAVE_UNITY_SUPPORT=False
try:
    from gi.repository import Unity
    HAVE_UNITY_SUPPORT=True
except ImportError as e:
    logging.warn("can not import unity GI %s" % e)

class IUnitySupport(object):
    """ interface for unity support """
    def __init__(self, parent): pass
    def set_progress(self, progress): pass
    def show_progress(self, show=True): pass

class UnitySupportImpl(IUnitySupport):
    """ implementation of unity support (if unity is available) """

    def __init__(self, parent):
        # create launcher and quicklist
        usbcreator_launcher_entry = Unity.LauncherEntry.get_for_desktop_id(
            "usb-creator-gtk.desktop")
        self._unity = usbcreator_launcher_entry
    
    def set_progress(self, progress):
        self._unity.set_property("progress", progress)
    def show_progress(self, show=True):
        self._unity.set_property("progress_visible", show)
    
# check what to export to the clients
if HAVE_UNITY_SUPPORT:
    UnitySupport = UnitySupportImpl
else:
    # we just provide the empty interface 
    UnitySupport = IUnitySupport
