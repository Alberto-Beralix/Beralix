package Foomatic::Defaults;

use vars qw(@EXPORT @EXPORT_OK $libdir $bindir $sysdeps $DEBUG);

require Exporter;
@ISA = qw/Exporter/;
@EXPORT = qw($libdir $bindir $sysdeps);
@EXPORT_OK = qw($DEBUG);

# Debug flag; set this to enable debugging messages from Perl modules.
$DEBUG = '';

# Library directory; typically /usr/share/foomatic or somesuch.
$libdir = '/usr/share/foomatic';
$libdir = $ENV{FOOMATICDB} if $ENV{FOOMATICDB};

# Binary directory; typically /usr/bin or somesuch.
$bindir = '/usr/bin';

# System configuration list
$sysdeps = {
    'foo-etc'    => '/etc/foomatic',
    'foomatic-rip'=> '/usr/bin/foomatic-rip',
    'lpd-dir'    => '/var/spool/lpd',
    'lpd-log'    => '/var/log/lp-errs',
    'lpd-bin'    => '/usr/sbin/lpd',
    'lpd-pcap'   => '/etc/printcap',
    'lprng-conf' => '/etc/lpd.conf',
    'lpd-lpr'    => '/usr/bin/lpr',
    'lpd-lpq'    => '/usr/bin/lpq',
    'lpd-lprm'   => '/usr/bin/lprm',
    'lpd-lpc'    => '/usr/sbin/lpc',
    'lprng-checkpc' => '/usr/sbin/checkpc',
    'cups-etc'   => '/etc/cups',
    'cups-admin' => '/usr/sbin/lpadmin',
    'cups-lpstat' => '/usr/bin/lpstat',
    'cups-ppds'  => '/usr/share/cups/model',
    'cups-filters' => '/usr/lib/cups/filter',
    'cups-backends' => '/usr/lib/cups/backend',
    'cups-driver' => '/usr/lib/cups/driver',
    'cups-pconf' => '/etc/cups/printers.conf',
    'cups-lpr'   => '/usr/bin/lpr',
    'cups-lpq'   => '/usr/bin/lpq',
    'cups-lprm'  => '/usr/bin/lprm',
    'cups-lpc'   => '/usr/sbin/lpc',
    'cups-lp'    => '/usr/bin/lp',
    'cups-cancel' => '/usr/bin/cancel',
    'cups-enable' => '/usr/bin/enable',
    'cups-disable' => '/usr/bin/disable',
    'cups-accept' => '/usr/sbin/accept',
    'cups-reject' => '/usr/sbin/reject',
    'cups-lpmove' => '/usr/sbin/lpmove',
    'cups-lpoptions' => '/usr/bin/lpoptions',
    'cups-lpinfo' => '/usr/sbin/lpinfo',
    'pdq-conf'   => '/usr/lib/pdq',
    'pdq-printrc' => '/usr/lib/pdq/printrc',
    'pdq-foomatic' => '/usr/lib/pdq/drivers/foomatic',
    'pdq-print'  => '/usr/bin/pdq',
    'pdq-jobdir' => '~/.printjobs',
    'ppr-pprd' => '/usr/lib/ppr/bin/pprd',
    'ppr-interfaces' => '/usr/lib/ppr/interfaces',
    'ppr-ppdfiles' => '/usr/share/ppr/PPDFiles',
    'ppr-etc' => '/etc/ppr',
    'ppr-ppr' => '/usr/bin/ppr',
    'ppr-ppad' => '/usr/bin/ppad',
    'ppr-ppop' => '/usr/bin/ppop',
    'direct-etc' => '/etc/foomatic/direct',
    'direct-config' => '/etc/foomatic/direct/.config',
    'nc' => '/usr/bin/nc',
    'rlpr' => '/usr/bin/rlpr',
    'smbclient' => '/usr/bin/smbclient',
    'nprint' => '/usr/bin/nprint',
    'ptal-connect' => '/usr/bin/ptal-connect',
    'ptal-pipes' => '/var/run/ptal-printd',
    'mtink-pipes' => '/var/mtink',
    'cat' => '/bin/cat',
    'gzip' => '/bin/gzip',
    'wget' => '/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin:/usr/local/sbin:/etc/sbin',
    'curl' => '/usr/bin:/bin:/usr/local/bin:/usr/sbin:/sbin:/usr/local/sbin:/etc/sbin'
};

