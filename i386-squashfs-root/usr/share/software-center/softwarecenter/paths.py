# Copyright (C) 2009 Canonical
#
# Authors:
#  Andrew Higginson
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import os

# ensure we don't create directories in /home/$user
if os.getuid() == 0 and "SUDO_USER" in os.environ and "HOME" in os.environ:
    del os.environ["HOME"]
# the check above must be *before* xdg is imported

# py3 possible compat mode (there is no python3-xdg yet)
# try:
#     from xdg import BaseDirectory as xdg
# except ImportError:
#     import collections
#     klass = collections.namedtuple('xdg', 'xdg_config_home, xdg_cache_home')
#     xdg = klass(xdg_config_home=os.path.expanduser("~/.config"),
#                 xdg_cache_home=os.path.expanduser("~/.cache"))
from xdg import BaseDirectory as xdg

from softwarecenter.toolkit import CURRENT_TOOLKIT, UIToolkits

# global datadir, this maybe overriden at startup
datadir = "/usr/share/software-center/"

# system pathes
APP_INSTALL_PATH = "/usr/share/app-install"
APP_INSTALL_DESKTOP_PATH = APP_INSTALL_PATH+"/desktop/"
APP_INSTALL_CHANNELS_PATH = APP_INSTALL_PATH+"/channels/"
ICON_PATH = APP_INSTALL_PATH+"/icons/"
APPSTREAM_BASE_PATH = "/usr/share/app-info"
APPSTREAM_XML_PATH = APPSTREAM_BASE_PATH + "/xmls/"

SOFTWARE_CENTER_BASE = "/usr/share/software-center"
SOFTWARE_CENTER_PLUGIN_DIRS = [
    os.environ.get("SOFTWARE_CENTER_PLUGINS_DIR", ""),
    os.path.join(SOFTWARE_CENTER_BASE, "plugins"),
    os.path.join(xdg.xdg_data_home, "software-center", "plugins"),
    ]

# FIXME: use relative paths here
INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

# xapian pathes
XAPIAN_BASE_PATH = "/var/cache/software-center"
XAPIAN_BASE_PATH_SOFTWARE_CENTER_AGENT = os.path.join(
    xdg.xdg_cache_home,
    "software-center", 
    "software-center-agent.db")
XAPIAN_PATH=os.path.join(XAPIAN_BASE_PATH, "xapian")

# ratings&review
# relative to datadir
class RNRApps:
    if CURRENT_TOOLKIT is UIToolkits.GTK2:
        SUBMIT_REVIEW = "submit_review.py"
        REPORT_REVIEW = "report_review.py"
        SUBMIT_USEFULNESS = "submit_usefulness.py"
        MODIFY_REVIEW = "modify_review.py"
        DELETE_REVIEW = "delete_review.py"
    elif CURRENT_TOOLKIT is UIToolkits.GTK3:
        SUBMIT_REVIEW = "submit_review_gtk3.py"
        REPORT_REVIEW = "report_review_gtk3.py"
        SUBMIT_USEFULNESS = "submit_usefulness_gtk3.py"
        MODIFY_REVIEW = "modify_review_gtk3.py"
        DELETE_REVIEW = "delete_review_gtk3.py"

# piston helpers
class PistonHelpers:
    GET_REVIEWS = "piston_get_reviews_helper.py"
    GET_REVIEW_STATS = "piston_get_review_stats_helper.py"
    GET_USEFUL_VOTES = "piston_get_useful_votes_helper.py"
    SOFTWARE_CENTER_AGENT = "piston_get_scagent_available_apps.py"

X2GO_HELPER = "x2go_helper.py"

# there was a bug in maverick 3.0.3 (#652151) that could lead to a empty
# root owned directory in ~/.cache/software-center - we remove it here
# so that it gets later re-created with the right permissions
def try_to_fixup_root_owned_dir_via_remove(directory):
    if os.path.exists(directory) and not os.access(directory, os.W_OK):
        try:
            logging.warn("trying to fix not writable cache directory")
            os.rmdir(directory)
        except:
            logging.exception("failed to fix not writable cache directory")

if "SOFTWARE_CENTER_FAKE_REVIEW_API" in os.environ:
    SOFTWARE_CENTER_CONFIG_DIR = os.path.join(xdg.xdg_config_home, "software-center", "fake-review")
    SOFTWARE_CENTER_CACHE_DIR = os.path.join(xdg.xdg_cache_home, "software-center", "fake-review")
else:
    SOFTWARE_CENTER_CONFIG_DIR = os.path.join(xdg.xdg_config_home, "software-center")
    SOFTWARE_CENTER_CACHE_DIR = os.path.join(xdg.xdg_cache_home, "software-center")
    
# FIXUP a brief broken software-center in maverick
try_to_fixup_root_owned_dir_via_remove(SOFTWARE_CENTER_CACHE_DIR)

SOFTWARE_CENTER_CONFIG_FILE = os.path.join(SOFTWARE_CENTER_CONFIG_DIR, "softwarecenter.cfg") 
SOFTWARE_CENTER_ICON_CACHE_DIR = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "icons")
