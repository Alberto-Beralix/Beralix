# ubuntuone.eventlog.zg_listener - listen for SD events, log into ZG
#
# Author: Alejandro J. Cura <alecu@canonical.com>
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
"""Event logging from SyncDaemon into Zeitgeist."""

import mimetypes

from os.path import basename

from zeitgeist.datamodel import Event, Interpretation, Manifestation, Subject
from zeitgeist.mimetypes import get_interpretation_for_mimetype

from ubuntuone.eventlog import zglog
from ubuntuone.syncdaemon.volume_manager import Share, UDF

ACTOR_UBUNTUONE = "dbus://com.ubuntuone.SyncDaemon.service"
DIRECTORY_MIMETYPE = "inode/directory"
DEFAULT_MIME = "application/octet-stream"
DEFAULT_INTERPRETATION = Interpretation.DOCUMENT
EVENT_INTERPRETATION_U1_FOLDER_SHARED = "u1://FolderShared"
EVENT_INTERPRETATION_U1_FOLDER_UNSHARED = "u1://FolderUnshared"
EVENT_INTERPRETATION_U1_SHARE_ACCEPTED = "u1://ShareAccepted"
EVENT_INTERPRETATION_U1_SHARE_UNACCEPTED = "u1://ShareUnaccepted"
EVENT_INTERPRETATION_U1_CONFLICT_RENAME = "u1://ConflictRename"
EVENT_INTERPRETATION_U1_UDF_CREATED = "u1://UserFolderCreated"
EVENT_INTERPRETATION_U1_UDF_DELETED = "u1://UserFolderDeleted"
EVENT_INTERPRETATION_U1_UDF_SUBSCRIBED = "u1://UserFolderSubscribed"
EVENT_INTERPRETATION_U1_UDF_UNSUBSCRIBED = "u1://UserFolderUnsubscribed"
MANIFESTATION_U1_CONTACT_DATA_OBJECT = "u1://ContactDataObject"
INTERPRETATION_U1_CONTACT = "u1://Contact"
URI_PROTOCOL_U1 = "ubuntuone:"
STORAGE_LOCAL = ""
STORAGE_NETWORK = "net"
STORAGE_DELETED = "deleted"

