'''Apport package hook for the Linux kernel.

(c) 2008 Canonical Ltd.
Contributors:
Matt Zimmerman <mdz@canonical.com>
Martin Pitt <martin.pitt@canonical.com>
Brian Murray <brian@canonical.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.
'''

import os.path
import subprocess
from apport.hookutils import *

SUBMIT_SCRIPT = "/usr/bin/kerneloops-submit"

def add_info(report, ui):

    # If running an upstream kernel, instruct reporter to file bug upstream
    abi = re.search("-(.*?)-", report['Uname'])
    if abi and (abi.group(1) == '999' or re.search("^0", abi.group(1))):
        ui.information("It appears you are currently running a mainline kernel.  It would be better to report this bug upstream at http://bugzilla.kernel.org/ so that the upstream kernel developers are aware of the issue.  If you'd still like to file a bug against the Ubuntu kernel, please boot with an official Ubuntu kernel and re-file.")
        report['UnreportableReason'] = 'The running kernel is not an Ubuntu kernel'
        return

    version_signature = report.get('ProcVersionSignature', '')
    if not version_signature.startswith('Ubuntu '):
        report['UnreportableReason'] = 'The running kernel is not an Ubuntu kernel'
        return

    # Prevent reports against linux-meta
    if report['SourcePackage'] == 'linux-meta':
        report['SourcePackage'] = 'linux'

    report.setdefault('Tags', '')

    attach_hardware(report)
    attach_alsa(report)
    attach_wifi(report)
    report['AcpiTables'] = root_command_output(['/usr/share/apport/dump_acpi_tables.py'])

    staging_drivers = re.findall("(\w+): module is from the staging directory", report['BootDmesg'])
    staging_drivers.extend(re.findall("(\w+): module is from the staging directory", report['CurrentDmesg']))
    if staging_drivers:
        staging_drivers = list(set(staging_drivers))
        report['StagingDrivers'] = ' '.join(staging_drivers)
        report['Tags'] += ' staging'
        # Only if there is an existing title prepend '[STAGING]'.
        # Changed to prevent bug titles with just '[STAGING] '.
        if report.get('Title'):
            report['Title'] = '[STAGING] ' + report.get('Title')

    attach_file_if_exists(report, "/etc/initramfs-tools/conf.d/resume", key="HibernationDevice")

    uname_release = os.uname()[2]
    lrm_package_name = 'linux-restricted-modules-%s' % uname_release
    lbm_package_name = 'linux-backports-modules-%s' % uname_release

    attach_related_packages(report, [lrm_package_name, lbm_package_name, 'linux-firmware'])

    if ('Failure' in report and report['Failure'] == 'oops'
            and 'OopsText' in report and os.path.exists(SUBMIT_SCRIPT)):
        # tag kerneloopses with the version of the kerneloops package
        attach_related_packages(report, ['kerneloops-daemon'])
        #it's from kerneloops, ask the user whether to submit there as well
        if ui is not None:
            summary = report['OopsText']
            # Some OopsText begin with "--- [ cut here ] ---", so remove it
            summary = re.sub("---.*\n", "", summary)
            first_line = re.match(".*\n", summary)
            ip = re.search("(R|E)?IP\:.*\n", summary)
            kernel_driver = re.search("(R|E)?IP(:| is at) .*\[(.*)\]\n", summary)
            call_trace = re.search("Call Trace(.*\n){,10}", summary)
            oops = ''
            if first_line:
                oops += first_line.group(0)
            if ip:
                oops += ip.group(0)
            if call_trace:
                oops += call_trace.group(0)
            if kernel_driver:
                report['Tags'] += ' kernel-driver-%s' % kernel_driver.group(3)
            if ui.yesno("This report may also be submitted to "
                "http://kerneloops.org/ in order to help collect aggregate "
                "information about kernel problems. This aids in identifying "
                "widespread issues and problematic areas. A condensed "
                "summary of the Oops is shown below.  Would you like to submit "
                "information about this crash to kerneloops.org ?"
                "\n\n%s" % oops):
                text = report['OopsText']
                proc = subprocess.Popen(SUBMIT_SCRIPT, stdin=subprocess.PIPE)
                proc.communicate(text)

    if report.get('ProblemType') == 'Package':
        # in case there is a failure with a grub script
        attach_related_packages(report, ['grub-pc'])
