'''Apport package hook for the ubiquity live CD installer.

Copyright (C) 2009 Canonical Ltd.
Authors: Colin Watson <cjwatson@ubuntu.com>,
         Brian Murray <brian@ubuntu.com>'''

import apport.hookutils
import os.path
import re

def add_installation_log(report, ident, name):
    if os.path.exists('/var/log/installer/%s' % name):
        f = '/var/log/installer/%s' % name
    elif os.path.exists('/var/log/%s' % name):
        f = '/var/log/%s' % name
    else:
        return

    if os.access(f, os.R_OK):
        report[ident] = open(f, 'r').read()
    elif os.path.exists(f):
        apport.hookutils.attach_root_command_outputs(report,
            {ident: "cat '%s'" % f})


def prepare_duplicate_signature(syslog, collect_grub, collect_trace):
    collect = ''
    for line in syslog.split('\n'):
        if collect_grub:
            if 'grub-installer:' in line and collect == "":
                collect = ' '.join(line.split(' ')[4:]) + '\n'
                continue
            elif 'grub-installer:' in line and collect != "":
                collect += ' '.join(line.split(' ')[4:]) + '\n'
                continue
        if not collect_trace and collect != '':
            return collect
        if 'Traceback (most recent call last):' in line and \
                collect_grub:
            collect += ' '.join(line.split(' ')[5:]) + '\n'
            continue
        if 'Traceback (most recent call last):' in line and \
                not collect_grub:
            collect = ' '.join(line.split(' ')[5:]) + '\n'
            continue
        if len(line.split(' ')[5:]) == 1 and 'Traceback' in collect:
            if collect != '':
                return collect
        if not 'Traceback' in collect:
            continue
        collect += ' '.join(line.split(' ')[5:]) + '\n'


def add_info(report, ui):
    add_installation_log(report, 'UbiquitySyslog', 'syslog')
    syslog = report['UbiquitySyslog']
    if 'Buffer I/O error on device' in syslog:
        if re.search('Attached .* CD-ROM (\w+)', syslog):
            cd_drive = re.search('Attached .* CD-ROM (\w+)', syslog).group(1)
            cd_error = re.search('Buffer I/O error on device %s' % cd_drive,
                syslog)
        if cd_error:
            ui.information("The system log from your installation contains an error.  The specific error commonly occurs when there is an issue with the media from which you were installing.  This can happen when your media is dirty or damaged or when you've burned the media at a high speed.  Please try cleaning the media and or burning new media at a lower speed.  In the event that you continue to encounter these errors it may be an issue with your CD / DVD drive.")
            raise StopIteration
    if 'SQUASHFS error: Unable to read' in syslog:
        ui.information("The system log from your installation contains an error.  The specific error commonly occurs when there is an issue with the media from which you were installing.  This can happen when your media is dirty or damaged or when you've burned the media at a high speed.  Please try cleaning the media and or burning new media at a lower speed.  In the event that you continue to encounter these errors it may be an issue with your CD / DVD drive.")
        raise StopIteration

    if report['ProblemType'] != 'Bug' and not 'Traceback' in report:
        collect_grub = False
        collect_trace = False
        if not 'grub-installer: Installation finished. No error reported' in syslog and 'grub-installer:' in syslog:
            collect_grub = True
        if 'Traceback' in syslog:
            collect_trace = True
        if collect_grub or collect_trace:
            duplicate_signature = prepare_duplicate_signature(syslog,
                collect_grub, collect_trace)
            if duplicate_signature:
                report['DuplicateSignature'] = duplicate_signature
        if collect_grub:
            report['SourcePackage'] = 'grub-installer'

    match = re.search('ubiquity.*Ubiquity (.*)\n', report['UbiquitySyslog'])
    if match:
        match = match.group(1)
    report.setdefault('Tags', '')
    if match:
        report['Tags'] += ' ubiquity-%s' % match.split()[0]

    add_installation_log(report, 'UbiquityPartman', 'partman')
    if os.path.exists('/var/log/installer/debug'):
        response = ui.yesno("The debug log file from your installation would help us a lot but includes the password you used for your user when installing Ubuntu.  Do you want to include this log file?")
        if response is None:
            raise StopIteration
        if response:
            add_installation_log(report, 'UbiquityDebug', 'debug')
    add_installation_log(report, 'UbiquityDm', 'dm')
    add_installation_log(report, 'Casper', 'casper.log')
    add_installation_log(report, 'OemConfigLog', 'oem-config.log')
    if 'OemConfigLog' in report:
        report['Tags'] += ' oem-config'
