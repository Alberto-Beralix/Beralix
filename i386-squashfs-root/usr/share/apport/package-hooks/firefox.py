'''firefox apport hook

/usr/share/apport/package-hooks/firefox.py

Copyright (c) 2007: Hilario J. Montoliu <hmontoliu@gmail.com>
          (c) 2011: Chris Coulson <chris.coulson@canonical.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.
'''

import os
import os.path
import sys
import fcntl
import subprocess
import struct
from subprocess import Popen
from ConfigParser import ConfigParser
import sqlite3
import tempfile
import re
import apport.packaging
from apport.hookutils import *

class PrefParseError(Exception):
    def __init__(self, msg):
        super(PrefParseError, self).__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg

class PluginRegParseError(Exception):
    def __init__(self, msg):
        super(PluginRegParseError, self).__init__(msg)
        self.msg = msg

    def __str__(self):
        return self.msg


class ExtensionTypeNotRecognised(Exception):
    def __init__(self, ext_type, ext_id):
        super(ExtensionTypeNotRecognised, self).__init__(ext_type, ext_id)
        self.ext_type = ext_type
        self.ext_id = ext_id

    def __str__(self):
        return "Extension type not recognised: %s (ID: %s)" % (self.ext_type, self.ext_id)


class VersionCompareFailed(Exception):
    def __init__(self, a, b, e):
        if a == None:
            a = ''
        if b == None:
            b = ''
        super(VersionCompareFailed, self).__init__(a, b, e)
        self.a = a
        self.b = b
        self.e = e

    def __str__(self):
        return "Failed to compare versions A = %s, B = %s (%s)" % (self.a, self.b, str(self.e))


def mkstemp_copy(path):
    '''Make a copy of a file to a temporary file, and return the path'''
    (outfd, outpath) = tempfile.mkstemp()
    outfile = os.fdopen(outfd, 'w')
    infile = open(path, 'r')

    total = 0
    while True:
        data = infile.read(4096)
        total += len(data)
        outfile.write(data)
        infile.seek(total)
        outfile.seek(total)
        if len(data) < 4096: break

    return outpath


class CompatINIParser(ConfigParser):
    def __init__(self, path):
        ConfigParser.__init__(self)
        self.read(os.path.join(path, "compatibility.ini"))

    @property
    def last_version(self):
        if not self.has_section("Compatibility") or not self.has_option("Compatibility", "LastVersion"):
            return None
        return re.sub(r'([^_]*)(.*)', r'\1', self.get("Compatibility", "LastVersion"))

    @property
    def last_buildid(self):
        if not self.has_section("Compatibility") or not self.has_option("Compatibility", "LastVersion"):
            return None
        return re.sub(r'([^_]*)_([^/]*)/(.*)', r'\2', self.get("Compatibility", "LastVersion"))


class AppINIParser(ConfigParser):
    def __init__(self, path):
        ConfigParser.__init__(self)
        self.read(os.path.join(path, "application.ini"))

    @property
    def buildid(self):
        if not self.has_section('App') or not self.has_option('App', 'BuildID'):
            return None
        return self.get('App', 'BuildID')

    @property
    def appid(self):
        if not self.has_section('App') or not self.has_option('App', 'ID'):
            return None
        return self.get('App', 'ID')


