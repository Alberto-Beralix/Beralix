#!/usr/bin/python

import sys
import os

import warnings
warnings.filterwarnings("ignore", "apt API not stable yet", FutureWarning)
import apt
import apt_pkg
import logging

logging.basicConfig(level=logging.DEBUG,
                    filename="/var/log/dist-upgrade/apt-autoinst-fixup.log",
                    format='%(asctime)s %(levelname)s %(message)s',
                    filemode='w')

cache = apt.Cache()

min_version = "0.6.20ubuntu13"
if apt_pkg.VersionCompare(cache["python-apt"].installedVersion, min_version) < 0:
    logging.error("Need at least python-apt version %s " % min_version)
    sys.exit(1)


# figure out what needs fixup
logging.debug("Starting to check for auto-install states that need fixup")
need_fixup = set()

# work around #105663
need_fixup.add("mdadm")

for pkg in cache:
    if pkg.is_installed and pkg.section == "metapackages":
        logging.debug("Found installed meta-pkg: '%s' " % pkg.name)
        dependsList = pkg._pkg.CurrentVer.DependsList
        for t in ["Depends","PreDepends","Recommends"]:
            if dependsList.has_key(t):
                for depOr in dependsList[t]:
                    for dep in depOr:
                        depname = dep.TargetPkg.Name
                        if (cache[depname].is_installed and
                            cache._depcache.is_auto_installed(cache[depname]._pkg)):
                            logging.info("Removed auto-flag from package '%s'" % depname)
                            need_fixup.add(depname)
        
# now go through the tagfile and actually fix it up
if len(need_fixup) > 0:
    # action is set to zero (reset the auto-flag)
    action = 0
    STATE_FILE = apt_pkg.Config.FindDir("Dir::State") + "extended_states"
    # open the statefile
    if os.path.exists(STATE_FILE):
        tagfile = apt_pkg.ParseTagFile(open(STATE_FILE))
        outfile = open(STATE_FILE+".tmp","w")
        while tagfile.Step():
            pkgname = tagfile.Section.get("Package")
            autoInst = tagfile.Section.get("Auto-Installed")
            if pkgname in need_fixup:
                newsec = apt_pkg.RewriteSection(tagfile.Section,
                                                [],
                                       [ ("Auto-Installed",str(action)) ]
                                       )
                outfile.write(newsec+"\n")
            else:
                outfile.write(str(tagfile.Section)+"\n")
        os.rename(STATE_FILE, STATE_FILE+".fixup-save")
        os.rename(outfile.name, STATE_FILE)
        os.chmod(STATE_FILE, 0644)



