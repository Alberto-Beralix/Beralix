#!/usr/bin/python 
#
# Read Debian popularity-contest submission data on stdin and produce
# some statistics about it.
#
import sys, string, time, glob, gzip

def ewrite(s):
    sys.stderr.write("%s\n" % s)


class Vote:
    yes = 0
    old_unused = 0
    too_recent = 0
    empty_package = 0

    def vote_for(vote, package, entry):
	now = time.time()
	if entry.atime == 0:  # no atime: empty package
	    vote.empty_package = vote.empty_package + 1
	elif now - entry.atime > 30 * 24*3600:  # 30 days since last use: old
	    vote.old_unused = vote.old_unused + 1
	elif now - entry.ctime < 30 * 24* 3600 \
	  and entry.atime - entry.ctime < 24*3600:  # upgraded too recently
	    vote.too_recent = vote.too_recent + 1
	else:			# otherwise, vote for this package
	    vote.yes = vote.yes + 1

UNKNOWN = '**UNKNOWN**'

votelist = {}
sectlist = { UNKNOWN : [] }
deplist = {}
provlist = {}
complained = {}
release_list = {}
arch_list = {}
subcount = 0

mirrorbase = "/org/ftp.debian.org/ftp"

def parse_depends(depline):
    l = []
    split = string.split(depline, ',')
    for d in split:
	x = string.split(d)
	if (x):
		l.append(x[0])
    return l


def read_depends(filename):
    file = gzip.open(filename, 'r')
    package = None

    while 1:
	line = file.readline()
	if line:
	    if line[0]==' ' or line[0]=='\t': continue  # continuation
	    split = string.split(line, ':')

	if not line or split[0]=='Package':
	    if package and (len(dep) > 0 or len(prov) > 0):
		deplist[package] = dep
		for d in prov:
		    if not provlist.has_key(d):
			provlist[d] = []
		    provlist[d].append(package)
	    if package:
		if not sectlist.has_key(section):
		    sectlist[section] = []
		if not votelist.has_key(package):
			sectlist[section].append(package)
		votelist[package] = Vote()
		ewrite(package)
		package = None
	    if line:
		package = string.strip(split[1])
		section = UNKNOWN
		dep = []
		prov = []
	elif split[0]=='Section':
	    section = string.strip(split[1])
	elif split[0]=='Depends' or split[0]=='Requires':
	    dep = dep + parse_depends(split[1])
	elif split[0]=='Provides':
	    prov = parse_depends(split[1])
	    
	if not line: break
    

class Entry:
    atime = 0;
    ctime = 0;
    mru_file = '';

    def __init__(self, atime, ctime, mru_file):
	try:
		self.atime = long(atime)
		self.ctime = long(ctime)
	except:
		self.atime = self.ctime = 0
	self.mru_file = mru_file


class Submission:
    # format: {package: [atime, ctime, mru_file]}
    entries = {}

    start_date = 0

    arch = "unknown"
    release= "unknown"

    # initialize a new entry with known data
    def __init__(self, version, owner_id, date):
	self.entries = {}
	self.start_date = long(date)
	ewrite('%s:\n\tSTART: %s' % (owner_id, time.ctime(long(date))))

    # process a line of input from the survey
    def addinfo(self, split):
	if len(split) < 4:
	    ewrite('Invalid input line: ' + `split`)
	    return
	self.entries[split[2]] = Entry(split[0], split[1], split[3])

    # update the atime of dependency to that of dependant, if newer
    def update_atime(self, dependency, dependant):
	if not self.entries.has_key(dependency): return
	e = self.entries[dependency]
	f = self.entries[dependant]
	if e.atime < f.atime:
	    e.atime = f.atime
	    e.ctime = f.ctime

    # we found the last line of the survey: finish it
    def done(self, date):
	ewrite('\t STOP: after %d seconds, %d packages'
	       % (date - self.start_date, len(self.entries)))
	for package in self.entries.keys():
	    e = self.entries[package]
	    if deplist.has_key(package):
		for d in deplist[package]:
		    self.update_atime(d, package)
		    if provlist.has_key(d):
			for dd in provlist[d]:
			    self.update_atime(dd, package)
	for package in self.entries.keys():
	    if not votelist.has_key(package):
		if not complained.has_key(package):
			ewrite(('Warning: package %s neither in '
				+ 'stable nor unstable')  % package)
			complained[package] = 1
		votelist[package] = Vote()
		sectlist[UNKNOWN].append(package)
	    votelist[package].vote_for(package, self.entries[package])

        if not release_list.has_key(self.release):
            release_list[self.release] = 1
        else:
            release_list[self.release] = release_list[self.release] + 1

        if not arch_list.has_key(self.arch):
            arch_list[self.arch] = 1
        else:
            arch_list[self.arch] = arch_list[self.arch] + 1

