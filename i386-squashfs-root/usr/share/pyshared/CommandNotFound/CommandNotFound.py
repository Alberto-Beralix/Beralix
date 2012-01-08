# (c) Zygmunt Krynicki 2005, 2006, 2007, 2008
# Licensed under GPL, see COPYING for the whole text

import gdbm
import gettext
import grp
import os
import os.path
import posix
import string
import sys

_ = gettext.translation("command-not-found", fallback=True).ugettext


class BinaryDatabase(object):

    def __init__(self, filename):
        self.db = None
        if filename.endswith(".db"):
            try:
                self.db = gdbm.open(filename, "r")
            except gdbm.error, err:
                print >> sys.stderr, "Unable to open binary database %s: %s" % (filename, err)

    def lookup(self, key):
        if self.db and self.db.has_key(key):
            return self.db[key]
        else:
            return None


class FlatDatabase(object):

    def __init__(self, filename):
        self.rows = []
        dbfile = file(filename)
        for line in (line.strip() for line in dbfile):
            self.rows.append(line.split("|"))
        dbfile.close()

    def lookup(self, column, text):
        result = []
        for row in self.rows:
            if row[column] == text:
                result.append(row)
        return result

    def createColumnByCallback(self, cb, column):
        for row in self.rows:
            row.append(cb(row[column]))

    def lookupWithCallback(self, column, cb, text):
        result = []
        for row in self.rows:
            if cb(row[column], text):
                result.append(row)
        return result


class ProgramDatabase(object):

    (PACKAGE, BASENAME_PATH) = range(2)

    def __init__(self, filename):
        basename = os.path.basename(filename)
        (self.arch, self.component) = basename.split(".")[0].split("-")
        self.db = BinaryDatabase(filename)

    def lookup(self, command):
        result = self.db.lookup(command)
        if result:
            return result.split("|")
        else:
            return []


def similar_words(word):
    """
    return a set with spelling1 distance alternative spellings

    based on http://norvig.com/spell-correct.html
    """
    alphabet = 'abcdefghijklmnopqrstuvwxyz-_0123456789'
    s = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = [a + b[1:] for a, b in s if b]
    transposes = [a + b[1] + b[0] + b[2:] for a, b in s if len(b) > 1]
    replaces = [a + c + b[1:] for a, b in s for c in alphabet if b]
    inserts = [a + c + b     for a, b in s for c in alphabet]
    return set(deletes + transposes + replaces + inserts)


