# ubuntuone.storageprotocol.client - the storage protocol client
#
# Author: Lucio Torre <lucio.torre@canonical.com>
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
# Author: Guillermo Gonzalez <guillermo.gonzalez@canonical.com>
# Author: Facundo Batista <facundo@canonical.com>
#
# Copyright 2009-2011 Canonical Ltd.
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
"""The storage protocol client."""

import logging
import uuid

from functools import partial
from itertools import chain
from oauth import oauth

from twisted.internet.protocol import ClientFactory
from twisted.internet import reactor, defer
from twisted.python import log

from ubuntuone.storageprotocol import (
    protocol_pb2, request, sharersp, volumes, delta)

log_debug = partial(log.msg, loglevel=logging.DEBUG)


class StorageClient(request.RequestHandler):
    """A Basic Storage Protocol client."""

    # we are a client, we do odd requests
    REQUEST_ID_START = 1

    def __init__(self):
        """Create the client. done by the factory."""
        request.RequestHandler.__init__(self)
        self.root_id = None
        self.root_id_defers = []

        self._node_state_callback = None
        self._share_change_callback = None
        self._share_delete_callback = None
        self._share_answer_callback = None
        self._free_space_callback = None
        self._account_info_callback = None
        self._volume_created_callback = None
        self._volume_deleted_callback = None
        self._volume_new_generation_callback = None

        self.line_mode = True
        self.max_payload_size = request.MAX_PAYLOAD_SIZE

    def protocol_version(self):
        """Ask for the protocol version

        will return a deferred that will get called with
        the request object when completed.

        """
        p = ProtocolVersion(self)
        p.start()
        return p.deferred

    def dataReceived(self, data):
        """Extend dataReceived.

        First reads the protocol hello line then switch back to len+data.

        """
        if self.line_mode:
            # first read the hello line, then back to binary.
            try:
                pos = data.index("\r\n")
            except ValueError:
                return
            self.line_mode = False
            data = data[pos + 2:]

        request.RequestHandler.dataReceived(self, data)

    def dummy_authenticate(self, credentials, metadata=None):
        """Authenticate to a server using the 'dummy auth' provider.

        Return a deferred that will get called with the request
        object when completed.

        """
        p = Authenticate(self, {'dummy_token': credentials},
                         metadata=metadata)
        p.start()
        return p.deferred

    def oauth_authenticate(self, consumer, token, metadata=None):
        """Authenticate to a server using the OAuth provider.

        @param consumer: the OAuth consumer to authenticate with.
        @type consumer: `oauth.OAuthConsumer`
        @param token: a previously acquired OAuth access token.
        @type consumer: `oauth.OAuthToken`
        @param kwargs: key/values to send as metadata

        Return a deferred that will get called with the request
        object when completed.

        """
        req = oauth.OAuthRequest.from_consumer_and_token(
            oauth_consumer=consumer,
            token=token,
            http_method="GET",
            http_url="storage://server")
        req.sign_request(
            oauth.OAuthSignatureMethod_PLAINTEXT(), consumer, token)

        # Make sure all parameter values are strings.
        auth_parameters = dict(
            (key, str(value)) for key, value in req.parameters.iteritems())
        p = Authenticate(self, auth_parameters, metadata=metadata)
        p.start()
        return p.deferred

    def handle_ROOT(self, message):
        """Handle incoming ROOT message.

        Will notify if someone is waiting for this information.

        """
        self.root_id = message.root.node
        if self.root_id_defers:
            for d in self.root_id_defers:
                d.callback(self.root_id)
            self.root_id_defers = []

    def handle_NODE_STATE(self, message):
        """Handle incoming NODE_STATE."""
        self.notify_node_state(message.node_state)

    def handle_NOTIFY_SHARE(self, message):
        """Handle incoming NOTIFY_SHARE."""
        self.notify_share_change(message.notify_share)

    def handle_SHARE_DELETED(self, message):
        """Handle incoming SHARE_DELETED."""
        self.notify_share_deleted(message.share_deleted)

    def handle_SHARE_ACCEPTED(self, message):
        """Handle incoming SHARE_ACCEPTED."""
        self.notify_share_answer(message.share_accepted)

    def handle_VOLUME_CREATED(self, message):
        """Handle incoming VOLUME_CREATED"""
        assert message.type == protocol_pb2.Message.VOLUME_CREATED
        msg = message.volume_created
        vol = None
        if self._volume_created_callback is not None:
            if msg.type == protocol_pb2.Volumes.ROOT:
                vol = volumes.RootVolume.from_msg(msg.root)
            elif msg.type == protocol_pb2.Volumes.SHARE:
                vol = volumes.ShareVolume.from_msg(msg.share)
            elif msg.type == protocol_pb2.Volumes.UDF:
                vol = volumes.UDFVolume.from_msg(msg.udf)
            else:
                msg = "Message.volume_created's type is not valid: %s" % \
                      message.volume_created.type
                raise TypeError(msg)

            self._volume_created_callback(vol)

    def handle_VOLUME_DELETED(self, message):
        """Handle incoming VOLUME_DELETED."""
        assert message.type == protocol_pb2.Message.VOLUME_DELETED
        if self._volume_deleted_callback is not None:
            vol_id = uuid.UUID(message.volume_deleted.volume)
            self._volume_deleted_callback(vol_id)

    def handle_VOLUME_NEW_GENERATION(self, message):
        """Handle incoming VOLUME_NEW_GENERATION."""
        assert message.type == protocol_pb2.Message.VOLUME_NEW_GENERATION
        if self._volume_new_generation_callback is not None:
            volume = message.volume_new_generation.volume
            if volume != request.ROOT:
                volume = uuid.UUID(volume)
            generation = message.volume_new_generation.generation
            self._volume_new_generation_callback(volume, generation)

    def handle_BEGIN_CONTENT(self, message):
        """Accept and discard a misplaced BEGIN_CONTENT.

        It can happen that while the server receives a PUT_CONTENT request
        and that it tells us to BEGIN_CONTENT, we cancelled the request,
        received the OK, and this side's request is gone, so receive this
        message here.

        """

    def handle_FREE_SPACE_INFO(self, message):
        """Handle unsolicited FREE_SPACE_INFO."""
        self.notify_free_space(message.free_space_info)

    def handle_ACCOUNT_INFO(self, message):
        """Handle unsolicited ACCOUNT_INFO."""
        self.notify_account_info(message.account_info)

    def get_root(self):
        """Get the root id through a deferred."""
        if self.root_id is not None:
            return defer.succeed(self.root_id)
        else:
            d = defer.Deferred()
            self.root_id_defers.append(d)
            return d

    def make_dir(self, share, parent, name):
        """Create a directory named name on the node parent

        the new node id will be on request.new_dir_id.

        """
        p = MakeDir(self, share, parent, name)
        p.start()
        return p.deferred

    def make_file(self, share, parent, name):
        """Create a file named name on the node parent

        the new node id will be on request.new_file_id.

        """
        p = MakeFile(self, share, parent, name)
        p.start()
        return p.deferred

    def move(self, share, node, new_parent, new_name):
        """Move a node."""
        p = Move(self, share, node, new_parent, new_name)
        p.start()
        return p.deferred

    def unlink(self, share, node):
        """Unlink a node."""
        p = Unlink(self, share, node)
        p.start()
        return p.deferred

    def get_content(self, share, node, a_hash, offset=0,
                    callback=None, node_attr_callback=None):
        """Get the content of node with 'a_hash'.

        the content will be on request.content
        or callback will be called for every piece that arrives.

        """
        req = self.get_content_request(share, node, a_hash, offset,
                                       callback, node_attr_callback)
        return req.deferred

    def get_content_request(self, share, node, a_hash, offset=0,
                            callback=None, node_attr_callback=None):
        """Get the content of node with 'a_hash', return the request.

        The content will be on request.content, or callback will be
        called for every piece that arrives.

        """
        p = GetContent(self, share, node, a_hash, offset,
                       callback, node_attr_callback)
        p.start()
        return p

    def put_content(self, share, node, previous_hash, new_hash,
                    crc32, size, deflated_size, fd, upload_id=None,
                    upload_id_cb=None, magic_hash=None):
        """Put the content of fd into file node."""
        req = self.put_content_request(share, node, previous_hash, new_hash,
                                       crc32, size, deflated_size, fd,
                                       upload_id=upload_id,
                                       upload_id_cb=upload_id_cb,
                                       magic_hash=magic_hash)
        return req.deferred

    def put_content_request(self, share, node, previous_hash, new_hash,
                            crc32, size, deflated_size, fd, upload_id=None,
                            upload_id_cb=None, magic_hash=None):
        """Put the content of fd into file node, return the request."""
        p = PutContent(self, share, node, previous_hash, new_hash,
                       crc32, size, deflated_size, fd,
                       upload_id=upload_id,
                       upload_id_cb=upload_id_cb,
                       magic_hash=magic_hash)
        p.start()
        return p

    def query(self, items):
        """Get the current hash for items if changed.

        'items' is a list of (node, hash) tuples.

        """
        r = MultiQuery(self, items)
        r.start()
        return r.deferred

    def get_delta(self, share_id, from_generation=None, callback=None,
                  from_scratch=False):
        """Get a delta for a share_id

        'share_id' is the share_id which we want to query.
        'from_generation' is the generation which we are at.
        'callback' can be specified to get deltas as they get instead of
            getting them all at once at the end.
        'from_scratch' at True means list all live nodes.

        """
        r = GetDelta(self, share_id, from_generation, callback, from_scratch)
        r.start()
        return r.deferred

    def get_free_space(self, share_id):
        """Get quota info for the given share (or the user's own space)."""
        r = FreeSpaceInquiry(self, share_id)
        r.start()
        return r.deferred

    def get_account_info(self):
        """Get account information (like purchased space etc.)."""
        r = AccountInquiry(self)
        r.start()
        return r.deferred

    def set_node_state_callback(self, callback):
        """Define the function to be called when a node_state message arrives

        The function will be called with the message as argument.

        """
        self._node_state_callback = callback

    def notify_node_state(self, node_state):
        """Call the current node state callback, if any, with the share, node,
        and hash given in the message.

        @param: node_state - a (raw) NodeState message

        """
        if self._node_state_callback:
            self._node_state_callback(node_state.share, node_state.node,
                                      node_state.hash)

    def set_free_space_callback(self, callback):
        """Set the quota notification callback.

        It will be called with the share id and free bytes.

        """
        self._free_space_callback = callback

    def notify_free_space(self, free_space_info):
        """Call the current quota info callback, if any, with the share
        and available bytes.

        @param: free_space_info - a (raw) FreeSpaceInfo message

        """
        if self._free_space_callback:
            self._free_space_callback(free_space_info.share_id,
                                      free_space_info.free_bytes)

    def set_account_info_callback(self, callback):
        """Set the account info notification callback; the callback
        will be passed a raw AccountInfo structure when it is called.

        """
        self._account_info_callback = callback

    def notify_account_info(self, account_info):
        """Call the current account info callback, if any."""
        if self._account_info_callback:
            self._account_info_callback(account_info)

    def set_share_change_callback(self, callback):
        """Set the callback when something changed regarding a share."""
        if callable(callback):
            self._share_change_callback = callback
        else:
            raise TypeError('callback for share_change must be callable')

    def notify_share_change(self, notify_share):
        """Call the current changed share callback, if any, with the
        notify info.

        @param notify_share: - a NotifyShare message

        """
        if self._share_change_callback:
            info = sharersp.NotifyShareHolder.load_from_msg(notify_share)
            self._share_change_callback(info)

    def set_share_delete_callback(self, callback):
        """Set the callback when something changed regarding a share."""
        if callable(callback):
            self._share_delete_callback = callback
        else:
            raise TypeError('callback for share_delete must be callable')

    def notify_share_deleted(self, share_deleted):
        """Call the current changed share callback, if any, with the
        notify info.

        @param msg: - a (raw) NotifyShare message

        """
        if self._share_delete_callback:
            self._share_delete_callback(uuid.UUID(share_deleted.share_id))

    def set_share_answer_callback(self, callback):
        """Define the function to be called when a share answer is received."""
        if callable(callback):
            self._share_answer_callback = callback
        else:
            raise TypeError('callback for share_answer must be callable')

    def notify_share_answer(self, msg):
        """Call the current share answer callback, if any, with the info.

        @param msg: - a (raw) ShareAccepted message

        """
        if self._share_answer_callback:
            if msg.answer == protocol_pb2.ShareAccepted.YES:
                answer = "Yes"
            elif msg.answer == protocol_pb2.ShareAccepted.NO:
                answer = "No"
            else:
                raise ValueError("Not supported ShareAccepted answer")
            self._share_answer_callback(uuid.UUID(msg.share_id), answer)

    def set_volume_created_callback(self, callback):
        """Set the callback for volume creation notification."""
        if callable(callback):
            self._volume_created_callback = callback
        else:
            raise TypeError('callback for volume_created must be callable')

    def set_volume_deleted_callback(self, callback):
        """Set the callback for volume deletion notification."""
        if callable(callback):
            self._volume_deleted_callback = callback
        else:
            raise TypeError('callback for volume_deleted must be callable')

    def set_volume_new_generation_callback(self, callback):
        """Set the callback for volume new generation notification."""
        if callable(callback):
            self._volume_new_generation_callback = callback
        else:
            raise TypeError('callback for volume_new_gen must be callable')

    def create_share(self, node, share_to, name, access_level):
        """Create a share to other user.

        node: which node to share.
        share_to: the id of the receiving user.
        name: the name of the share
        access_level: the permissions on the share

        There's no need to indicate where the node lives, as it only can be
        in own root (there's no re-sharing).

        """
        r = CreateShare(self, node, share_to, name, access_level)
        r.start()
        return r.deferred

    def delete_share(self, share_id):
        """Delete a share we have offered.

        @param share_id: the id of the share to delete

        """
        r = DeleteShare(self, share_id)
        r.start()
        return r.deferred

    def accept_share(self, share_id, answer):
        """Accept (or not) a share from other user.

        share_id: the share id
        answer: if it was accepted ("Yes") or not ("No")

        """
        r = AcceptShare(self, share_id, answer)
        r.start()
        return r.deferred

    def list_shares(self):
        """List all the shares the user is involved.

        This includes the shares the user created, and those that were
        shared to her.

        """
        p = ListShares(self)
        p.start()
        return p.deferred

    def create_udf(self, path, name):
        """Create a User Defined Folder.

        @param path: the path in disk to the UDF.
        @param name: the name of the UDF.

        """
        p = CreateUDF(self, path, name)
        p.start()
        return p.deferred

    def list_volumes(self):
        """List all the volumes the user has.

        This includes the volumes:
            - all the user's UDFs.
            - all the shares the user has accepted.
            - the root-root volume.

        """
        p = ListVolumes(self)
        p.start()
        return p.deferred

    def delete_volume(self, volume_id):
        """Delete 'volume' on the server, removing the associated tree.

        @param volume: the id of the volume to delete.

        """
        p = DeleteVolume(self, volume_id)
        p.start()
        return p.deferred

    def query_caps(self, caps):
        """Query the server to discover its capabilitis.

        The server should answer if it supports or not all the given
        caps.

        """
        r = QuerySetCaps(self, caps)
        r.start()
        return r.deferred

    def set_caps(self, caps):
        """Set the server to this capabilities."""
        r = QuerySetCaps(self, caps, set_mode=True)
        r.start()
        return r.deferred