def compare_versions(a, b):
    '''Compare 2 version numbers, returns -1 for a<b, 0 for a=b and 1 for a>b
       This is basically just a python reimplementation of nsVersionComparator'''
    class VersionPart:
        def __init__(self):
            self.numA = 0
            self.strB = None
            self.numC = 0
            self.extraD = None

    def parse_version(part):
        res = VersionPart()
        if part == None or part == '':
            return (part, res)
        spl = part.split('.')

        if part == '*' and len(part) == 1:
            res.numA = sys.maxint
            res.strB = ""
        else:
            res.numA = int(re.sub(r'([0-9]*)(.*)', r'\1', spl[0]))
            res.strB = re.sub(r'([0-9]*)(.*)', r'\2', spl[0])

        if res.strB == '':
            res.strB = None

        if res.strB != None:
            if res.strB[0] == '+':
                res.numA += 1
                res.strB = "pre"
            else:
                tmp = res.strB
                res.strB = re.sub(r'([^0-9+-]*)([0-9]*)(.*)', r'\1', tmp)
                strC = re.sub(r'([^0-9+-]*)([0-9]*)(.*)', r'\2', tmp)
                if strC != '':
                    res.numC = int(strC)
                res.extraD = re.sub(r'([^0-9+-]*)([0-9]*)(.*)', r'\3', tmp)
                if res.extraD == '':
                    res.extraD = None

        return (re.sub(r'([^\.]*)\.*(.*)', r'\2', part), res)

    def strcmp(stra, strb):
        if stra == None and strb != None:
            return 1
        elif stra != None and strb == None:
            return -1
        if stra < strb:
            return -1
        elif stra > strb:
            return 1
        else:
            return 0

    def do_compare(apart, bpart):
        if apart.numA < bpart.numA:
            return -1
        elif apart.numA > bpart.numA:
            return 1

        res = strcmp(apart.strB, bpart.strB)
        if res != 0:
            return res

        if apart.numC < bpart.numC:
            return -1
        elif apart.numC > bpart.numC:
            return 1

        return strcmp(apart.extraD, bpart.extraD)

    try:
        saved_a = a
        saved_b = b
        while a or b:
            (a, va) = parse_version(a)
            (b, vb) = parse_version(b)

            res = do_compare(va, vb)
            if res != 0:
                break
    except Exception as e:
        raise VersionCompareFailed(saved_a, saved_b, e)

    return res


class Plugin:
    def __init__(self):
        self.lib = None
        self.path = None
        self.desc = None
        self.package = None

    def dump(self):
        if self.path.startswith(os.path.join(os.environ['HOME'], '.mozilla', 'firefox')):
            location = "app-profile"
        else:
            location = os.path.dirname(self.path)

        return "%s - Lib=%s, Location=%s%s" % (self.desc, self.lib, location, " (%s)" % self.package if self.package != None else "")

    @property
    def package(self):
        if self._package == None:
            self._package = apport.packaging.get_file_package(self.path)
        return self._package

class PluginRegistry:

    STATE_PENDING = 0
    STATE_START = 1
    STATE_PROCESSING_1 = 2
    STATE_PROCESSING_2 = 3
    STATE_PROCESSING_3 = 4
    STATE_FINISHED = 5

    def __init__(self, filename):
        self.plugins = {}
        self._state = PluginRegistry.STATE_PENDING
        self._count = 0
        self._current_plugin = None
        self.available = False
        try:
            fd = open(filename, 'r')
            skip = 0
            for line in fd.readlines():
                if skip == 0:
                    skip = self._parseline(line)
                    if skip == -1:
                        break
                else:
                    skip -= 1
            self.available = True
        except Exception as e:
            self.parse_error = str(e)

    def _parseline(self, line):
        line = line.strip()
        if line != '' and line[0] == '[' and self._state != PluginRegistry.STATE_START and self._state != PluginRegistry.STATE_PENDING:
            raise PluginRegParseError('Unexpected section header')

        if self._state == PluginRegistry.STATE_PENDING:
            if line == '[PLUGINS]':
                self._state += 1
            return 0
        elif self._state == PluginRegistry.STATE_START:
            if line == '':
                return 0
            if line[0] == '[':
                self._state = PluginRegistry.STATE_FINISHED
                return -1
            self._current_plugin = Plugin()
            self._current_plugin.lib = line.split(':')[0]
            self._state += 1
            return 0
        elif self._state == PluginRegistry.STATE_PROCESSING_1:
            self._current_plugin.path = line.split(':')[0]
            if self._current_plugin.path[0] != '/':
                raise PluginRegParseError("Invalid path %s" % self._current_plugin.path)
            self._state += 1
            return 3
        elif self._state == PluginRegistry.STATE_PROCESSING_2:
            self._current_plugin.desc = line.split(':')[0]
            self._state += 1
            return 0
        elif self._state == PluginRegistry.STATE_PROCESSING_3:
            self.plugins[self._count] = self._current_plugin
            self._count += 1
            self._state = PluginRegistry.STATE_START
            return int(line.strip())
        else:
            return -1

    def __getitem__(self, key):
        if not key in self.plugins:
            raise IndexError
        return self.plugins[key]

    def __iter__(self):
        self._current_index = 0
        return self

    def next(self):
        if self._current_index == len(self.plugins):
            raise StopIteration
        ret = self.plugins[self._current_index]
        self._current_index += 1
        return ret

    def __len__(self):
        return len(self.plugins)


