#!/usr/bin/python

'''Xorg Apport interface

Copyright (C) 2007, 2008 Canonical Ltd.
Author: Bryce Harrington <bryce.harrington@ubuntu.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.

Testing:  APPORT_STAGING="yes"
'''

import os.path
import glob
import re
import subprocess
from apport.hookutils import *
from launchpadlib.launchpad import Launchpad

core_x_packages = [
    'xorg', 'xorg-server', 'xserver-xorg-core', 'mesa'
    ]
video_packages = [
    'xserver-xorg-video-intel', 'xserver-xorg-video-nouveau', 'xserver-xorg-video-ati',
    ]
keyboard_packages = [
    'xorg', 'xkb-data', 'xkeyboard-config', 'xserver-xorg-input-keyboard', 'xserver-xorg-input-evdev'
    ]
opt_debug = False

######
#
# Apport helper routines
#
######
def debug(text):
    if opt_debug:
        sys.stderr.write("%s\n" %(text))

def retrieve_ubuntu_release_statuses():
    '''
    Attempts to access launchpad to get a mapping of Ubuntu releases to status.

    Returns a dictionary of ubuntu release keywords to their current status,
    or None in case of a failure reading launchpad.
    '''
    releases = { }
    try:
        lp = Launchpad.login_anonymously('apport', 'production')
        d = lp.distributions['ubuntu']
        for series in d.series:
            releases[series.name] = series.status
    except:
        releases = None
    return releases

def installed_version(pkg):
    '''
    Queries apt for the version installed at time of filing
    '''
    script = subprocess.Popen(['apt-cache', 'policy', pkg], stdout=subprocess.PIPE)
    output = script.communicate()[0]
    return output.split('\n')[1].replace("Installed: ", "")

def is_process_running(proc):
    '''
    Determine if process has a registered process id
    '''
    log = command_output(['pidof', proc])
    if not log or log[:5] == "Error" or len(log)<1:
        return False
    return True

def is_xorg_input_package(pkg):
    if (pkg == 'xkeyboard-config' or
        pkg == 'xkb-data' or
        pkg[:18] == 'xserver-xorg-input' or
        pkg[:10] == 'xf86-input'):
        return True
    else:
        return False

def is_xorg_video_package(pkg):
    if (pkg[:18] == 'xserver-xorg-video' or
        pkg[:6] == 'nvidia' or
        pkg[:5] == 'fglrx' or
        pkg[:10] == 'xf86-video'):
        return True
    else:
        return False

def nonfree_graphics_module(module_list = '/proc/modules'):
    '''
    Check loaded modules to see if a proprietary graphics driver is loaded.
    Return the first such driver found.
    '''
    try:
        mods = [l.split()[0] for l in open(module_list)]
    except IOError:
        return None

    for m in mods:
        if m == "nvidia" or m == "fglrx":
            return m

def attach_command_output(report, command_list, key):
    debug(" %s" %(' '.join(command_list)))
    log = command_output(command_list)
    if not log or log[:5] == "Error":
        return
    report[key] = log