class GetContent(request.Request):
    """A Request to get the content of a node id.

    @ivar data: the content of the node (available upon success)

    """

    __slots__ = ('share', 'node_id', 'hash', 'offset', 'callback',
                 'node_attr_callback', 'parts', 'data')

    def __init__(self, protocol, share, node_id, a_hash,
                 offset=0, callback=None, node_attr_callback=None):
        """Request the content of node with 'a_hash'.

        @param protocol: the request handler
        @param share: the share node or root
        @param node_id: the node id of the node we want to read
        @param a_hash: the hash of the content of the version we have
        @param offset: offset for reading
        @param callback: function to call when data arrives

        """
        request.Request.__init__(self, protocol)
        self.share = share
        self.node_id = node_id
        self.hash = a_hash
        self.offset = offset
        self.callback = callback
        self.node_attr_callback = node_attr_callback
        self.parts = []

    def _start(self):
        """Send GET_CONTENT."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.GET_CONTENT
        message.get_content.node = str(self.node_id)
        message.get_content.hash = str(self.hash)
        message.get_content.share = self.share
        message.get_content.offset = self.offset
        self.sendMessage(message)

    def processMessage(self, message):
        """Process messages."""
        # pylint: disable=W0201
        if message.type == protocol_pb2.Message.NODE_ATTR:
            if self.node_attr_callback is not None:
                self.node_attr_callback(
                    deflated_size=message.node_attr.deflated_size,
                    size=message.node_attr.size,
                    hash=message.node_attr.hash,
                    crc32=message.node_attr.crc32)
        elif message.type == protocol_pb2.Message.BYTES:
            if self.cancelled:
                # don't care about more bytes if already cancelled
                return
            if self.callback is not None:
                self.callback(message.bytes.bytes)
            else:
                self.parts.append(message.bytes.bytes)
        elif message.type == protocol_pb2.Message.EOF:
            if self.cancelled:
                # eof means that the cancel request arrived late. this is the
                # end.
                self.done()
                return
            if self.callback is None:
                self.data = "".join(self.parts)
            self.done()
        elif message.type == protocol_pb2.Message.OK:
            self.done()
        elif message.type == protocol_pb2.Message.CANCELLED:
            self.error(request.RequestCancelledError("CANCELLED"))
        else:
            self._default_process_message(message)

    def _cancel(self):
        """Cancel the current download."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.CANCEL_REQUEST
        self.sendMessage(message)


