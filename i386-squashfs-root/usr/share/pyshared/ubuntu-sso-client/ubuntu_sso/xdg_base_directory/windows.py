# Authors: Manuel de la Pena <manuel@canonical.com>
#          Diego Sarmentero <diego.sarmentero@canonical.com>
#
# Copyright 2011 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""XDG helpers for windows."""

import os


# pylint: disable=C0103
def get_special_folders():
    """ Routine to grab all the Windows Special Folders locations.

    If successful, returns dictionary
    of shell folder locations indexed on Windows keyword for each;
    otherwise, returns an empty dictionary.
    """
    # pylint: disable=W0621, F0401, E0611
    special_folders = {}

    from win32com.shell import shell, shellcon
    # CSIDL_LOCAL_APPDATA = C:\Users\<username>\AppData\Local
    # CSIDL_PROFILE = C:\Users\<username>
    # CSIDL_COMMON_APPDATA = C:\ProgramData
    # More information on these at
    # http://msdn.microsoft.com/en-us/library/bb762494(v=vs.85).aspx
    get_path = lambda name: shell.SHGetFolderPath(
        0, getattr(shellcon, name), None, 0).encode('utf8')
    special_folders['Personal'] = get_path("CSIDL_PROFILE")
    special_folders['Local AppData'] = get_path("CSIDL_LOCAL_APPDATA")
    special_folders['AppData'] = os.path.dirname(
        special_folders['Local AppData'])
    special_folders['Common AppData'] = get_path("CSIDL_COMMON_APPDATA")
    return special_folders

special_folders = get_special_folders()

home_path = special_folders['Personal']
app_local_data_path = special_folders['Local AppData']
app_global_data_path = special_folders['Common AppData']

# use the non roaming app data
xdg_data_home = os.environ.get('XDG_DATA_HOME',
    os.path.join(app_local_data_path, 'xdg'))


def get_data_dirs():
    """Returns XDG data directories."""
    return os.environ.get('XDG_DATA_DIRS',
        '{0}{1}{2}'.format(app_local_data_path, os.pathsep,
        app_global_data_path)).split(os.pathsep)

xdg_data_dirs = get_data_dirs()

# we will return the roaming data wich is as close as we get in windows
# regarding caching.
xdg_cache_home = os.environ.get('XDG_CACHE_HOME',
    os.path.join(xdg_data_home, 'cache'))

# point to the not roaming app data for the user
xdg_config_home = os.environ.get('XDG_CONFIG_HOME',
    app_local_data_path)


def get_config_dirs():
    """Return XDG config directories."""
    return [xdg_config_home] + \
        os.environ.get('XDG_CONFIG_DIRS',
            app_global_data_path,
            ).split(os.pathsep)

xdg_config_dirs = get_config_dirs()

xdg_data_dirs = filter(lambda x: x, xdg_data_dirs)
xdg_config_dirs = filter(lambda x: x, xdg_config_dirs)


def load_config_paths(*resource):
    """Iterator of configuration paths.

    Return an iterator which gives each directory named 'resource' in
    the configuration search path. Information provided by earlier
    directories should take precedence over later ones (ie, the user's
    config dir comes first).
    """
    resource = os.path.join(*resource)
    for config_dir in xdg_config_dirs:
        path = os.path.join(config_dir, resource)
        if os.path.exists(path):
            yield path


def save_config_path(*resource):
    """Path to save configuration.

    Ensure $XDG_CONFIG_HOME/<resource>/ exists, and return its path.
    'resource' should normally be the name of your application. Use this
    when SAVING configuration settings. Use the xdg_config_dirs variable
    for loading.
    """
    resource = os.path.join(*resource)
    assert not resource.startswith('/')
    path = os.path.join(xdg_config_home, resource)
    if not os.path.isdir(path):
        os.makedirs(path, 0700)
    return path
