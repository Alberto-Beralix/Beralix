# UpdateList.py 
#  
#  Copyright (c) 2004-2008 Canonical
#  
#  Author: Michael Vogt <mvo@debian.org>
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

import warnings
warnings.filterwarnings("ignore", "Accessed deprecated property", DeprecationWarning)

from gettext import gettext as _
import os
import sys

class UpdateOrigin(object):
  def __init__(self, desc, importance):
    self.packages = []
    self.importance = importance
    self.description = desc

class UpdateList(object):
  """
  class that contains the list of available updates in 
  self.pkgs[origin] where origin is the user readable string
  """

  def __init__(self, parent):
    # a map of packages under their origin
    try:
        pipe = os.popen("lsb_release -c -s")
        dist = pipe.read().strip()
        del pipe
    except Exception, e:
        print "Error in lsb_release: %s" % e
        parent.error(_("Failed to detect distribution"),
                     _("A error '%s' occurred while checking what system "
                       "you are using.") % e)
        sys.exit(1)
    self.distUpgradeWouldDelete = 0
    self.pkgs = {}
    self.num_updates = 0
    self.matcher = self.initMatcher(dist)
    
  def initMatcher(self, dist):
      # (origin, archive, description, importance)
      matcher_templates = [
          ("%s-security" % dist, "Ubuntu", _("Important security updates"),10),
          ("%s-updates" % dist, "Ubuntu", _("Recommended updates"), 9),
          ("%s-proposed" % dist, "Ubuntu", _("Proposed updates"), 8),
          ("%s-backports" % dist, "Ubuntu", _("Backports"), 7),
          (dist, "Ubuntu", _("Distribution updates"), 6)
      ]
      matcher = {}
      for (origin, archive, desc, importance) in matcher_templates:
          matcher[(origin, archive)] = UpdateOrigin(desc, importance)
      matcher[(None,None)] = UpdateOrigin(_("Other updates"), -1)
      return matcher

  def update(self, cache):
    self.held_back = []

    # do the upgrade
    self.distUpgradeWouldDelete = cache.saveDistUpgrade()

    #dselect_upgrade_origin = UpdateOrigin(_("Previous selected"), 1)

    # sort by origin
    for pkg in cache:
      if pkg.is_upgradable or pkg.marked_install:
        if pkg.candidateOrigin == None:
            # can happen for e.g. locked packages
            # FIXME: do something more sensible here (but what?)
            print "WARNING: upgradable but no canidateOrigin?!?: ", pkg.name
            continue
        # check where the package belongs
        origin_node = cache.matchPackageOrigin(pkg, self.matcher)
        if not self.pkgs.has_key(origin_node):
          self.pkgs[origin_node] = []
        self.pkgs[origin_node].append(pkg)
        self.num_updates = self.num_updates + 1
      if pkg.is_upgradable and not (pkg.marked_upgrade or pkg.marked_install):
          self.held_back.append(pkg.name)
    for l in self.pkgs.keys():
      self.pkgs[l].sort(lambda x,y: cmp(x.name,y.name))
    self.keepcount = cache._depcache.keep_count

