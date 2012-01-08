"""
The SyncDaemon reactor -- a less power-hungry version of twisted's gtk2reactor
"""
#
# This is the quickest way to make twisted's Gtk2Reactor use
# timeout_add_seconds instead of timeout_add; the former uses high-resolution
# timers, which are more power-intensive.
# It's pretty much verbatim from their source.

from twisted.python import log
from twisted.internet.main import installReactor
from twisted.internet.gtk2reactor import Gtk2Reactor
import gobject

class SyncDaemonReactor(Gtk2Reactor):
    """
    This is twisted.internet.Gtk2Reactor, but using timeout_add_seconds
    instead of timeout_add.
    """
    def __init__(self, use_gtk):
        Gtk2Reactor.__init__(self, use_gtk)
        # ugh... why would somebody make these private?
        self.__iteration = self._Gtk2Reactor__iteration
        self.__pending = self._Gtk2Reactor__pending
        self.__run = self._Gtk2Reactor__run

    def doIteration(self, delay):
        """
        Process some events
        """
        log.msg(channel='system', event='iteration', reactor=self)
        if self.__pending():
            self.__iteration(0)
            return
        # nothing to do, must delay
        if delay == 0:
            return # shouldn't delay, so just return
        self.doIterationTimer = gobject.timeout_add_seconds(
            int(delay), self.doIterationTimeout)
        # This will either wake up from IO or from a timeout.
        self.__iteration(1) # block
        # note: with the .simulate timer below, delays > 0.1 will always be
        # woken up by the .simulate timer
        if self.doIterationTimer:
            # if woken by IO, need to cancel the timer
            gobject.source_remove(self.doIterationTimer)
            self.doIterationTimer = None

    def run(self, installSignalHandlers=1):
        """
        See IReactorCore.run
        """
        self.startRunning(installSignalHandlers=installSignalHandlers)
        gobject.timeout_add_seconds(0, self.simulate)
        if self._started:
            self.__run()


    def simulate(self):
        """
        Run simulation loops and reschedule callbacks.
        """
        if self._simtag is not None:
            gobject.source_remove(self._simtag)
        self.runUntilCurrent()
        timeout = min(self.timeout(), 0.1)
        if timeout is None:
            timeout = 0.1
        # grumble
        self._simtag = gobject.timeout_add_seconds(int(timeout * 1010/1000),
                                                   self.simulate)


def install(use_gtk):
    """
    Configure the twisted mainloop to be run inside the glib mainloop.
    If use_gtk, then use the gtk mainloop instead.
    """
    installReactor(SyncDaemonReactor(use_gtk))
