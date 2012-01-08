# plugin_tests.py - unit tests for plugin.py
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


import os
import tempfile
import unittest

import computerjanitor


class PluginTests(unittest.TestCase):

    def testGetCruftRaisesException(self):
        p = computerjanitor.Plugin()
        self.assertRaises(computerjanitor.UnimplementedMethod, p.get_cruft)

    def testPostCleanupReturnsNone(self):
        p = computerjanitor.Plugin()
        self.assertEqual(p.post_cleanup(), None)

    def testDoesNotHaveAppAttributeByDefault(self):
        p = computerjanitor.Plugin()
        self.assertFalse(hasattr(p, "app"))

    def testSetApplicationSetsApp(self):
        p = computerjanitor.Plugin()
        p.set_application("foo")
        self.assertEqual(p.app, "foo")

    def testSetsRequiredConditionToNoneByDefault(self):
        p = computerjanitor.Plugin()
        self.assertEqual(p.condition, [])


class PluginManagerTests(unittest.TestCase):

    def testFindsNoPluginsInEmptyDirectory(self):
        tempdir = tempfile.mkdtemp()
        pm = computerjanitor.PluginManager(None, [tempdir])
        plugins = pm.get_plugins()
        os.rmdir(tempdir)
        self.assertEqual(plugins, [])

    def testFindsOnePluginFileInTestPluginDirectory(self):
        pm = computerjanitor.PluginManager(None, ["testplugins"])
        self.assertEqual(pm.get_plugin_files(), 
                         ["testplugins/hello_plugin.py"])

    def testFindsOnePluginInTestPluginDirectory(self):
        pm = computerjanitor.PluginManager(None, ["testplugins"])
        self.assertEqual(len(pm.get_plugins()), 1)

    def testFindPluginsSetsApplicationInPluginsFound(self):
        pm = computerjanitor.PluginManager("foo", ["testplugins"])
        self.assertEqual(pm.get_plugins()[0].app, "foo")

    def callback(self, filename, index, count):
        self.callback_called = True

    def testCallsCallbackWhenFindingPlugins(self):
        pm = computerjanitor.PluginManager(None, ["testplugins"])
        self.callback_called = False
        pm.get_plugins(callback=self.callback)
        self.assert_(self.callback_called)


class ConditionTests(unittest.TestCase):

    def setUp(self):
        self.pm = computerjanitor.PluginManager(None, ["testplugins"])

        class White(computerjanitor.Plugin):
            pass

        class Red(computerjanitor.Plugin):
            def __init__(self):
                self.condition = ["red"]

        class RedBlack(computerjanitor.Plugin):
            def __init__(self):
                self.condition = ["red","black"]

        self.white = White()
        self.red = Red()
        self.redblack = RedBlack()
        self.pm._plugins = [self.white, self.red, self.redblack]

    def testReturnsOnlyConditionlessPluginByDefault(self):
        self.assertEqual(self.pm.get_plugins(), [self.white])

    def testReturnsOnlyRedPluginWhenConditionIsRed(self):
        self.assertEqual(self.pm.get_plugins(condition="red"), [self.red, self.redblack])

    def testReturnsOnlyRedPluginWhenConditionIsRedAndBlack(self):
        self.assertEqual(self.pm.get_plugins(condition=["red","black"]), [self.redblack])

    def testReturnsEallPluginsWhenRequested(self):
        self.assertEqual(set(self.pm.get_plugins(condition="*")),
                         set([self.white, self.red, self.redblack]))
