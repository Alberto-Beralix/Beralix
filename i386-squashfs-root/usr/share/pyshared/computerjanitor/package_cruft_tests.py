# package_cruft_tests.py - unit tests for package_cruft.py
# Copyright (C) 2008  Canonical, Ltd.
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


import unittest

import computerjanitor


class MockAptPackage(object):

    def __init__(self):
        self.name = "name"
        self.summary = "summary"
        self.installedSize = 12765
        self.deleted = False
        
    def markDelete(self):
        self.deleted = True


class PackageCruftTests(unittest.TestCase):

    def setUp(self):
        self.pkg = MockAptPackage()
        self.cruft = computerjanitor.PackageCruft(self.pkg, "description")

    def testReturnsCorrectPrefix(self):
        self.assertEqual(self.cruft.get_prefix(), "deb")

    def testReturnsCorrectPrefixDescription(self):
        self.assertEqual(self.cruft.get_prefix_description(), ".deb package")

    def testReturnsCorrectShortname(self):
        self.assertEqual(self.cruft.get_shortname(), "name")

    def testReturnsCorrectName(self):
        self.assertEqual(self.cruft.get_name(), "deb:name")

    def testReturnsCorrectDescription(self):
        self.assertEqual(self.cruft.get_description(), 
                         "description\n\nsummary")

    def testReturnsCorrectDiskUsage(self):
        self.assertEqual(self.cruft.get_disk_usage(), 12765)
    
    def testDeletesPackage(self):
        self.cruft.cleanup()
        self.assert_(self.pkg.deleted)
