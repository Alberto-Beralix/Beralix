import logging
import shutil

from DistUpgradeFetcherCore import DistUpgradeFetcherCore

class DistUpgradeFetcherSelf(DistUpgradeFetcherCore):
    def __init__(self, new_dist, progress, options, view):
        DistUpgradeFetcherCore.__init__(self,new_dist,progress)
        self.view = view
        # user chose to use the network, otherwise it would not be
        # possible to download self
        self.run_options += ["--with-network"]
        # make sure to run self with proper options
        if options.cdromPath is not None:
            self.run_options += ["--cdrom=%s" % options.cdromPath]
        if options.frontend is not None:
            self.run_options += ["--frontend=%s" % options.frontend]

    def error(self, summary, message):
        return self.view.error(summary, message)

    def runDistUpgrader(self):
        " overwrite to ensure that the log is copied "
        # copy log so it isn't overwritten
        logging.info("runDistUpgrader() called, re-exec self")
        logging.shutdown()
        shutil.copy("/var/log/dist-upgrade/main.log",
                    "/var/log/dist-upgrade/main_update_self.log")
        # re-exec self
        DistUpgradeFetcherCore.runDistUpgrader(self)
