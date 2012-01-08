# Orca
#
# Copyright 2005-2009 Sun Microsystems Inc.
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

"""Custom script for rhythmbox."""

__id__ = "$Id$"
__version__   = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2005-2009 Sun Microsystems Inc."
__license__   = "LGPL"

import orca.speech_generator as speech_generator

class SpeechGenerator(speech_generator.SpeechGenerator):

    # pylint: disable-msg=W0142

    """Overrides _generateRealTableCell to correctly handle the table
    cells in the Library table.
    """
    def __init__(self, script):
        speech_generator.SpeechGenerator.__init__(self, script)

    def _generateRealTableCell(self, obj, **args):
        return speech_generator.SpeechGenerator._generateRealTableCell(
            self, self._script.adjustTableCell(obj), **args)
