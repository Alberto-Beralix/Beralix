#!/usr/bin/python

import re
import sys
import fileinput

'''
This updates lines in config files matching the following syntax.  It
preserves the rest of the file contents unchanged.

PARAMETER_FIRST="some string values"
PARAMETER_SECOND=""

# This is a comment
PARAMETER_THIRD="0x01234567,0xfefefefe,0x89abcdef,0xefefefef"
PARAMETER_FOURTH=false
PARAMETER_FIFTH=42
'''

import os
import shutil

def safe_backup(path, keep_original=True):
    """
    Rename a file or directory safely without overwriting an existing
    backup of the same name.
    """
    count = -1
    new_path = None
    while True:
        if os.path.exists(path):
            if count == -1:
                new_path = "%s.bak" % (path)
            else:
                new_path = "%s.bak.%s" % (path, count)
            if os.path.exists(new_path):
                count += 1
                continue
            else:
                if keep_original:
                    if os.path.isfile(path):
                        shutil.copy(path, new_path)
                    elif os.path.isdir(path):
                        shutil.copytree(path, new_path)
                    else:
                        shutil.move(path, new_path)
                    break
        else:
            break
    return new_path

def config_dict(filename, delim='='):
    re_param = re.compile("^\s*(\w+)\s*"+delim+"\s*(.*)")
    data = {}
    for line in fileinput.input(filename):
        m = re_param.match(line)
        if m:
            data[m.group(1)] = m.group(2)
    return data

# TODO: Perhaps the filename should be a fileio too?
def config_update(filename, override_params=None, merge_params=None, delim='=', fileio=sys.stdout):
    '''filename is the input file.  fileio is the output stream'''
    keys = []
    if override_params:
        keys = override_params.keys()
    if merge_params:
        keys.extend(merge_params.keys())
    keys = list(set(keys))
    keys.sort()

    for line in fileinput.input(filename):
        new_line = line

        if merge_params:
            for key in merge_params:
                p = re.compile("^\s*"+key+"\s*"+delim+"\s*\"(.*)\"")
                m = p.match(line)
                if m:
                    value = merge_params[key].replace('"', '')
                    if len(value)>0:
                        new_line = "%s%s\"%s %s\"\n" %(key, delim, m.group(1), value)
                    keys.remove(key)

        if override_params:
            for key in override_params.keys():
                p = re.compile("^\s*"+key+"\s*"+delim)
                if p.match(line):
                    new_line = "%s%s%s\n" %(key, delim, override_params[key])
                    keys.remove(key)

        fileio.write(new_line)

    # Handle case of parameters that weren't already present in the file
    for key in keys:
        if override_params and key in override_params:
            fileio.write("%s%s%s\n" %(key, delim, override_params[key]))
        elif merge_params and key in merge_params:
            fileio.write("%s%s%s\n" %(key, delim, merge_params[key]))

if __name__ == '__main__':
    filename = '/etc/default/grub'
    override_params = {
        'FOO':                        '"xyz"',
        'BOTH':                       '"correct"',
        'GRUB_DEFAULT':               2,
        'GRUB_CMDLINE_LINUX':         '"foo=bar"',
        'GRUB_HIDDEN_TIMEOUT_QUIET':  False,
        }
    merge_params = {
        'GRUB_CMDLINE_LINUX_DEFAULT': '"vesafb.invalid=1"',
        'BAR':                        'f(1&&2*$i^2) # \o/',
        'BOTH':                        '"incorrect"',
        }
    
    config_update(filename, override_params, None)
    config_update(filename, None,            merge_params)
    config_update(filename, override_params, merge_params)
    
    # TODO: Test for if drm.debug=0x4 and we want to set it to 0xe
