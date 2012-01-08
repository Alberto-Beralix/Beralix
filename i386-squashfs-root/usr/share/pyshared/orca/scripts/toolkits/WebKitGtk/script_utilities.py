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

__id__ = "$Id$"
__version__   = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2010 Joanmarie Diggs."
__license__   = "LGPL"

import pyatspi

import orca.script_utilities as script_utilities

#############################################################################
#                                                                           #
# Utilities                                                                 #
#                                                                           #
#############################################################################

class Utilities(script_utilities.Utilities):

    def __init__(self, script):
        """Creates an instance of the Utilities class.

        Arguments:
        - script: the script with which this instance is associated.
        """

        script_utilities.Utilities.__init__(self, script)

    def headingLevel(self, obj):
        """Determines the heading level of the given object.  A value
        of 0 means there is no heading level."""

        level = 0

        if obj is None:
            return level

        if obj.getRole() == pyatspi.ROLE_HEADING:
            attributes = obj.getAttributes()
            if attributes is None:
                return level
            for attribute in attributes:
                if attribute.startswith("level:"):
                    level = int(attribute.split(":")[1])
                    break

        return level

    def isWebKitGtk(self, obj):
        """Returns True if this object is a WebKitGtk object."""

        if not obj:
            return False

        attrs = dict([attr.split(':', 1) for attr in obj.getAttributes()])
        return attrs.get('toolkit', '') == 'WebKitGtk'

    def isReadOnlyTextArea(self, obj):
        """Returns True if obj is a text entry area that is read only."""

        if not obj.getRole() == pyatspi.ROLE_ENTRY:
            return False

        state = obj.getState()
        readOnly = state.contains(pyatspi.STATE_FOCUSABLE) \
                   and not state.contains(pyatspi.STATE_EDITABLE)

        return readOnly

    def adjustForLinks(self, obj, line, startOffset):
        """Adjust line to include the word "link" after any hypertext links.
        Overridden here to deal with parents containing children which in
        turn contain the links and implement the hypertext interface.

        Arguments:
        - obj: the accessible object that this line came from.
        - line: the string to adjust for links.
        - startOffset: the caret offset at the start of the line.

        Returns: a new line adjusted to add the speaking of "link" after
        text which is also a link.
        """

        adjustedLine = script_utilities.Utilities.adjustForLinks(
                self, obj, line, startOffset)

        roles = [pyatspi.ROLE_LIST_ITEM]
        if not obj.getRole() in roles or not obj.childCount:
            return adjustedLine

        child = obj[0]
        try:
            hypertext = obj.queryHypertext()
            nLinks = hypertext.getNLinks()
        except NotImplementedError:
            nLinks = 0

        if not nLinks:
            try:
                hypertext = child.queryHypertext()
                nLinks = hypertext.getNLinks()
            except NotImplementedError:
                pass

        if not nLinks:
            return adjustedLine

        try:
            objText = obj.queryText()
            childText = child.queryText()
        except NotImplementedError:
            return adjustedLine

        adjustment = objText.characterCount - childText.characterCount
        if adjustment:
            adjustedLine = script_utilities.Utilities.adjustForLinks(
                self, child, line, startOffset - adjustment)

        return adjustedLine
