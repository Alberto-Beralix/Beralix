# file_cruft_tests.py - unit tests for file_cruft.py
# Copyright (C) 2008, 2009  Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import subprocess
import tempfile

import unittest

import computerjanitor


class FileCruftTests(unittest.TestCase):

    def setUp(self):
        fd, self.pathname = tempfile.mkstemp()
        os.write(fd, "x" * 1024)
        os.close(fd)
        self.cruft = computerjanitor.FileCruft(self.pathname, "description")

    def tearDown(self):
        if False and os.path.exists(self.pathname):
            os.remove(self.pathname)

    def testReturnsCorrectPrefix(self):
        self.assertEqual(self.cruft.get_prefix(), "file")

    def testReturnsCorrectPrefixDescription(self):
        self.assertEqual(self.cruft.get_prefix_description(), "A file on disk")

    def testReturnsCorrectShortname(self):
        self.assertEqual(self.cruft.get_shortname(), self.pathname)

    def testReturnsCorrectName(self):
        self.assertEqual(self.cruft.get_name(), "file:%s" % self.pathname)

    def testReturnsCorrectDescription(self):
        self.assertEqual(self.cruft.get_description(), "description\n")

    def testReturnsCorrectDiskUsage(self):
        p = subprocess.Popen(["du", "-s", "-B", "1", self.pathname], 
                             stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        du = int(stdout.splitlines()[0].split("\t")[0])
        self.assertEqual(self.cruft.get_disk_usage(), du)
    
    def testDeletesPackage(self):
        self.assert_(os.path.exists(self.pathname))
        self.cruft.cleanup()
        self.assertFalse(os.path.exists(self.pathname))