class PrefFile:
    '''Class which represents a pref file. Handles all of the parsing, and can be accessed
       like a normal python dictionary'''
    PREF_WHITELIST = [
        r'accessibility\.*',
        r'browser\.fixup\.*',
        r'browser\.history_expire_*',
        r'browser\.link\.open_newwindow',
        r'browser\.mousewheel\.*',
        r'browser\.places\.*',
        r'browser\.startup\.homepage',
        r'browser\.tabs\.*',
        r'browser\.zoom\.*',
        r'dom\.*',
        r'extensions\.checkCompatibility\.*',
        r'extensions\.lastAppVersion\.*',
        r'font\.*',
        r'general\.skins\.*',
        r'general\.useragent\.*',
        r'gfx\.*',
        r'html5\.*',
        r'mozilla\.widget\.render\-mode',
        r'layers\.*',
        r'javascript\.*',
        r'keyword\.*',
        r'layout\.css\.dpi',
        r'network\.*',
        r'places\.*',
        r'plugin\.*',
        r'plugins\.*',
        r'print\.*',
        r'privacy\.*',
        r'security\.*',
        r'webgl\.*'
    ]

    PREF_BLACKLIST = [
        r'^network.*proxy\.*',
        r'.*print_to_filename$',
        r'print\.tmp\.',
        r'print\.printer_*'
    ]

    def __init__(self, filename, whitelist=None, blacklist=None):
        self.whitelist = whitelist if whitelist != None else PrefFile.PREF_WHITELIST
        self.blacklist = blacklist if blacklist != None else PrefFile.PREF_BLACKLIST
        self.prefs = {}
        self._in_comment = False
        self.available = False
        try:
            f = open(filename)
            for line in f.readlines():
                self._parseline(line)
            self.available = True
        except Exception as e:
            self.parse_error = str(e)

    def _maybe_add_pref(self, key, value):
        for match in self.blacklist:
            if re.match(match, key):
                return

        for match in self.whitelist:
            if re.match(match, key):
                self.prefs[key] = value

    def _do_parse(self, line, start):
        # XXX: I pity the poor soul who ever needs to change anything inside this function
        in_escape = False
        in_name = True
        in_value = False
        in_quote = False
        has_name = False
        has_value = False
        done = False
        name = ""
        value = ""
        for i in range(start, len(line)):
            if in_escape == True:
                in_escape = False
                if in_name == True:
                    name += line[i]
                elif in_value == True:
                    value += line[i]
                else:
                    raise PrefParseError("Unexpected character")
            elif line[i] == '"':
                if in_name == False and in_value == False:
                    raise PrefParseError("Unexpected double quote")
                in_quote = not in_quote
                if in_quote == False:
                    if in_name == True:
                        in_name = False
                        has_name = True
                    elif in_value == True:
                        in_value = False
                        has_value = True
            elif line[i] == '\\':
                if in_quote == True:
                    in_escape = True
                else:
                    raise PrefParseError("Unexpected escape character")
            elif line[i] == ' ' and in_quote == False:
                if in_name == True and len(name) > 0:
                    in_name = False
                    has_name = True
                elif in_value == True and len(value) > 0:
                    in_value = False
                    has_value = True
            elif line[i] == ',' and in_quote == False:
                if (in_name == True or has_name == True) and in_value == False and has_value == False:
                    in_name = False
                    in_value = True
                    has_name = True
                else:
                    raise PrefParseError("Unexpected comma")
            elif line[i] == ')' and in_quote == False:
                if (in_value == True or has_value == True) and has_name == True and done == False:
                    in_value = False
                    has_value = True
                    done = True
                else:
                    raise PrefParseError("Unexpected close braces character for " + line)
            elif line[i] == ';' and in_quote == False:
                if done == False:
                    raise PrefParseError("Unexpected line terminator")
            else:
                if in_name == True:
                    name += line[i]
                elif in_value == True:
                    value += line[i]
                else:
                    raise PrefParseError("Unexpected character")

        if done == True and in_name == False and in_value == False:
            self._maybe_add_pref(name, value)
        else:
            raise PrefParseError("Failed to parse line")

    def _parseline(self, line):
        line = line.strip()
        if line == '' or line[0] == '#' or line.startswith('//'):
            return

        if line.startswith('/*'):
            self._in_comment = True

        if self._in_comment == True:
            for i in range(len(line)):
                if i < len(line) - 1 and line[i]+line[i+1] == '*/':
                    self._in_comment = False
                    break
            return

        if line.startswith("user_pref("):
            self._do_parse(line, 10)
        elif line.startswith("pref("):
            self._do_parse(line, 5)
        else:
            raise PrefParseError("Unexpected line start")

    def __getitem__(self, key):
        if not key in self.prefs:
            raise IndexError
        return self.prefs[key]

    def __iter__(self):
        self.keys = self.prefs.keys()
        self.current = 0
        return self

    def next(self):
        if self.current == len(self.keys):
            raise StopIteration
        val = self.keys[self.current]
        self.current += 1
        return val

    def __len__(self):
        return len(self.prefs)


