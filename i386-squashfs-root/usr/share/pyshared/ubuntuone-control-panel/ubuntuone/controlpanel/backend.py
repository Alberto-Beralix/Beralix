# -*- coding: utf-8 -*-

# Authors: Alejandro J. Cura <alecu@canonical.com>
# Authors: Natalia B. Bidart <nataliabidart@canonical.com>
#
# Copyright 2010 Canonical Ltd.
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

"""A backend for the Ubuntu One Control Panel."""

import operator
import os

from collections import defaultdict
from functools import wraps

from twisted.internet.defer import inlineCallbacks, returnValue
# No name 'is_link' in module 'ubuntuone.platform'
# pylint: disable=E0611, F0401
from ubuntuone.platform import is_link
from ubuntuone.platform.credentials import CredentialsManagementTool
# pylint: enable=E0611, F0401

from ubuntuone.controlpanel import sd_client, replication_client
from ubuntuone.controlpanel.logger import setup_logging, log_call
# pylint: disable=W0611
from ubuntuone.controlpanel.web_client import (UnauthorizedError,
    web_client_factory, WebClientError)
# pylint: enable=W0611

logger = setup_logging('backend')

ACCOUNT_API = "account/"
QUOTA_API = "quota/"
DEVICES_API = "1.0/devices/"
DEVICE_REMOVE_API = "1.0/devices/remove/%s/%s"
DEVICE_TYPE_PHONE = "Phone"
DEVICE_TYPE_COMPUTER = "Computer"
AUTOCONNECT_KEY = 'autoconnect'
SHOW_ALL_NOTIFICATIONS_KEY = 'show_all_notifications'
SHARE_AUTOSUBSCRIBE_KEY = 'share_autosubscribe'
UDF_AUTOSUBSCRIBE_KEY = 'udf_autosubscribe'
LIMIT_BW_KEY = 'limit_bandwidth'
UPLOAD_KEY = "max_upload_speed"
DOWNLOAD_KEY = "max_download_speed"

FILE_SYNC_DISABLED = 'file-sync-disabled'
FILE_SYNC_DISCONNECTED = 'file-sync-disconnected'
FILE_SYNC_ERROR = 'file-sync-error'
FILE_SYNC_IDLE = 'file-sync-idle'
FILE_SYNC_STARTING = 'file-sync-starting'
FILE_SYNC_STOPPED = 'file-sync-stopped'
FILE_SYNC_SYNCING = 'file-sync-syncing'
FILE_SYNC_UNKNOWN = 'file-sync-unknown'

MSG_KEY = 'message'
STATUS_KEY = 'status'

CONTACTS_PKG = 'thunderbird-couchdb'


def append_path_sep(path):
    """If 'path' does not end with the path separator, append it."""
    if not path.endswith(os.path.sep):
        path += os.path.sep
    return path


def filter_field(info, field):
    """Return a copy of 'info' where each item has 'field' hidden."""
    result = []
    for item in info:
        item = item.copy()
        item[field] = '<hidden>'
        result.append(item)
    return result


def process_unauthorized(f):
    """Catch UnauthorizedError from the web_client and act upon."""

    @inlineCallbacks
    @wraps(f)
    def inner(instance, *args, **kwargs):
        """Handle UnauthorizedError and clear credentials."""
        try:
            result = yield f(instance, *args, **kwargs)
        except UnauthorizedError, e:
            logger.exception('process_unauthorized (clearing credentials):')
            yield instance.clear_credentials()
            raise e

        returnValue(result)

    return inner