class ListShares(request.Request):
    """List all the shares the user is involved.

    This includes the shares the user created, and those that were
    shared to her.

    """

    __slots__ = ('shares',)

    def _start(self):
        """Send the LIST_SHARES message to the server."""
        # pylint: disable=W0201
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.LIST_SHARES
        self.sendMessage(message)
        self.shares = []

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.SHARES_INFO:
            share = sharersp.ShareResponse.load_from_msg(message.shares)
            self.shares.append(share)
        elif message.type == protocol_pb2.Message.SHARES_END:
            self.done()
        else:
            self._default_process_message(message)


class CreateShare(request.Request):
    """Create a share."""

    __slots__ = ('node', 'share_to', 'name', 'access_level', 'share_id')

    # these are the valid access levels and their translation to the
    # protocol message
    _valid_access_levels = {
        "View": protocol_pb2.CreateShare.VIEW,
        "Modify": protocol_pb2.CreateShare.MODIFY,
    }

    def __init__(self, protocol, node_id, share_to, name, access_level):
        """Create a share.

        @param node_id: which node will be root to share.
        @param share_to: the id of the receiving user.
        @param name: the name of the share
        @param access_level: the permissions on the share

        """
        request.Request.__init__(self, protocol)
        self.node = node_id
        self.share_to = share_to
        self.name = name
        self.access_level = access_level
        self.share_id = None

    def _start(self):
        """Send the CREATE_SHARE message to the server."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.CREATE_SHARE
        message.create_share.node = self.node
        message.create_share.share_to = self.share_to
        message.create_share.name = self.name

        # we make this testing here and not in __init__ because it should
        # be done when creating the message (to support that the access_level
        # is changed between instantiating and message creation)
        try:
            message_access_level = self._valid_access_levels[self.access_level]
        except KeyError:
            raise ValueError("Invalid access level! (%r)" % self.access_level)
        message.create_share.access_level = message_access_level

        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.SHARE_CREATED:
            self.share_id = message.share_created.share_id
            self.done()
        elif message.type == protocol_pb2.Message.OK:
            # this is for PROTOCOL_VERSION=1 backward compatibility
            self.done()
        else:
            self._default_process_message(message)


class AcceptShare(request.Request):
    """Accept a share (or not)."""

    __slots__ = ('share_id', 'answer')

    # these are the valid answers and their translation to the
    # protocol message
    _valid_answer = {
        "Yes": protocol_pb2.ShareAccepted.YES,
        "No": protocol_pb2.ShareAccepted.NO,
    }

    def __init__(self, protocol, share_id, answer):
        """Accept (or not) a share from other user.

        @param share_id: the share id
        @param answer: if it was accepted ("Yes") or not ("No")

        """
        request.Request.__init__(self, protocol)
        self.share_id = share_id
        self.answer = answer

    def _start(self):
        """Send the SHARE_ACCEPTED message to the server."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.SHARE_ACCEPTED
        message.share_accepted.share_id = str(self.share_id)

        # we make this testing here and not in __init__ because it should
        # be done when creating the message (to support that the answer
        # is changed between instantiating and message creation)
        try:
            message.share_accepted.answer = self._valid_answer[self.answer]
        except KeyError:
            raise ValueError("Invalid answer! (%r)" % self.answer)

        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.OK:
            self.done()
        else:
            self._default_process_message(message)


