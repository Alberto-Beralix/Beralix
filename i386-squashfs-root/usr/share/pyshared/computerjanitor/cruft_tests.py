# cruft_tests.py - unit tests for cruft.py
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


class CruftTests(unittest.TestCase):

    def setUp(self):
        self.cruft = computerjanitor.Cruft()

    def testReturnsClassNameAsDefaultPrefix(self):
        class Mockup(computerjanitor.Cruft):
            pass
        self.assertEqual(Mockup().get_prefix(), "Mockup")

    def testReturnsEmptyStringAsDefaultPrefixDescription(self):
        self.assertEqual(self.cruft.get_prefix_description(), "")

    def testReturnsDescriptionAsDefaultPrefixDescription(self):
        self.cruft.get_description = lambda: "foo"
        self.assertEqual(self.cruft.get_prefix_description(), "foo")

    def testRaisesErrorForDefaultGetShortname(self):
        self.assertRaises(computerjanitor.UnimplementedMethod,
                          self.cruft.get_shortname)

    def testReturnsCorrectStringForFullName(self):
        self.cruft.get_prefix = lambda *args: "foo"
        self.cruft.get_shortname = lambda *args: "bar"
        self.assertEqual(self.cruft.get_name(), "foo:bar")

    def testReturnsEmptyStringAsDefaultDescription(self):
        self.assertEqual(self.cruft.get_description(), "")

    def testReturnsNoneForDiskUsage(self):
        self.assertEqual(self.cruft.get_disk_usage(), None)

    def testRaisesErrorForDefaultCleanup(self):
        self.assertRaises(computerjanitor.UnimplementedMethod,
                          self.cruft.cleanup)
