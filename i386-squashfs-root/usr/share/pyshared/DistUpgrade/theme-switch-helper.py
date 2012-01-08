#!/usr/bin/python
#
# This is a helper for the ReleaseUpgrader. it will need to be called
# like this:
# os.system("sudo -u %s theme-switch-helper.py", os.environ["SUDO_USER"])
# to make sure that it is run in the users session
# 

import gconf
import subprocess
from optparse import OptionParser


parser = OptionParser()
parser.add_option("-g", "--get", action="store_true", dest="get",
                  help="get the current gnome/gtk theme settings")
parser.add_option("-s", "--set", dest="set", 
                  help="set the current gnome/gtk theme settings")
parser.add_option("-d", "--defaults", dest="defaults", action="store_true",
                  help="set gtk/gnome settings to save defaults")
(options, args) = parser.parse_args()

client = gconf.client_get_default()

if options.get:
    # get current settings
    gtk_theme = client.get_string("/desktop/gnome/interface/gtk_theme")
    icon_theme = client.get_string("/desktop/gnome/interface/icon_theme")
    metacity_theme = client.get_string("/apps/metacity/general/theme")
    print gtk_theme
    print icon_theme
    print metacity_theme

if options.defaults:
    # set to save defaults
    client.set_string("/desktop/gnome/interface/gtk_theme","Human")
    client.set_string("/desktop/gnome/interface/icon_theme","Human")
    client.set_string("/apps/metacity/general/theme","Human")

if options.set:
    (gtk_theme, icon_theme, metacity_theme) = open(options.set).read().strip().split("\n")
    print gtk_theme
    print icon_theme
    print metacity_theme
    client.set_string("/desktop/gnome/interface/gtk_theme", gtk_theme)
    client.set_string("/desktop/gnome/interface/icon_theme", icon_theme)
    client.set_string("/apps/metacity/general/theme", metacity_theme)
    

