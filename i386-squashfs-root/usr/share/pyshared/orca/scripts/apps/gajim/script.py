# Orca
#
# Copyright 2010 Joanmarie Diggs.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., Franklin Street, Fifth Floor,
# Boston MA  02110-1301 USA.

"""Custom script for Gajim."""

__id__        = "$Id$"
__version__   = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2010 Joanmarie Diggs."
__license__   = "LGPL"

import pyatspi

import orca.chat as chat
import orca.scripts.default as default

########################################################################
#                                                                      #
# The Empathy script class.                                            #
#                                                                      #
########################################################################

class Script(default.Script):

    def __init__(self, app):
        """Creates a new script for the given application."""

        # So we can take an educated guess at identifying the buddy list.
        #
        self._buddyListAncestries = [[pyatspi.ROLE_TABLE,
                                      pyatspi.ROLE_SCROLL_PANE,
                                      pyatspi.ROLE_FILLER,
                                      pyatspi.ROLE_SPLIT_PANE,
                                      pyatspi.ROLE_FILLER,
                                      pyatspi.ROLE_FRAME]]

        default.Script.__init__(self, app)

    def getChat(self):
        """Returns the 'chat' class for this script."""

        return chat.Chat(self, self._buddyListAncestries)

    def setupInputEventHandlers(self):
        """Defines InputEventHandler fields for this script that can be
        called by the key and braille bindings. Here we need to add the
        handlers for chat functionality.
        """

        default.Script.setupInputEventHandlers(self)
        self.inputEventHandlers.update(self.chat.inputEventHandlers)

    def getKeyBindings(self):
        """Defines the key bindings for this script. Here we need to add
        the keybindings associated with chat functionality.

        Returns an instance of keybindings.KeyBindings.
        """

        keyBindings = default.Script.getKeyBindings(self)

        bindings = self.chat.keyBindings
        for keyBinding in bindings.keyBindings:
            keyBindings.add(keyBinding)

        return keyBindings

    def getAppPreferencesGUI(self):
        """Return a GtkGrid containing the application unique configuration
        GUI items for the current application. The chat-related options get
        created by the chat module."""

        return self.chat.getAppPreferencesGUI()

    def setAppPreferences(self, prefs):
        """Write out the application specific preferences lines and set the
        new values. The chat-related options get written out by the chat
        module.

        Arguments:
        - prefs: file handle for application preferences.
        """

        self.chat.setAppPreferences(prefs)

    def onTextInserted(self, event):
        """Called whenever text is added to an object."""

        if self.chat.presentInsertedText(event):
            return

        default.Script.onTextInserted(self, event)

    def onWindowActivated(self, event):
        """Called whenever a toplevel window is activated."""

        # Hack to "tickle" the accessible hierarchy. Otherwise, the
        # events we need to present text added to the chatroom are
        # missing.
        #
        allPageTabs = self.utilities.descendantsWithRole(
            event.source, pyatspi.ROLE_PAGE_TAB)

        default.Script.onWindowActivated(self, event)