class Extension:
    '''Small class representing an extension'''
    def __init__(self, ext_id, location, ver, ext_type, active, desc, min_appver, max_appver, cur_appver):
        self.ext_id = ext_id;
        self.location = location
        self.ver = ver
        self.ext_type = ext_type
        self.active = active
        self.desc = desc
        self.min_appver = min_appver
        self.max_appver = max_appver
        self.cur_appver = cur_appver

    def dump(self):
        active = "Yes" if self.active == 1 else "No"
        return "%s - ID=%s, Version=%s, minVersion=%s, maxVersion=%s, Location=%s, Type=%s, Active=%s" % (self.desc, self.ext_id, self.ver, self.min_appver, self.max_appver, self.location, self.ext_type, active)

    @property
    def active_but_incompatible(self):
        return self.active and (self.cur_appver != None and compare_versions(self.cur_appver, self.min_appver) == -1 or compare_versions(self.cur_appver, self.max_appver) == 1)


class Profile:
    '''Container to represent a profile'''
    def __init__(self, id, name, path, is_default, appini):
        self.extensions = {}
        self.locales = {}
        self.themes = {}
        self.id = id
        self.name = name
        self.path = path
        self.default = is_default
        self.appini = appini

        try:
            self._populate_extensions()
        except:
            self.extensions = None

        self.prefs = PrefFile(os.path.join(path, "prefs.js"))
        self.userjs = PrefFile(os.path.join(path, "user.js"))
        self.plugins = PluginRegistry(os.path.join(path, "pluginreg.dat"))

    def _populate_extensions(self):
        # We copy the db as it's locked whilst Firefox is open. This is still racy
        # though, as it could be modified during the copy, leaving us with a corrupt
        # DB. Can we detect this somehow?
        tmp_db = mkstemp_copy(os.path.join(self.path, "extensions.sqlite"))
        conn = sqlite3.connect(tmp_db)

        def get_extension_from_row(row):
            moz_id = row[0]
            ext_id = row[1]
            location = row[2]
            ext_ver = row[3]
            ext_type = row[4]
            active = True if row[6] == 1 else False

            cur = conn.cursor()
            cur.execute("select name from locale where id=:id", { "id": row[5] })
            desc = cur.fetchone()[0]

            cur = conn.cursor()
            cur.execute("select minVersion, maxVersion from targetApplication where addon_internal_id=:id and (id=:appid or id=:tkid)", \
                        { "id": row[0], "appid": self.appini.appid, "tkid": "toolkit@mozilla.org" })
            (min_ver, max_ver) = cur.fetchone()

            return Extension(ext_id, location, ext_ver, ext_type, active, desc, min_ver, max_ver, self.last_version)

        cur = conn.cursor()
        cur.execute("select internal_id, id, location, version, type, defaultLocale, active from addon")
        rows = cur.fetchall()
        for row in rows:
            extension = get_extension_from_row(row)
            if extension.ext_type == "extension":
                storage_array = self.extensions
            elif extension.ext_type == "locale":
                storage_array = self.locales
            elif extension.ext_type == "theme":
                storage_array = self.themes
            else:
                raise ExtensionTypeNotRecognised(extension.type, extension.ext_id)

            if not extension.location in storage_array:
                storage_array[extension.location] = []
            storage_array[extension.location].append(extension)

        os.remove(tmp_db)

    def _do_dump(self, storage_array):
        if self.extensions == None:
            return "extensions.sqlite corrupt or missing"

        ret = ""
        for location in storage_array:
            ret += "Location: " + location + "\n\n"
            for extension in storage_array[location]:
                prefix = "  (Inactive) " if not extension.active else ""
                ret += "\t%s%s = ID=%s, Version=%s, minVersion=%s, maxVersion=%s\n" % (prefix, extension.desc, extension.ext_id, extension.ver, extension.min_appver, extension.max_appver)
            ret += "\n\n\n"
        return ret

    @property
    def running(self):
        if not hasattr(self, '_running'):
            # We detect if this profile is running or not by trying to lock the lockfile
            # If we can't lock it, then Firefox is running
            fd = os.open(os.path.join(self.path, ".parentlock"), os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0666)
            lock = struct.pack("hhqqi", 1, 0, 0, 0, 0)
            try:
                fcntl.fcntl(fd, fcntl.F_SETLK, lock)
                self._running = False
                # If we acquired the lock, ensure that we unlock again immediately
                lock = struct.pack("hhqqi", 2, 0, 0, 0, 0)
                fcntl.fcntl(fd, fcntl.F_SETLK, lock)
            except:
                self._running = True

        return self._running

    def dump_extensions(self):
        return self._do_dump(self.extensions)

    def dump_locales(self):
        return self._do_dump(self.locales)

    def dump_themes(self):
        return self._do_dump(self.themes)

    def dump_prefs(self):
        if self.prefs.available == False:
            if os.path.exists(os.path.join(self.path, "prefs.js")):
                return "prefs.js exists but isn't parseable - %s" % self.prefs.parse_error
            else:
                return "prefs.js is not available"

        ret = ''
        for pref in self.prefs:
            ret += pref + " - " + self.prefs[pref] + '\n'
        return ret

    def dump_user_js(self):
        if self.userjs.available == False:
            if os.path.exists(os.path.join(self.path, "user.js")):
                return "user.js exists but isn't parseable - %s" % self.userjs.parse_error
            else:
                return None

        ret = ''
        for pref in self.userjs:
            ret += pref + " - " + self.userjs[pref] + '\n'
        return ret

    def dump_plugins(self):
        if self.plugins.available == False:
            if os.path.exists(os.path.join(self.path, "pluginreg.dat")):
                return "pluginreg.dat exists but isn't parseable = %s" % self.plugins.parse_error
            else:
                return "pluginreg.dat isn't available"

        ret = ''
        for plugin in self.plugins:
            ret += plugin.dump() + '\n'
        return ret

    def get_plugin_packages(self, pkglist):
        if self.plugins.available == False:
            return None

        for plugin in self.plugins:
            if plugin.package != None and plugin.package not in pkglist:
                pkglist.append(plugin.package)

    @property
    def current(self):
        return True if self.appini.buildid == self.last_buildid or self.appini.buildid == None else False

    @property
    def has_active_but_incompatible_extensions(self):
        if self.last_version == None:
            return False
        for storage_array in self.extensions, self.locales, self.themes:
            for location in storage_array:
                for extension in storage_array[location]:
                    if extension.active_but_incompatible:
                        return True
        return False

    def dump_active_but_incompatible_extensions(self):
        if self.last_version == None:
            return "Unavailable (corrupt or non-existant compatibility.ini)"
        res = ''
        for storage_array in self.extensions, self.locales, self.themes:
            for location in storage_array:
                for extension in storage_array[location]:
                    if extension.active_but_incompatible:
                        res += extension.dump() + "\n"
        return res

    @property
    def has_forced_layers_acceleration(self):
        if self.prefs != None and "layers.acceleration.force-enabled" in self.prefs and self.prefs["layers.acceleration.force-enabled"] == "true":
            return True

        if self.userjs != None and "layers.acceleration.force-enabled" in self.userjs and self.userjs["layers.acceleration.force-enabled"] == "true":
            return True

        return False

    @property
    def compatini(self):
        if not hasattr(self, '_compatini'):
            self._compatini = CompatINIParser(self.path)
        return self._compatini

    @property
    def last_version(self):
        return self.compatini.last_version

    @property
    def last_buildid(self):
        return self.compatini.last_buildid

    @property
    def addon_compat_check_disabled(self):
        is_nightly = re.sub(r'^[^\.]+\.[0-9]+([a-z0-9]*).*', r'\1', self.last_version) == 'a1'
        if is_nightly == True:
            pref = "extensions.checkCompatibility.nightly"
        else:
            pref = "extensions.checkCompatibility.%s" % re.sub(r'(^[^\.]+\.[0-9]+[a-z]*).*', r'\1', self.last_version)
        return pref in self.prefs and self.prefs[pref] == 'false'


