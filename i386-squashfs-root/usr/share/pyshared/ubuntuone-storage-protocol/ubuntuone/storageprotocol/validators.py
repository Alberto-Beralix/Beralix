"""
Message validation.
"""

import re
from uuid import UUID
from google.protobuf.message import Message as _PBMessage
from google.protobuf.internal.containers import BaseContainer as _PBContainer


def is_valid_node(node_id):
    """
    A node id is a hex UUID.
    """
    try:
        return str(UUID(node_id)) == node_id
    except StandardError:
        return False


def is_valid_crc32(crc32):
    """
    Valid CRC32s are nonnegative integers
    """
    return int(crc32) >= 0


def is_valid_share(share_id):
    """
    A share id is either the empty string, or a node id.
    """
    return share_id == '' or is_valid_node(share_id)


def is_valid_sha1(sha1):
    """Validate 'sha1'.

    A valid sha1 hash reads "sha1:", and then a 40 hex characters.

    """
    return bool(re.match(r'sha1:[0-9a-z]{40}$', sha1))


def is_valid_hash(a_hash):
    """Validate 'a_hash'.

    A valid hash is either the empty string, request.UNKNOWN_HASH, or one of
    the other known hash types.

    """
    # circular import
    from ubuntuone.storageprotocol import request
    is_valid = a_hash == '' or a_hash == request.UNKNOWN_HASH or \
               is_valid_sha1(a_hash)
    return is_valid


def validate_message(message):
    """
    Recursively validate a message's fields
    """
    # we will import ourselves
    # pylint: disable=W0406

    is_invalid = []
    from ubuntuone.storageprotocol import validators  # this is us!
    for descriptor, submsg in message.ListFields():
        if isinstance(submsg, _PBContainer):
            # containers are iterables that have messages in them
            for i in submsg:
                is_invalid.extend(validate_message(i))
        elif isinstance(submsg, _PBMessage):
            # a plain sub-message
            is_invalid.extend(validate_message(submsg))
        else:
            # we got down to the actual fields! yay
            validator = getattr(validators,
                                "is_valid_" + descriptor.name, None)
            if validator is not None:
                if not validator(submsg):
                    is_invalid.append("Invalid %s: %r"
                                      % (descriptor.name, submsg))
    return is_invalid


# these are valid, pylint: disable=C0103
is_valid_parent_node = is_valid_node
is_valid_new_parent_node = is_valid_node
is_valid_subtree = is_valid_node
is_valid_share_id = is_valid_share
# pylint: enable=C0103
