'''apport package hook for gnome-power-manager

(c) 2009 Canonical Ltd.
Author: Martin Pitt <martin.pitt@ubuntu.com>
'''

from apport.hookutils import *
from os import path
import dbus

def add_info(report):
    report['DevkitPower'] = command_output(['upower', '-d'])
    report['gnome-power-bugreport'] = command_output('/usr/share/gnome-power-manager/gnome-power-bugreport')
    attach_hardware(report)
    attach_gconf(report, 'gnome-power-manager')

    try:
        bus = dbus.SessionBus()
        session_manager = bus.get_object('org.gnome.SessionManager', '/org/gnome/SessionManager')
        session_manager_iface = dbus.Interface(session_manager, dbus_interface='org.gnome.SessionManager')
        inhibitors = session_manager_iface.GetInhibitors()
        inhibitors_str = ''
        master_flag = 0
        j = 1
        for i in inhibitors:
            obj = bus.get_object('org.gnome.SessionManager', i)
            iface = dbus.Interface(obj, dbus_interface='org.gnome.SessionManager.Inhibitor')
            app_id = iface.GetAppId()
            flags = iface.GetFlags()
            reason = iface.GetReason()
	    if j > 1:
		    inhibitors_str += '\n'
            inhibitors_str += str(j) + ': AppId = ' + app_id + ', Flags = ' + str(flags) + ', Reason = ' + reason
            j = j + 1
            master_flag |= flags

        report['GnomeSessionInhibitors'] = 'None' if inhibitors_str == '' else inhibitors_str
        report['GnomeSessionIdleInhibited'] = 'Yes' if master_flag & 8 else 'No'
	report['GnomeSessionSuspendInhibited'] = 'Yes' if master_flag & 4 else 'No'
    except:
        report['GnomeSessionInhibitors'] = 'Failed to acquire'
        report['GnomeSessionIdleInhibited'] = 'Unknown'
	report['GnomeSessionSuspendInhibited'] = 'Unknown'