class Profiles:
    '''Small class to build an array of profiles from a profile.ini.
       Can be accessed like a normal array'''
    def __init__(self, ini_file, appini):
        self.profiles = {}

        parser = ConfigParser()
        parser.read(ini_file)
        profile_folder = os.path.dirname(ini_file)

        i = 0
        for section in parser.sections():
            if section == "General": continue
            if not parser.has_option(section, "Path"): continue
            path = parser.get(section, "Path")
            name = parser.get(section, "Name")
            is_default = True if parser.has_option(section, "Default") and parser.getint(section, "Default") == 1 else False
            self.profiles[i] = Profile(section, name, os.path.join(profile_folder, path), is_default, appini)
            i += 1

        # No "Default" entry when there is one profile
        if len(self) == 1: self[0].default = True

    def __getitem__(self, key):
        if not key in self.profiles:
            raise IndexError
        return self.profiles[key]

    def __iter__(self):
        self.current_index = 0
        return self

    def __len__(self):
        return len(self.profiles)

    def next(self):
        if self.current_index == len(self.profiles):
            raise StopIteration
        else:
            val = self.profiles[self.current_index]
            self.current_index += 1
            return val

    def dump_profile_summaries(self):
        res = ''
        for profile in self:
            running = " (Running)" if profile.running == True else ""
            default = " (Default)" if profile.default else ""
            outdated = " (Out of date)" if not profile.current else ""
            res += "%s%s - LastVersion=%s/%s%s%s\n" % (profile.id, default, profile.last_version, profile.last_buildid, running, outdated)
        return res


