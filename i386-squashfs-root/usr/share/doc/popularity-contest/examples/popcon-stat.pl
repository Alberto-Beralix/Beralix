#! /usr/bin/perl -wT
#
# Require the debian package libchart-perl.

#BEGIN {
#@INC=("./usr/share/perl5/", @INC);
#}

$ENV{PATH}="/usr/bin:/bin";
$dirpng="../www/stat";
$oneyearago = `date +"%Y-%m-%d" -d "1 year ago"`;

while (<>)
{
   my ($file);
   m/^(.*\/popcon-([0-9-]+)\.gz)$/ or next;
   $file=$1;
   $f=$2;
   push @date,$f;
   open FILE,"zcat $file|";
   while(<FILE>)
   {
     my @line=split(/ +/);
     if ($line[0] eq "Submissions:")
     {
       $subt{$f}=$line[1];
     }
     elsif ($line[0] eq "Architecture:")
     {
       $sub{$f}->{$line[1]}=$line[2];
       $arch{$line[1]}++;
     }
     elsif ($line[0] eq "Release:")
     {
       if (defined($line[2]))
       {
         if ($line[1] =~ m/^([0-9]+(?:\.[0-9]+)*)/)
         {
           $rel{$f}->{"$1"}+=$line[2];
         } else {
           $rel{$f}->{"unknown"}+=$line[2];
         }
       } else {
         $rel{$f}->{"unknown"}+=$line[1];
       }
     }
     elsif ($line[0] eq "Package:")
     {
       last;
     }
   }
   close FILE;
}

sub ytick
{
  my ($x)=$_[0]-.5;
  $x < 0 and return 0;
  return int 2**$x;
}

use Chart::LinesPoints;

sub getsub
{
  my ($day,$r)=@_;
  return defined($sub{$day}->{$r})?$sub{$day}->{$r}:0;
}

sub submission_chart
{
  my ($pngname,$startdate,$ticks,$title)=@_;
  my (@days) = sort grep { defined($sub{$_}->{'i386'}) } @date;
  @days = sort grep { $_ ge $startdate } @days;
  my (@data) = (\@days);
  my ($today)=$days[-1];
  my (@arch)= sort {getsub($today,$b) <=> getsub($today,$a)} (keys %arch);
  $maxv = -10;
  for $arch (@arch)
  {
	  my @res=();
	  for (@days)
	  {
		  my $data=defined($sub{$_}->{$arch})?log($sub{$_}->{$arch})/log(2)+1:0;
		  push @res,$data;
		  $maxv=$data if ($data > $maxv);
	  }
	  push @data,\@res;
  }

  $obj=Chart::LinesPoints->new (600,400);
  $obj->set ('title' => "Number of submissions per architectures $title");
  $obj->set ('legend_labels' => [@arch]);
  $obj->set ('f_y_tick' => \&ytick);
  $obj->set ('brush_size' => 3);
  $obj->set ('pt_size' => 7);
  $obj->set ('max_val' => $maxv+1);
  $obj->set ('max_y_ticks' => 30);
  $obj->set ('y_ticks' => int $maxv +1);
  $obj->set ('x_ticks' => 'vertical');
  $obj->set ('skip_x_ticks' => $ticks);
  $obj->png ("$dirpng/submission$pngname.png", \@data);
}

submission_chart ("","0000-00-00",63,"");
submission_chart ("-1year",$oneyearago,14,"(last 12 months)");

use Chart::Composite;
my (@days) = sort grep { defined($sub{$_}->{'i386'}) } @date;
my (@arch)= sort (keys %arch);
for $arch (@arch)
{
  my @data;
  my @res=();
  my @tot=();
  for (@days)
  {
    push @res,defined($sub{$_}->{$arch})?$sub{$_}->{$arch}:0;
    push @tot,defined($subt{$_})?$subt{$_}:0;
  }
  @data=(\@days,\@res,\@tot);
  @labels=($arch, 'all submissions');
  $obj=Chart::Composite->new (700,400);
  $obj->set ('title' => "Number of submissions for $arch");
  $obj->set ('legend_labels' => \@labels);
  $obj->set ('brush_size' => 3);
  $obj->set ('pt_size' => 7);
  $obj->set ('x_ticks' => 'vertical');
  $obj->set ('skip_x_ticks' => 63);
  $obj->set ('composite_info' => [ ['LinesPoints', [1]], ['LinesPoints', [2] ] ]); 
  $obj->png ("$dirpng/sub-$arch.png", \@data);
}

sub getrel
{
  my ($day,$r)=@_;
  return defined($rel{$day}->{$r})?$rel{$day}->{$r}:0;
}

sub release_chart
{
  my ($pngname,$startdate,$ticks,$title)=@_;
  my (@days) = sort grep { $_ ge $startdate } @date;
  my (%release) = map { map { $_ => 1 } keys %{$rel{$_}}  } @days;
  my (@data) = (\@days);
  my ($today)=$days[-1];
  my (@release)= sort {getrel($today,$b) <=> getrel($today,$a)} (keys %release);
  for $release (@release)
  {
    my @res=();
    for (@days)
    {
      my $data=getrel($_,$release);
      push @res,$data;
    }
    push @data,\@res;
  }
  $obj=Chart::LinesPoints->new (600,400);
  $obj->set ('title' => "popularity-contest versions in use $title");
  $obj->set ('legend_labels' => [@release]);
  $obj->set ('brush_size' => 3);
  $obj->set ('pt_size' => 7);
  $obj->set ('x_ticks' => 'vertical');
  $obj->set ('skip_x_ticks' => $ticks);
  $obj->png ("$dirpng/release$pngname.png", \@data);
}
release_chart ("","2004-05-14",63,"");
release_chart ("-1year",$oneyearago,14,"(last 12 months)");
