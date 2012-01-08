# exc_tests.py - unit tests for exc.py
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


class ComputerJanitorExceptionTests(unittest.TestCase):

    def testReturnsStrCorrectly(self):
        e = computerjanitor.Exception()
        e._str = "pink"
        self.assertEqual(str(e), "pink")


class UnimplementedMethodTests(unittest.TestCase):

    def testErrorMessageContainsMethodName(self):
        e = computerjanitor.UnimplementedMethod(self.__init__)
        self.assert_("__init__" in str(e))