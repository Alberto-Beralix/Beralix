#!/usr/bin/perl -wT
# Accept popularity-contest entries on stdin and drop them into a
# subdirectory with a name based on their MD5 ID.
#
# Only the most recent entry with a given MD5 ID is kept.
#

$dirname = 'popcon-entries';
$now = time;
$state='initial'; # one of ('initial','accept','reject')

my($file,$mtime);
while(<>)
{
    $state eq 'initial' and do
    {
       /^POPULARITY-CONTEST-0/ or next;
       my @line=split(/ +/);
       my %field;
       for (@line)
       {
	    my ($key, $value) = split(':', $_, 2);
            $field{$key}=$value;
       };
       $id=$field{'ID'};
       if (!defined($id) || $id !~ /^([a-f0-9]{32})$/) 
       {
         print STDERR "Bad hostid: $id\n";
         $state='reject'; next;
       }
       $id=$1; #untaint $id
       $mtime=$field{'TIME'};
       if (!defined($mtime) || $mtime!~/^([0-9]+)$/)
       {
         print STDERR "Bad mtime $mtime\n";
         $state='reject'; next;
       }
       $mtime=int $1; #untaint $mtime;
       $mtime=$now if ($mtime > $now);
       my $dir=substr($id,0,2);
       unless (-d "$dirname/$dir") {
         mkdir("$dirname/$dir",0755) or do {$state='reject';next;};
       };
       $file="$dirname/$dir/$id"; 
       open REPORT, ">",$file or do {$state='reject';next;};
       print REPORT $_;
       $state='accept'; next;
    };
    $state eq 'reject' and do
    {
      /^From/ or next;
      $state='initial';next;
    };
    $state eq 'accept' and do
    {
      /^From/ and do 
      {
        close REPORT; 
        unlink $file; 
        print STDERR "Bad report $file\n";
        $state='initial';
        next;
      };
      print REPORT $_; #accept line.
      /^END-POPULARITY-CONTEST-0/ and do 
      {
        close REPORT; 
        utime $mtime, $mtime, $file;
        $state='initial';
        next;
      };
    };
}
if ($state eq 'accept')
{
        close REPORT;
        unlink $file; #Reject
        print STDERR "Bad last report $file\n";
}