class DeleteShare(request.Request):
    """Delete a share."""

    __slots__ = ('share_id',)

    def __init__(self, protocol, share_id):
        """Delete a share we had offered to someone else.

        @param share_id: the share id

        """
        request.Request.__init__(self, protocol)
        self.share_id = share_id

    def _start(self):
        """Send the DELETE_SHARE message to the server."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.DELETE_SHARE
        message.delete_share.share_id = str(self.share_id)

        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.OK:
            self.done()
        else:
            self._default_process_message(message)


class CreateUDF(request.Request):
    """Create a UDF."""

    __slots__ = ('path', 'name', 'volume_id', 'node_id')

    def __init__(self, protocol, path, name):
        """Create a UDF.

        @param path: which node will be root to be UDF.
        @param name: the name of the UDF

        """
        request.Request.__init__(self, protocol)
        self.path = path
        self.name = name
        self.volume_id = None
        self.node_id = None

    def _start(self):
        """Send the CREATE_UDF message to the server."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.CREATE_UDF
        message.create_udf.path = self.path
        message.create_udf.name = self.name
        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if (message.type == protocol_pb2.Message.VOLUME_CREATED and
            message.volume_created.type == protocol_pb2.Volumes.UDF):
            self.volume_id = message.volume_created.udf.volume
            self.node_id = message.volume_created.udf.node
            self.done()
        else:
            self._default_process_message(message)


class ListVolumes(request.Request):
    """List all the volumes the user has.

    Including:
        - the UDFs the user created.
        - the shares the user has accepted.
        - the user's root-root.

    """
    __slots__ = ('volumes',)

    def __init__(self, protocol):
        """List volumes."""
        request.Request.__init__(self, protocol)
        self.volumes = []

    def _start(self):
        """Send the LIST_VOLUMES message to the server."""
        self.volumes = []
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.LIST_VOLUMES
        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.VOLUMES_INFO:
            if message.list_volumes.type == protocol_pb2.Volumes.SHARE:
                vol = volumes.ShareVolume.from_msg(message.list_volumes.share)
                self.volumes.append(vol)
            elif message.list_volumes.type == protocol_pb2.Volumes.UDF:
                vol = volumes.UDFVolume.from_msg(message.list_volumes.udf)
                self.volumes.append(vol)
            elif message.list_volumes.type == protocol_pb2.Volumes.ROOT:
                vol = volumes.RootVolume.from_msg(message.list_volumes.root)
                self.volumes.append(vol)
            else:
                self.error(request.StorageRequestError(self, message))
        elif message.type == protocol_pb2.Message.VOLUMES_END:
            self.done()
        else:
            self._default_process_message(message)


class DeleteVolume(request.Request):
    """Delete a volume."""

    __slots__ = ('volume_id',)

    def __init__(self, protocol, volume_id):
        """Delete a volume.

        @param volume_id: the volume id

        """
        request.Request.__init__(self, protocol)
        self.volume_id = str(volume_id)

    def _start(self):
        """Send the DELETE_VOLUME message to the server."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.DELETE_VOLUME
        message.delete_volume.volume = self.volume_id

        self.sendMessage(message)

    def processMessage(self, message):
        """Process the answer from the server."""
        if message.type == protocol_pb2.Message.OK:
            self.done()
        else:
            self._default_process_message(message)


class Unlink(request.Request):
    """Unlink a node.

    @ivar new_generation: the generation that the volume is at now
    """
    # pylint: disable=C0111

    __slots__ = ('share', 'node', 'new_generation')

    def __init__(self, protocol, share, node_id):
        """Request that node_id be unlinked

        @param protocol: the request handler
        @param share: the share node or root
        @param node_id: the node id of the node we want to unlink

        """
        request.Request.__init__(self, protocol)
        self.share = share
        self.node = node_id
        self.new_generation = None

    def _start(self):
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.UNLINK
        message.unlink.share = self.share
        message.unlink.node = self.node

        self.sendMessage(message)

    def processMessage(self, message):
        if message.type == protocol_pb2.Message.OK:
            self.new_generation = message.new_generation
            self.done()
        else:
            self._default_process_message(message)


class Move(request.Request):
    """Move a node.

    @ivar new_generation: the generation that the volume is at now
    """

    __slots__ = ('share', 'node_id', 'new_parent_id', 'new_name',
                 'new_generation')

    def __init__(self, protocol, share, node_id, new_parent_id, new_name):
        """Create the move request

        @param protocol: the request handler
        @param share: the share node or root
        @param node_id: the node id of the node we want to move
        @param new_parent_id: the id of the new parent
        @param new_name: the new name for this node
        @param callback: function to call when data arrives

        """
        request.Request.__init__(self, protocol)
        self.share = share
        self.node_id = node_id
        self.new_parent_id = new_parent_id
        self.new_name = new_name
        self.new_generation = None

    def _start(self):
        """Send MOVE."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.MOVE
        message.move.share = self.share
        message.move.node = self.node_id
        message.move.new_parent_node = str(self.new_parent_id)
        message.move.new_name = self.new_name

        self.sendMessage(message)

    def processMessage(self, message):
        """Process messages."""
        if message.type == protocol_pb2.Message.OK:
            self.new_generation = message.new_generation
            self.done()
        else:
            self._default_process_message(message)


