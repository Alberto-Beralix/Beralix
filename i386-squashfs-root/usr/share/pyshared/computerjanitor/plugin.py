# plugin.py - plugin base class for computerjanitor
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


import imp
import inspect
import logging
import os

import computerjanitor
_ = computerjanitor.setup_gettext()
import logging

class Plugin(object):

    """Base class for plugins.
    
    These plugins only do one thing: identify cruft. See the 'get_cruft'
    method for details.
    
    """

    def get_condition(self):
        if hasattr(self, "_condition"):
            return self._condition
        else:
            return []
            
    def set_condition(self, condition):
        self._condition = condition

    condition = property(get_condition, set_condition)
    
    def set_application(self, app):
        """Set the Application instance this plugin belongs to.
        
        This is used by the plugin manager when creating the plugin
        instance. In a perfect world, this would be done via the
        __init__ method, but since I took a wrong left turn, I ended
        up in an imperfect world, and therefore giving the Application
        instance to __init__ would mandate that all sub-classes would
        have to deal with that explicitly. That is a lot of unnecessary
        make-work, which we should avoid. Therefore, we do it via this
        method.
        
        The class may access the Application instance via the
        'app' attribute.
        
        """
        
        self.app = app

    def do_cleanup_cruft(self): # pragma: no cover
        """Find cruft and clean it up.

        This is a helper method.
        """

        for cruft in self.get_cruft():
            cruft.cleanup()
        self.post_cleanup()

    def get_cruft(self):
        """Find some cruft in the system.
        
        This method MUST return an iterator (see 'yield' statement).
        This interface design allows cruft to be collected piecemeal,
        which makes it easier to show progress in the user interface.
        
        The base class default implementation of this raises an
        exception. Subclasses MUST override this method.

        """

        raise computerjanitor.UnimplementedMethod(self.get_cruft)

    def post_cleanup(self):
        """Does plugin wide cleanup after the individual cleanup
           was performed.
           
           This is useful for stuff that needs to be proccessed
           in batches (e.g. for performance reasons) like package
           removal.
        """
        pass


class PluginManager(object):

    """Class to find and load plugins.
    
    Plugins are stored in files named '*_plugin.py' in the list of
    directories given to the initializer.
    
    """
    
    def __init__(self, app, plugin_dirs):
        self._app = app
        self._plugin_dirs = plugin_dirs
        self._plugins = None

    def get_plugin_files(self):
        """Return all filenames in which plugins may be stored."""
        
        names = []
        

        for dirname in self._plugin_dirs:
            if not os.path.exists(dirname):
                continue
            basenames = [x for x in os.listdir(dirname) 
                            if x.endswith("_plugin.py")]
            logging.debug("Plugin modules in %s: %s" % 
                            (dirname, " ".join(basenames)))
            names += [os.path.join(dirname, x) for x in basenames]
        
        return names

    def _find_plugins(self, module):
        """Find and instantiate all plugins in a module."""
        plugins = []
        for dummy, member in inspect.getmembers(module):
            if inspect.isclass(member) and issubclass(member, Plugin):
                plugins.append(member)
        logging.debug("Plugins in %s: %s" %
                      (module, " ".join(str(x) for x in plugins)))
        return [plugin() for plugin in plugins]

    def _load_module(self, filename):
        """Load a module from a filename."""
        logging.debug("Loading module %s" % filename)
        module_name, dummy = os.path.splitext(os.path.basename(filename))
        f = file(filename, "r")
        try:
            module = imp.load_module(module_name, f, filename,
                                     (".py", "r", imp.PY_SOURCE))
        except Exception, e: # pragma: no cover
            logging.warning("Failed to load plugin '%s' (%s)" % 
                            (module_name, e))
            return None
        f.close()
        return module

    def get_plugins(self, condition=[], callback=None):
        """Return all plugins that have been found.
        
        If callback is specified, it is called after each plugin has
        been found, with the following arguments: filename, index of
        filename in list of files to be examined (starting with 0), and
        total number of files to be examined. The purpose of this is to
        allow the callback to inform the user in case things take a long
        time.
        
        """

        if self._plugins is None:
            self._plugins = []
            filenames = self.get_plugin_files()
            for i in range(len(filenames)):
                if callback:
                    callback(filenames[i], i, len(filenames))
                module = self._load_module(filenames[i])
                for plugin in self._find_plugins(module):
                    plugin.set_application(self._app)
                    self._plugins.append(plugin)
        # get the matching plugins
        plugins = [p for p in self._plugins 
                   if (p.condition == condition) or
                   (condition in p.condition) or
                   (condition == "*") ]
        logging.debug("plugins for condition '%s' are '%s'" %
                      (condition, plugins))
        return plugins
