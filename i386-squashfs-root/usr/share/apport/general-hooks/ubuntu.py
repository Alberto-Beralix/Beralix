'''Attach generally useful information, not specific to any package.

Copyright (C) 2009 Canonical Ltd.
Authors: Matt Zimmerman <mdz@canonical.com>,
         Brian Murray <brian@ubuntu.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.
'''

import apport.packaging
import re, os, os.path, pwd, time
from urlparse import urljoin
from urllib2 import urlopen
from apport.hookutils import *
from apport import unicode_gettext as _

def add_info(report, ui):
    add_release_info(report)

    add_kernel_info(report)

    add_cloud_info(report)

    report['ApportVersion'] = apport.packaging.get_version('apport')

    if report.get('ProblemType') == 'Package':
        check_for_disk_error(report)

    match_error_messages(report)

    for log in ['DpkgTerminalLog', 'VarLogDistupgradeApttermlog']:
        if log in report:
            check_attachment_for_errors(report, log)

    wrong_grub_msg = _('''Your system was initially configured with grub version 2, but you have removed it from your system in favor of grub 1 without configuring it.  To ensure your bootloader configuration is updated whenever a new kernel is available, open a terminal and run:

  sudo apt-get install grub-pc
''')

    if 'DpkgTerminalLog' in report \
       and re.search(r'^Not creating /boot/grub/menu.lst as you wish', report['DpkgTerminalLog'], re.MULTILINE):
        grub_hook_failure = True
    else:
        grub_hook_failure = False

    # crash reports from live system installer often expose target mount
    for f in ('ExecutablePath', 'InterpreterPath'):
        if f in report and report[f].startswith('/target/'):
            report[f] = report[f][7:]

    # Allow filing update-manager bugs with obsolete packages
    if report.get('Package', '').startswith('update-manager'):
        os.environ['APPORT_IGNORE_OBSOLETE_PACKAGES'] = '1'

    # file bugs against OEM project for modified packages
    if 'Package' in report:
        v = report['Package'].split()[1]
        oem_project = get_oem_project(report)
        if oem_project and ('common' in v or oem_project in v):
            report['CrashDB'] = 'canonical-oem'

    if 'Package' in report:
        package = report['Package'].split()[0]
        if package:
            attach_conffiles(report, package, ui=ui)

        # do not file bugs against "upgrade-system" if it is not installed (LP#404727)
        if package == 'upgrade-system' and 'not installed' in report['Package']:
            report['UnreportableReason'] = 'You do not have the upgrade-system package installed. Please report package upgrade failures against the package that failed to install, or against upgrade-manager.'

    if 'Package' in report:
        package = report['Package'].split()[0]
        if package:
            attach_upstart_overrides(report, package)

    # build a duplicate signature tag for package reports
    if report.get('ProblemType') == 'Package':
        if 'DpkgTerminalLog' in report:
            termlog = report['DpkgTerminalLog']
        elif 'VarLogDistupgradeApttermlog' in report:
            termlog = report['VarLogDistupgradeApttermlog']
        else:
            termlog = None
        if termlog:
            dupe_sig = ''
            for line in termlog.split('\n'):
                if line.startswith('Setting up') or line.startswith('Unpacking'):
                    dupe_sig = '%s\n' % line
                    continue
                dupe_sig += '%s\n' % line
                if 'dpkg: error' in dupe_sig and line.startswith(' '):
                    if 'trying to overwrite' in line:
                        conflict_pkg = re.search('in package (.*) ', line)
                        if conflict_pkg and not apport.packaging.is_distro_package(conflict_pkg.group(1)):
                            report['UnreportableReason'] = _('An Ubuntu package has a file conflict with a package that is not a genuine Ubuntu package')
                        add_tag(report, 'package-conflict')
                    if 'Setting up' in dupe_sig or 'Unpacking' in dupe_sig:
                        report['DuplicateSignature'] = dupe_sig
                        # the duplicate signature should be the first failure
                        break

    # running Unity?
    username = pwd.getpwuid(os.geteuid()).pw_name
    if subprocess.call(['killall', '-s0', '-u', username,
	'unity-panel-service'], stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT) == 0:
        add_tag(report, 'running-unity')


def match_error_messages(report):
    # There are enough of these now that it is probably worth refactoring...
    # -mdz
    if report['ProblemType'] == 'Package':
        if 'failed to install/upgrade: corrupted filesystem tarfile' in report.get('Title', ''):
            report['UnreportableReason'] = 'This failure was caused by a corrupted package download or file system corruption.'

        if 'is already installed and configured' in report.get('ErrorMessage', ''):
            report['SourcePackage'] = 'dpkg'


