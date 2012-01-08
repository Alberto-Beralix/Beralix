"""
Code used to identify a package based on one of the following:
 * A process ID
 * A file name
 * A desktop file
 * A binary package name
"""

import sys
import os
import socket

import subprocess

DPKGDIR = '/var/lib/dpkg'
INFODIR = os.path.join(DPKGDIR, 'info')
STATUSFILE = os.environ.get('LPI_PACKAGE_FILE', os.path.join(DPKGDIR, 'status'))

if os.environ.has_key('LPI_PACKAGE_FILE'):
    print "Using STATUSFILE: %s"%STATUSFILE

class PackageNotFoundError(Exception):
    pass


def _get_pkg(filename):
    """Find the binary package associated with the given filename

    This scans the list files in /var/lib/dpkg/info, since it is faster
    than 'dpkg-query -S'.
    """
    for listfile in os.listdir(INFODIR):
        if not listfile.endswith('.list'): continue
        contents = open(os.path.join(INFODIR, listfile), 'r').read()
        if filename in contents.splitlines(False):
            return listfile[:-len('.list')]


class PackageInfo(object):
    def __init__(self, binarypackage, sourcepackage, provides,
                 version, architecture, status, dependencies):
        self.binarypackage = binarypackage
        self.sourcepackage = sourcepackage or binarypackage
        self.provides = set(provides)
        self.version = version
        self.architecture = architecture
        self.status = status
        self.dependencies = set(dependencies)

        self.names = set(self.provides)
        self.names.add(self.binarypackage)

    @property
    def installed(self):
        if self.status:
            state = self.status.split()[2]
            return state not in ('config-files', 'not-installed')
        else:
            return False

    @property
    def shortstatus(self):
        if self.status:
            sinfo = self.status.split()
            return sinfo[0][0] + sinfo[2][0]
        else:
            return None

    def __repr__(self):
        return "<PackageInfo '%s_%s_%s'>" % (self.binarypackage,
                                             self.version,
                                             self.architecture)

    @classmethod
    def fromXID(cls, xid=None, logger=None):
        """Return a PackageInfo instance corresponding to a window

        This is performed by calling xprop to get WM_CLIENT_MACHINE
        and _NET_WM_PID properties of a window.  If WM_CLIENT_MACHINE
        is our hostname, and _NET_WM_PID is set, then chain to
        fromProcessID().

        If no XID is passed, xprop works in 'picker' mode.
        """
        cmdline = ['xprop', '-notype']
        if xid is not None:
            cmdline.extend(['-id', str(xid)])
            
        cmdline.extend(['WM_CLIENT_MACHINE', '_NET_WM_PID'])
        if logger:
            logger.debug('Executing %r', cmdline)
        try:
            p = subprocess.Popen(cmdline,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 close_fds=True)
            stdout, stderr = p.communicate()
            result = p.returncode
        except (OSError, IOError):
            if logger:
                logger.exception('Could not find process ID')
            raise PackageNotFoundError('Could not find process ID')
        if result != 0:
            raise PackageNotFoundError('Could not find process ID')

        # unpack properties
        props = dict(x.split(' = ', 1) for x in stdout.splitlines(False))

        if logger:
            logger.debug('WM_CLIENT_MACHINE = %s, _NET_WM_PID = %s',
                         props.get('WM_CLIENT_MACHINE'),
                         props.get('_NET_WM_PID'))

        # if the window comes from another host, or doesn't have a PID
        # property, raise an exception.
        hostname = '"%s"' % socket.gethostname()
        if (props.get('WM_CLIENT_MACHINE', hostname) != hostname or
            '_NET_WM_PID' not in props):
            raise PackageNotFoundError('Could not find process ID')

        try:
            pid = int(props['_NET_WM_PID'])
        except ValueError:
            raise PackageNotFoundError('Could not find process ID')

        if logger:
            logger.info('Process ID for selected window is %d', pid)

        return cls.fromProcessID(pid, logger)

    @classmethod
    def fromProcessID(cls, pid, logger=None):
        """Return a PackageInfo instance corresponding to a process ID

        This is performed by looking up the executable name in the /proc
        filesystem, then chaining to fromFilename().
        """
        if logger:
            logger.debug('Looking up executable for process %d', pid)
        try:
            filename = os.readlink('/proc/%d/exe' % pid)
        except OSError:
            if logger:
                logger.exception('Could not find executable for process %d',
                                 pid)
            raise PackageNotFoundError('Could not find executable for '
                                       'process %d' % pid)

        # if the executable is deleted, then the user is not running the
        # version of the file installed by the package (they probably
        # started the app, then ran "apt-get upgrade" or similar).
        if filename.endswith(' (deleted)'):
            logger.error('Process %d is running deleted executable "%s"',
                         pid, filename)
            raise PackageNotFoundError('Process %d is running deleted '
                                       'executable "%s"' %(pid, filename))
        if logger:
            logger.info('Executable for process %d is "%s"', pid, filename)
        # dirty fix for the Live CD
        if filename.startswith('/rofs'):
            filename = filename[len('/rofs'):]
        elif filename.startswith('/filesystem.squashfs'):
            filename = filename[len('/filesystem.squashfs'):]
	return cls.fromFilename(filename, logger)

    @classmethod
    def fromDesktopFile(cls, filename, logger=None):
        """Return a PackageInfo instance corresponding to a Desktop file

        This is performed by looking for the executable name in the 'exec'
        line of the desktop file, then chains to fromFilename().

        This function should be used instead of fromFilename() because
        the desktop file might be a customised one in the user's home
        directory, but still points to an installed application.
        """
        raise NotImplementedError

    @classmethod
    def fromFilename(cls, filename, logger=None):
        """Return a PackageInfo instance corresponding to a file

        This is performed by finding the package that owns the file
        using dpkg-query, and then chaining to fromPackageName to
        fill in the PackageInfo instance.
        """
        if logger:
            logger.debug('Looking up binary package name for file "%s"',
                         filename)
        try:
            package = _get_pkg(filename)
        except (OSError, IOError):
            if logger:
                logger.exception('Could not find binary package for file "%s"',
                                 filename)
            raise PackageNotFoundError('Could not find binary package for '
                                       'file "%s"' % filename)
        if package is None:
            raise PackageNotFoundError('Could not look up binary package for '
                                       'file "%s"' % filename)
        if logger:
            logger.info('Binary package for file "%s" is "%s"',
                         filename, package)

        return cls.fromPackageName(package, logger)

    @classmethod
    def fromPackageName(cls, package, logger=None):
        """Return a PackageInfo instance for a particular binary package name
        """
        if logger:
            logger.debug('Looking up package information for "%s"', package)

        for info in cls._iterPackages():
            if package in info.names:
                break
        else:
            raise PackageNotFoundError('Could not look up package info for '
                                       '"%s"' % package)

        if logger:
            logger.debug('Package info for %s is %r', package, info)
        return info

    @classmethod
    def fromPackageNames(cls, packages, logger=None):
        """Iterate through PackageInfo instances that match names in packages.

        This is an optimisation of fromPackageName() for when you want
        multiple packages.
        """
        packages = set(packages)
        for info in cls._iterPackages():
            if packages & info.names:
                if logger:
                    logger.debug('Package %r matched', info)
                yield info

    @classmethod
    def _iterPackages(cls, filename=STATUSFILE):
        """Iterate through the list of packages in the DPKG database"""
        package = None
        status = None
        architecture = None
        source = None
        version = None
        provides = []
        dependencies = []
        for line in open(filename, 'r'):
            if line == '\n': # end of record
                yield cls(binarypackage=package,
                          sourcepackage=source,
                          provides=provides,
                          version=version,
                          architecture=architecture,
                          status=status,
                          dependencies=dependencies)
                package = None
                status = None
                architecture = None
                source = None
                version = None
                provides = []
                dependencies = []
            elif line.startswith('Package: '):
                package = line[len('Package: '):].strip()
            elif line.startswith('Status: '):
                status = line[len('Status: '):].strip()
            elif line.startswith('Architecture: '):
                architecture = line[len('Architecture: '):].strip()
            elif line.startswith('Source: '):
                source = line[len('Source: '):].strip()
            elif line.startswith('Version: '):
                version = line[len('Version: '):].strip()
            elif line.startswith('Provides: '):
                provides.extend(x.strip()
                                for x in line[len('Provides: '):].split(', '))
            elif line.startswith('Depends: '):
                deps = line[len('Depends: '):].strip()
                dependencies.extend(y.split()[0]
                                    for x in deps.split(', ')
                                    for y in x.split('|'))
            elif line.startswith('Pre-Depends'):
                deps = line[len('Pre-Depends: '):].strip()
                dependencies.extend(y.split()[0]
                                    for x in deps.split(', ')
                                    for y in x.split('|'))
        if package is not None:
            yield cls(binarypackage=package,
                      sourcepackage=source,
                      provides=provides,
                      version=version,
                      architecture=architecture,
                      status=status,
                      dependencies=dependencies)

