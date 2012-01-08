# ubuntuone.platform.linux.vm_helper- vm helpers for linux.
#
# Authors: Guillermo Gonzalez <guillermo.gonzalez@canonical.com>
#          Natalia B. Bidart <natalia.bidart@canonical.com>
#
# Copyright 2010-11 Canonical Ltd.
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

"""Volume manager helpers."""

import os


from ubuntuone.platform import (
    is_link,
    make_link,
    path_exists,
    read_link,
    remove_link,
)


def get_share_dir_name(share):
    """Builds the directory name of a share using the share information.

    This method is not platform dependent, so do not override in platform.

    """
    if hasattr(share, 'volume_id'):
        share_id = share.volume_id
    elif hasattr(share, 'share_id'):
        share_id = share.share_id
    else:
        share_id = share.id

    if hasattr(share, 'name'):
        share_name = share.name
    else:
        share_name = share.share_name

    if hasattr(share, 'other_visible_name'):
        visible_name = share.other_visible_name
    else:
        visible_name = share.from_visible_name

    if visible_name:
        dir_name = u'%s (%s, %s)' % (share_name, visible_name, share_id)
    else:
        dir_name = u'%s (%s)' % (share_name, share_id)

    # Unicode boundary! the name is Unicode in protocol and server,
    # but here we use bytes for paths
    dir_name = dir_name.encode("utf8")

    return dir_name


def create_shares_link(source, dest):
    """Create the shares symlink."""
    result = False
    if not path_exists(dest):
        # remove the symlink if it's broken
        if is_link(dest) and read_link(dest) != source:
            remove_link(dest)

        if not is_link(dest):
            # only create the link if it does not exist
            make_link(source, dest)
            result = True

    return result


def get_udf_suggested_path(path):
    """Return the suggested_path, name for 'path'.

    'path' must be a path inside the user home directory, if it's not
    a ValueError is raised.
    """
    if not path:
        raise ValueError("no path specified")

    assert isinstance(path, str)

    path = path.decode('utf8')

    user_home = os.path.expanduser(u'~')
    start_list = os.path.abspath(user_home).split(os.path.sep)
    path_list = os.path.abspath(path).split(os.path.sep)

    # Work out how much of the filepath is shared by user_home and path.
    common_prefix = os.path.commonprefix([start_list, path_list])
    if os.path.sep.join(common_prefix) != user_home:
        raise ValueError("path isn't inside user home: %r" % path)

    # suggested_path is always unicode, because the suggested path is a
    # server-side metadata, and we will always use the unix path separator '/'

    suggested_path = path.replace(user_home, u'~')
    suggested_path = suggested_path.replace(os.path.sep, u'/')
    assert isinstance(suggested_path, unicode)
    return suggested_path


def get_udf_path(suggested_path):
    """Build the udf path using the suggested_path.

    'suggested_path' is a non-local path, with unix-like slashes since is send
    to and received from the server.

    """
    assert isinstance(suggested_path, unicode)
    # Unicode boundary! the suggested_path is Unicode in protocol and server,
    # but here we use bytes for paths
    path = suggested_path.replace(u'/', os.path.sep)
    return os.path.expanduser(path).encode("utf8")