def check_attachment_for_errors(report, attachment):
    if report['ProblemType'] == 'Package':
        trim_dpkg_log(report)

        if report['Package'] not in ['grub', 'grub2']:
            # linux-image postinst emits this when update-grub fails
            # https://wiki.ubuntu.com/KernelTeam/DebuggingUpdateErrors
            grub_errors = [r'^User postinst hook script \[.*update-grub\] exited with value',
                r'^run-parts: /etc/kernel/post(inst|rm).d/zz-update-grub exited with return code [1-9]+',
                r'^/usr/sbin/grub-probe: error']

            for grub_error in grub_errors:
                if attachment in report and re.search(grub_error, report[attachment], re.MULTILINE):
                    # File these reports on the grub package instead
                    grub_package = apport.packaging.get_file_package('/usr/sbin/update-grub')
                    if grub_package is None or grub_package == 'grub' and not 'grub-probe' in report[attachment]:
                        report['SourcePackage'] = 'grub'
                        if os.path.exists('/boot/grub/grub.cfg') \
                           and grub_hook_failure:
                            report['UnreportableReason'] = wrong_grub_msg
                    else:
                        report['SourcePackage'] = 'grub2'

        if report['Package'] != 'initramfs-tools':
            # update-initramfs emits this when it fails, usually invoked from the linux-image postinst
            # https://wiki.ubuntu.com/KernelTeam/DebuggingUpdateErrors
            if attachment in report and re.search(r'^update-initramfs: failed for ', report[attachment], re.MULTILINE):
                # File these reports on the initramfs-tools package instead
                report['SourcePackage'] = 'initramfs-tools'

        if report['Package'] in ['emacs22', 'emacs23', 'emacs-snapshot', 'xemacs21']:
            # emacs add-on packages trigger byte compilation, which might fail
            # we are very interested in reading the compilation log to determine
            # where to reassign this report to
            regex = r'^!! Byte-compilation for x?emacs\S+ failed!'
            if attachment in report and re.search(regex, report[attachment], re.MULTILINE):
                for line in report[attachment].split('\n'):
                    m = re.search(r'^!! and attach the file (\S+)', line)
                    if m:
                        path = m.group(1)
                        attach_file_if_exists(report, path)

        if report['Package'].startswith('linux-image-') and attachment in report:
            # /etc/kernel/*.d failures from kernel package postinst
            m = re.search(r'^run-parts: (/etc/kernel/\S+\.d/\S+) exited with return code \d+', report[attachment], re.MULTILINE)
            if m:
                path = m.group(1)
                package = apport.packaging.get_file_package(path)
                if package:
                    report['SourcePackage'] = package
                    report['ErrorMessage'] = m.group(0)
                    if package == 'grub-pc' and grub_hook_failure:
                        report['UnreportableReason'] = wrong_grub_msg
                else:
                    report['UnreportableReason'] = 'This failure was caused by a program which did not originate from Ubuntu'

        if 'failed to install/upgrade: corrupted filesystem tarfile' in report.get('Title', ''):
            report['UnreportableReason'] = 'This failure was caused by a corrupted package download or file system corruption.'

        if 'is already installed and configured' in report.get('ErrorMessage', ''):
            report['SourcePackage'] = 'dpkg'

def check_for_disk_error(report):
    devs_to_check = []
    if not 'Dmesg.txt' in report and not 'CurrentDmesg.txt' in report:
        return
    if not 'Df.txt' in report:
        return
    df = report['Df.txt']
    for line in df:
        line = line.strip('\n')
        if line.endswith('/') or line.endswith('/usr') or line.endswith('/var'):
            # without manipulation it'd look like /dev/sda1
            device = line.split(' ')[0].strip('0123456789')
            device = device.replace('/dev/', '')
            devs_to_check.append(device)
    dmesg = report.get('CurrentDmesg.txt', report['Dmesg.txt'])
    for line in dmesg:
        line = line.strip('\n')
        if 'I/O error' in line:
            # no device in this line
            if 'journal commit I/O error' in line:
                continue
            if not 'JBD2' in line:
                error_device = line.split(' ')[6].strip(',')
            elif 'JBD2' in line:
                error_device = line.split(' ')[-1].split('-')[0]
                error_device = error_device.strip('0123456789')
            if error_device in devs_to_check:
                report['UnreportableReason'] = 'This failure was caused by a hardware error on /dev/%s' % error_device


def add_kernel_info(report):
    # This includes the Ubuntu packaged kernel version
    attach_file_if_exists(report, '/proc/version_signature', 'ProcVersionSignature')

