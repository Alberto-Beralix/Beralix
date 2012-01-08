# ubuntuone.storageprotocol.context - ssl context creation
#
# Copyright 2009 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Standard Routines for working with ssl context creation
"""
import os
import sys

from OpenSSL import SSL
from twisted.internet import ssl

if sys.platform == "win32":
    # diable pylint warning, as it may be the wrong platform
    # pylint: disable=F0401
    import _winreg

    # First open the registry hive
    hive = _winreg.ConnectRegistry(None, _winreg.HKEY_LOCAL_MACHINE)
    # Open the registry key where Windows stores the Shell Folder locations
    key = _winreg.OpenKey(hive, str(
            "Software\\Microsoft\\Windows\\CurrentVersion"
            "\\Explorer\\Shell Folders"))
    for i in range(0, _winreg.QueryInfoKey(key)[1]):
        name, value, val_type = _winreg.EnumValue(key, i)
        # Common AppData will always be present unless the user
        # played with regedit
        if name == "Common AppData":
            ssl_cert_location = os.path.join(value,
                                             "ubuntuone-storageprotocol")
            break
else:
    ssl_cert_location = '/etc/ssl/certs'


def get_ssl_context(no_verify):
    """ Get the ssl context """
    if no_verify:
        ctx = ssl.ClientContextFactory()
    else:
        ca_file = ssl.Certificate.loadPEM(file(
            os.path.join(ssl_cert_location,
                         'UbuntuOne-Go_Daddy_Class_2_CA.pem'), 'r').read())
        ca_file_2 = ssl.Certificate.loadPEM(file(
            os.path.join(ssl_cert_location,
                        'UbuntuOne-Go_Daddy_CA.pem'), 'r').read())
        ctx = ssl.CertificateOptions(verify=True,
            caCerts=[ca_file.original, ca_file_2.original],
                     method=SSL.SSLv23_METHOD)
    return ctx
