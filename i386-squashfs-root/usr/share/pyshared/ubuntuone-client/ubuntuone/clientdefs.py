# ubuntuone.clientdefs - Configure-time definitions
#
# Author: David Planella <david.planella@ubuntu.com>
#
# Copyright 2009 Canonical Ltd.
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
"""Ubuntu One client definitions.

This is a package containing configure-time definitions for the Ubuntu One
client.

"""
import gettext


Q_ = lambda string: gettext.dgettext(GETTEXT_PACKAGE, string)

# pylint: disable-msg=C0301
VERSION = "2.0.0"
LOCALEDIR = "/usr/share/locale"
LIBEXECDIR = "/usr/lib/ubuntuone-client"
GETTEXT_PACKAGE = "ubuntuone-client"

# these variables are Deprecated, use those defined in ubuntuone.credentials
APP_NAME = "Ubuntu One"
TC_URL = "https://one.ubuntu.com/terms/"
PING_URL = "https://one.ubuntu.com/oauth/sso-finished-so-get-tokens/"
DESCRIPTION = Q_("Ubuntu One requires an Ubuntu Single Sign On (SSO) account. This process will allow you to create a new account, if you do not yet have one.")
