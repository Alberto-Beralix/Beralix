# -*- coding: utf-8 -*-

# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
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

"""Client to use replication services."""

from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from ubuntuone.controlpanel.logger import setup_logging


logger = setup_logging('replication_client')

CONTACTS = 'contacts'
# we should get this list from somewhere else
REPLICATIONS = set([CONTACTS])


class ReplicationError(Exception):
    """A replication error."""


class NoPairingRecord(ReplicationError):
    """There is no pairing record."""


class InvalidIdError(ReplicationError):
    """The replication id is not valid."""


class NotExcludedError(ReplicationError):
    """The replication can not be replicated since is not excluded."""


class AlreadyExcludedError(ReplicationError):
    """The replication can not be excluded since is already excluded."""


def get_replication_proxy(replication_module=None):
    """Return a proxy to the replication client."""
    d = Deferred()
    if replication_module is None:
        # delay import in case DC is not installed at module import time
        # Unable to import 'desktopcouch.application.replication_services'
        # pylint: disable=W0404,F0401
        from desktopcouch.application.replication_services \
            import ubuntuone as replication_module
    try:
        result = replication_module.ReplicationExclusion()
    except ValueError:
        d.errback(NoPairingRecord())
    else:
        d.callback(result)

    return d


@inlineCallbacks
def get_replications():
    """Retrieve the list of replications."""
    yield get_replication_proxy()
    returnValue(REPLICATIONS)


@inlineCallbacks
def get_exclusions():
    """Retrieve the list of exclusions."""
    proxy = yield get_replication_proxy()
    result = proxy.all_exclusions()
    returnValue(result)


@inlineCallbacks
def replicate(replication_id):
    """Remove replication_id from the exclusions list."""
    replications = yield get_replications()
    if replication_id not in replications:
        raise InvalidIdError(replication_id)

    exclusions = yield get_exclusions()
    if replication_id not in exclusions:
        raise NotExcludedError(replication_id)

    proxy = yield get_replication_proxy()
    yield proxy.replicate(replication_id)


@inlineCallbacks
def exclude(replication_id):
    """Add replication_id to the exclusions list."""
    replications = yield get_replications()
    if replication_id not in replications:
        raise InvalidIdError(replication_id)

    exclusions = yield get_exclusions()
    if replication_id in exclusions:
        raise AlreadyExcludedError(replication_id)

    proxy = yield get_replication_proxy()
    yield proxy.exclude(replication_id)
