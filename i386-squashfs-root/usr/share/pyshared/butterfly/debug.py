# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2009 Collabora Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import telepathy

class ButterflyDebug(telepathy.server.Debug):
    """Butterfly debug interface

    Implements the org.freedesktop.Telepathy.Debug interface"""

    def __init__(self, conn_manager):
        telepathy.server.Debug.__init__(self, conn_manager)

    def get_record_name(self, record):
        name = record.name
        if name.startswith("Butterfly."):
            domain, category = name.split('.', 1)
        else:
            domain = "papyon"
            category = name
        name = domain.lower() + "/" + category.lower()
        return name
