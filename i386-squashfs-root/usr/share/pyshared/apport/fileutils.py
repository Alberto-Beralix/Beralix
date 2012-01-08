'''Functions to manage apport problem report files.'''

# Copyright (C) 2006 - 2009 Canonical Ltd.
# Author: Martin Pitt <martin.pitt@ubuntu.com>
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

import os, glob, subprocess, os.path

try:
    from configparser import ConfigParser, NoOptionError, NoSectionError
except ImportError:
    # Python 2
    from ConfigParser import ConfigParser, NoOptionError, NoSectionError

from problem_report import ProblemReport

from apport.packaging_impl import impl as packaging

report_dir = os.environ.get('APPORT_REPORT_DIR', '/var/crash')

_config_file = '~/.config/apport/settings'

def find_package_desktopfile(package):
    '''Return a package's .desktop file.

    If given package is installed and has a single .desktop file, return the
    path to it, otherwise return None.
    '''
    if package is None:
        return None

    desktopfile = None

    for line in packaging.get_files(package):
        if line.endswith('.desktop'):
            if desktopfile:
                return None # more than one
            else:
                desktopfile = line

    return desktopfile

def likely_packaged(file):
    '''Check whether the given file is likely to belong to a package.

    This is semi-decidable: A return value of False is definitive, a True value
    is only a guess which needs to be checked with find_file_package().
    However, this function is very fast and does not access the package
    database.
    '''
    pkg_whitelist = ['/bin/', '/boot', '/etc/', '/initrd', '/lib', '/sbin/',
    '/usr/', '/var'] # packages only ship executables in these directories

    whitelist_match = False
    for i in pkg_whitelist:
        if file.startswith(i):
            whitelist_match = True
            break
    return whitelist_match and not file.startswith('/usr/local/') and not \
        file.startswith('/var/lib/')

def find_file_package(file):
    '''Return the package that ships the given file.
    
    Return None if no package ships it.
    '''
    # resolve symlinks in directories
    (dir, name) = os.path.split(file)
    resolved_dir = os.path.realpath(dir)
    if os.path.isdir(resolved_dir):
        file = os.path.join(resolved_dir, name)

    if not likely_packaged(file):
        return None

    return packaging.get_file_package(file)

def seen_report(report):
    '''Check whether the report file has already been processed earlier.'''

    st = os.stat(report)
    return (st.st_atime > st.st_mtime) or (st.st_size == 0)

def mark_report_seen(report):
    '''Mark given report file as seen.'''

    st = os.stat(report)
    try:
        os.utime(report, (st.st_mtime, st.st_mtime-1))
    except OSError:
        # file is probably not our's, so do it the slow and boring way
        # change the file's access time until it stat's different than the mtime.
        # This might take a while if we only have 1-second resolution. Time out
        # after 1.2 seconds.
        timeout = 12
        while timeout > 0:
            f = open(report)
            f.read(1)
            f.close()
            try:
                st = os.stat(report)
            except OSError:
                return

            if st.st_atime > st.st_mtime:
                break
            time.sleep(0.1)
            timeout -= 1

        if timeout == 0:
            # happens on noatime mounted partitions; just give up and delete
            delete_report(report)

def get_all_reports():
    '''Return a list with all report files accessible to the calling user.'''

    reports = []
    for r in glob.glob(os.path.join(report_dir, '*.crash')):
        try:
            if os.path.getsize(r) > 0 and os.access(r, os.R_OK):
                reports.append(r)
        except OSError:
            # race condition, can happen if report disappears between glob and
            # stat
            pass
    return reports

def get_new_reports():
    '''Get new reports for calling user.

    Return a list with all report files which have not yet been processed
    and are accessible to the calling user.
    '''
    reports = []
    for r in get_all_reports():
        try:
            if not seen_report(r):
                reports.append(r)
        except OSError:
            # race condition, can happen if report disappears between glob and
            # stat
            pass
    return reports

def get_all_system_reports():
    '''Get all system reports.

    Return a list with all report files which belong to a system user (i. e.
    uid < 500 according to LSB).
    '''
    reports = []
    for r in glob.glob(os.path.join(report_dir, '*.crash')):
        try:
            if os.path.getsize(r) > 0 and os.stat(r).st_uid < 500:
                reports.append(r)
        except OSError:
            # race condition, can happen if report disappears between glob and
            # stat
            pass
    return reports

