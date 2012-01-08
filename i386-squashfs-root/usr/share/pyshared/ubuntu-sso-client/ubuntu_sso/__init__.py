# ubuntu_sso - Ubuntu Single Sign On client support for desktop apps
#
# Copyright 2009-2010 Canonical Ltd.
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
"""Ubuntu Single Sign On client code."""

# constants
DBUS_BUS_NAME = "com.ubuntu.sso"
DBUS_PATH = "/sso"  # deprecated!
DBUS_CRED_PATH = "/credentials"  # deprecated!
DBUS_ACCOUNT_PATH = "/com/ubuntu/sso/accounts"

DBUS_IFACE_AUTH_NAME = "com.ubuntu.sso"
DBUS_IFACE_USER_NAME = "com.ubuntu.sso.UserManagement"
DBUS_IFACE_CRED_NAME = "com.ubuntu.sso.ApplicationCredentials"

DBUS_CREDENTIALS_PATH = "/com/ubuntu/sso/credentials"
DBUS_CREDENTIALS_IFACE = "com.ubuntu.sso.CredentialsManagement"

NO_OP = lambda *args, **kwargs: None
