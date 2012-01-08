# remtest.py - estimate remaining time of some task
# Copyright (C) 2009  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import time

class RemainingTimeEstimator:

    """Estimate the remaining time of some task.
    
    The estimate is based on measurements of the progress of the task at
    various intervals. The caller occasionally feeds this class how much of a
    task has been achieved, and the total size of the task. The caller can

    The remaining time is estimated based on timings taken from calls to
    the estimate method.
    
    The caller may set the min_age and max_age attributes (defaults are
    one and five seconds, respectively). min_age is the minimum age of
    the measurements before speed is computed. max_age is the maximum age
    of measurements before they are discarded.
    
    """
    
    # The caller provides data via the 'estimate' method. We take the amount
    # of work done and total from the caller, and the current time from
    # time.time. Then we do an estimate by measuring the total amount of
    # work done during the last X seconds, and compute the speed from
    # that. Using the speed, we can compute the remaining time.
    
    def __init__(self):
        self.measurements = []
        self.min_age = 1.0 # seconds
        self.max_age = 5.0 # seconds
        
    def measure(self, done, total, current_time):
        self.measurements.append((done, current_time))
        while self.measurements:
            x, t = self.measurements[0]
            if t >= current_time - self.max_age:
                break
            del self.measurements[0]
        
    def compute_speed(self):
        """Compute speed from current set of measurements."""
        if not self.measurements:
            return None
        done_oldest, time_oldest = self.measurements[0]
        done_newest, time_newest = self.measurements[-1]
        duration = time_newest - time_oldest
        if duration < self.min_age:
            return None
        done = done_newest - done_oldest
        return done / duration
        
    def estimate(self, done, total):
        """Estimate remaining time, given work done and work total.
        
        Return tuple (remaining_time, speed), where time is in seconds,
        and speed is in units of work per second.
        
        If either can't be estimated, return a tuple of two Nones instead.
        
        Neither done nor total should decrease from call to call.
        
        """

        self.measure(done, total, time.time())
        speed = self.compute_speed()
        if speed:
            return (total - done) / speed, speed
        else:
            return None, None