def recent_kernlog(pattern):
    '''Extract recent messages from kern.log or message which match a regex.
       pattern should be a "re" object.  '''
    lines = ''
    if os.path.exists('/var/log/kern.log'):
        file = '/var/log/kern.log'
    elif os.path.exists('/var/log/messages'):
        file = '/var/log/messages'
    else:
        return lines

    for line in open(file):
        if pattern.search(line):
            lines += line
    return lines


def recent_auditlog(pattern):
    '''Extract recent messages from kern.log or message which match a regex.
       pattern should be a "re" object.  '''
    lines = ''
    if os.path.exists('/var/log/audit/audit.log'):
        file = '/var/log/audit/audit.log'
    else:
        return lines

    for line in open(file):
        if pattern.search(line):
            lines += line
    return lines


def add_info(report, ui):
    '''Entry point for apport'''

    def populate_item(key, data):
        if data != None and data.strip() != '':
            report[key] = data

    def append_tag(tag):
        tags = report.get('Tags', '')
        if tags:
            tags += ' '
        report['Tags'] = tags + tag

    ddproc = Popen(['dpkg-divert', '--truename', '/usr/bin/firefox'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    truename = ddproc.communicate()
    if ddproc.returncode == 0 and truename[0].strip() != '/usr/bin/firefox':
        ddproc = Popen(['dpkg-divert', '--listpackage', '/usr/bin/firefox'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        diverter = ddproc.communicate()
        report['UnreportableReason'] = "/usr/bin/firefox has been diverted by a third party package (%s)" % diverter[0].strip()
        return

    conf_dir = os.path.join(os.environ["HOME"], ".mozilla", "firefox")
    appini = AppINIParser('/usr/lib/firefox-7.0.1')
    populate_item("BuildID", appini.buildid)
    try:
        profiles = Profiles(os.path.join(conf_dir, "profiles.ini"), appini)
        populate_item("Profiles", profiles.dump_profile_summaries())
    except:
        pass
    finally:
        if len(profiles) == 0: report["NoProfiles"] = 'True'

    for profile in profiles:
        if profile.running and not profile.current:
            report["UnreportableReason"] = "Firefox has been upgraded since you started it. Please restart all instances of Firefox and try again"
            return

    seen_default = False
    running_incompatible_addons = False
    forced_layers_accel = False
    addon_compat_check_disabled = False
    for profile in profiles:
        if profile.default and not seen_default and len(profiles) > 1:
            prefix = 'DefaultProfile'
            seen_default = True
        elif len(profiles) > 1:
            prefix = profile.id
        else:
            prefix = ''

        populate_item(prefix + "Extensions", profile.dump_extensions())
        populate_item(prefix + "Locales", profile.dump_locales())
        populate_item(prefix + "Themes", profile.dump_themes())
        populate_item(prefix + "Plugins", profile.dump_plugins())
        populate_item(prefix + "IncompatibleExtensions", profile.dump_active_but_incompatible_extensions())
        populate_item(prefix + "Prefs", profile.dump_prefs())
        populate_item(prefix + "UserJS", profile.dump_user_js())

        if (profile.current or profile.default) and profile.has_active_but_incompatible_extensions:
            running_incompatible_addons = True
        if (profile.current or profile.default) and profile.has_forced_layers_acceleration:
            forced_layers_accel = True
        if (profile.current or profile.default) and profile.addon_compat_check_disabled:
            addon_compat_check_disabled = True

    plugin_packages = []
    for profile in profiles:
        profile.get_plugin_packages(plugin_packages)
    if len(plugin_packages) > 0: attach_related_packages(report, plugin_packages)

    report["RunningIncompatibleAddons"] = 'True' if running_incompatible_addons == True else 'False'
    report["ForcedLayersAccel"] = 'True' if forced_layers_accel == True else 'False'
    report["AddonCompatCheckDisabled"] = 'True' if addon_compat_check_disabled == True else 'False'

    syspref = PrefFile("/etc/firefox/syspref.js")
    if syspref.available == False:
        report["EtcFirefoxSyspref"] = "Cannot parse /etc/firefox/syspref.js - %s" % syspref.parse_error
    for pref in syspref:
        report["EtcFirefoxSyspref"] += "%s - %s\n" % (pref, syspref[pref])

    if 'firefox' == 'firefox-trunk':
        report["Channel"] = 'nightly'
        append_tag('nightly-channel')
        report["SourcePackage"] = 'firefox'
    else:
        channelpref = PrefFile("/usr/lib/firefox-7.0.1/defaults/pref/channel-prefs.js", whitelist = [ r'app\.update\.channel' ])
        if channelpref.available == False:
            report["Channel"] = 'release'
        else:
            if "app.update.channel" in channelpref:
                report["Channel"] = channelpref["app.update.channel"]
                append_tag(channelpref["app.update.channel"] + '-channel')

    if os.path.exists('/sys/bus/pci'):
        report['Lspci'] = command_output(['lspci','-vvnn'])
    attach_alsa(report)
    attach_network(report)
    attach_wifi(report)

    # Get apparmor stuff if the profile isn't disabled. copied from
    # source_apparmor.py until apport runs hooks via attach_related_packages
    apparmor_disable_dir = "/etc/apparmor.d/disable"
    add_apparmor = True
    if os.path.isdir(apparmor_disable_dir):
        for f in os.listdir(apparmor_disable_dir):
            if f.startswith("usr.bin.firefox"):
                add_apparmor = False
                break
    if add_apparmor:
        attach_related_packages(report, ['apparmor', 'libapparmor1',
            'libapparmor-perl', 'apparmor-utils', 'auditd', 'libaudit0'])

        attach_file(report, '/proc/version_signature', 'ProcVersionSignature')
        attach_file(report, '/proc/cmdline', 'ProcCmdline')

        sec_re = re.compile('audit\(|apparmor|selinux|security', re.IGNORECASE)
        report['KernLog'] = recent_kernlog(sec_re)

        if os.path.exists("/var/log/audit"):
            # this needs to be run as root
            report['AuditLog'] = recent_auditlog(sec_re)


if __name__ == "__main__":
    import apport
    from apport import packaging
    D = {}
    D['Package'] = 'firefox'
    add_info(D, None)
    for KEY in D.keys(): 
        print '''-------------------%s: ------------------\n''' % KEY, D[KEY]