class MultiQuery(object):
    """Create a Request-like object that encapsulates many Query requests

    We may need to split this request into many Query rests if the list of
    items to query is to big to fit in one message.

    """

    __slots__ = ('queries', 'deferred')

    def __init__(self, protocol, items):
        """Create a multiquery.

        @param protocol: the request handler
        @param items: a list of (node, hash) tuples

        """
        items = iter(items)
        defers = []
        self.queries = []

        while True:
            r = Query(protocol, items)
            self.queries.append(r)
            defers.append(r.deferred)
            if r.overflow:
                items = chain([r.overflow], items)
            else:
                break

        self.deferred = defer.DeferredList(defers, consumeErrors=True)

    def start(self):
        """Start the queries."""
        for q in self.queries:
            q.start()


class Query(request.Request):
    """Query about the hash of a node_id.

    @ivar remains: the items that could not fit in the query
    @ivar response: the node state messages that were received

    """

    __slots__ = ('query_message', 'response', 'overflow')

    def __init__(self, protocol, items):
        """Generate a query message to send to the server.

        Put as much items as it can inside the message whats left is
        left in self.remainder.

        @param protocol: the request handler
        @param items: a list of (node, hash, share) tuples

        """
        request.Request.__init__(self, protocol)
        self.query_message = qm = protocol_pb2.Message()
        qm.id = 0  # just to have something in the field when calculating size
        qm.type = protocol_pb2.Message.QUERY
        self.response = []
        self.overflow = None
        items_that_fit = []

        def add_items(msg, *args):
            """Add items to query."""
            for share, node, content_hash in args:
                qi = msg.query.add()
                qi.share = share
                qi.node = str(node)
                qi.hash = content_hash

        for item in items:
            add_items(qm, item)
            if qm.ByteSize() > request.MAX_MESSAGE_SIZE:
                self.overflow = item
                break
            items_that_fit.append(item)

        if self.overflow is not None:
            qm.ClearField("query")
            add_items(qm, *items_that_fit)

    def _start(self):
        """Send QUERY."""
        self.sendMessage(self.query_message)

    def processMessage(self, message):
        """Handle messages."""
        if message.type == protocol_pb2.Message.NODE_STATE:
            self.response.append(message.node_state)
            self.protocol.notify_node_state(message.node_state)
        elif message.type == protocol_pb2.Message.QUERY_END:
            self.done()
        else:
            self._default_process_message(message)


class BytesMessageProducer(object):
    """Produce BYTES messages from a file."""

    # to allow patching this in test and use task.Clock
    callLater = reactor.callLater

    def __init__(self, req, fh, offset):
        """Create a BytesMessageProducer."""
        self.request = req
        self.producing = False
        self.fh = fh
        self.offset = offset
        self.finished = False

    def resumeProducing(self):
        """IPushProducer interface."""
        self.producing = True
        self.go()

    def stopProducing(self):
        """IPushProducer interface."""
        self.producing = False

    def pauseProducing(self):
        """IPushProducer interface."""
        self.producing = False

    def go(self):
        """While producing, generates data.

        Read a little from the file, generates a BYTES message, and pass the
        control to the reactor.  If no more data, finish with EOF.

        """
        if not self.producing or self.request.cancelled or self.finished:
            return

        if self.offset:
            self.fh.seek(self.offset)
        data = self.fh.read(self.request.max_payload_size)
        if data:
            if self.offset:
                self.offset += len(data)
            response = protocol_pb2.Message()
            response.type = protocol_pb2.Message.BYTES
            response.bytes.bytes = data
            self.request.sendMessage(response)
            self.callLater(0, self.go)
        else:
            message = protocol_pb2.Message()
            message.type = protocol_pb2.Message.EOF
            self.request.sendMessage(message)
            self.producing = False
            self.finished = True


