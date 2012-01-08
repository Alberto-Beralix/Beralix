# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Markus Korn <thekorn@gmx.de>
# Copyright © 2009-2010 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
from xdg import BaseDirectory

from zeitgeist.client import ZeitgeistDBusInterface

__all__ = [
	"log",
	"get_engine",
	"constants"
]

log = logging.getLogger("zeitgeist.engine")

_engine = None
def get_engine():
	""" Get the running engine instance or create a new one. """
	global _engine
	if _engine is None or _engine.is_closed():
		import main # _zeitgeist.engine.main
		_engine = main.ZeitgeistEngine()
	return _engine

class _Constants:
	# Directories
	DATA_PATH = os.environ.get("ZEITGEIST_DATA_PATH",
		BaseDirectory.save_data_path("zeitgeist"))
	DATABASE_FILE = os.environ.get("ZEITGEIST_DATABASE_PATH",
		os.path.join(DATA_PATH, "activity.sqlite"))
	DATABASE_FILE_BACKUP = os.environ.get("ZEITGEIST_DATABASE_BACKUP_PATH",
		os.path.join(DATA_PATH, "activity.sqlite.bck"))
	DEFAULT_LOG_PATH = os.path.join(BaseDirectory.xdg_cache_home,
		"zeitgeist", "daemon.log")
	
	# D-Bus
	DBUS_INTERFACE = ZeitgeistDBusInterface.INTERFACE_NAME
	SIG_EVENT = "asaasay"
	
	# Required version of DB schema
	CORE_SCHEMA="core"
	CORE_SCHEMA_VERSION = 4
	
	USER_EXTENSION_PATH = os.path.join(DATA_PATH, "extensions")
	
	# configure runtime cache for events
	# default size is 2000
	CACHE_SIZE = int(os.environ.get("ZEITGEIST_CACHE_SIZE", 2000))
	log.debug("Cache size = %i" %CACHE_SIZE)

constants = _Constants()
