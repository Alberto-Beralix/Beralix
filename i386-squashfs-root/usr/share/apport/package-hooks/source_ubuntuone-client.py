# Apport integration for Ubuntu One client
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
"""Stub for Apport"""
# pylint: disable-msg=F0401,C0103
# shut up about apport. We know. We aren't going to backport it for pqm
import apport
from apport.hookutils import attach_file_if_exists, packaging
import os.path
from xdg.BaseDirectory import xdg_cache_home, xdg_config_home

# Paths where things we might want live
u1_log_path = os.path.join(xdg_cache_home, "ubuntuone", "log")
u1_user_config_path = os.path.join(xdg_config_home, "ubuntuone")
# things we may want to collect for the report
u1_client_log = os.path.join(u1_log_path, "syncdaemon.log")
u1_except_log = os.path.join(u1_log_path, "syncdaemon-exceptions.log")
u1_invalidnames_log = os.path.join(u1_log_path, "syncdaemon-invalid-names.log")
u1_oauth_log = os.path.join(u1_log_path, "oauth-login.log")
u1_prefs_log = os.path.join(u1_log_path, "u1-prefs.log")
u1_sd_conf = os.path.join("etc", "xdg", "ubuntuone", "syncdaemon.conf")
u1_usersd_conf = os.path.join(u1_user_config_path, "syncdaemon.conf")
u1_user_conf = os.path.join(u1_user_config_path, "ubuntuone-client.conf")


def add_info(report):
    """add report info"""
    attach_file_if_exists(report, u1_except_log,
                                  "UbuntuOneSyncdaemonExceptionsLog")
    attach_file_if_exists(report, u1_invalidnames_log,
                                  "UbuntuOneSyncdaemonInvalidNamesLog")
    attach_file_if_exists(report, u1_oauth_log,
                                  "UbuntuOneOAuthLoginLog")
    attach_file_if_exists(report, u1_prefs_log,
                                  "UbuntuOnePreferencesLog")
    attach_file_if_exists(report, u1_usersd_conf,
                                  "UbuntuOneUserSyncdaemonConfig")
    attach_file_if_exists(report, u1_sd_conf,
                                  "UbuntuOneSyncdaemonConfig")
    attach_file_if_exists(report, u1_user_conf,
                                  "UbuntuOneClientConfig")

    if not apport.packaging.is_distro_package(report['Package'].split()[0]):
        report['ThirdParty'] = 'True'
        report['CrashDB'] = 'ubuntuone'

    packages = ['ubuntuone-client',
                'python-ubuntuone-client',
                'ubuntuone-client-tools',
                'ubuntuone-client-gnome',
                'python-ubuntuone-storageprotocol',
                'ubuntuone-ppa-beta']

    versions = ''
    for package in packages:
        try:
            version = packaging.get_version(package)
        except ValueError:
            version = 'N/A'
        if version is None:
            version = 'N/A'
        versions += '%s %s\n' % (package, version)
    report['UbuntuOneClientPackages'] = versions
