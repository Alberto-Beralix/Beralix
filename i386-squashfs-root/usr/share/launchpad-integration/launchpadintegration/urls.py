import urlparse
import subprocess
import os

def showUrl(url, logger=None):
    """Show the given URL in the user's preferred browser.

    Currently just shells out to gnome-open, which uses the browser
    picked in the Gnome "preferred applications" control panel.
    If firefox is used open a new window.
    If Gnome is not available it uses the x-www-browser setting
    """
    if logger:
        logger.info('opening URL %s', url)
    
    if os.environ.get('GNOME_DESKTOP_SESSION_ID') and os.path.exists('/usr/bin/gnome-open'):
	command = ['gnome-open', url]
	if os.path.exists('/usr/bin/gconftool-2'):
		gconf_key = os.popen('gconftool-2 --get /desktop/gnome/url-handlers/http/command')
		if gconf_key.read().strip() == 'firefox %s':
			if (subprocess.call(['firefox', '-remote', 'ping()'], stderr=open('/dev/null', 'w')) == 0):
				command = ['firefox', '-remote', 'openURL(%s, new-window)'%url]
			else:
				command = ['firefox', url]
    elif os.environ.get('KDE_FULL_SESSION') and os.path.exists('/usr/bin/kfmclient'):
        command = ['kfmclient', 'openURL', url]
    else:
        command = ['x-www-browser', url]

    # check if we run from sudo (happens for e.g. gnome-system-tools, synaptic)
    if os.getuid() == 0 and os.environ.has_key('SUDO_USER'):
        command = ['sudo', '-u', os.environ['SUDO_USER']] + command

    p = subprocess.Popen(command,
                         close_fds=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE)
    p.communicate()
    return p.returncode

def launchpadDistroPrefix(facet=None):
    if facet is None:
        prefix = ''
    else:
        prefix = '%s.' % facet
    distro = subprocess.Popen(['lsb_release', '--id', '--short'],
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE).communicate()[0].strip()
    release = subprocess.Popen(['lsb_release', '--codename', '--short'],
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE).communicate()[0].strip()
    return 'https://%slaunchpad.net/%s/%s/' % (prefix, distro.lower(), release)

def getSourcePackageUrl(pkginfo, facet=None):
    prefix = launchpadDistroPrefix(facet)
    return urlparse.urljoin(prefix, '+source/%s/' % pkginfo.sourcepackage)

def getInfoUrl(pkginfo):
    return urlparse.urljoin(getSourcePackageUrl(pkginfo, 'answers'),
                            '+gethelp')

def getTranslateUrl(pkginfo):
    return getSourcePackageUrl(pkginfo, 'translations')

# def getBugURL(pkginfo):
#     return urlparse.urljoin(getSourcePackageUrl(pkginfo, 'bugs'), '+bugs')
