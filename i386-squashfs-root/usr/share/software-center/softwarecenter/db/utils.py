# Copyright (C) 2011 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import xapian

def get_query_for_pkgnames(pkgnames):
    """ return a xapian query that matches exactly the list of pkgnames """
    query = xapian.Query()
    for pkgname in pkgnames:
        query = xapian.Query(xapian.Query.OP_OR,
                             query,
                             xapian.Query("XP"+pkgname))
        query = xapian.Query(xapian.Query.OP_OR,
                             query,
                             xapian.Query("AP"+pkgname))
    return query
