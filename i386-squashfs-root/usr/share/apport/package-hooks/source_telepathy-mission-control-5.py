'''apport package hook for itelepathy-mission-control

(c) 2011 Canonical Ltd.
Author:
Jamie Strandboge <jamie@ubuntu.com>

'''

from apport.hookutils import *
from os import path
import re

def add_info(report):
    attach_conffiles(report, 'telepathy-mission-control-5')
    attach_related_packages(report, ['apparmor', 'libapparmor1',
        'libapparmor-perl', 'apparmor-utils', 'auditd', 'libaudit0'])

    attach_mac_events(report)
