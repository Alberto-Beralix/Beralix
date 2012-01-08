# -*- coding: utf-8 -*-

# Authors: Natalia B Bidart <natalia.bidart@canonical.com>
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

"""The control panel UI for Ubuntu One."""

import gettext

from oauth import oauth

_ = gettext.gettext


ERROR_COLOR = 'red'
KILOBYTES = 1024
NO_OP = lambda *a, **kw: None
# http://design.canonical.com/the-toolkit/ubuntu-logo-and-circle-of-friends/
ORANGE = '#DD4814'
QUOTA_THRESHOLD = 0.95
SHARES_MIN_SIZE_FULL = 1048576
SUCCESS_COLOR = 'green'

ERROR_ICON = u'✘'
SYNCING_ICON = u'⇅'
IDLE_ICON = u'✔'

CONTACT_ICON_NAME = 'avatar-default'
FOLDER_ICON_NAME = 'folder'
SHARE_ICON_NAME = 'folder-remote'
MUSIC_ICON_NAME = 'audio-x-generic'

CONTACTS_ICON = 'contacts.png'
FACEBOOK_LOGO = 'facebook.png'
FILES_ICON = 'files.png'
OVERVIEW_BANNER = 'overview.png'
TWITTER_LOGO = 'twitter.png'
MUSIC_STORE_ICON = 'music-store.png'
MUSIC_STREAM_ICON = 'music-stream.png'
NOTES_ICON = 'notes.png'
SERVICES_CONTACTS_ICON = 'services-contacts.png'
SERVICES_FILES_EXAMPLE = 'services-files-example.png'
SERVICES_FILES_ICON = 'services-files.png'

FILE_URI_PREFIX = 'file://'
UBUNTUONE_FROM_OAUTH = 'https://one.ubuntu.com/api/1.0/from_oauth/'
UBUNTUONE_LINK = 'https://one.ubuntu.com/'

CONTACTS_LINK = UBUNTUONE_LINK
EDIT_ACCOUNT_LINK = UBUNTUONE_LINK + 'account/'
EDIT_DEVICES_LINK = EDIT_ACCOUNT_LINK + 'machines/'
EDIT_PROFILE_LINK = 'https://login.ubuntu.com/'
EDIT_SERVICES_LINK = UBUNTUONE_LINK + 'services'
FACEBOOK_LINK = 'http://www.facebook.com/ubuntuone/'
GET_SUPPORT_LINK = UBUNTUONE_LINK + 'support/'
LEARN_MORE_LINK = UBUNTUONE_LINK
MANAGE_FILES_LINK = UBUNTUONE_LINK + 'files/'
RESET_PASSWORD_LINK = EDIT_PROFILE_LINK + '+forgot_password'
TWITTER_LINK = 'http://twitter.com/ubuntuone/'

ALWAYS_SUBSCRIBED = _('Always in sync')
CONNECT_BUTTON_LABEL = _('Connect to Ubuntu One')
CONTACTS = _('Thunderbird plug-in')
CREDENTIALS_ERROR = _('There was a problem while retrieving the credentials.')
DASHBOARD_BUTTON_TOOLTIP = _('View your personal details and service '
                             'summary')
DASHBOARD_TITLE = _('Welcome to Ubuntu One!')
DASHBOARD_VALUE_ERROR = _('The information could not be retrieved. '
                          'Maybe your internet connection is down?')
DESKTOPCOUCH_PKG = 'desktopcouch-ubuntuone'
DEVICE_CHANGE_ERROR = _('The settings could not be changed,\n'
                        'previous values were restored.')
DEVICE_CONFIRM_REMOVE = _('Are you sure you want to remove this device '
                          'from Ubuntu One?')
DEVICE_REMOVABLE_PREFIX = 'Ubuntu One @ '
DEVICE_REMOVAL_ERROR = _('The device could not be removed.')
DEVICES_BUTTON_TOOLTIP = _('Manage devices registered with your personal '
                           'cloud')
DEVICES_TITLE = _('The devices connected with your personal cloud are listed '
                  'below.')
EXPLORE = _('Explore')
FAILED_INSTALL = _('<i>%(package_name)s</i> could not be installed')
FOLDER_ADD_BUTTON_TEXT = _('Sync another folder with your cloud')
FOLDER_INVALID_PATH = _('The chosen directory "%(folder_path)s" is not valid. '
                        '\n\n'
                        'Please choose a folder inside your "%(home_folder)s" '
                        'directory, and not overlapping with any existing '
                        'cloud folder.')
FOLDER_OWNED_BY = _('My personal folders')
FOLDER_SHARED_BY = _('Shared by %(other_user_display_name)s')
FOLDERS_CONFIRM_MERGE = _('The contents of your cloud folder will be merged '
                          'with your local folder "%(folder_path)s" when '
                          'subscribing.\nDo you want to subscribe to this '
                          'cloud folder?')
FOLDERS_BUTTON_TOOLTIP = VOLUMES_BUTTON_TOOLTIP = _('Manage your cloud '
                                                     'folders')