def get_new_system_reports():
    '''Get new system reports.

    Return a list with all report files which have not yet been processed
    and belong to a system user (i. e. uid < 500 according to LSB).
    '''
    return [r for r in get_all_system_reports() if not seen_report(r)]

def delete_report(report):
    '''Delete the given report file.

    If unlinking the file fails due to a permission error (if report_dir is not
    writable to normal users), the file will be truncated to 0 bytes instead.
    '''
    try:
        os.unlink(report)
    except OSError:
        open(report, 'w').truncate(0)

def get_recent_crashes(report):
    '''Return the number of recent crashes for the given report file.

    Return the number of recent crashes (currently, crashes which happened more
    than 24 hours ago are discarded).
    '''
    pr = ProblemReport()
    pr.load(report, False)
    try:
        count = int(pr['CrashCounter'])
        report_time = time.mktime(time.strptime(pr['Date']))
        cur_time = time.mktime(time.localtime())
        # discard reports which are older than 24 hours
        if cur_time - report_time > 24*3600:
            return 0
        return count
    except (ValueError, KeyError):
        return 0

def make_report_path(report, uid=None):
    '''Construct a canonical pathname for the given report.

    If uid is not given, it defaults to the uid of the current process.
    '''
    if report.has_key('ExecutablePath'):
        subject = report['ExecutablePath'].replace('/', '_')
    elif report.has_key('Package'):
        subject = report['Package'].split(None, 1)[0]
    else:
        raise ValueError('report has neither ExecutablePath nor Package attribute')

    if not uid:
        uid = os.getuid()

    return os.path.join(report_dir, '%s.%s.crash' % (subject, str(uid)))

def check_files_md5(sumfile):
    '''Check file integrity against md5 sum file.

    sumfile must be md5sum(1) format (relative to /).

    Return a list of files that don't match.
    '''
    assert os.path.exists(sumfile)
    m = subprocess.Popen(['/usr/bin/md5sum', '-c', sumfile],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        cwd='/', env={})
    out = m.communicate()[0]

    # if md5sum succeeded, don't bother parsing the output
    if m.returncode == 0:
        return []

    mismatches = []
    for l in out.splitlines():
        if l.endswith('FAILED'):
            mismatches.append(l.rsplit(':', 1)[0])

    return mismatches

def get_config(section, setting, default=None, bool=False):
    '''Return a setting from user configuration.

    This is read from ~/.config/apport/settings. If bool is True, the value is
    interpreted as a boolean.
    '''
    if not get_config.config:
        get_config.config = ConfigParser()
        get_config.config.read(os.path.expanduser(_config_file))

    try:
        if bool:
            return get_config.config.getboolean(section, setting)
        else:
            return get_config.config.get(section, setting)
    except (NoOptionError, NoSectionError):
        return default

get_config.config = None

#
# Unit test
#

import unittest, tempfile, os, shutil, sys, time
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