def add_release_info(report):
    # https://bugs.launchpad.net/bugs/364649
    attach_file_if_exists(report, '/var/log/installer/media-info',
                          'InstallationMedia')

    # if we are running from a live system, add the build timestamp
    attach_file_if_exists(report, '/cdrom/.disk/info', 'LiveMediaBuild')
    if os.path.exists('/cdrom/.disk/info'):
        report['CasperVersion'] = apport.packaging.get_version('casper')


    # https://wiki.ubuntu.com/FoundationsTeam/Specs/OemTrackingId
    attach_file_if_exists(report, '/var/lib/ubuntu_dist_channel', 
        'DistributionChannelDescriptor')

    release_codename = command_output(['lsb_release', '-sc'])
    if release_codename.startswith('Error'):
        release_codename = None
    else:
        add_tag(report, release_codename)

    log ='/var/log/dist-upgrade/apt.log'
    if os.path.exists(log):
        mtime = os.stat(log).st_mtime
        human_mtime = time.strftime('%Y-%m-%d', time.gmtime(mtime))
        delta = time.time() - mtime
        
        # Would be nice if this also showed which release was originally installed
        report['UpgradeStatus'] = 'Upgraded to %s on %s (%d days ago)' % (release_codename, human_mtime, delta / 86400)
    else:
        report['UpgradeStatus'] = 'No upgrade log present (probably fresh install)'

def add_cloud_info(report):
    # EC2 and Ubuntu Enterprise Cloud instances
    ec2_instance = False
    for pkg in ('ec2-init', 'cloud-init'):
        try:
            if apport.packaging.get_version(pkg):
                ec2_instance = True
                break
        except ValueError:
            pass
    if ec2_instance:
        metadata_url = 'http://169.254.169.254/latest/meta-data/'
        ami_id_url = urljoin(metadata_url, 'ami-id')

        try:
            ami = urlopen(ami_id_url).read()
        except:
            ami = None

        if ami is None:
            cloud = None
        elif ami.startswith('ami'):
            cloud = 'ec2'
            add_tag(report, 'ec2-images')
            fields = { 'Ec2AMIManifest':'ami-manifest-path',
                       'Ec2Kernel':'kernel-id',
                       'Ec2Ramdisk':'ramdisk-id',
                       'Ec2InstanceType':'instance-type',
                       'Ec2AvailabilityZone':'placement/availability-zone' }

            report['Ec2AMI'] = ami
            for key,value in fields.items():
                try:
                    report[key]=urlopen(urljoin(metadata_url, value)).read()
                except:
                    report[key]='unavailable'
        else:
            cloud = 'uec'
            add_tag(report, 'uec-images')

def add_tag(report, tag):
    report.setdefault('Tags', '')
    report['Tags'] += ' ' + tag

def get_oem_project(report):
    '''Determine OEM project name from Distribution Channel Descriptor
    
    Return None if it cannot be determined or does not exist.
    '''
    dcd = report.get('DistributionChannelDescriptor', None)
    if dcd and dcd.startswith('canonical-oem-'):
        return dcd.split('-')[2]
    return None

def trim_dpkg_log(report):
    '''Trim DpkgTerminalLog to the most recent installation session.'''

    if 'DpkgTerminalLog' not in report:
        return
    lines = []
    trim_re = re.compile('^\(.* ... \d+ .*\)$')
    for line in report['DpkgTerminalLog'].splitlines():
        if line.startswith('Log started: ') or trim_re.match(line):
            lines = []
            continue
        lines.append(line)
    report['DpkgTerminalLog'] = '\n'.join(lines)

    if not report['DpkgTerminalLog'].strip():
        report['UnreportableReason'] = '/var/log/apt/term.log does not contain any data'

if __name__ == '__main__':
    import sys

    # for testing: update report file given on command line
    if len(sys.argv) != 2:
        print >> sys.stderr, 'Usage for testing this hook: %s <report file>' % sys.argv[0]
        sys.exit(1)

    report_file = sys.argv[1]

    report = apport.Report()
    report.load(open(report_file))
    report_keys = set(report.keys())

    new_report = report.copy()
    add_info(new_report, None)

    new_report_keys = set(new_report.keys())

    # Show differences   
    changed = 0
    for key in sorted(report_keys | new_report_keys):
        if key in new_report_keys and key not in report_keys:
            print "+%s: %s" % (key, new_report[key])
            changed += 1
        elif key in report_keys and key not in new_report_keys:
            print "-%s: (deleted)" % key
            changed += 1
    print "%d items changed" % changed