def headersplit(pairs):
    header = {}
    for d in pairs:
	list = string.split(d, ':')
	try:
		key, value = list
		header[key] = value
	except:
		pass
    return header


def read_submissions(stream):
    global subcount
    e = None
    while 1:
	line = stream.readline()
	if not line: break

	split = string.split(line)
	if not split: continue

	if split[0]=='POPULARITY-CONTEST-0':
	    header = headersplit(split[1:])

	    if not header.has_key('ID') or not header.has_key('TIME'):
		ewrite('Invalid header: ' + split)
		continue

	    subcount = subcount + 1
	    ewrite('#%s' % subcount)
	    e = None
	    try:
		e = Submission(0, header['ID'], header['TIME'])
	    except:
		ewrite('Invalid date: ' + header['TIME'] + ' for ID ' + header['ID'])
		continue

            if header.has_key('POPCONVER'):
		if header['POPCONVER']=='':
	            e.release = 'unknown'
                elif header['POPCONVER']=='1.27.bill.1':
                    e.release = '1.27'
		else:
	            e.release = header['POPCONVER']
	
            if header.has_key('ARCH'):
	    	if header['ARCH']=='x86_64':
                    e.arch = 'amd64'
	    	elif header['ARCH']=='i386-gnu':
                    e.arch = 'hurd-i386'
		elif header['ARCH']=='':
                    e.arch = 'unknown'
		else:
                    e.arch = header['ARCH']

	elif split[0]=='END-POPULARITY-CONTEST-0' and e != None:
	    header = headersplit(split[1:])
	    if header.has_key('TIME'):
		try:
		  date = long(header['TIME'])
		except: 
		  ewrite('Invalid date: ' + header['TIME'])
		  continue
		e.done(date)
	    e = None

	elif e != None:
	    e.addinfo(split)
    # end of while loop
    ewrite('Processed %d submissions.' % subcount)


# main program

for d in glob.glob('%s/dists/stable/*/binary-i386/Packages.gz' % mirrorbase):
    read_depends(d)
for d in glob.glob('%s/dists/unstable/*/binary-i386/Packages.gz' % mirrorbase):
    read_depends(d)
read_submissions(sys.stdin)

def nicename(s):
    new_s = ''
    for c in s:
    	if c == '/':
    	    new_s = new_s + ',';
	elif c in string.letters or c in string.digits or c=='-':
	    new_s = new_s + c
	else:
	    new_s = new_s + '.'
    return new_s

# dump the results
out = open('results', 'w')
out.write("Submissions: %8d\n" % subcount)  
for release in release_list.keys():
    out.write("Release: %-30s %5d\n"
                  % (release, release_list[release]))

for arch in arch_list.keys():
    out.write("Architecture: %-30s %5d\n"
                  % (arch, arch_list[arch]))
for section in sectlist.keys():
    for package in sectlist[section]:
	fv = votelist[package]
	out.write("Package: %-30s %5d %5d %5d %5d\n"
		  % (package, fv.yes, fv.old_unused,
		     fv.too_recent, fv.empty_package))

