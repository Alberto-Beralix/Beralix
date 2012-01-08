#!/usr/bin/perl -wT
#
# Receive HTTP post request with a file upload, uncompress it if
# needed, and submit it as an email to the popcon collector.
#
# Handle three different submission methods
#  - simple post message, where the complete body is the popcon report
#    (used by popcon version 1.30).
#  - mime-encoded upload with report in compressed form (used by
#    popcon version 1.31 and newer).
#  - mime-encoded upload with report in uncompressed form (used by
#    ubuntu popcon).

use strict;
use CGI;
use Compress::Zlib;

my $email='survey@popcon.ubuntu.com';

my $directsave = 0; # Enable to store on disk instead of sending an email
my $basedir   = "/var/lib/popcon";
my $bindir    = "$basedir/bin";

$ENV{PATH}="";

print "Content-Type: text/plain\n\n";
if (exists $ENV{REQUEST_METHOD} && $ENV{REQUEST_METHOD} ne "POST")
{
    print "Debian Popularity-Contest HTTP-POST submission URL\n";
    print "Visit http://popcon.ubuntu.com/ for more info.\n";
    exit 0;
}

# Extract post data, handle both simple and multipart way
my @entry;
if (exists $ENV{CONTENT_TYPE} && $ENV{CONTENT_TYPE} =~ m%multipart/form-data%){
    # New method, used in popularity-contest after 1.30
    my $query = new CGI;
    my $fh = $query->upload("popcondata");
    if ($fh) {
	my $filename = $query->param("popcondata");
	my $type = $query->uploadInfo($filename)->{'Content-Type'};
	if ("text/plain; charset=utf-8" ne $type &&
	    "application/octet-stream" ne $type) { # Used by ubuntu script
	    print "Only 'text/plain; charset=utf-8' and 'application/octet-stream' is supported (not $type)!";
	    die;
	} else {
	    my $encoding = $query->uploadInfo($filename)->{'Content-Encoding'};
	    if ("x-gzip" eq $encoding || "gzip" eq $encoding) {
		# Uncompress
		print "Compressed ($encoding) encoding detected.\n";
		my $data;
		# $data = join("", <$fh>);
		my $len = (stat($fh))[7];
		read $fh, $data, $len;
		$data = Compress::Zlib::memGunzip($data);
		@entry = ($data);
	    } else { # Pass throught
		print "Identity encoding detected.\n";
		@entry = <$fh>;
	    }
	}
    } else {
	print $query->cgi_error;
	die;
    }
} else {
    # Old submit method, used in popularity-contest version 1.30
    print "Old method detected.\n";
    open GZIP, '/bin/gzip -dc|' or die "gzip";
    close STDIN;
    open STDIN, "<&GZIP";
    @entry = <GZIP>;
}

my ($id) = $entry[0] =~ m/POPULARITY-CONTEST-0 .+ ID:(\S+) /;
if ($id) {
    if ($directsave) {
	open(POPCON, "|$bindir/prepop.pl") or die "Unable to pipe to prepop.pl";
	print POPCON @entry;
	close POPCON;
    } else {
	open POPCON, "|/usr/lib/sendmail -oi $email" or die "sendmail";
	print POPCON <<"EOF";
To: $email
Subject: popularity-contest submission

EOF
        print POPCON @entry;
	close POPCON;
    }
}
if ($id) {
    print "Thanks for your submission to Debian Popularity-Contest!\n";
    print "DEBIAN POPCON HTTP-POST OK\n";
} else {
    print "The submission to Debian Popularity-Contest failed!\n";
}
exit 0;