class _T(unittest.TestCase):
    def setUp(self):
        global report_dir
        global _config_file
        self.orig_report_dir = report_dir
        report_dir = tempfile.mkdtemp()
        self.orig_config_file = _config_file

    def tearDown(self):
        global report_dir
        global _config_file
        shutil.rmtree(report_dir)
        report_dir = self.orig_report_dir
        self.orig_report_dir = None
        _config_file = self.orig_config_file

    def _create_reports(self, create_inaccessible = False):
        '''Create some test reports.'''

        r1 = os.path.join(report_dir, 'rep1.crash')
        r2 = os.path.join(report_dir, 'rep2.crash')

        open(r1, 'w').write('report 1')
        open(r2, 'w').write('report 2')
        os.chmod(r1, 0o600)
        os.chmod(r2, 0o600)
        if create_inaccessible:
            ri = os.path.join(report_dir, 'inaccessible.crash')
            open(ri, 'w').write('inaccessible')
            os.chmod(ri, 0)
            return [r1, r2, ri]
        else:
            return [r1, r2]

    def test_find_package_desktopfile(self):
        '''find_package_desktopfile().'''

        # package without any .desktop file
        nodesktop = 'bash'
        assert len([f for f in packaging.get_files(nodesktop)
            if f.endswith('.desktop')]) == 0

        # find a package with one and a package with multiple .desktop files
        onedesktop = None
        multidesktop = None
        for d in os.listdir('/usr/share/applications/'):
            if not d.endswith('.desktop'):
                continue
            pkg = packaging.get_file_package(
                os.path.join('/usr/share/applications/', d))
            num = len([f for f in packaging.get_files(pkg)
                if f.endswith('.desktop')])
            if not onedesktop and num == 1:
                onedesktop = pkg
            elif not multidesktop and num > 1:
                multidesktop = pkg

            if onedesktop and multidesktop:
                break

        if nodesktop:
            self.assertEqual(find_package_desktopfile(nodesktop), None, 'no-desktop package %s' % nodesktop)
        if multidesktop:
            self.assertEqual(find_package_desktopfile(multidesktop), None, 'multi-desktop package %s' % multidesktop)
        if onedesktop:
            d = find_package_desktopfile(onedesktop)
            self.assertNotEqual(d, None, 'one-desktop package %s' % onedesktop)
            self.assertTrue(os.path.exists(d))
            self.assertTrue(d.endswith('.desktop'))

    def test_likely_packaged(self):
        '''likely_packaged().'''

        self.assertEqual(likely_packaged('/bin/bash'), True)
        self.assertEqual(likely_packaged('/usr/bin/foo'), True)
        self.assertEqual(likely_packaged('/usr/local/bin/foo'), False)
        self.assertEqual(likely_packaged('/home/test/bin/foo'), False)
        self.assertEqual(likely_packaged('/tmp/foo'), False)
        # ignore crashes in /var/lib (LP#122859, LP#414368)
        self.assertEqual(likely_packaged('/var/lib/foo'), False)

    def test_find_file_package(self):
        '''find_file_package().'''

        self.assertEqual(find_file_package('/bin/bash'), 'bash')
        self.assertEqual(find_file_package('/bin/cat'), 'coreutils')
        self.assertEqual(find_file_package('/nonexisting'), None)

    def test_seen(self):
        '''get_new_reports() and seen_report().'''

        self.assertEqual(get_new_reports(), [])
        if os.getuid() == 0:
            tr = self._create_reports(True)
        else:
            tr = [r for r in self._create_reports(True) if not 'inaccessible' in r]
        self.assertEqual(set(get_new_reports()), set(tr))

        # now mark them as seen and check again
        nr = set(tr)
        for r in tr:
            self.assertEqual(seen_report(r), False)
            nr.remove(r)
            mark_report_seen(r)
            self.assertEqual(seen_report(r), True)
            self.assertEqual(set(get_new_reports()), nr)

    def test_get_all_reports(self):
        '''get_all_reports().'''

        self.assertEqual(get_all_reports(), [])
        if os.getuid() == 0:
            tr = self._create_reports(True)
        else:
            tr = [r for r in self._create_reports(True) if not 'inaccessible' in r]
        self.assertEqual(set(get_all_reports()), set(tr))

        # now mark them as seen and check again
        for r in tr:
            mark_report_seen(r)

        self.assertEqual(set(get_all_reports()), set(tr))

    def test_get_system_reports(self):
        '''get_all_system_reports() and get_new_system_reports().'''

        self.assertEqual(get_all_reports(), [])
        self.assertEqual(get_all_system_reports(), [])
        if os.getuid() == 0:
            tr = self._create_reports(True)
            self.assertEqual(set(get_all_system_reports()), set(tr))
            self.assertEqual(set(get_new_system_reports()), set(tr))

            # now mark them as seen and check again
            for r in tr:
                mark_report_seen(r)

            self.assertEqual(set(get_all_system_reports()), set(tr))
            self.assertEqual(set(get_new_system_reports()), set([]))
        else:
            tr = [r for r in self._create_reports(True) if not 'inaccessible' in r]
            self.assertEqual(set(get_all_system_reports()), set([]))
            self.assertEqual(set(get_new_system_reports()), set([]))

    def test_delete_report(self):
        '''delete_report().'''

        tr = self._create_reports()

        while tr:
            self.assertEqual(set(get_all_reports()), set(tr))
            delete_report(tr.pop())

    def test_get_recent_crashes(self):
        '''get_recent_crashes().'''

        # incomplete fields
        r = StringIO('''ProblemType: Crash''')
        self.assertEqual(get_recent_crashes(r), 0)

        r = StringIO('''ProblemType: Crash
Date: Wed Aug 01 00:00:01 1990''')
        self.assertEqual(get_recent_crashes(r), 0)

        # ancient report
        r = StringIO('''ProblemType: Crash
Date: Wed Aug 01 00:00:01 1990
CrashCounter: 3''')
        self.assertEqual(get_recent_crashes(r), 0)

        # old report (one day + one hour ago)
        r = StringIO('''ProblemType: Crash
Date: %s
CrashCounter: 3''' % time.ctime(time.mktime(time.localtime())-25*3600))
        self.assertEqual(get_recent_crashes(r), 0)

        # current report (one hour ago)
        r = StringIO('''ProblemType: Crash
Date: %s
CrashCounter: 3''' % time.ctime(time.mktime(time.localtime())-3600))
        self.assertEqual(get_recent_crashes(r), 3)

    def test_make_report_path(self):
        '''make_report_path().'''

        pr = ProblemReport()
        self.assertRaises(ValueError, make_report_path, pr)

        pr['Package'] = 'bash 1'
        self.assertTrue(make_report_path(pr).startswith('%s/bash' % report_dir))
        pr['ExecutablePath'] = '/bin/bash';
        self.assertTrue(make_report_path(pr).startswith('%s/_bin_bash' % report_dir))

    def test_check_files_md5(self):
        '''check_files_md5().'''

        f1 = os.path.join(report_dir, 'test 1.txt')
        f2 = os.path.join(report_dir, 'test:2.txt')
        sumfile = os.path.join(report_dir, 'sums.txt')
        open(f1, 'w').write('Some stuff')
        open(f2, 'w').write('More stuff')
        # use one relative and one absolute path in checksums file
        open(sumfile, 'w').write('''2e41290da2fa3f68bd3313174467e3b5  %s
f6423dfbc4faf022e58b4d3f5ff71a70  %s
''' % (f1[1:], f2))
        self.assertEqual(check_files_md5(sumfile), [], 'correct md5sums')

        open(f1, 'w').write('Some stuff!')
        self.assertEqual(check_files_md5(sumfile), [f1[1:]], 'file 1 wrong')
        open(f2, 'w').write('More stuff!')
        self.assertEqual(check_files_md5(sumfile), [f1[1:], f2], 'files 1 and 2 wrong')
        open(f1, 'w').write('Some stuff')
        self.assertEqual(check_files_md5(sumfile), [f2], 'file 2 wrong')

    def test_get_config(self):
        '''get_config().'''

        global _config_file

        # nonexisting
        _config_file = '/nonexisting'
        self.assertEqual(get_config('main', 'foo'), None)
        self.assertEqual(get_config('main', 'foo', 'moo'), 'moo')
        get_config.config = None # trash cache

        # empty
        f = tempfile.NamedTemporaryFile()
        _config_file = f.name
        self.assertEqual(get_config('main', 'foo'), None)
        self.assertEqual(get_config('main', 'foo', 'moo'), 'moo')
        get_config.config = None # trash cache

        # nonempty
        f.write('[main]\none=1\ntwo = TWO\nb1 = 1\nb2=False\n[spethial]\none= 99\n')
        f.flush()
        self.assertEqual(get_config('main', 'foo'), None)
        self.assertEqual(get_config('main', 'foo', 'moo'), 'moo')
        self.assertEqual(get_config('main', 'one'), '1')
        self.assertEqual(get_config('main', 'one', default='moo'), '1')
        self.assertEqual(get_config('main', 'two'), 'TWO')
        self.assertEqual(get_config('main', 'b1', bool=True), True)
        self.assertEqual(get_config('main', 'b2', bool=True), False)
        self.assertEqual(get_config('main', 'b3', bool=True), None)
        self.assertEqual(get_config('main', 'b3', default=False, bool=True), False)
        self.assertEqual(get_config('spethial', 'one'), '99')
        self.assertEqual(get_config('spethial', 'two'), None)
        self.assertEqual(get_config('spethial', 'one', 'moo'), '99')
        self.assertEqual(get_config('spethial', 'nope', 'moo'), 'moo')
        get_config.config = None # trash cache

        f.close()

if __name__ == '__main__':
    unittest.main()