class CommandNotFound(object):

    programs_dir = "programs.d"

    prefixes = (
        "/bin",
        "/usr/bin",
        "/usr/local/bin",
        "/sbin",
        "/usr/sbin",
        "/usr/local/sbin",
        "/usr/games")

    def __init__(self, data_dir="/usr/share/command-not-found"):
        self.programs = []
        self.priority_overrides = []
        p = os.path.join(data_dir, "priority.txt")
        if os.path.exists(p):
            self.priority_overrides = map(string.strip, open(p).readlines())
        self.components = ['main', 'universe', 'contrib', 'restricted',
                           'non-free', 'multiverse']
        self.components.reverse()
        self.sources_list = self._getSourcesList()
        for filename in os.listdir(os.path.sep.join([data_dir, self.programs_dir])):
            self.programs.append(ProgramDatabase(os.path.sep.join([data_dir, self.programs_dir, filename])))
        try:
            self.user_can_sudo = grp.getgrnam("admin")[2] in posix.getgroups()
        except KeyError:
            self.user_can_sudo = False

    def print_spelling_suggestion(self, word, min_len=3, max_len=15):
        " try to correct the spelling "
        if len(word) < min_len:
            return
        possible_alternatives = []
        for w in similar_words(word):
            packages = self.getPackages(w)
            for (package, comp) in packages:
                possible_alternatives.append((w, package, comp))
        if len(possible_alternatives) > max_len:
            print >> sys.stderr, _("No command '%s' found, but there are %s similar ones") % (word, len(possible_alternatives))
        elif len(possible_alternatives) > 0:
            print >> sys.stderr, _("No command '%s' found, did you mean:") % word
            for (w, p, c) in possible_alternatives:
                print >> sys.stderr, _(" Command '%s' from package '%s' (%s)") % (w, p, c)

    def getPackages(self, command):
        result = set()
        for db in self.programs:
            result.update([(pkg, db.component) for pkg in db.lookup(command)])
        return list(result)

    def getBlacklist(self):
        try:
            blacklist = file(os.sep.join((os.getenv("HOME", "/root"), ".command-not-found.blacklist")))
            return [line.strip() for line in blacklist if line.strip() != ""]
        except IOError:
            return []
        else:
            blacklist.close()

    def _getSourcesList(self):
        try:
            import apt_pkg
            from aptsources.sourceslist import SourcesList
            apt_pkg.init()
        except (SystemError, ImportError):
            return []
        sources_list = set([])
        # The matcher parses info files from
        # /usr/share/python-apt/templates/
        # But we don't use the calculated data, skip it
        for source in SourcesList(withMatcher=False):
            if not source.disabled and not source.invalid:
                for component in source.comps:
                    sources_list.add(component)
        return sources_list

    def sortByComponent(self, x, y):
        # check overrides
        if (x[0] in self.priority_overrides and
            y[0] in self.priority_overrides):
            # both have priority, do normal sorting
            pass
        elif x[0] in self.priority_overrides:
            return -1
        elif y[0] in self.priority_overrides:
            return 1
        # component sorting
        try:
            xidx = self.components.index(x[1])
        except:
            xidx = -1
        try:
            yidx = self.components.index(y[1])
        except:
            xidx = -1
        return (yidx - xidx) or cmp(x, y)

    def advise(self, command, ignore_installed=False):
        " give advice where to find the given command to stderr "
        def _in_prefix(prefix, command):
            " helper that returns if a command is found in the given prefix "
            return (os.path.exists(os.path.join(prefix, command))
                    and not os.path.isdir(os.path.join(prefix, command)))

        if command.startswith("/"):
            if os.path.exists(command):
                prefixes = [os.path.dirname(command)]
            else:
                prefixes = []
        else:
            prefixes = [prefix for prefix in self.prefixes if _in_prefix(prefix, command)]

        # check if we have it in a common prefix that may not be in the PATH
        if prefixes and not ignore_installed:
            if len(prefixes) == 1:
                print >> sys.stderr, _("Command '%(command)s' is available in '%(place)s'") % {"command": command, "place": os.path.join(prefixes[0], command)}
            else:
                print >> sys.stderr, _("Command '%(command)s' is available in the following places") % {"command": command}
                for prefix in prefixes:
                    print >> sys.stderr, " * %s" % os.path.join(prefix, command)
            missing = list(set(prefixes) - set(os.getenv("PATH", "").split(":")))
            if len(missing) > 0:
                print >> sys.stderr, _("The command could not be located because '%s' is not included in the PATH environment variable.") % ":".join(missing)
                if "sbin" in ":".join(missing):
                    print >> sys.stderr, _("This is most likely caused by the lack of administrative privileges associated with your user account.")
            return False

        # do not give advice if we are in a situation where apt-get
        # or aptitude are not available (LP: #394843)
        if not (os.path.exists("/usr/bin/apt-get") or
                os.path.exists("/usr/bin/aptitude")):
            return False

        if command in self.getBlacklist():
            return False
        packages = self.getPackages(command)
        if len(packages) == 0:
            self.print_spelling_suggestion(command)
        elif len(packages) == 1:
            print >> sys.stderr, _("The program '%s' is currently not installed. ") % command,
            if posix.geteuid() == 0:
                print >> sys.stderr, _("You can install it by typing:")
                print >> sys.stderr, "apt-get install %s" % packages[0][0]
            elif self.user_can_sudo:
                print >> sys.stderr, _("You can install it by typing:")
                print >> sys.stderr, "sudo apt-get install %s" % packages[0][0]
            else:
                print >> sys.stderr, _("To run '%(command)s' please ask your administrator to install the package '%(package)s'") % {'command': command, 'package': packages[0][0]}
            if not packages[0][1] in self.sources_list:
                print >> sys.stderr, _("You will have to enable the component called '%s'") % packages[0][1]
        elif len(packages) > 1:
            packages.sort(self.sortByComponent)
            print >> sys.stderr, _("The program '%s' can be found in the following packages:") % command
            for package in packages:
                if package[1] in self.sources_list:
                    print >> sys.stderr, " * %s" % package[0]
                else:
                    print >> sys.stderr, " * %s" % package[0] + " (" + _("You will have to enable component called '%s'") % package[1] + ")"
            if posix.geteuid() == 0:
                print >> sys.stderr, _("Try: %s <selected package>") % "apt-get install"
            elif self.user_can_sudo:
                print >> sys.stderr, _("Try: %s <selected package>") % "sudo apt-get install"
            else:
                print >> sys.stderr, _("Ask your administrator to install one of them")
        return len(packages) > 0
