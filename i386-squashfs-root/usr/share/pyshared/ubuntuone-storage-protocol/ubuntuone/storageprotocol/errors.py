# -*- coding: utf-8 -*-
#
# Author: Natalia B. Bidart <natalia.bidart@canonical.com>
#
# Copyright 2010 Canonical Ltd.
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
"""The errors abstraction."""

import uuid

from ubuntuone.storageprotocol import protocol_pb2


class StorageProtocolError(Exception):
    """Base class for all client/server exceptions."""


class StorageProtocolErrorSizeTooBig(StorageProtocolError):
    """The size we received was too big."""


class StorageProtocolProtocolError(StorageProtocolError):
    """A protocol error on the storage protocol."""


class StorageRequestError(StorageProtocolError):
    """An exception that keeps the request that generated it around."""

    def __init__(self, request, message):
        """Create a StorageRequestError.

        @param request: the request that generated this error.
        @param message: the message received that generated the error.
        """
        error_name = protocol_pb2.Error.DESCRIPTOR \
                 .enum_types_by_name['ErrorType'] \
                 .values_by_number[message.error.type].name
        super(StorageRequestError, self).__init__(error_name)
        #: the request that generated the error
        self.request = request
        #: the message received that generated the error
        self.error_message = message


class RequestCancelledError(StorageProtocolError):
    """The request was cancelled."""


# Request specific errors


class UnsupportedVersionError(StorageRequestError):
    """The version is not supported."""


class AuthenticationFailedError(StorageRequestError):
    """The authencation failed."""


class InternalError(StorageRequestError):
    """There was an internal error on the other side."""


class AuthenticationRequiredError(StorageRequestError):
    """The authentication is required and hasn't been established yet."""


class NoPermissionError(StorageRequestError):
    """Current permissions are not the required ones."""


class AlreadyExistsError(StorageRequestError):
    """The node already exists."""


class DoesNotExistError(StorageRequestError):
    """The node does not exists."""


class NotADirectoryError(StorageRequestError):
    """The node is not a directory."""


class NotEmptyError(StorageRequestError):
    """The node is not empty."""


class NotAvailableError(StorageRequestError):
    """The node is not available."""


class UploadInProgressError(StorageRequestError):
    """There is already an upload in progress."""


class UploadCorruptError(StorageRequestError):
    """The upload is corrupted."""


class UploadCanceledError(StorageRequestError):
    """There upload was canceled."""


class ConflictError(StorageRequestError):
    """The was a conflict."""


class TryAgainError(StorageRequestError):
    """Server answered to try again."""


class ProtocolError(StorageRequestError):
    """There was a protocol error."""


class CannotProduceDelta(StorageRequestError):
    """Server can't build this delta."""


class QuotaExceededError(StorageRequestError):
    """The quota was exceeded."""

    def __init__(self, request, message):
        """Create the exception and store important attributes.

        share_id will be None if we got the exception without free space info.
        """
        # to avoid circular dependencies
        from ubuntuone.storageprotocol.request import ROOT
        super(QuotaExceededError, self).__init__(request, message)
        self.free_bytes = message.free_space_info.free_bytes
        if message.free_space_info.share_id:
            self.share_id = uuid.UUID(message.free_space_info.share_id)
        else:
            self.share_id = ROOT


class InvalidFilenameError(StorageRequestError):
    """The filename is invalid."""


_error_mapping = {
      protocol_pb2.Error.UNSUPPORTED_VERSION: UnsupportedVersionError,
      protocol_pb2.Error.AUTHENTICATION_FAILED: AuthenticationFailedError,
      protocol_pb2.Error.INTERNAL_ERROR: InternalError,
      protocol_pb2.Error.AUTHENTICATION_REQUIRED: AuthenticationRequiredError,
      protocol_pb2.Error.NO_PERMISSION: NoPermissionError,
      protocol_pb2.Error.ALREADY_EXISTS: AlreadyExistsError,
      protocol_pb2.Error.DOES_NOT_EXIST: DoesNotExistError,
      protocol_pb2.Error.NOT_A_DIRECTORY: NotADirectoryError,
      protocol_pb2.Error.NOT_EMPTY: NotEmptyError,
      protocol_pb2.Error.NOT_AVAILABLE: NotAvailableError,
      protocol_pb2.Error.UPLOAD_IN_PROGRESS: UploadInProgressError,
      protocol_pb2.Error.UPLOAD_CORRUPT: UploadCorruptError,
      protocol_pb2.Error.UPLOAD_CANCELED: UploadCanceledError,
      protocol_pb2.Error.CONFLICT: ConflictError,
      protocol_pb2.Error.TRY_AGAIN: TryAgainError,
      protocol_pb2.Error.PROTOCOL_ERROR: ProtocolError,
      protocol_pb2.Error.QUOTA_EXCEEDED: QuotaExceededError,
      protocol_pb2.Error.INVALID_FILENAME: InvalidFilenameError,
      protocol_pb2.Error.CANNOT_PRODUCE_DELTA: CannotProduceDelta,
}


def error_to_exception(error_code):
    """Map protocol errors to specific exceptions."""
    return _error_mapping[error_code]