FOLDERS_TITLE = _('Select which folders from your cloud you want to sync with '
  'this computer')
FILE_SYNC_CONNECT = _('Connect')
FILE_SYNC_CONNECT_TOOLTIP = _('Connect the file sync service with '
                              'your personal cloud')
FILE_SYNC_DISABLED = _('File Sync is disabled.')
FILE_SYNC_DISCONNECT = _('Disconnect')
FILE_SYNC_DISCONNECT_TOOLTIP = _('Disconnect the file sync service from '
                                 'your personal cloud')
FILE_SYNC_DISCONNECTED = _('File Sync is disconnected.')
FILE_SYNC_ENABLE = _('Enable')
FILE_SYNC_ENABLE_TOOLTIP = _('Enable the file sync service')
FILE_SYNC_ERROR = _('File Sync error.')
FILE_SYNC_IDLE = _('File Sync is up-to-date.')
FILE_SYNC_RESTART = _('Restart')
FILE_SYNC_RESTART_TOOLTIP = _('Restart the file sync service')
FILE_SYNC_SERVICE_NAME = _('File Sync')
FILE_SYNC_START = _('Start')
FILE_SYNC_START_TOOLTIP = _('Start the file sync service')
FILE_SYNC_STARTING = _('File Sync starting...')
FILE_SYNC_STOP = _('Stop')
FILE_SYNC_STOP_TOOLTIP = _('Stop the file sync service')
FILE_SYNC_STOPPED = _('File Sync is stopped.')
FILE_SYNC_SYNCING = _('File Sync in progress...')
FREE_SPACE_TEXT = _('%(free_space)s available storage')
GREETING = _('Hi %(user_display_name)s')
INSTALL_PACKAGE = _('You need to install the package <i>%(package_name)s'
                    '</i> in order to enable more sync services.')
INSTALL_PLUGIN = _('Install the %(plugin_name)s for the sync service: '
                   '%(service_name)s')
INSTALLING = _('Installation of <i>%(package_name)s</i> in progress')
LOADING = _('Loading...')
MAIN_WINDOW_TITLE = _('%(app_name)s Control Panel')
MY_FOLDERS = _('My folders')
NAME_NOT_SET = _('[unknown user name]')
MUSIC_DISPLAY_NAME = _('Purchased Music')
MUSIC_REAL_PATH = '.ubuntuone/Purchased from Ubuntu One'
NETWORK_OFFLINE = _('An internet connection is required to join or sign '
                    'in to %(app_name)s.')
NO_DEVICES = _('No devices to show.')
NO_FOLDERS = _('No folders to show.')
NO_PAIRING_RECORD = _('There is no Ubuntu One pairing record.')
PERCENTAGE_LABEL = _('%(percentage)s used')
QUOTA_LABEL = _('Using %(used)s of %(total)s (%(percentage).0f%%)')
USAGE_LABEL = _('%(used)s of %(total)s')
SERVICES_BUTTON_TOOLTIP = _('Manage the sync services')
SERVICES_TITLE = _('Enable the sync services for this computer.')
SETTINGS_CHANGE_ERROR = _('The settings could not be changed,\n'
                          'previous values were restored.')
SHARES_BUTTON_TOOLTIP = _('Manage the shares offered to others')
SHARES_TITLE = _('Manage permissions for shares made to other users.')
SUCCESS_INSTALL = _('<i>%(package_name)s</i> was successfully installed')
SYNC_LOCALLY = _('Sync locally?')
VALUE_ERROR = _('Value could not be retrieved.')
UNKNOWN_ERROR = _('Unknown error')


def humanize(int_bytes):
    """Return a human readable representation of 'int_bytes'.

    This method follows the https://wiki.ubuntu.com/UnitsPolicy to build
    the result.

    """
    units = {0: 'bytes', 1: 'KiB', 2: 'MiB', 3: 'GiB', 4: 'TiB',
             5: 'PiB', 6: 'Eib', 7: 'ZiB', 8: 'YiB'}
    unit = 0
    while int_bytes >= KILOBYTES:
        int_bytes = int_bytes / float(KILOBYTES)
        unit += 1
    str_bytes = "%.1f" % int_bytes
    str_bytes = str_bytes.rstrip('0')
    str_bytes = str_bytes.rstrip('.')
    return '%s %s' % (str_bytes, units[unit])


def sign_url(url, credentials):
    """Sign the URL using the currently available credentials."""
    consumer = oauth.OAuthConsumer(credentials["consumer_key"],
                                   credentials["consumer_secret"])
    token = oauth.OAuthToken(credentials["token"],
                             credentials["token_secret"])
    request = oauth.OAuthRequest.from_consumer_and_token(
        http_url=UBUNTUONE_FROM_OAUTH, http_method='GET',
        oauth_consumer=consumer, token=token,
        parameters={'next': url})
    sig_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
    request.sign_request(sig_method, consumer, token)
    signed = request.to_url()
    return signed