class PutContent(request.Request):
    """Put content request.

    @ivar new_generation: the generation that the volume is at now
    """

    __slots__ = ('share', 'node_id', 'previous_hash', 'hash', 'crc32', 'size',
                 'size', 'deflated_size', 'fd', 'upload_id_cb', 'upload_id',
                 'new_generation', 'max_payload_size', 'magic_hash')

    def __init__(self, protocol, share, node_id, previous_hash, new_hash,
                 crc32, size, deflated_size, fd, upload_id=None,
                 upload_id_cb=None, magic_hash=None):
        """Put content into a node.

        @param protocol: the request handler
        @param share: the share node or root
        @param node_id: the node to receive the content
        @param previous_hash: the hash the node has (for conflict checking)
        @param new_hash: the hash hint for the new content
        @param crc32: the crc32 hint for the new content
        @param size: the size hint for the new content
        @param fd: a file-like object to read data from
        @param upload_id: the upload id (to resume the upload.)
        @param upload_id_cb: callback that will be called with the upload id
                             assigned by the server for the session
        @param magic_hash: the magic_hash of the file

        """
        request.Request.__init__(self, protocol)
        self.share = share
        self.node_id = node_id
        self.previous_hash = previous_hash
        self.hash = new_hash
        self.crc32 = crc32
        self.size = size
        self.deflated_size = deflated_size
        self.fd = fd
        self.upload_id_cb = upload_id_cb
        self.upload_id = upload_id
        self.new_generation = None
        self.magic_hash = magic_hash
        self.max_payload_size = protocol.max_payload_size

    def _start(self):
        """Send PUT_CONTENT."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.PUT_CONTENT
        message.put_content.share = self.share
        message.put_content.node = str(self.node_id)
        message.put_content.previous_hash = self.previous_hash
        message.put_content.hash = self.hash
        message.put_content.crc32 = self.crc32
        message.put_content.size = self.size
        message.put_content.deflated_size = self.deflated_size
        if self.upload_id:
            message.put_content.upload_id = self.upload_id
        if self.magic_hash is not None:
            message.put_content.magic_hash = self.magic_hash
        self.sendMessage(message)

    def processMessage(self, message):
        """Handle messages."""
        if message.type == protocol_pb2.Message.BEGIN_CONTENT:
            # call the upload_id_cb (if the upload_id it's in the message)
            if message.begin_content.upload_id \
               and self.upload_id_cb:
                self.upload_id_cb(message.begin_content.upload_id)
            message_producer = BytesMessageProducer(
                self, self.fd, message.begin_content.offset)
            self.registerProducer(message_producer, streaming=True)
        elif message.type == protocol_pb2.Message.OK:
            self.new_generation = message.new_generation
            self.done()
        elif message.type == protocol_pb2.Message.CANCELLED:
            self.error(request.RequestCancelledError("CANCELLED"))
        else:
            self._default_process_message(message)

    def _cancel(self):
        """Cancel the current upload."""
        if self.producer is not None:
            self.producer.stopProducing()
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.CANCEL_REQUEST
        self.sendMessage(message)


class MakeObject(request.Request):
    """Handle the creation of new objects.

    On completion it will have the attribute 'new_id' with the
    node id of the created object.

    @cvar create_message: must be overridden with the correct creation message
    to send
    @cvar response_message: must be overridden with the correct creation
    success message that will be received

    @ivar new_id: the id of the node that was created (available upon success)
    @ivar new_parent_id: the parent id the node now exists under
    @ivar new_name: the name the node now exists under
    @ivar new_generation: the generation that the volume is at now

    """

    __slots__ = ('share', 'parent_id', 'name')

    def __init__(self, protocol, share, parent_id, name):
        """Create a node.

        @param protocol: the request handler
        @param share: the share node or root
        @param parent_id: the desired parent id
        @param name: the desired name

        """
        request.Request.__init__(self, protocol)
        self.share = share
        self.parent_id = parent_id
        self.name = name

    def _start(self):
        """Send MAKE message."""
        message = protocol_pb2.Message()
        message.type = self.create_message

        message.make.share = self.share
        message.make.parent_node = str(self.parent_id)
        message.make.name = self.name
        self.sendMessage(message)

    def processMessage(self, message):
        """Handle messages."""
        # pylint: disable=W0201
        if message.type == self.create_response:
            self.new_id = message.new.node
            self.new_parent_id = message.new.parent_node
            self.new_name = message.new.name
            self.new_generation = message.new_generation
            self.done()
        else:
            self._default_process_message(message)


class MakeDir(MakeObject):
    """Extend MakeObject to make directories."""

    create_message = protocol_pb2.Message.MAKE_DIR
    create_response = protocol_pb2.Message.NEW_DIR


class MakeFile(MakeObject):
    """Extend MakeObject to make files."""

    create_message = protocol_pb2.Message.MAKE_FILE
    create_response = protocol_pb2.Message.NEW_FILE


class ProtocolVersion(request.Request):
    """Handle the protocol version query.

    when completed will contain the servers protocol version
    on `other_protocol_version`

    @ivar other_protocol_version: the other peer's protocol version (available
        upon success)

    """

    def _start(self):
        """Send PROTOCOL_VERSION."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.PROTOCOL_VERSION
        message.protocol.version = self.protocol.PROTOCOL_VERSION
        self.sendMessage(message)

    def processMessage(self, message):
        """Handle messages."""
        # pylint: disable=W0201
        if message.type == protocol_pb2.Message.PROTOCOL_VERSION:
            self.other_protocol_version = message.protocol.version
            self.done()
        else:
            self._default_process_message(message)


class Authenticate(request.Request):
    """Request to authenticate the user.

    @ivar session_id: the session id with the server.
    """

    __slots__ = ('auth_parameters', 'session_id', 'metadata')

    def __init__(self, protocol, auth_parameters, metadata=None):
        """Create an authentication request.

        @param protocol: the request handler
        @param auth_parameters: a dictionary of authentication parameters.
        @param metadata: a dictionary of extra info

        """
        request.Request.__init__(self, protocol)
        self.auth_parameters = auth_parameters
        self.metadata = metadata
        self.session_id = None

    def _start(self):
        """Send AUTH_REQUEST."""
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.AUTH_REQUEST
        for key, value in self.auth_parameters.items():
            param = message.auth_parameters.add()
            param.name = key
            param.value = value
        if self.metadata:
            for key, value in self.metadata.items():
                param = message.metadata.add()
                param.key = key
                param.value = value
        self.sendMessage(message)

    def processMessage(self, message):
        """Handle messages."""
        if message.type == protocol_pb2.Message.AUTH_AUTHENTICATED:
            self.session_id = message.session_id
            self.done()
        else:
            self._default_process_message(message)


class QuerySetCaps(request.Request):
    """Query or Set the server to use capabilities."""

    __slots__ = ('caps', 'accepted', 'redirect_hostname', 'redirect_port',
                 'redirect_srvrecord', 'set_mode')

    def __init__(self, protocol, caps, set_mode=False):
        """Generate a query_caps or set_caps message to send to the server.

        @param protocol: the request handler
        @param caps: a list of capabilities to ask for or to set

        """
        request.Request.__init__(self, protocol)
        self.caps = caps
        self.accepted = None
        self.redirect_hostname = None
        self.redirect_port = None
        self.redirect_srvrecord = None
        self.set_mode = set_mode

    def _start(self):
        """Send QUERY_CAPS or SET_CAPS."""
        message = protocol_pb2.Message()
        if self.set_mode:
            message.type = protocol_pb2.Message.SET_CAPS
            for cap in self.caps:
                qc = message.set_caps.add()
                qc.capability = cap
        else:
            message.type = protocol_pb2.Message.QUERY_CAPS
            for cap in self.caps:
                qc = message.query_caps.add()
                qc.capability = cap

        self.sendMessage(message)

    def processMessage(self, message):
        """Handle the message."""
        if message.type == protocol_pb2.Message.ACCEPT_CAPS:
            self.accepted = message.accept_caps.accepted
            self.redirect_hostname = message.accept_caps.redirect_hostname
            self.redirect_port = message.accept_caps.redirect_port
            self.redirect_srvrecord = message.accept_caps.redirect_srvrecord
            self.done()
        else:
            self._default_process_message(message)


