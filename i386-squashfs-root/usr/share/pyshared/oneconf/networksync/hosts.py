# Copyright (C) 2010 Canonical
#
# Authors:
#  Didier Roche <didrocks@ubuntu.com>
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

import datetime
import hashlib
import json
import logging
import os
import platform
from gi.repository import Gio

import gettext
from gettext import gettext as _

LOG = logging.getLogger(__name__)

from paths import (ONECONF_CACHE_DIR, OTHER_HOST_FILENAME, HOST_DATA_FILENAME, PENDING_UPLOAD_FILENAME,
                   PACKAGE_LIST_PREFIX, LOGO_PREFIX, LOGO_BASE_FILENAME, LAST_SYNC_DATE_FILENAME)

class HostError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

class Hosts(object):
    """
    Class to get hosts
    """

    def __init__(self):
        '''initialize database

        This will register/update this host if not already done.
        '''

        # create cache dir if doesn't exist
        if not os.path.isdir(ONECONF_CACHE_DIR):
            os.mkdir(ONECONF_CACHE_DIR)

        (logo_checksum, logo_path) = self._get_current_wallpaper_data()
        
        try:
            # faking this id for testing purpose. Format is hostid:hostname
            hostid, hostname = os.environ["ONECONF_HOST"].split(':')
            LOG.debug ("Fake current hostid to %s and hostname to %s" % (hostid, hostname))
        except KeyError:
            hostid = open('/var/lib/dbus/machine-id').read()[:-1]
            hostname = platform.node()

        self._host_file_dir = os.path.join(ONECONF_CACHE_DIR, hostid)
        try:
            with open(os.path.join(self._host_file_dir, HOST_DATA_FILENAME), 'r') as f:
                self.current_host = json.load(f)
                has_changed = False
                if hostname != self.current_host['hostname']:
                    self.current_host['hostname'] = hostname
                    has_changed = True
                if logo_checksum != self.current_host['logo_checksum']:
                    if (self._create_logo(logo_path)):
                        self.current_host['logo_checksum'] = logo_checksum
                    has_changed = True
            if has_changed:
                self.save_current_host()
        except IOError:
            self.current_host = {'hostid': hostid, 'hostname': hostname, 'share_inventory': False,
                                 'logo_checksum': logo_checksum, 'packages_checksum': None}
            if not os.path.isdir(self._host_file_dir):
                os.mkdir(self._host_file_dir)
            if not (self._create_logo(logo_path)):
                self.current_host['logo_checksum'] = None
            self.save_current_host()
        self.other_hosts = None
        self.update_other_hosts()

    def _get_current_wallpaper_data(self):
        '''Get current wallpaper metadatas from store'''
        settings = Gio.Settings.new("org.gnome.desktop.background")
        file_path = settings.get_string("picture-uri").replace("file://", "")
        try:
            logo_checksum = "%s%f" % (hashlib.sha224(file_path).hexdigest(), os.stat(file_path).st_mtime)
        except OSError:
            logo_checksum = None
            file_path = None
        return (logo_checksum, file_path)

    def _create_logo(self, wallpaper_path):
        '''create a logo from a wallpaper
        
        return True if succeeded'''
        if not wallpaper_path:
            return False
        from PIL import Image
        try:
            im = Image.open(LOGO_BASE_FILENAME)
            im2 = Image.open(wallpaper_path)
            im3 = im2.resize((42, 26), Image.BICUBIC)
            im.paste(im3, (3,3))
            im.save(os.path.join(self._host_file_dir, "%s_%s.png" % (LOGO_PREFIX, self.current_host['hostid'])))
            return True
        except IOError, e:
            LOG.warning ("Cant create logo for %s: %s" % (wallpaper_path, e))
            return False

    def update_other_hosts(self):
        '''Update all the other hosts from local store'''
        new_other_hosts = self._load_other_hosts()
        if self.other_hosts:
            for old_hostid in self.other_hosts:
                if old_hostid not in new_other_hosts:
                    try:
                        os.remove(os.path.join(self.get_currenthost_dir(), '%s_%s' % (PACKAGE_LIST_PREFIX, old_hostid)))
                    except OSError:
                        pass
                    try:
                        os.remove(os.path.join(self.get_currenthost_dir(), '%s_%s.png' % (LOGO_PREFIX, old_hostid)))
                    except OSError:
                        pass
            # TODO: remove rather with regexp in case of crash during upgrade, do not keep cruft
        self.other_hosts = new_other_hosts

    def _load_other_hosts(self):
        '''Load all other hosts from local store'''

        try:
            with open(os.path.join(self._host_file_dir, OTHER_HOST_FILENAME), 'r') as f:
                return json.load(f)
        except (IOError, TypeError), e:
            LOG.warning("Error in loading %s file: %s" % (OTHER_HOST_FILENAME, e))
            return {}

    def save_current_host(self, arg=None):
        '''Save current host on disk'''
        
        LOG.debug("Save current host to disk")
        with open(os.path.join(self._host_file_dir, HOST_DATA_FILENAME), 'w') as f:
            json.dump(self.current_host, f)

    def add_hostid_pending_change(self, change):
        '''Pend a scheduled change for another host on disk

        change has a {hostid: {key: value, key2: value2}} format'''
        
        LOG.debug("Pend a change for another host on disk")
        try:
            with open(os.path.join(self._host_file_dir, PENDING_UPLOAD_FILENAME), 'r') as f:
                pending_changes = json.load(f)
        except IOError:
            pending_changes = {}

        # merge existing changes with new ones
        for hostid in change:
            if not hostid in pending_changes:
                pending_changes[hostid] = {}
            pending_changes[hostid].update(change[hostid])

        with open(os.path.join(self._host_file_dir, PENDING_UPLOAD_FILENAME), 'w') as f:
            json.dump(pending_changes, f)

    def get_hostid_pending_change(self, hostid, attribute):
        '''Get the status if a pending change is in progress for an host

        Return None if nothing in progress'''
        try:
            with open(os.path.join(self._host_file_dir, PENDING_UPLOAD_FILENAME), 'r') as f:
                return json.load(f)[hostid][attribute]
        except IOError, KeyError:
            return None
    
    def gethost_by_id(self, hostid):
        '''Get host dictionnary by id

        Return: hostname

        can trigger HostError exception if no hostname found for this id
        '''
        
        if hostid == self.current_host['hostid']:
            return self.current_host
        try:
            return self.other_hosts[hostid]
        except KeyError:
            raise HostError(_("No hostname registered for this id"))
        

    def _gethostid_by_name(self, hostname):
        '''Get hostid by hostname

        Return: hostid

        can trigger HostError exception unexisting hostname
        or multiple hostid for this hostname
        '''
        
        LOG.debug("Get a hostid for %s", hostname)

        result_hostid = None
        if hostname == self.current_host['hostname']:
            result_hostid = self.current_host['hostid']
        for hostid in self.other_hosts:
            if hostname == self.other_hosts[hostid]['hostname']:
                if not result_hostid:
                    result_hostid = hostid
                else:
                    raise HostError(_("Multiple hostid registered for this "\
                        "hostname. Use --list --host to get the hostid and "\
                        "use the --hostid option."))
        if not result_hostid:
            raise HostError(_("No hostid registered for this hostname"))
        return result_hostid


    def get_hostid_from_context(self, hostid=None, hostname=None):
        '''get and check hostid

        if hostid and hostname are none, hostid is the current one
        Return: the corresponding hostid, raise an error if multiple hostid
                for an hostname
        '''

        if not hostid and not hostname:
            hostid = self.current_host['hostid']
        if hostid:
            # just checking if it exists
            self.gethost_by_id(hostid)
            hostid = hostid
        else:
            hostid = self._gethostid_by_name(hostname) 
        return hostid

    def get_currenthost_dir(self):
        '''Get the oneconf current host directory'''
        return self._host_file_dir

    def get_all_hosts(self):
        '''Return a dictionnary of all hosts

        put in them as dict -> tuple for dbus connection'''

        LOG.debug("Request to compute an list of all hosts")
        result = {self.current_host['hostid']: (True, self.current_host['hostname'], self.current_host['share_inventory'])}
        for hostid in self.other_hosts:
            result[hostid] = (False, self.other_hosts[hostid]['hostname'], True)
        return result

    def set_share_inventory(self, share_inventory, hostid=None, hostname=None):
        '''Change if we share the current inventory to other hosts'''

        if hostid or hostname:
            hostid = self.get_hostid_from_context(hostid, hostname)
            # do not update if there is already this pending change is already registered
            pending_change_scheduled = self.get_hostid_pending_change(hostid, 'share_inventory')
            if pending_change_scheduled != None:
                if share_inventory == pending_change_scheduled:
                    return

            save_function = self.add_hostid_pending_change
            arg = {hostid: {'share_inventory': share_inventory}}
            msg = "Update share_inventory state for %s to %s" % (hostid, share_inventory)
        else:
            save_function = self.save_current_host
            arg = None
            msg = "Update current share_inventory state to %s" % share_inventory
            if self.current_host['share_inventory'] == share_inventory:
                return
            self.current_host['share_inventory'] = share_inventory
        LOG.debug(msg)
        save_function(arg)

    def get_last_sync_date(self):
        '''Get last sync date, if already synced, with remote server'''
        
        LOG.debug("Getting last sync date with remote server")
        try:
            with open(os.path.join(self._host_file_dir, LAST_SYNC_DATE_FILENAME), 'r') as f:
                content = json.load(f)
                last_sync = content['last_sync']
                #last_sync = datetime.datetime.fromtimestamp(content['last_sync']).strftime("%X %x")
        except IOError:
            last_sync = _("Was never synced")
        return last_sync
        