def retval(command_list):
    '''
    Call the command and return the command exit code
    '''
    return subprocess.call(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def ubuntu_variant_name():
    '''
    Detect if system runs kubuntu by looking for kdesudo or ksmserver

    Returns 'ubuntu' or 'kubuntu' as appropriate.
    '''
    if (retval(['which', 'kdesudo']) == 0 and
        retval(['pgrep', '-x', '-u', str(os.getuid()), 'ksmserver']) == 0):
        return "kubuntu"
    else:
        return "ubuntu"

def ubuntu_code_name():
    '''
    Return the LSB ubuntu release code name, 'dapper', 'natty', etc.
    '''
    debug(" lsb_release -sc")
    code_name = command_output(['lsb_release','-sc'])
    if code_name[:5] == "Error":
        return None
    return code_name

######
#
# Supportability tests
#
######

def check_is_supported(report, ui=None):
    '''
    Bug reports against the development release are higher priority than
    ones filed against already released versions.  We steer reporters of
    the latter towards technical support resources, which are better geared
    for helping end users solve problems with their installations.
    '''
    distro_codename = ubuntu_code_name()
    report['DistroCodename'] = distro_codename
    report['DistroVariant'] = ubuntu_variant_name()
    report['Tags'] += ' ' + report['DistroVariant']

    if not ui:
        return

    # Look up status of this and other releases
    release_status = retrieve_ubuntu_release_statuses()
    if not release_status or not report['DistroCodename']:
        # Problem accessing launchpad, can't tell anything about status
        # so assume by default that it's supportable.
        return True
    status = release_status.get(distro_codename, "Unknown")

    if status == "Active Development":
        # Allow user to set flags for things that may help prioritize support
        response = ui.choice(
            "Thank you for testing the '%s' development version of Ubuntu.\n"
            "You may mark any of the following that apply to help us better\n"
            "process your issue." %(distro_codename),
            [
                "Regression",
                "Has happened more than once",
                "I can reproduce the bug",
                "I know a workaround",
                "I know the fix for this",
                ],
            multiple=True
            )
        if response == None:
            return False
        if 0 in response:
            # TODO: Prompt for what type of regression and when it started
            # Perhaps parse dpkg.log for update dates
            report['Tags'] += ' regression'
        if 1 not in response:
            report['Tags'] += ' single-occurrence'
        if 2 in response:
            report['Tags'] += ' reproducible'
        if 3 in response:
            report['Tags'] += ' has-workaround'
        if 4 in response:
            report['Tags'] += ' has-fix'
        return True

    elif status == "Obsolete":
        ui.information("Sorry, the '%s' version of Ubuntu is obsolete, which means the developers no longer accept bug reports about it." %(distro_codename))
        report['UnreportableReason'] = 'Unsupported Ubuntu Release'
        return False

    elif status == "Supported" or status == "Current Stable Release":
        # TODO: Perhaps avoid this check if the time since the release < 1 month?
        response = ui.choice(
            "Development is completed for the '%s' version of Ubuntu, so\n"
            "you should probably use technical support channels unless you know for\n"
            "certain it should be reported here?" %(distro_codename),
            [
                "I don't know",
                "Yes, I already know the fix for this problem.",
                "Yes, The problem began right after doing a system software update.",
                "Yes.",
                "No, please point me to a good place to get support.",
                ]
            )
        if response == None:
            return False

        # Fix is known
        if 1 in response:
            report['Tags'] += ' ' + 'patch'
            ui.information("Thanks for helping improve Ubuntu!  Tip:  If you attach the fix to the bug report as a patch, it will be flagged to the developers and should get a swifter response.")
            return True

        # Regression after a system update
        elif 2 in response:
            report['Tags'] += ' ' + 'regression-update'
            response = ui.yesno("Thanks for reporting this regression in Ubuntu %s.  Do you know exactly which package and version caused the regression?" %(distro_codename))
            if response:
                ui.information("Excellent.  Please make sure to list the package name and version in the bug report's description.  That is vital information for pinpointing the cause of the regression, which will make solving this bug go much faster.")
                report['Tags'] += ' ' + 'needs-reassignment'
                return True
            else:
                ui.information("Alright, please indicate roughly when you first started noticing the problem.  This information will help in narrowing down the suspect package updates.")
                return True

        # Referred by technical support
        elif 3 in response:
            ui.information("Thanks for using technical support channels before filing this report.  In your bug report, please restate the issue and include a link or transcript of your discussion with them.")
            return True

        # Anything else should be redirected to technical support channels
        else:
            ui.information("http://askubuntu.com is the best place to get free help with technical issues.\n\n"
                           "See http://www.ubuntu.com/support for paid support and other free options.")
            report['UnreportableReason'] = 'Please work this issue through technical support channels first.'
            return False
 
    return True

def check_is_reportable(report, ui=None):
    '''Checks system to see if there is any reason the configuration is not
    valid for filing bug reports'''

    version_signature = report.get('ProcVersionSignature', '')
    if version_signature and not version_signature.startswith('Ubuntu '):
        report['UnreportableReason'] = 'The running kernel is not an Ubuntu kernel: %s' %version_signature
        return False

    bios = report.get('dmi.bios.version', '')
    if bios.startswith('VirtualBox '):
        report['SourcePackage'] = "virtualbox-ose"
        return False

    product_name = report.get('dmi.product.name', '')
    if product_name.startswith('VMware '):
        report['UnreportableReason'] = 'VMware is installed.  If you upgraded X recently be sure to upgrade vmware to a compatible version.'
        return False

    if os.path.exists('/var/log/nvidia-installer.log'):
        # User has installed nVidia drivers manually at some point.
        # This is likely to have caused problems.
        if ui and not ui.yesno("""It appears you may have installed the nVidia drivers manually from nvidia.com at some point in the past.  This can cause problems with the Ubuntu-supplied drivers.

If you have not already uninstalled the drivers downloaded from nvidia.com, please uninstall them and reinstall the Ubuntu packages before filing a bug with Ubuntu.  If you have uninstalled them, then you may want to remove the file /var/log/nvidia-installer.log as well.

Have you uninstalled the drivers from nvidia.com?"""):
            report['UnreportableReason'] = 'The drivers from nvidia.com are not supported by Ubuntu.  Please uninstall them and test whether your problem still occurs.'
            return
        attach_file(report, '/var/log/nvidia-installer.log', 'nvidia-installer.log')
        report['Tags'] += ' ' + 'possible-manual-nvidia-install'

    return True

######
#
# Attach relevant data files
#
######

def attach_dkms_info(report, ui=None):
    '''
    DKMS is the dynamic kernel module service, for rebuilding modules
    against a new kernel on the fly, during boot.  Occasionally this fails
    such as when installing/upgrading with proprietary video drivers.
    '''
    if os.path.lexists('/var/lib/dkms'):
        # Gather any dkms make.log files for proprietary drivers
        for logfile in glob.glob("/var/lib/dkms/*/*/build/make.log"):
            attach_file(report, logfile, "make.log")
        attach_command_output(report, ['dkms', 'status'], 'DkmsStatus')

def attach_dist_upgrade_status(report, ui=None):
    '''
    This routine indicates whether a system was upgraded from a prior
    release of ubuntu, or was a fresh install of this release.
    '''
    attach_file_if_exists(report, "/var/log/dpkg.log", "DpkgLog")
    if os.path.lexists('/var/log/dist-upgrade/apt.log'):
        # TODO: Not sure if this is quite exactly what I want, but close...
        attach_command_output(
            report,
            ['head', '-n', '1', '/var/log/dist-upgrade/apt.log'],
            'DistUpgraded')
        return True
    else:
        report['DistUpgraded'] = 'Fresh install'
        return False

def attach_graphic_card_pci_info(report, ui=None):
    '''
    Extracts the device system and subsystem IDs for the video card.
    Note that the user could have multiple video cards installed, so
    this may return a multi-line string.
    '''
    info = ''
    display_pci = pci_devices(PCI_DISPLAY)
    for paragraph in display_pci.split('\n\n'):
        for line in paragraph.split('\n'):
            if ':' not in line:
                continue
            m = re.match(r'(.*?):\s(.*)', line)
            if not m:
                continue
            key, value = m.group(1), m.group(2)
            value = value.strip()
            key = key.strip()
            if "VGA compatible controller" in key:
                info += "%s\n" % (value)
            elif key == "Subsystem":
                info += "  %s: %s\n" %(key, value)
    report['GraphicsCard'] = info

def attach_xorg_package_versions(report, ui=None):
    '''
    Gathers versions for various X packages of interest
    '''
    for package in [
        "xserver-xorg",
        "libgl1-mesa-glx",
        "libgl1-mesa-dri",
        "libgl1-mesa-dri-experimental",
        "libdrm2",
        "compiz",
        "xserver-xorg-input-evdev",
        "xserver-xorg-video-intel",
        "xserver-xorg-video-ati",
        "xserver-xorg-video-nouveau"]:
        report['version.%s' %(package)] = package_versions(package)
    if 'Architecture' in report and report['Architecture'] == 'amd64':
        report['version.ia32-libs'] = package_versions('ia32-libs')

def attach_2d_info(report, ui=None):
    '''
    Attaches various data for debugging basic graphics issues.
    '''
    attach_file_if_exists(report, '/var/log/boot.log', 'BootLog')
    attach_file_if_exists(report, '/var/log/plymouth-debug.log', 'PlymouthDebug')
    attach_file_if_exists(report, '/etc/X11/xorg.conf', 'XorgConf')
    attach_file_if_exists(report, '/var/log/Xorg.0.log', 'XorgLog')
    attach_file_if_exists(report, '/var/log/Xorg.0.log.old', 'XorgLogOld')

    if os.environ.get('DISPLAY'):
        # For resolution/multi-head bugs
        attach_command_output(report, ['xrandr', '--verbose'], 'Xrandr')
        attach_file_if_exists(report,
                              os.path.expanduser('~/.config/monitors.xml'),
                              'MonitorsUser.xml')
        attach_file_if_exists(report,
                              '/etc/gnome-settings-daemon/xrandr/monitors.xml',
                              'MonitorsGlobal.xml')

        # For font dpi bugs
        attach_command_output(report, ['xdpyinfo'], 'xdpyinfo')

    if ui:
        display_manager_files = {}
        if os.path.lexists('/var/log/gdm'):
            display_manager_files['GdmLog'] = 'cat /var/log/gdm/:0.log'
            display_manager_files['GdmLog1'] = 'cat /var/log/gdm/:0.log.1'
            display_manager_files['GdmLog2'] = 'cat /var/log/gdm/:0.log.2'

        if os.path.lexists('/var/log/lightdm'):
            display_manager_files['LightdmLog'] = 'cat /var/log/lightdm/lightdm.log'
            display_manager_files['LightdmDisplayLog'] = 'cat /var/log/lightdm/:0.log'
            display_manager_files['LightdmGreeterLog'] = 'cat /var/log/lightdm/:0-greeter.log'

        if ui.yesno("Your display manager log files may help developers diagnose the bug, but may contain sensitive information such as your hostname.  Do you want to include these logs in your bug report?") == True:
            attach_root_command_outputs(report, display_manager_files)

def attach_3d_info(report, ui=None):
    # How are the alternatives set?
    attach_command_output(report, ['ls','-l','/etc/alternatives/gl_conf'], 'GlAlternative')

    # Detect software rasterizer
    xorglog = report.get('XorgLog', '')
    if len(xorglog)>0:
        if 'reverting to software rendering' in xorglog:
            report['Renderer'] = 'Software'
        elif 'Direct rendering disabled' in xorglog:
            report['Renderer'] = 'Software'

    if ui and report.get('Renderer', '') == 'Software':
        ui.information("Your system is providing 3D via software rendering rather than hardware rendering.  This is a compatibility mode which should display 3D graphics properly but the performance may be very poor.  If the problem you're reporting is related to graphics performance, your real question may be why X didn't use hardware acceleration for your system.")

    # Plugins
    attach_command_output(report, [
        'gconftool-2', '--get', '/apps/compiz-1/general/screen0/options/active_plugins'],
        'CompizPlugins')

    # User configuration
    attach_command_output(report, [
        'gconftool-2', '-R', '/apps/compiz-1'],
        'GconfCompiz')

    # Compiz internal state if compiz crashed
    if report.get('SourcePackage','Unknown') == "compiz" and report.has_key("ProcStatus"):
        compiz_pid = 0
        pid_line = re.search("Pid:\t(.*)\n", report["ProcStatus"])
        if pid_line:
            compiz_pid = pid_line.groups()[0]
        compiz_state_file = '/tmp/compiz_internal_state%s' % compiz_pid
        attach_file_if_exists(report, compiz_state_file, "compiz_internal_states")

    # Remainder of this routine requires X running
    if not os.environ.get('DISPLAY'):
        return

    # Unity test
    if os.path.lexists('/usr/lib/nux/unity_support_test'):
        try:
            debug(" unity_support_test")
            ust = command_output([
                '/usr/lib/nux/unity_support_test', '-p', '-f'])
            ust = ust.replace('\x1b','').replace('[0;38;48m','').replace('[1;32;48m','')
            report['UnitySupportTest'] = ust
        except AssertionError:
            report['UnitySupportTest'] = 'FAILED TO RUN'
        for testcachefile in glob.glob('/tmp/unity*'):
            attach_file(report, testcachefile)

    attach_file_if_exists(report,
                          os.path.expanduser('~/.drirc'),
                          'drirc')

    if (is_process_running('compiz') or
        (report.get('SourcePackage','Unknown') == "compiz" and report.get('ProblemType', '') == 'Crash')
        ):
        report['CompositorRunning'] = 'compiz'
        compiz_version = command_output(['compiz', '--version'])
        if compiz_version:
            version = compiz_version.split(' ')[1]
            version = version[:3]
            compiz_version_string = 'compiz-%s' % version
            report['Tags'] += ' ' + compiz_version_string
    elif is_process_running('kwin'):
        report['CompositorRunning'] = 'kwin'
    else:
        report['CompositorRunning'] = 'None'

def attach_input_device_info(report, ui=None):
    '''
    Gathers data for debugging keyboards, mice, and other input devices.
    '''
    # Only collect the following data if X11 is available
    if not os.environ.get('DISPLAY'):
        return

    # For input device bugs
    attach_command_output(report, ['xinput', '--list'], 'xinput')
    attach_command_output(report, ['gconftool-2', '-R', '/desktop/gnome/peripherals'], 'peripherals')

    # For keyboard bugs only
    if not report.get('SourcePackage','Unknown') in keyboard_packages:
        attach_command_output(report, ['setxkbmap', '-print'], 'setxkbmap')
        attach_command_output(report, ['xkbcomp', ':0', '-w0', '-'], 'xkbcomp')
        attach_command_output(report, ['locale'], 'locale')
        if ui and ui.yesno("Your kernel input device details (lsinput and dmidecode) may be useful to the developers, but gathering it requires admin privileges. Would you like to include this info?") == True:
            attach_root_command_outputs(report, {
                'lsinput.txt': 'lsinput',
                'dmidecode.txt': 'dmidecode',
                })

def attach_nvidia_info(report, ui=None):
    '''
    Gathers special files for the nvidia proprietary driver
    '''
    # Attach information for upstreaming nvidia binary bugs
    if nonfree_graphics_module() != 'nvidia':
        return
    
    report['version.nvidia-graphics-drivers'] = package_versions("nvidia-graphics-drivers")

    for logfile in glob.glob('/proc/driver/nvidia/*'):
        if os.path.isfile(logfile):
            attach_file(report, logfile)

    for logfile in glob.glob('/proc/driver/nvidia/*/*'):
        if os.path.basename(logfile) != 'README':
            attach_file(report, logfile)

    if os.path.lexists('/usr/lib/nvidia-current/bin/nvidia-bug-report.sh'):
        if retval(['/usr/lib/nvidia-current/bin/nvidia-bug-report.sh']) == 0:
            attach_file_if_exists(report, os.path.expanduser('~/nvidia-bug-report.log.gz'),
                                      'NvidiaBugReportLog')

    if os.environ.get('DISPLAY'):
        # Attach output of nvidia-settings --query if we've got a display
        # to connect to.
        attach_command_output(report, ['nvidia-settings', '-q', 'all'], 'nvidia-settings')

    attach_command_output(report, ['jockey-text', '-l'], 'JockeyStatus')
    attach_command_output(report, ['update-alternatives', '--display', 'gl_conf'], 'GlConf')

    # File any X crash with -nvidia involved with the -nvidia bugs
    if (report.get('ProblemType', '') == 'Crash' and 'Traceback' not in report):
        if report.get('SourcePackage','Unknown') in core_x_packages:
            report['SourcePackage'] = "nvidia-graphics-drivers"

def attach_fglrx_info(report, ui=None):
    '''
    Gathers special files for the fglrx proprietary driver
    '''
    if nonfree_graphics_module() != 'fglrx':
        return

    report['version.fglrx-installer'] = package_versions("fglrx-installer")

    attach_command_output(report, ['jockey-text', '-l'], 'JockeyStatus')
    attach_command_output(report, ['update-alternatives', '--display', 'gl_conf'], 'GlConf')

    # File any X crash with -fglrx involved with the -fglrx bugs
    if report.get('SourcePackage','Unknown') in core_x_packages:
        if (report.get('ProblemType', '') == 'Crash' and 'Traceback' not in report):
            report['SourcePackage'] = "fglrx-installer"

def attach_gpu_hang_info(report, ui):
    '''
    Surveys reporter for some additional clarification on GPU freezes
    '''
    if not ui:
        return
    if not 'freeze' in report['Tags']:
        return
    
    if not ui.yesno("Apport has detected a possible GPU hang.  Did your system recently lock up and/or require a hard reboot?"):
        # If user isn't experiencing freeze symptoms, the remaining questions aren't relevant
        report['Tags'] += ' false-gpu-hang'
        report['Title'] = report['Title'].replace('GPU lockup', 'False GPU lockup')
        return

    text = 'How frequently have you been experiencing lockups like this?'
    choices = [
        "I don't know",
        "This is the first time",
        "Very infrequently",
        "Once a week",
        "Several times a week",
        "Several times a day",
        "Continuously",
        ]
    response = ui.choice(text, choices)
    if response == None:
        raise StopIteration
    report['GpuHangFrequency'] = choices[response[0]]

    # Don't ask more questions if bug is infrequent
    if response < 3:
        return
    
    text = "When did you first start experiencing these lockups?"
    choices = [
        "I don't know",
        "Since before I upgraded",
        "Immediately after installing this version of Ubuntu",
        "Since a couple weeks or more",
        "Within the last week or two",
        "Within the last few days",
        "Today",
        ]
    response = ui.choice(text, choices)
    if response == None:
        raise StopIteration
    report['GpuHangStarted'] = choices[response[0]]
        
    text = "Are you able to reproduce the lockup at will?"
    choices = [
        "I don't know",
        "Seems to happen randomly",
        "Occurs more often under certain circumstances",
        "Yes, I can easily reproduce it",
        ]
    response = ui.choice(text, choices)
    if response == None:
        raise StopIteration
    report['GpuHangReproducibility'] = choices[response[0]]

def attach_debugging_interest_level(report, ui):
    if not ui:
        return

    if (report.get('SourcePackage','Unknown') in core_x_packages or 
        report.get('SourcePackage','Unknown') in video_packages):
        text = "Would you be willing to do additional debugging work?"
        choices = [
            "I don't know",
            "No",
            "I just need an easy workaround",
            "Yes, if not too technical",
            "Yes, whatever it takes to get this fixed in Ubuntu",
            ]
        response = ui.choice(text, choices)
        if response == None:
            raise StopIteration
        choice = response[0]
        if choice>0:
            report['ExtraDebuggingInterest'] = choices[choice]

def add_info(report, ui):
    report.setdefault('Tags', '')

    # Verify the bug is valid to be filed
    if check_is_reportable(report, ui) == False:
        return False
    if check_is_supported(report, ui) == False:
        return False

    debug("attach_gpu_hang_info")
    attach_gpu_hang_info(report, ui)
    debug("attach_xorg_package_versions")
    attach_xorg_package_versions(report, ui)
    debug("attach_dist_upgrade_status")
    attach_dist_upgrade_status(report, ui)
    debug("attach_hardware")
    attach_hardware(report)

    pkg = report.get('SourcePackage','Unknown')
    if not is_xorg_input_package(pkg):
        debug("attach_graphic_card_pci_info")
        attach_graphic_card_pci_info(report, ui)
        debug("attach_dkms_info")
        attach_dkms_info(report, ui)
        debug("attach_nvidia_info")
        attach_nvidia_info(report, ui)
        debug("attach_fglrx_info")
        attach_fglrx_info(report, ui)
        debug("attach_2d_info")
        attach_2d_info(report, ui)
        debug("attach_3d_info")
        attach_3d_info(report, ui)

    if not is_xorg_video_package(pkg):
        debug("attach_input_device_info")
        attach_input_device_info(report, ui)

    debug("attach_debugging_interest_level")
    attach_debugging_interest_level(report, ui)
    return True

## DEBUGING ##
if __name__ == '__main__':
    import sys

    opt_debug = True

    report = {}
    if not add_info(report, None):
        print "Unreportable bug"
        sys.exit(1)
    for key in report:
        print '[%s]\n%s' % (key, report[key])
