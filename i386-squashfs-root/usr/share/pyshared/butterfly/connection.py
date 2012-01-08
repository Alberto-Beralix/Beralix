# telepathy-butterfly - an MSN connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2007 Johann Prieur <johann.prieur@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import weakref
import logging

import dbus
import telepathy
import papyon
import papyon.event

from butterfly.presence import ButterflyPresence
from butterfly.aliasing import ButterflyAliasing
from butterfly.avatars import ButterflyAvatars
from butterfly.capabilities import ButterflyCapabilities
from butterfly.handle import ButterflyHandleFactory, network_to_extension
from butterfly.contacts import ButterflyContacts
from butterfly.channel_manager import ButterflyChannelManager
from butterfly.mail_notification import ButterflyMailNotification

__all__ = ['ButterflyConnection']

logger = logging.getLogger('Butterfly.Connection')


class ButterflyConnection(telepathy.server.Connection,
        telepathy.server.ConnectionInterfaceRequests,
        ButterflyPresence,
        ButterflyAliasing,
        ButterflyAvatars,
        ButterflyCapabilities,
        ButterflyContacts,
        ButterflyMailNotification,
        papyon.event.ClientEventInterface,
        papyon.event.InviteEventInterface,
        papyon.event.OfflineMessagesEventInterface):


    def __init__(self, protocol, manager, parameters):
        protocol.check_parameters(parameters)

        try:
            account = unicode(parameters['account'])
            self._server = (parameters['server'].encode('utf-8'), parameters['port'])

            self._proxies = {}
            self._direct_proxies = [None]
            self._http_proxies = [None]
            self._default_http_proxy = None
            self._default_https_proxy = None

            # Build the proxies configurations
            self._try_http = parameters['http-method']
            proxy = build_proxy_infos(parameters, 'http')
            if proxy is not None:
                self._http_proxies = [proxy]
                self._default_http_proxy = proxy
            proxy = build_proxy_infos(parameters, 'https')
            if proxy is not None:
                self._default_https_proxy = proxy

            self._fill_suggested_proxies()
            self._use_next_proxy()

            self._manager = weakref.proxy(manager)
            self._new_client(use_http=self._try_http)
            self._account = (parameters['account'].encode('utf-8'),
                    parameters['password'].encode('utf-8'))
            self._channel_manager = ButterflyChannelManager(self, protocol)

            # Call parent initializers
            telepathy.server.Connection.__init__(self, 'msn', account,
                    'butterfly', protocol)
            telepathy.server.ConnectionInterfaceRequests.__init__(self)
            ButterflyPresence.__init__(self)
            ButterflyAliasing.__init__(self)
            ButterflyAvatars.__init__(self)
            ButterflyCapabilities.__init__(self)
            ButterflyContacts.__init__(self)
            ButterflyMailNotification.__init__(self)

            self_handle = self.create_handle(telepathy.HANDLE_TYPE_CONTACT,
                    self._account[0])
            self.set_self_handle(self_handle)

            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NONE_SPECIFIED
            self._initial_presence = papyon.Presence.INVISIBLE
            self._initial_personal_message = None

            logger.info("Connection to the account %s created" % account)
        except Exception, e:
            import traceback
            logger.exception("Failed to create Connection")
            raise

    def _new_client(self, use_http=False):
        if hasattr(self, '_msn_client') and self._msn_client:
            if self._msn_client.state != papyon.event.ClientState.CLOSED:
                self._msn_client.logout()
            self._msn_client._events_handlers.remove(self)

        if use_http:
            self._tried_http = True
            self._msn_client = papyon.Client(self._server, self._proxies,
                papyon.transport.HTTPPollConnection, 18)
        else:
            self._tried_http = False
            self._msn_client = papyon.Client(self._server, self._proxies,
                version=18)

        papyon.event.ClientEventInterface.__init__(self, self._msn_client)
        papyon.event.InviteEventInterface.__init__(self, self._msn_client)
        papyon.event.OfflineMessagesEventInterface.__init__(self, self._msn_client)

    def _fill_suggested_proxies(self):
        try:
            import libproxy
        except ImportError:
            logger.warning("Please install libproxy python bindings to enable proxy support.")
            return

        factory = libproxy.ProxyFactory()

        # Get DirectConnection proxies
        proxies = factory.getProxies('none://messenger.msn.com:1863')
        proxies = [self._parse_proxy(p) for p in proxies]
        self._direct_proxies = proxies

        # Get HTTP proxies (if not already set by a parameter)
        if not self._default_http_proxy:
            proxies = factory.getProxies('http://gateway.messenger.msn.com/')
            proxies = [self._parse_proxy(p) for p in proxies]
            self._http_proxies = proxies
            if len(proxies) > 0:
                self._default_http_proxy = proxies[0]

        # Get HTTPS proxies (if not already set by a parameter)
        if not self._default_https_proxy:
            proxies = factory.getProxies('https://rsi.hotmail.com/rsi/rsi.asmx')
            proxies = [self._parse_proxy(p) for p in proxies]
            if len(proxies) > 0:
                self._default_https_proxy = proxies[0]

    def _use_next_proxy(self):
        if not self._try_http and self._direct_proxies:
            direct_proxy = self._direct_proxies.pop(0)
            http_proxy   = self._default_http_proxy
            https_proxy  = self._default_https_proxy
        elif self._http_proxies:
            self._try_http = True
            direct_proxy = None
            http_proxy   = self._http_proxies.pop(0)
            https_proxy  = self._default_https_proxy
        else:
            return False

        self._proxies['direct'] = direct_proxy
        self._proxies['http']   = http_proxy
        self._proxies['https']  = https_proxy

        # Clean proxies (remove None)
        for conn_type in ('direct', 'http', 'https'):
            if conn_type not in self._proxies:
                pass
            proxy = self._proxies[conn_type]
            if proxy is None:
                del self._proxies[conn_type]
            logger.info('Using %s proxy: %s' % (conn_type, proxy))

        return True

    def _parse_proxy(self, proxy):
        # libproxy documentation states:
        #
        #  * The format of the returned proxy strings are as follows:
        #  *   - http://[username:password@]proxy:port
        #  *   - socks://[username:password@]proxy:port
        #  *   - direct://
        #  etc.

        if proxy is None or proxy == "direct://":
            return None

        index = proxy.find("://")
        ptype = proxy[0:index]
        proxy = proxy[index + 3:]

        # Get username and password out.
        if '@' in proxy:
            auth, proxy = proxy.split('@')
            user, password = auth.split(':')
        else:
            user = password = None

        if ':' in proxy:
            server, port = proxy.split(':')

        return papyon.ProxyInfos(host=server, port=int(port), type=ptype,
                user=user, password=password)

    @property
    def manager(self):
        return self._manager

    @property
    def msn_client(self):
        return self._msn_client

    def handle(self, handle_type, handle_id):
        self.check_handle(handle_type, handle_id)
        return self._handles[handle_type, handle_id]

    def create_handle(self, handle_type, handle_name, **kwargs):
        """Create new handle with given type and name."""
        handle_id = self.get_handle_id()
        handle = ButterflyHandleFactory(self, handle_type, handle_id,
                handle_name, **kwargs)
        if handle is None:
            raise telepathy.NotAvailable('Handle type unsupported %d' % handle_type)
        logger.info("New Handle %s" % unicode(handle))
        self._handles[handle_type, handle_id] = handle
        return handle

    def is_valid_handle_name(self, handle_type, handle_name):
        """Make sure the name is valid for this type of handle."""
        if handle_type == telepathy.HANDLE_TYPE_CONTACT:
            if '@' not in handle_name:
                return False
            if '.' not in handle_name.split("@", 1)[1]:
                return False
        return True

    def normalize_handle_name(self, handle_type, handle_name):
        """Normalize handle name so the name is consistent everywhere."""
        if not self.is_valid_handle_name(handle_type, handle_name):
            raise telepathy.InvalidHandle('TargetID %s not valid for type %d' %
                (name, handle_type))
        if handle_type == telepathy.HANDLE_TYPE_CONTACT:
            return handle_name.lower().strip()
        return handle_name

    def ensure_contact_handle(self, contact):
        """Build handle name for contact and ensure handle."""
        if contact is None:
            return telepathy.NoneHandler()
        handle_type = telepathy.HANDLE_TYPE_CONTACT
        extension = network_to_extension.get(contact.network_id, "")
        handle_name = contact.account.lower() + extension
        return self.ensure_handle(handle_type, handle_name, contact=contact)

    def Connect(self):
        if self._status == telepathy.CONNECTION_STATUS_DISCONNECTED:
            logger.info("Connecting")
            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NONE_SPECIFIED
            self._msn_client.login(*self._account)

    def Disconnect(self):
        logger.info("Disconnecting")
        self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_REQUESTED
        if self._msn_client.state != papyon.event.ClientState.CLOSED:
            self._msn_client.logout()
        else:
            self._disconnected()

    def _disconnected(self):
        logger.info("Disconnected")
        self.StatusChanged(telepathy.CONNECTION_STATUS_DISCONNECTED,
                self.__disconnect_reason)
        self._channel_manager.close()
        self._manager.disconnected(self)

    def GetInterfaces(self):
        # The self._interfaces set is only ever touched in ButterflyConnection.__init__,
        # where connection interfaces are added.

        # The mail notification interface is added then too, but also removed in its
        # ButterflyMailNotification.__init__ because it might not actually be available.
        # It is added before the connection status turns to connected, if available.

        # The spec denotes that this method can return a subset of the actually
        # available interfaces before connected. As the only possible change will
        # be adding the mail notification interface before connecting, this is fine.

        return self._interfaces

    def _generate_props(self, channel_type, handle, suppress_handler, initiator_handle=None):
        props = {
            telepathy.CHANNEL_INTERFACE + '.ChannelType': channel_type,
            telepathy.CHANNEL_INTERFACE + '.TargetHandle': handle.get_id(),
            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': handle.get_type(),
            telepathy.CHANNEL_INTERFACE + '.Requested': suppress_handler
            }

        if initiator_handle is not None:
            if initiator_handle.get_type() is not telepathy.HANDLE_TYPE_NONE:
                props[telepathy.CHANNEL_INTERFACE + '.InitiatorHandle'] = \
                        initiator_handle.get_id()

        return props


    @dbus.service.method(telepathy.CONNECTION, in_signature='suub',
        out_signature='o', async_callbacks=('_success', '_error'))
    def RequestChannel(self, type, handle_type, handle_id, suppress_handler,
            _success, _error):
        self.check_connected()
        channel_manager = self._channel_manager

        if handle_id == telepathy.HANDLE_TYPE_NONE:
            handle = telepathy.server.handle.NoneHandle()
        else:
            handle = self.handle(handle_type, handle_id)
        props = self._generate_props(type, handle, suppress_handler)
        self._validate_handle(props)

        channel = channel_manager.channel_for_props(props, signal=False)

        _success(channel._object_path)
        self.signal_new_channels([channel])

    # papyon.event.ClientEventInterface
    def on_client_state_changed(self, state):
        if state == papyon.event.ClientState.CONNECTING:
            self.StatusChanged(telepathy.CONNECTION_STATUS_CONNECTING,
                    telepathy.CONNECTION_STATUS_REASON_REQUESTED)
        elif state == papyon.event.ClientState.SYNCHRONIZED:
            handle = self.ensure_handle(telepathy.HANDLE_TYPE_LIST, 'subscribe')
            props = self._generate_props(telepathy.CHANNEL_TYPE_CONTACT_LIST,
                handle, False)
            self._channel_manager.channel_for_props(props, signal=True)

            handle = self.ensure_handle(telepathy.HANDLE_TYPE_LIST, 'publish')
            props = self._generate_props(telepathy.CHANNEL_TYPE_CONTACT_LIST,
                handle, False)
            self._channel_manager.channel_for_props(props, signal=True)

            #handle = self.ensure_handle(telepathy.HANDLE_TYPE_LIST, 'hide')
            #props = self._generate_props(telepathy.CHANNEL_TYPE_CONTACT_LIST,
            #    handle, False)
            #self._channel_manager.channel_for_props(props, signal=True)

            #handle = self.ensure_handle(telepathy.HANDLE_TYPE_LIST, 'allow')
            #props = self._generate_propstelepathy.CHANNEL_TYPE_CONTACT_LIST,
            #    handle, False)
            #self._channel_manager.channel_for_props(props, signal=True)

            #handle = self.ensure_handle(telepathy.HANDLE_TYPE_LIST, 'deny')
            #props = self._generate_props(telepathy.CHANNEL_TYPE_CONTACT_LIST,
            #    handle, False)
            #self._channel_manager.channel_for_props(props, signal=True)

            for group in self.msn_client.address_book.groups:
                handle = self.ensure_handle(telepathy.HANDLE_TYPE_GROUP,
                        group.name.decode("utf-8"))
                props = self._generate_props(
                    telepathy.CHANNEL_TYPE_CONTACT_LIST, handle, False)
                self._channel_manager.channel_for_props(props, signal=True)
        elif state == papyon.event.ClientState.OPEN:
            self._populate_capabilities()
            if self._client.profile.profile['EmailEnabled'] == '1':
                self.enable_mail_notification_interface()
            self.StatusChanged(telepathy.CONNECTION_STATUS_CONNECTED,
                    telepathy.CONNECTION_STATUS_REASON_REQUESTED)
            presence = self._initial_presence
            message = self._initial_personal_message
            if presence is not None:
                self._client.profile.presence = presence
            if message is not None:
                self._client.profile.personal_message = message
            self._client.profile.end_point_name = "PAPYON"

            if (presence is not None) or (message is not None):
                self._presence_changed(self._self_handle,
                        self._client.profile.presence,
                        self._client.profile.personal_message)
        elif state == papyon.event.ClientState.CLOSED:
            self._disconnected()

    # papyon.event.ClientEventInterface
    def on_client_error(self, type, error):
        if type == papyon.event.ClientErrorType.NETWORK:
            # Only move onto the next proxy if we've not already tried
            # HTTP and we're in the connecting state. We don't want to
            # connect to HTTP if we're already connected and we lose
            # connectivity (see fd.o#26147).
            if self._status == telepathy.CONNECTION_STATUS_CONNECTING and \
                    self._use_next_proxy():
                logger.info("Failed to connect, trying HTTP "
                            "(possibly again with another proxy)")
                self._new_client(use_http=self._try_http)
                self._msn_client.login(*self._account)
            else:
                self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NETWORK_ERROR
        elif type == papyon.event.ClientErrorType.AUTHENTICATION:
            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_AUTHENTICATION_FAILED
        elif type == papyon.event.ClientErrorType.PROTOCOL and \
             error == papyon.event.ProtocolError.OTHER_CLIENT:
            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NAME_IN_USE
        else:
            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NONE_SPECIFIED

    # papyon.event.InviteEventInterface
    def on_invite_conversation(self, conversation):
        logger.debug("Conversation invite")

        if len(conversation.participants) == 1:
            p = list(conversation.participants)[0]
            handle = self.ensure_contact_handle(p)
        else:
            handle = telepathy.server.handle.NoneHandle()

        props = self._generate_props(telepathy.CHANNEL_TYPE_TEXT,
            handle, False, initiator_handle=handle)

        channel = self._channel_manager.channel_for_props(props,
            signal=True, conversation=conversation)

        if channel._conversation is not conversation:
            # If we get an existing channel, attach the conversation object to it
            channel.attach_conversation(conversation)

    # papyon.event.InviteEventInterface
    def on_invite_conference(self, call):
        logger.debug("Call invite")

        handle = self.ensure_contact_handle(call.peer)
        props = self._generate_props(telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
                handle, False, initiator_handle=handle)
        channel = self._channel_manager.channel_for_props(props,
                signal=True, call=call)

    # papyon.event.InviteEventInterface
    def on_invite_webcam(self, session, producer):
        direction = (producer and "send") or "receive"
        logger.debug("Invitation to %s webcam" % direction)

        handle = self.ensure_contact_handle(session.peer)
        props = self._generate_props(telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
                handle, False, initiator_handle=handle)
        channel = self._channel_manager.channel_for_props(props, signal=True,
                call=session)

    # papyon.event.OfflineMessagesEventInterface
    def on_oim_messages_received(self, messages):
        # We got notified we received some offlines messages so we
        #are going to fetch them
        self.msn_client.oim_box.fetch_messages(messages)

    # papyon.event.OfflineMessagesEventInterface
    def on_oim_messages_fetched(self, messages):
        for message in messages:
            if message.sender is None:
                continue
            # Request butterfly text channel (creation, what happen when it exist)
            sender = message.sender
            logger.info('received offline message from %s : %s' % (sender.account, message.text))

            handle = self.ensure_contact_handle(sender)
            props = self._generate_props(telepathy.CHANNEL_TYPE_TEXT,
                handle, False)
            channel = self._channel_manager.channel_for_props(props,
                signal=True)
            # Notify it of the message
            channel.offline_message_received(message)

    # papyon.event.InviteEventInterface
    def on_invite_file_transfer(self, session):
        logger.debug("File transfer invite")

        handle = self.ensure_contact_handle(session.peer)
        props = self._generate_props(telepathy.CHANNEL_TYPE_FILE_TRANSFER,
                handle, False)
        channel = self._channel_manager.create_channel_for_props(props,
                signal=True, session=session)


def build_proxy_infos(parameters, proxy_type='http'):
    server_key = proxy_type + '-proxy-server'
    port_key = proxy_type + '-proxy-port'
    username_key = proxy_type + '-proxy-username'
    password_key = proxy_type + '-proxy-password'
    if server_key in parameters and port_key in parameters:
        return papyon.ProxyInfos(host = parameters[server_key],
                port = parameters[port_key],
                type = proxy_type,
                user = parameters.get(username_key, None),
                password = parameters.get(password_key, None) )
    else:
        return None