class ZeitgeistListener(object):
    """An Event Queue listener that logs into ZG."""

    def __init__(self, fsm, vm):
        """Initialize this instance."""
        self.fsm = fsm
        self.vm = vm
        self.zg = zglog.ZeitgeistLogger()
        self.newly_created_server_files = set()
        self.newly_created_local_files = set()

    def handle_AQ_CREATE_SHARE_OK(self, share_id, marker):
        """Log the 'directory shared thru the server' event."""
        share_id = str(share_id)
        share = self.vm.shared.get(share_id)
        if not share:
            share = self.vm.marker_share_map[marker]
            share_id = share.node_id
        self.log_folder_shared(share, share_id)

    def handle_AQ_SHARE_INVITATION_SENT(self, marker):
        """Log the 'directory shared thru http' event."""
        share = self.vm.marker_share_map[marker]
        mdo = self.fsm.get_by_mdid(marker)
        self.log_folder_shared(share, mdo.share_id)

    def log_folder_shared(self, share, share_id):
        """Log the 'directory shared' event."""
        fullpath = share.path
        folder_name = basename(fullpath)

        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(share.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + fullpath,
            text=folder_name,
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        other_username = share.other_username
        other_user = Subject.new_for_values(
            uri="mailto:" + other_username,
            interpretation=INTERPRETATION_U1_CONTACT,
            text=other_username,
            manifestation=MANIFESTATION_U1_CONTACT_DATA_OBJECT)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_FOLDER_SHARED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder, other_user])

        self.zg.log(event)

    def handle_VM_SHARE_DELETED(self, share):
        """Log the share deleted event."""
        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(share.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + share.path,
            text=basename(share.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        other_username = share.other_username
        other_user = Subject.new_for_values(
            uri="mailto:" + other_username,
            interpretation=INTERPRETATION_U1_CONTACT,
            text=other_username,
            manifestation=MANIFESTATION_U1_CONTACT_DATA_OBJECT)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_FOLDER_UNSHARED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder, other_user])

        self.zg.log(event)

    def handle_VM_SHARE_CREATED(self, share_id):
        """Log the share accepted event."""
        share = self.vm.shares[share_id]

        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(share.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + share.path,
            text=basename(share.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        other_username = share.other_username
        other_user = Subject.new_for_values(
            uri="mailto:" + other_username,
            interpretation=INTERPRETATION_U1_CONTACT,
            text=other_username,
            manifestation=MANIFESTATION_U1_CONTACT_DATA_OBJECT)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_SHARE_ACCEPTED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder, other_user])

        self.zg.log(event)

    def log_share_unaccepted(self, share):
        """Log the share unaccepted event."""
        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(share.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + share.path,
            text=basename(share.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        other_username = share.other_username
        other_user = Subject.new_for_values(
            uri="mailto:" + other_username,
            interpretation=INTERPRETATION_U1_CONTACT,
            text=other_username,
            manifestation=MANIFESTATION_U1_CONTACT_DATA_OBJECT)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_SHARE_UNACCEPTED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder, other_user])

        self.zg.log(event)

    def log_udf_deleted(self, volume):
        """Log the udf deleted event."""
        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(volume.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.DELETED_RESOURCE,
            origin="file:///" + volume.path,
            text=basename(volume.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_DELETED)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_UDF_DELETED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder])

        self.zg.log(event)

    def handle_VM_VOLUME_DELETED(self, volume):
        """Log the share/UDF unaccepted event."""
        if isinstance(volume, Share):
            self.log_share_unaccepted(volume)
        if isinstance(volume, UDF):
            self.log_udf_deleted(volume)

    def handle_VM_UDF_CREATED(self, udf):
        """An udf was created. Log it into Zeitgeist."""
        folder = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(udf.node_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + udf.path,
            text=basename(udf.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_UDF_CREATED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder])

        self.zg.log(event)

    def handle_VM_UDF_SUBSCRIBED(self, udf):
        """An udf was subscribed."""

        folder = Subject.new_for_values(
            uri="file:///" + udf.path,
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.FILE_DATA_OBJECT,
            origin=URI_PROTOCOL_U1 + str(udf.node_id),
            text=basename(udf.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_LOCAL)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_UDF_SUBSCRIBED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder])

        self.zg.log(event)

    def handle_VM_UDF_UNSUBSCRIBED(self, udf):
        """An udf was unsubscribed."""

        folder = Subject.new_for_values(
            uri="file:///" + udf.path,
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.DELETED_RESOURCE,
            origin=URI_PROTOCOL_U1 + str(udf.node_id),
            text=basename(udf.path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_DELETED)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_UDF_UNSUBSCRIBED,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder])

        self.zg.log(event)

    def handle_AQ_FILE_NEW_OK(self, volume_id, marker, new_id, new_generation):
        """A new file was created on server. Store and wait till it uploads."""
        self.newly_created_server_files.add((volume_id, new_id))

    def get_mime_and_interpretation_for_filepath(self, filepath):
        """Try to guess the mime and the interpretation from the path."""
        mime, encoding = mimetypes.guess_type(filepath)
        if mime is None:
            return DEFAULT_MIME, DEFAULT_INTERPRETATION
        interpret = get_interpretation_for_mimetype(mime)
        if interpret is None:
            return DEFAULT_MIME, Interpretation.DOCUMENT
        return mime, interpret

    def handle_AQ_UPLOAD_FINISHED(self, share_id, node_id, hash,
                                  new_generation):
        """A file finished uploading to the server."""

        mdo = self.fsm.get_by_node_id(share_id, node_id)
        path = self.fsm.get_abspath(share_id, mdo.path)

        if (share_id, node_id) in self.newly_created_server_files:
            self.newly_created_server_files.remove((share_id, node_id))
            event_interpretation = Interpretation.CREATE_EVENT
        else:
            event_interpretation = Interpretation.MODIFY_EVENT

        mime, interp = self.get_mime_and_interpretation_for_filepath(path)

        file_subject = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(node_id),
            interpretation=interp,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + path,
            text=basename(path),
            mimetype=mime,
            storage=STORAGE_NETWORK)

        event = Event.new_for_values(
            interpretation=event_interpretation,
            manifestation=Manifestation.SCHEDULED_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_AQ_DIR_NEW_OK(self, volume_id, marker, new_id, new_generation):
        """A dir was created on the server."""

        mdo = self.fsm.get_by_node_id(volume_id, new_id)
        path = self.fsm.get_abspath(volume_id, mdo.path)

        file_subject = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(new_id),
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin="file:///" + path,
            text=basename(path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_NETWORK)

        event = Event.new_for_values(
            interpretation=Interpretation.CREATE_EVENT,
            manifestation=Manifestation.SCHEDULED_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_SV_FILE_NEW(self, volume_id, node_id, parent_id, name):
        """A file was created locally by Syncdaemon."""
        self.newly_created_local_files.add((volume_id, node_id))

    def handle_AQ_DOWNLOAD_FINISHED(self, share_id, node_id, server_hash):
        """A file finished downloading from the server."""

        mdo = self.fsm.get_by_node_id(share_id, node_id)
        path = self.fsm.get_abspath(share_id, mdo.path)

        if (share_id, node_id) in self.newly_created_local_files:
            self.newly_created_local_files.remove((share_id, node_id))
            event_interpretation = Interpretation.CREATE_EVENT
        else:
            event_interpretation = Interpretation.MODIFY_EVENT

        mime, interp = self.get_mime_and_interpretation_for_filepath(path)

        file_subject = Subject.new_for_values(
            uri="file:///" + path,
            interpretation=interp,
            manifestation=Manifestation.FILE_DATA_OBJECT,
            origin=URI_PROTOCOL_U1 + str(node_id),
            text=basename(path),
            mimetype=mime,
            storage=STORAGE_LOCAL)

        event = Event.new_for_values(
            interpretation=event_interpretation,
            manifestation=Manifestation.WORLD_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_SV_DIR_NEW(self, volume_id, node_id, parent_id, name):
        """A file finished downloading from the server."""

        mdo = self.fsm.get_by_node_id(volume_id, node_id)
        path = self.fsm.get_abspath(volume_id, mdo.path)

        file_subject = Subject.new_for_values(
            uri="file:///" + path,
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.FILE_DATA_OBJECT,
            origin=URI_PROTOCOL_U1 + str(node_id),
            text=basename(path),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_LOCAL)

        event = Event.new_for_values(
            interpretation=Interpretation.CREATE_EVENT,
            manifestation=Manifestation.WORLD_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_SV_FILE_DELETED(self, volume_id, node_id, was_dir, old_path):
        """A file or folder was deleted locally by Syncdaemon."""
        if was_dir:
            mime, interp = DIRECTORY_MIMETYPE, Interpretation.FOLDER
        else:
            mime, interp = self.get_mime_and_interpretation_for_filepath(
                                                                    old_path)

        file_subject = Subject.new_for_values(
            uri="file:///" + old_path,
            interpretation=interp,
            manifestation=Manifestation.DELETED_RESOURCE,
            origin=URI_PROTOCOL_U1 + str(node_id),
            text=basename(old_path),
            mimetype=mime,
            storage=STORAGE_DELETED)

        event = Event.new_for_values(
            interpretation=Interpretation.DELETE_EVENT,
            manifestation=Manifestation.WORLD_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_AQ_UNLINK_OK(self, share_id, parent_id, node_id,
                            new_generation, was_dir, old_path):
        """A file or folder was deleted on the server by Syncdaemon,"""
        if was_dir:
            mime, interp = DIRECTORY_MIMETYPE, Interpretation.FOLDER
        else:
            mime, interp = self.get_mime_and_interpretation_for_filepath(
                                                                    old_path)

        file_subject = Subject.new_for_values(
            uri=URI_PROTOCOL_U1 + str(node_id),
            interpretation=interp,
            manifestation=Manifestation.DELETED_RESOURCE,
            origin="file:///" + old_path,
            text=basename(old_path),
            mimetype=mime,
            storage=STORAGE_DELETED)

        event = Event.new_for_values(
            interpretation=Interpretation.DELETE_EVENT,
            manifestation=Manifestation.SCHEDULED_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_FSM_FILE_CONFLICT(self, old_name, new_name):
        """A file was renamed because of conflict."""
        mime, interp = self.get_mime_and_interpretation_for_filepath(old_name)

        file_subject = Subject.new_for_values(
            uri="file:///" + new_name,
            interpretation=interp,
            manifestation=Manifestation.FILE_DATA_OBJECT,
            origin="file:///" + old_name,
            text=basename(new_name),
            mimetype=mime,
            storage=STORAGE_LOCAL)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_CONFLICT_RENAME,
            manifestation=Manifestation.WORLD_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[file_subject])

        self.zg.log(event)

    def handle_FSM_DIR_CONFLICT(self, old_name, new_name):
        """A dir was renamed because of conflict."""
        folder_subject = Subject.new_for_values(
            uri="file:///" + new_name,
            interpretation=Interpretation.FOLDER,
            manifestation=Manifestation.FILE_DATA_OBJECT,
            origin="file:///" + old_name,
            text=basename(new_name),
            mimetype=DIRECTORY_MIMETYPE,
            storage=STORAGE_LOCAL)

        event = Event.new_for_values(
            interpretation=EVENT_INTERPRETATION_U1_CONFLICT_RENAME,
            manifestation=Manifestation.WORLD_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[folder_subject])

        self.zg.log(event)

    def handle_AQ_CHANGE_PUBLIC_ACCESS_OK(self, share_id, node_id, is_public,
                                          public_url):
        """The status of a published resource changed. Log it!"""
        if is_public:
            self.log_publishing(share_id, node_id, is_public, public_url)
        else:
            self.log_unpublishing(share_id, node_id, is_public, public_url)

    def log_publishing(self, share_id, node_id, is_public, public_url):
        """Log the publishing of a resource."""
        mime, interp = self.get_mime_and_interpretation_for_filepath(
                                                                    public_url)

        origin = "" if node_id is None else URI_PROTOCOL_U1 + str(node_id)

        public_file = Subject.new_for_values(
            uri=public_url,
            interpretation=interp,
            manifestation=Manifestation.REMOTE_DATA_OBJECT,
            origin=origin,
            text=public_url,
            mimetype=mime,
            storage=STORAGE_NETWORK)

        event = Event.new_for_values(
            interpretation=Interpretation.CREATE_EVENT,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[public_file])

        self.zg.log(event)

    def log_unpublishing(self, share_id, node_id, is_public, public_url):
        """Log the unpublishing of a resource."""
        mime, interp = self.get_mime_and_interpretation_for_filepath(
                                                                    public_url)

        origin = "" if node_id is None else URI_PROTOCOL_U1 + str(node_id)

        public_file = Subject.new_for_values(
            uri=public_url,
            interpretation=interp,
            manifestation=Manifestation.DELETED_RESOURCE,
            text=public_url,
            origin=origin,
            mimetype=mime,
            storage=STORAGE_DELETED)

        event = Event.new_for_values(
            interpretation=Interpretation.DELETE_EVENT,
            manifestation=Manifestation.USER_ACTIVITY,
            actor=ACTOR_UBUNTUONE,
            subjects=[public_file])

        self.zg.log(event)
