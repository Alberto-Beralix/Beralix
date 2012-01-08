# missing_package_cruft_tests.py - unit tests for missing_package_cruft.py
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


import unittest

import computerjanitor


class MockAptPackage(object):

    def __init__(self):
        self.name = "name"
        self.summary = "summary"
        self.installedSize = 12765
        self.installed = False
        
    def markInstall(self):
        self.installed = True


class MissingPackageCruftTests(unittest.TestCase):

    def setUp(self):
        self.pkg = MockAptPackage()
        self.cruft = computerjanitor.MissingPackageCruft(self.pkg)

    def testReturnsCorrectPrefix(self):
        self.assertEqual(self.cruft.get_prefix(), "install-deb")

    def testReturnsCorrectPrefixDescription(self):
        self.assert_("Install" in self.cruft.get_prefix_description())

    def testReturnsCorrectShortname(self):
        self.assertEqual(self.cruft.get_shortname(), "name")

    def testReturnsCorrectName(self):
        self.assertEqual(self.cruft.get_name(), "install-deb:name")

    def testReturnsCorrectDescription(self):
        self.assert_("name" in self.cruft.get_description())

    def testSetsDescriptionWhenAsked(self):
        pkg = computerjanitor.MissingPackageCruft(self.pkg, "foo")
        self.assertEqual(pkg.get_description(), "foo")
    
    def testInstallsPackage(self):
        self.cruft.cleanup()
        self.assert_(self.pkg.installed)