class FreeSpaceInquiry(request.Request):
    """Query available space."""

    __slots__ = ('share_id', 'free_bytes')

    def __init__(self, protocol, share_id):
        """Initialize the request."""
        request.Request.__init__(self, protocol)
        self.share_id = share_id

    def _start(self):
        """Send the FREE_SPACE_INQUIRY message to the server."""
        # pylint: disable=W0201
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.FREE_SPACE_INQUIRY
        message.free_space_inquiry.share_id = self.share_id
        self.sendMessage(message)
        self.free_bytes = None

    def processMessage(self, message):
        """Process the answer from the server."""
        # pylint: disable=W0201
        if message.type == protocol_pb2.Message.FREE_SPACE_INFO:
            self.free_bytes = message.free_space_info.free_bytes
            self.done()
        else:
            self._default_process_message(message)


class AccountInquiry(request.Request):
    """Query account information."""

    __slots__ = ('purchased_bytes',)

    def _start(self):
        """Send the FREE_SPACE_INQUIRY message to the server."""
        # pylint: disable=W0201
        message = protocol_pb2.Message()
        message.type = protocol_pb2.Message.ACCOUNT_INQUIRY
        self.sendMessage(message)
        self.purchased_bytes = None

    def processMessage(self, message):
        """Process the answer from the server."""
        # pylint: disable=W0201
        if message.type == protocol_pb2.Message.ACCOUNT_INFO:
            self.purchased_bytes = message.account_info.purchased_bytes
            self.done()
        else:
            self._default_process_message(message)


class GetDelta(request.Request):
    """Get a delta on a volume

    @ivar end_generation: The generation the volume will be after aplying this
                delta
    @ivar full: True if all changes were included. False is there is some
                later generations not included.
    @ivar free_bytes: The free space of the volume.
                Only a hint if full is False.
    @ivar response: the list of deltanodes received or empty if called with
                callback
    """

    def __init__(self, protocol, share_id, from_generation=None,
                 callback=None, from_scratch=False):
        """Generates a GET_DELTA message to the server.

        @param protocol: the request handler
        @param volume_id: the volume id
        @param from_generation: the starting generation for the delta
        @param from_scratch: request a delta with all live files

        """
        if from_generation is None and from_scratch is False:
            raise TypeError("get_delta needs from_generation or from_scratch.")

        request.Request.__init__(self, protocol)
        self.share_id = str(share_id)
        self.from_generation = from_generation
        self.callback = callback
        self.delta_message = dm = protocol_pb2.Message()
        dm.type = protocol_pb2.Message.GET_DELTA
        dm.get_delta.share = self.share_id
        if not from_scratch:
            dm.get_delta.from_generation = from_generation
        dm.get_delta.from_scratch = from_scratch

        self.response = []
        self.end_generation = None
        self.full = None
        self.free_bytes = None
        self.generation = None

    __slots__ = ('share_id', 'from_generation', 'callback', 'delta_message',
                 'response', 'end_generation', 'full', 'free_bytes',
                 'generation')

    def _start(self):
        """Send GET_DELTA."""
        self.sendMessage(self.delta_message)

    def processMessage(self, message):
        """Handle messages."""
        if message.type == protocol_pb2.Message.DELTA_INFO:
            info = delta.from_message(message)
            if self.callback:
                self.callback(info)
            else:
                self.response.append(info)
        elif message.type == protocol_pb2.Message.DELTA_END:
            self.end_generation = message.delta_end.generation
            self.full = message.delta_end.full
            self.free_bytes = message.delta_end.free_bytes
            self.done()
        else:
            self._default_process_message(message)


class ThrottlingStorageClient(StorageClient):
    """The throttling version of the StorageClient protocol."""

    factory = None

    def connectionMade(self):
        """Handle connectionMade."""
        if self.factory.client is None:
            self.factory.client = self
        StorageClient.connectionMade(self)

    def connectionLost(self, reason=None):
        """Handle connectionLost."""
        if self.factory.client is self:
            self.factory.unregisterProtocol(self)
        StorageClient.connectionLost(self, reason=reason)

    def write(self, data):
        """Transport API to capture bytes written."""
        if self.factory.client is self:
            self.factory.registerWritten(len(data))
        StorageClient.write(self, data)

    def writeSequence(self, seq):
        """Transport API to capture bytes written in a sequence."""
        if self.factory.client is self:
            self.factory.registerWritten(sum(len(x) for x in seq))
        StorageClient.writeSequence(self, seq)

    def dataReceived(self, data):
        """Override transport default to capture bytes read."""
        if self.factory.client is self:
            self.factory.registerRead(len(data))
        StorageClient.dataReceived(self, data)

    def throttleReads(self):
        """Pause self.transport."""
        self.transport.pauseProducing()

    def unthrottleReads(self):
        """Resume self.transport."""
        self.transport.resumeProducing()

    def throttleWrites(self):
        """Pause producing."""
        self.pauseProducing()

    def unthrottleWrites(self):
        """Resume producing."""
        self.resumeProducing()


class StorageClientFactory(ClientFactory):
    """StorageClient factory."""
    # pylint: disable=W0232
    protocol = StorageClient