class ControlBackend(object):
    """The control panel backend."""

    ROOT_TYPE = u'ROOT'
    FOLDER_TYPE = u'UDF'
    SHARE_TYPE = u'SHARE'
    NAME_NOT_SET = u'ENAMENOTSET'
    FREE_BYTES_NOT_AVAILABLE = u'EFREEBYTESNOTAVAILABLE'
    STATUS_DISABLED = {MSG_KEY: '', STATUS_KEY: FILE_SYNC_DISABLED}
    DEFAULT_FILE_SYNC_SETTINGS = {
        AUTOCONNECT_KEY: True,
        SHOW_ALL_NOTIFICATIONS_KEY: True,
        SHARE_AUTOSUBSCRIBE_KEY: False,
        UDF_AUTOSUBSCRIBE_KEY: False,
        DOWNLOAD_KEY: -1,  # no limit
        UPLOAD_KEY: -1,  # no limit
    }

    def __init__(self, shutdown_func=None):
        """Initialize the web_client."""
        self._status_changed_handler = None
        self._credentials = None
        self._volumes = {}  # cache last known volume info

        self.shutdown_func = shutdown_func
        self.file_sync_disabled = False

        self.login_client = CredentialsManagementTool()
        self.sd_client = sd_client.SyncDaemonClient()
        self.wc = web_client_factory(self.get_credentials)

        logger.info('ControlBackend: instance started.')

    def _process_file_sync_status(self, status):
        """Process raw file sync status into custom format.

        Return a dictionary with two members:
        * STATUS_KEY: the current status of syncdaemon, can be one of:
            FILE_SYNC_DISABLED, FILE_SYNC_STARTING, FILE_SYNC_DISCONNECTED,
            FILE_SYNC_SYNCING, FILE_SYNC_IDLE, FILE_SYNC_ERROR,
            FILE_SYNC_UNKNOWN
        * MSG_KEY: a non translatable but human readable string of the status.

        """
        logger.debug('sync status: %r', status)
        if not status:
            self.file_sync_disabled = True
            return self.STATUS_DISABLED

        msg = '%s (%s)' % (status['description'], status['name'])
        result = {MSG_KEY: msg}

        # file synch is enabled
        is_error = bool(status['is_error'])
        is_synching = bool(status['is_connected'])
        is_idle = bool(status['is_online']) and status['queues'] == 'IDLE'
        is_disconnected = status['name'] == 'WAITING' or \
                          (status['name'] == 'READY' and \
                           'Not User' in status['connection'])
        is_starting = status['name'] in ('INIT', 'LOCAL_RESCAN', 'READY')
        is_stopped = status['name'] == 'SHUTDOWN'

        if is_error:
            result[STATUS_KEY] = FILE_SYNC_ERROR
        elif is_idle:
            result[STATUS_KEY] = FILE_SYNC_IDLE
        elif is_synching:
            result[STATUS_KEY] = FILE_SYNC_SYNCING
        elif is_disconnected:
            result[STATUS_KEY] = FILE_SYNC_DISCONNECTED
        elif is_starting:
            self.file_sync_disabled = False
            result[STATUS_KEY] = FILE_SYNC_STARTING
        elif is_stopped:
            result[STATUS_KEY] = FILE_SYNC_STOPPED
        else:
            logger.warning('file_sync_status: unknown (got %r)', status)
            result[STATUS_KEY] = FILE_SYNC_UNKNOWN

        if self.file_sync_disabled:
            return self.STATUS_DISABLED
        else:
            return result

    def _set_status_changed_handler(self, handler):
        """Set 'handler' to be called when file sync status changes."""
        logger.debug('setting status_changed_handler to %r', handler)

        def process_and_callback(status):
            """Process syncdaemon's status and callback 'handler'."""
            result = self._process_file_sync_status(status)
            handler(result)

        self._status_changed_handler = handler
        self.sd_client.set_status_changed_handler(process_and_callback)

    def _get_status_changed_handler(self):
        """Return the handler to be called when file sync status changes."""
        return self._status_changed_handler

    status_changed_handler = property(_get_status_changed_handler,
                                      _set_status_changed_handler)

    @inlineCallbacks
    def _process_device_web_info(self, devices,
        enabled=None, limit_bw=None, limits=None, autoconnect=None,
        show_notifs=None, share_autosubscribe=None, udf_autosubscribe=None):
        """Return a lis of processed devices.

        If all the file sync settings are None, do not attach that info.

        """
        result = []
        for d in devices:
            di = {}
            di["type"] = d["kind"]
            di["name"] = d["description"] if d["description"] \
                                          else self.NAME_NOT_SET
            if di["type"] == DEVICE_TYPE_COMPUTER:
                di["device_id"] = di["type"] + d["token"]
            if di["type"] == DEVICE_TYPE_PHONE:
                di["device_id"] = di["type"] + str(d["id"])

            is_local = yield self.device_is_local(di["device_id"])
            di["is_local"] = is_local

            if is_local:  # prepend the local device!
                result.insert(0, di)
            else:
                result.append(di)

            if enabled is None:
                # without knowing if file sync is enabled or not,
                # we can't add any extra info about the device.
                continue

            # currently, only local devices are configurable.
            di["configurable"] = is_local and enabled

            if di["configurable"]:
                di[LIMIT_BW_KEY] = limit_bw
                di[AUTOCONNECT_KEY] = autoconnect
                di[SHOW_ALL_NOTIFICATIONS_KEY] = show_notifs
                di[SHARE_AUTOSUBSCRIBE_KEY] = share_autosubscribe
                di[UDF_AUTOSUBSCRIBE_KEY] = udf_autosubscribe
                di[UPLOAD_KEY] = limits["upload"]
                di[DOWNLOAD_KEY] = limits["download"]

        returnValue(result)

    @inlineCallbacks
    def _process_device_local_info(self,
        enabled=None, limit_bw=None, limits=None, autoconnect=None,
        show_notifs=None, share_autosubscribe=None, udf_autosubscribe=None):
        """Return the information for the local device.

        If all the file sync settings are None, do not attach that info.

        """
        credentials = yield self.get_credentials()

        local_device = {}
        local_device["type"] = DEVICE_TYPE_COMPUTER
        local_device["name"] = credentials['name']
        device_id = local_device["type"] + credentials["token"]
        local_device["device_id"] = device_id
        local_device["is_local"] = True

        if enabled is not None:
            local_device["configurable"] = enabled
            if local_device["configurable"]:
                local_device[LIMIT_BW_KEY] = limit_bw
                local_device[AUTOCONNECT_KEY] = autoconnect
                local_device[SHOW_ALL_NOTIFICATIONS_KEY] = show_notifs
                local_device[SHARE_AUTOSUBSCRIBE_KEY] = share_autosubscribe
                local_device[UDF_AUTOSUBSCRIBE_KEY] = udf_autosubscribe
                upload = limits["upload"]
                download = limits["download"]
                local_device[UPLOAD_KEY] = upload
                local_device[DOWNLOAD_KEY] = download

        returnValue(local_device)

    def _process_path(self, path):
        """Trim 'path' so the '~' is removed."""
        home = os.path.expanduser('~')
        result = path.replace(os.path.join(home, ''), '')
        return result

    @inlineCallbacks
    def get_credentials(self):
        """Find credentials."""
        if not self._credentials:
            self._credentials = yield self.login_client.find_credentials()
        returnValue(self._credentials)

    @inlineCallbacks
    def clear_credentials(self):
        """Clear the credentials."""
        self._credentials = None
        yield self.login_client.clear_credentials()

    @inlineCallbacks
    def get_token(self):
        """Return the token from the credentials."""
        credentials = yield self.get_credentials()
        returnValue(credentials["token"])

    @log_call(logger.debug, with_args=False)
    @inlineCallbacks
    def login(self, email, password):
        """Login using 'email' and 'password'."""
        result = yield self.login_client.login_email_password(
                    email=email, password=password)
        # cache credentils
        self._credentials = result
        returnValue(result)

    @inlineCallbacks
    def device_is_local(self, device_id):
        """Return whether 'device_id' is the local devicew or not."""
        dtype, did = self.type_n_id(device_id)
        local_token = yield self.get_token()
        is_local = (dtype == DEVICE_TYPE_COMPUTER and did == local_token)
        returnValue(is_local)

    @log_call(logger.debug)
    @process_unauthorized
    @inlineCallbacks
    def account_info(self):
        """Get the user account info."""
        result = {}

        account_info = yield self.wc.call_api(ACCOUNT_API)
        logger.debug('account_info from api call: %r', account_info)

        if "current_plan" in account_info:
            desc = account_info["current_plan"]
        elif "subscription" in account_info \
                 and "description" in account_info["subscription"]:
            desc = account_info["subscription"]["description"]
        else:
            desc = ''

        result["type"] = desc
        result["name"] = account_info["nickname"]
        result["email"] = account_info["email"]

        quota_info = yield self.wc.call_api(QUOTA_API)
        result["quota_total"] = quota_info["total"]
        result["quota_used"] = quota_info["used"]

        returnValue(result)

    @log_call(logger.debug)
    @process_unauthorized
    @inlineCallbacks
    def devices_info(self):
        """Get the user devices info."""
        result = limit_bw = limits = None
        autoconnect = show_notifs = None
        share_autosubscribe = udf_autosubscribe = None

        enabled = yield self.sd_client.files_sync_enabled()
        enabled = bool(enabled)
        if enabled:
            sd_res = yield self.sd_client.autoconnect_enabled()
            autoconnect = bool(sd_res)

            sd_res = yield self.sd_client.show_all_notifications_enabled()
            show_notifs = bool(sd_res)

            sd_res = yield self.sd_client.share_autosubscribe_enabled()
            share_autosubscribe = bool(sd_res)

            sd_res = yield self.sd_client.udf_autosubscribe_enabled()
            udf_autosubscribe = bool(sd_res)

            sd_res = yield self.sd_client.bandwidth_throttling_enabled()
            limit_bw = bool(sd_res)

            limits = yield self.sd_client.get_throttling_limits()

        logger.debug('devices_info: file sync enabled? %s limit_bw %s, limits '
                     '%s, autoconnect %s, show_notifs %s, '
                     'share_autosubscribe %s, udf_autosubscribe %s',
                     enabled, limit_bw, limits, autoconnect, show_notifs,
                     share_autosubscribe, udf_autosubscribe)

        try:
            devices = yield self.wc.call_api(DEVICES_API)
        except UnauthorizedError:
            raise
        except WebClientError:
            logger.exception('devices_info: web client failure:')
        else:
            result = yield self._process_device_web_info(devices, enabled,
                        limit_bw, limits, autoconnect, show_notifs,
                        share_autosubscribe, udf_autosubscribe)

        if result is None:
            local_device = yield self._process_device_local_info(enabled,
                            limit_bw, limits, autoconnect, show_notifs,
                            share_autosubscribe, udf_autosubscribe)
            result = [local_device]

        logger.info('devices_info: result is %r',
                    filter_field(result, field='device_id'))

        returnValue(result)

    @log_call(logger.debug)
    @process_unauthorized
    @inlineCallbacks
    def device_names_info(self):
        """Get the user devices info, only list names and kind."""
        result = None
        try:
            devices = yield self.wc.call_api(DEVICES_API)
        except UnauthorizedError:
            raise
        except WebClientError:
            logger.exception('device_names_info: web client failure:')
        else:
            result = yield self._process_device_web_info(devices)

        if result is None:
            local_device = yield self._process_device_local_info()
            result = [local_device]

        logger.info('device_names_info: result is %r',
                    filter_field(result, field='device_id'))

        returnValue(result)

    def type_n_id(self, device_id):
        """Return the device type and id, as used by the /devices api."""
        if device_id.startswith(DEVICE_TYPE_COMPUTER):
            return DEVICE_TYPE_COMPUTER, device_id[8:]
        if device_id.startswith(DEVICE_TYPE_PHONE):
            return DEVICE_TYPE_PHONE, device_id[5:]
        return "No device", device_id

    @log_call(logger.info, with_args=False)
    @inlineCallbacks
    def change_device_settings(self, device_id, settings):
        """Change the settings for the given device."""
        is_local = yield self.device_is_local(device_id)

        if is_local and SHOW_ALL_NOTIFICATIONS_KEY in settings:
            if not settings[SHOW_ALL_NOTIFICATIONS_KEY]:
                yield self.sd_client.disable_show_all_notifications()
            else:
                yield self.sd_client.enable_show_all_notifications()

        if is_local and LIMIT_BW_KEY in settings:
            if not settings[LIMIT_BW_KEY]:
                yield self.sd_client.disable_bandwidth_throttling()
            else:
                yield self.sd_client.enable_bandwidth_throttling()

        if is_local and (UPLOAD_KEY in settings or
                         DOWNLOAD_KEY in settings):
            current_limits = yield self.sd_client.get_throttling_limits()
            limits = {
                "download": current_limits["download"],
                "upload": current_limits["upload"],
            }
            if UPLOAD_KEY in settings:
                limits["upload"] = settings[UPLOAD_KEY]
            if DOWNLOAD_KEY in settings:
                limits["download"] = settings[DOWNLOAD_KEY]
            self.sd_client.set_throttling_limits(limits)

        # still pending: more work on the settings dict (LP: #673674)
        returnValue(device_id)

    @log_call(logger.warning, with_args=False)
    @process_unauthorized
    @inlineCallbacks
    def remove_device(self, device_id):
        """Remove a device's tokens from the sso server."""
        dtype, did = self.type_n_id(device_id)
        is_local = yield self.device_is_local(device_id)

        api = DEVICE_REMOVE_API % (dtype.lower(), did)
        yield self.wc.call_api(api)

        if is_local:
            logger.warning('remove_device: device is local! removing and '
                           'clearing credentials.')
            yield self.clear_credentials()

        returnValue(device_id)

    @log_call(logger.debug)
    @inlineCallbacks
    def file_sync_status(self):
        """Return the status of the file sync service."""
        enabled = yield self.sd_client.files_sync_enabled()
        if enabled:
            status = yield self.sd_client.get_current_status()
        else:
            status = {}
        returnValue(self._process_file_sync_status(status))

    @log_call(logger.debug)
    @inlineCallbacks
    def enable_files(self):
        """Enable the files service."""
        yield self.sd_client.set_files_sync_enabled(True)
        self.file_sync_disabled = False

    @log_call(logger.debug)
    @inlineCallbacks
    def disable_files(self):
        """Enable the files service."""
        yield self.sd_client.set_files_sync_enabled(False)
        self.file_sync_disabled = True

    @log_call(logger.debug)
    @inlineCallbacks
    def connect_files(self):
        """Connect the files service."""
        yield self.sd_client.connect_file_sync()

    @log_call(logger.debug)
    @inlineCallbacks
    def disconnect_files(self):
        """Disconnect the files service."""
        yield self.sd_client.disconnect_file_sync()

    @log_call(logger.debug)
    @inlineCallbacks
    def restart_files(self):
        """restart the files service."""
        yield self.sd_client.stop_file_sync()
        yield self.sd_client.start_file_sync()

    @log_call(logger.debug)
    @inlineCallbacks
    def start_files(self):
        """start the files service."""
        yield self.sd_client.start_file_sync()

    @log_call(logger.debug)
    @inlineCallbacks
    def stop_files(self):
        """stop the files service."""
        yield self.sd_client.stop_file_sync()

    @log_call(logger.debug)
    @inlineCallbacks
    def volumes_info(self, with_storage_info=True):
        """Get the volumes info."""
        self._volumes = {}

        free_bytes = self.FREE_BYTES_NOT_AVAILABLE
        if with_storage_info:
            try:
                account = yield self.account_info()
            except Exception:  # pylint: disable=W0703
                logger.exception('volumes_info: quota could not be retrieved:')
            else:
                free_bytes = account['quota_total'] - account['quota_used']

        root_dir = yield self.sd_client.get_root_dir()
        shares_dir = yield self.sd_client.get_shares_dir()
        shares_dir_link = yield self.sd_client.get_shares_dir_link()
        folders = yield self.sd_client.get_folders()
        shares = yield self.sd_client.get_shares()

        root_volume = {u'volume_id': u'', u'path': root_dir,
                       u'subscribed': True, u'type': self.ROOT_TYPE,
                       u'display_name': self._process_path(root_dir)}
        self._volumes[u''] = root_volume

        # group shares by the offering user
        shares_result = defaultdict(list)
        for share in shares:
            if not bool(share['accepted']):
                continue

            share[u'type'] = self.SHARE_TYPE

            vid = share['volume_id']
            if vid in self._volumes:
                logger.warning('volumes_info: share %r already in the volumes '
                               'list (%r).', vid, self._volumes[vid])
            self._volumes[vid] = share

            share[u'realpath'] = share[u'path']
            nicer_path = share[u'path'].replace(shares_dir, shares_dir_link)
            share[u'path'] = nicer_path
            share[u'subscribed'] = bool(share[u'subscribed'])
            share[u'display_name'] = share[u'name']

            username = share['other_visible_name']
            if not username:
                username = u'%s (%s)' % (share['other_username'],
                                         self.NAME_NOT_SET)

            shares_result[username].append(share)

        for folder in folders:
            folder[u'type'] = self.FOLDER_TYPE

            vid = folder['volume_id']
            if vid in self._volumes:
                logger.warning('volumes_info: udf %r already in the volumes '
                               'list (%r).', vid, self._volumes[vid])
            folder[u'subscribed'] = bool(folder[u'subscribed'])
            folder[u'display_name'] = self._process_path(folder[u'path'])
            self._volumes[vid] = folder

        folders.sort(key=operator.itemgetter('path'))
        result = [(u'', free_bytes, [root_volume] + folders)]

        for other_username, shares in shares_result.iteritems():
            send_freebytes = any(s['access_level'] == 'Modify' for s in shares)
            if send_freebytes:
                free_bytes = int(shares[0][u'free_bytes'])
            else:
                free_bytes = self.FREE_BYTES_NOT_AVAILABLE
            shares.sort(key=operator.itemgetter('path'))
            result.append((other_username, free_bytes, shares))

        returnValue(result)

    @log_call(logger.debug)
    @inlineCallbacks
    def change_volume_settings(self, volume_id, settings):
        """Change settings for 'volume_id'.

        Currently, only supported setting is boolean 'subscribed'.

        """
        if 'subscribed' in settings:
            subscribed = settings['subscribed']
            if subscribed:
                yield self.subscribe_volume(volume_id)
            else:
                yield self.unsubscribe_volume(volume_id)

        returnValue(volume_id)

    @inlineCallbacks
    def subscribe_volume(self, volume_id):
        """Subscribe to 'volume_id'."""
        if self._volumes[volume_id][u'type'] == self.FOLDER_TYPE:
            yield self.sd_client.subscribe_folder(volume_id)
        elif self._volumes[volume_id][u'type'] == self.SHARE_TYPE:
            yield self.sd_client.subscribe_share(volume_id)

    @inlineCallbacks
    def unsubscribe_volume(self, volume_id):
        """Unsubscribe from 'volume_id'."""
        if self._volumes[volume_id][u'type'] == self.FOLDER_TYPE:
            yield self.sd_client.unsubscribe_folder(volume_id)
        elif self._volumes[volume_id][u'type'] == self.SHARE_TYPE:
            yield self.sd_client.unsubscribe_share(volume_id)

    @log_call(logger.debug)
    @inlineCallbacks
    def create_folder(self, folder_path):
        """Create a new User Defined Folder pointing to 'folder_path'."""
        yield self.sd_client.create_folder(path=folder_path)

    @log_call(logger.debug)
    @inlineCallbacks
    def validate_path_for_folder(self, folder_path):
        """Validate 'folder_path' for folder creation."""
        user_home = os.path.expanduser('~')
        folder_path = append_path_sep(folder_path)

        # handle folder_path not within '~' or links
        # XXX is_link expects bytes, see bug #824252
        if not folder_path.startswith(user_home) or is_link(
            folder_path.encode('utf-8')):
            returnValue(False)

        # handle folder_path nested with a existing cloud folder
        volumes = yield self.volumes_info(with_storage_info=False)
        for _, _, data in volumes:
            for volume in data:
                cloud_folder = append_path_sep(volume['path'])
                if (folder_path.startswith(cloud_folder) or
                    cloud_folder.startswith(folder_path)):
                    returnValue(False)

        returnValue(True)

    @log_call(logger.debug)
    @inlineCallbacks
    def replications_info(self):
        """Get the user replications info."""
        replications = yield replication_client.get_replications()
        exclusions = yield replication_client.get_exclusions()

        result = []
        for rep in replications:
            dependency = ''
            if rep == replication_client.CONTACTS:
                dependency = CONTACTS_PKG

            repd = {
                "replication_id": rep,
                "name": rep,  # this may change to be more user friendly
                "enabled": rep not in exclusions,
                "dependency": dependency,
            }
            result.append(repd)

        returnValue(result)

    @log_call(logger.info)
    @inlineCallbacks
    def change_replication_settings(self, replication_id, settings):
        """Change the settings for the given replication."""
        if 'enabled' in settings:
            if settings['enabled']:
                yield replication_client.replicate(replication_id)
            else:
                yield replication_client.exclude(replication_id)
        returnValue(replication_id)

    @log_call(logger.debug)
    @inlineCallbacks
    def file_sync_settings_info(self):
        """Get the file sync settings info."""
        result = {}

        for name in (AUTOCONNECT_KEY, SHOW_ALL_NOTIFICATIONS_KEY,
                     SHARE_AUTOSUBSCRIBE_KEY, UDF_AUTOSUBSCRIBE_KEY):
            sd_method = getattr(self.sd_client, '%s_enabled' % name)
            value = yield sd_method()
            result[name] = bool(value)

        limits = yield self.sd_client.get_throttling_limits()
        result[DOWNLOAD_KEY] = limits['download']
        result[UPLOAD_KEY] = limits['upload']

        returnValue(result)

    @inlineCallbacks
    def _change_boolean_file_sync_setting(self, setting_name, settings):
        """Change the value for 'setting_name' to be 'new_value'."""
        if setting_name in settings:
            new_value = settings[setting_name]
            sd_method_name = 'enable_%s' if new_value else 'disable_%s'
            sd_method = getattr(self.sd_client, sd_method_name % setting_name)
            yield sd_method()

    @log_call(logger.info)
    @inlineCallbacks
    def change_file_sync_settings(self, settings):
        """Change the file sync settings."""
        for name in (AUTOCONNECT_KEY, SHOW_ALL_NOTIFICATIONS_KEY,
                     SHARE_AUTOSUBSCRIBE_KEY, UDF_AUTOSUBSCRIBE_KEY):
            yield self._change_boolean_file_sync_setting(name, settings)

        if DOWNLOAD_KEY in settings or UPLOAD_KEY in settings:
            current_limits = yield self.sd_client.get_throttling_limits()
            limits = {
                "download": current_limits["download"],
                "upload": current_limits["upload"],
            }
            if UPLOAD_KEY in settings:
                limits["upload"] = settings[UPLOAD_KEY]
            if DOWNLOAD_KEY in settings:
                limits["download"] = settings[DOWNLOAD_KEY]
            yield self.sd_client.set_throttling_limits(limits)

            throttling_disabled = sum(limits.itervalues()) == -2
            if throttling_disabled:
                yield self.sd_client.disable_bandwidth_throttling()
            else:
                yield self.sd_client.enable_bandwidth_throttling()

    @log_call(logger.info)
    @inlineCallbacks
    def restore_file_sync_settings(self):
        """Restore the file sync settings."""
        yield self.change_file_sync_settings(self.DEFAULT_FILE_SYNC_SETTINGS)

    @log_call(logger.info)
    def shutdown(self):
        """Stop this service."""
        # do any other needed cleanup
        if self.shutdown_func is not None:
            self.shutdown_func()
