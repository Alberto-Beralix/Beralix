# -*- coding: utf-8 -*-
#
# Author: Alejandro J. Cura <alecu@canonical.com>
#
# Copyright 2010 Canonical Ltd.
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
"""Log into the Zeitgeist daemon."""

from twisted.internet.defer import Deferred

from ubuntuone.logger import logging

logger = logging.getLogger('ubuntuone.eventlog.zglog')


class ZeitgeistLogger(object):
    """A class that logs zeitgeist events."""
    client = None

    def __init__(self):
        """Initialize this instance."""
        try:
            from zeitgeist.client import ZeitgeistClient
            self.client = ZeitgeistClient()
            logger.info("Zeitgeist support initialized.")
        except Exception:
            logger.exception("Zeitgeist support not started:")

    def log(self, event):
        """Log a zeitgeist event."""
        d = Deferred()
        if self.client:
            logger.info("Logging Zeitgeist event: %r", event)
            self.client.insert_event(event, d.callback, d.errback)
        else:
            d.callback([])
        return d
