import os.path, os

import apport.hookutils

XORG_CONF = '/etc/X11/xorg.conf'

def add_info(report):
    try:
        report['XorgConf'] = open(XORG_CONF).read()
    except IOError:
        pass

    report['Devices'] = ''
    for dirpath, dirnames, filenames in os.walk("/sys/devices"):
        if "modalias" in filenames:
            modalias = open(os.path.join(dirpath, "modalias")).read().strip()
            report['Devices'] += modalias + "\n"

    apport.hookutils.attach_file_if_exists(report, '/var/log/jockey.log')
    apport.hookutils.attach_hardware(report)
