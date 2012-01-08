import sys
import logging
import optparse
import subprocess

from launchpadintegration.packageinfo import PackageInfo
from launchpadintegration.urls import (
    showUrl, getInfoUrl, getTranslateUrl)

def main():
    parser = optparse.OptionParser(usage="launchpad-integration [options]")
    parser.add_option('-p', '--pid', dest='pid', type='int', default=None,
                      metavar="PID", help="Process ID to look up")
    parser.add_option('-f', '--file', dest='filename', default=None,
                      metavar="FILE", help="Filename to look up")
    parser.add_option('-P', '--package', dest='package', default=None,
                      metavar="PACKAGE", help="Package to look up")
    parser.add_option('-x', '--xid', dest='xid', default=None,
                      metavar="XID", help="X Window ID to look up")
    parser.add_option('-d', '--debug', action='store_true', dest='debug',
                      help="Print debugging info")

    parser.add_option('-i', '--info', action='store_true', dest='getinfo',
                      help="Show Launchpad information page for package")
    parser.add_option('-t', '--translate', action='store_true',
                      dest='translate',
                      help="Show Launchpad translate page for package")
    parser.add_option('-b', '--bugs', action='store_true',
                      dest='filebug',
                      help="File a bug for package")

    (options, args) = parser.parse_args()

    logger = logging.getLogger()
    hdlr = logging.StreamHandler()
    hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(hdlr)
    if options.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARN)

    if options.pid:
        pkginfo = PackageInfo.fromProcessID(options.pid, logger)
    elif options.filename:
        pkginfo = PackageInfo.fromFilename(options.filename, logger)
    elif options.package:
        pkginfo = PackageInfo.fromPackageName(options.package, logger)
    elif options.xid:
        pkginfo = PackageInfo.fromXID(options.xid, logger)
    else:
        #info = PackageInfo.fromXID(None, logger)
        pkginfo = None
        parser.print_help()
        sys.exit(1)       

    if options.getinfo:
        return showUrl(getInfoUrl(pkginfo), logger)
    elif options.translate:
        return showUrl(getTranslateUrl(pkginfo), logger)
    elif options.filebug:
	args = ['apport-bug', '--tag', 'apport-lpi']
	if options.pid:
	    args.append(str(options.pid))
	else: 
	    assert pkginfo.binarypackage, 'need to specify pid or package'
	    args.append(pkginfo.binarypackage)
	subprocess.call(args)
    else:
        print 'Name:', pkginfo.binarypackage
        print 'Source:', pkginfo.sourcepackage
        print 'Version:', pkginfo.version
        print 'Arch:', pkginfo.architecture
        sys.stderr.write('show GUI here\n')
        sys.exit(1)