class ThrottlingStorageClientFactory(StorageClientFactory, object):
    """The throttling version of StorageClientFactory."""

    protocol = ThrottlingStorageClient
    client = None

    def __init__(self, throttling_enabled=False,
                 read_limit=None, write_limit=None):
        """Create the instance."""
        self._readLimit = None  # max bytes we should read per second
        self._writeLimit = None  # max bytes we should write per second
        self._throttling_reads = False
        self._throttling_writes = False
        self._set_read_limit(read_limit)
        self._set_write_limit(write_limit)
        self.throttling_enabled = throttling_enabled
        self.readThisSecond = 0
        self.writtenThisSecond = 0
        self.unthrottleReadsID = None
        self.resetReadThisSecondID = None
        self.unthrottleWritesID = None
        self.resetWriteThisSecondID = None
        self.stopped = True
        if self.throttling_enabled:
            self.enable_throttling()
        else:
            self.disable_throttling()

    def valid_limit(self, limit):
        """Check if limit is a valid valid."""
        return limit is None or limit > 0

    def _set_write_limit(self, limit):
        """Set writeLimit value.

        Raise a ValueError if the value ins't valid.
        """
        if not self.valid_limit(limit):
            raise ValueError('Write limit must be greater than 0.')
        self._writeLimit = limit

    def _set_read_limit(self, limit):
        """Set readLimit value.

        Raise a ValueError if the value ins't valid.
        """
        if not self.valid_limit(limit):
            raise ValueError('Read limit must be greater than 0.')
        self._readLimit = limit
    # it's a property, pylint: disable=W0212
    readLimit = property(lambda self: self._readLimit, _set_read_limit)
    writeLimit = property(lambda self: self._writeLimit, _set_write_limit)
    # pylint: enable=W0212

    def callLater(self, period, func, *args, **kwargs):
        """Wrapper around L{reactor.callLater} for test purpose."""
        return reactor.callLater(period, func, *args, **kwargs)

    def maybeCallLater(self, call_id, period, func):
        """Maybe run callLater(period, func).

        Only if we don't have a DelayedCall with the
        specified id already running.
        """
        delayed_call = getattr(self, call_id)
        # check if we already have a DelayedCall running
        if delayed_call is None or (not delayed_call.active() \
           and delayed_call.cancelled):
            return self.callLater(period, func)
        return delayed_call

    def registerWritten(self, length):
        """Called by protocol to tell us more bytes were written."""
        if self.throttling_enabled:
            self.writtenThisSecond += length
            self.checkWriteBandwidth()

    def registerRead(self, length):
        """Called by protocol to tell us more bytes were read."""
        if self.throttling_enabled:
            self.readThisSecond += length
            self.checkReadBandwidth()

    def _get_throttle_time(self, data_bytes, limit):
        """Calculate the throttle_time for data_bytes and limit."""
        return (float(data_bytes) / limit) - 1.0

    def checkReadBandwidth(self):
        """Check if we've passed bandwidth limits."""
        limit_check = self.valid_limit(self.readLimit) and \
                self.readLimit is not None and \
                self.readThisSecond >= self.readLimit
        should_check = self.throttling_enabled and limit_check and \
                self.unthrottleReadsID is None
        if should_check:
            self.throttleReads()
            throttle_time = self._get_throttle_time(self.readThisSecond,
                                                    self.readLimit)
            log_debug("pause reads for: %s", str(throttle_time))
            self.unthrottleReadsID = self.maybeCallLater(
                'unthrottleReadsID', throttle_time, self.unthrottleReads)

    def checkWriteBandwidth(self):
        """Check if we've passed bandwidth limits."""
        limit_check = self.valid_limit(self.writeLimit) and \
                self.writeLimit is not None and \
                self.writtenThisSecond >= self.writeLimit
        should_check = self.throttling_enabled and limit_check and \
                self.unthrottleWritesID is None
        if should_check:
            self.throttleWrites()
            throttle_time = self._get_throttle_time(self.writtenThisSecond,
                                                self.writeLimit)
            log_debug("pause writes for: %s", str(throttle_time))
            self.unthrottleWritesID = self.maybeCallLater(
                'unthrottleWritesID', throttle_time, self.unthrottleWrites)

    def _resetReadThisSecond(self):
        """Reset the counter named with 'name' every 1 second."""
        # check the bandwidth limits
        self.readThisSecond = 0
        self.resetReadThisSecondID = self.callLater(1,
                                                   self._resetReadThisSecond)

    def _resetWrittenThisSecond(self):
        """Reset the counter named with 'name' every 1 second."""
        self.writtenThisSecond = 0
        self.resetWriteThisSecondID = self.callLater(
            1, self._resetWrittenThisSecond)

    def throttleReads(self):
        """Throttle reads on all protocols."""
        if self.client is not None:
            self._throttling_reads = True
            self.client.throttleReads()

    def unthrottleReads(self):
        """Stop throttling reads on all protocols."""
        self.unthrottleReadsID = None
        if self.client is not None:
            self._throttling_reads = False
            self.client.unthrottleReads()

    def throttleWrites(self):
        """Throttle writes on all protocols."""
        if self.client is not None:
            self._throttling_writes = True
            self.client.throttleWrites()

    def unthrottleWrites(self):
        """Stop throttling writes on all protocols."""
        self.unthrottleWritesID = None
        if self.client is not None:
            self._throttling_writes = False
            self.client.unthrottleWrites()

    def buildProtocol(self, addr):
        """Build the protocol and start the counters reset loops."""
        if self.throttling_enabled:
            self.enable_throttling()
        self.stopped = False
        return StorageClientFactory.buildProtocol(self, addr)

    def unregisterProtocol(self, protocol):
        """Stop all DelayedCall we have around."""
        for delayed in [self.unthrottleReadsID, self.resetReadThisSecondID,
                        self.unthrottleWritesID, self.resetWriteThisSecondID]:
            self._cancel_delayed_call(delayed)

    def _cancel_delayed_call(self, delayed):
        """Safely cancel a DelayedCall."""
        if delayed is not None and not delayed.cancelled \
           and delayed.active():
            try:
                delayed.cancel()
            except defer.AlreadyCalledError:
                # ignore AlreadyCalledError
                pass

    def enable_throttling(self):
        """Enable throttling and start the counter reset loops."""
        # check if we need to start the reset loops
        if self.resetReadThisSecondID is None and \
           self.valid_limit(self.readLimit):
            self._resetReadThisSecond()
        if self.resetWriteThisSecondID is None and \
           self.valid_limit(self.writeLimit):
            self._resetWrittenThisSecond()
        self.throttling_enabled = True

    def disable_throttling(self):
        """Disable throttling and cancel the counter reset loops."""
        # unthrottle if there is an active unthrottle*ID
        self._cancel_delayed_call(self.unthrottleReadsID)
        self._cancel_delayed_call(self.unthrottleWritesID)
        # Stop the reset loops
        self._cancel_delayed_call(self.resetReadThisSecondID)
        self._cancel_delayed_call(self.resetWriteThisSecondID)
        # unthrottle read/writes
        if self._throttling_reads:
            self.unthrottleReads()
        if self._throttling_writes:
            self.unthrottleWrites()
        self.throttling_enabled = False


if __name__ == "__main__":
    # these 3 lines show the different ways of connecting a client to the
    # server

    # using tcp
    reactor.connectTCP('localhost', 20100, StorageClientFactory())

    # using ssl
    #reactor.connectSSL('localhost', 20101, StorageClientFactory(),
    #           ssl.ClientContextFactory())

    # using ssl over a proxy
    #from ubuntuone.storageprotocol import proxy_tunnel
    #proxy_tunnel.connectHTTPS('localhost', 3128,
    #        'localhost', 20101, StorageClientFactory(),
    #        user="test", passwd="test")

    reactor.run()
