# vim:cindent:ts=2:sw=2:et:fdm=marker:cms=\ #\ %s
#
# $Id: DB.pm 223 2011-02-28 23:34:22Z robert $
#

package Debian::DocBase::DB;

use strict;
use warnings;

use Debian::DocBase::Common;
use Debian::DocBase::Utils;
use Debian::DocBase::Gettext;
use YAML::Tiny;

my $filesdb  = undef;
my $statusdb = undef;

sub new { # {{{
    my $class   = shift;
    my $dbfile  = shift;
    my $enckey  = shift;
    my $self    = {
        YAML    => YAML::Tiny->new,
        DB      => {},
        FILE    => $dbfile,
        ENCKEY  => $enckey,
        CHANGED => 0
    };
    bless($self, $class);
    $self->_Init();
    return $self;
} # }}}

sub _Init() { #  {{{
  my $self = shift;
#  # read-only access for `install-docs --status or --dump-db' run as non-root user
#  my $readonly = $> != 0;
  my $file = $self->{'FILE'};
  if (-f $file)
  {
    eval { $self->{'YAML'} = YAML::Tiny->read ($file) } 
      or Fatal($ERR_DATABASE, _g("Cannot read file `%s': %s."), $file, $@);
  }
  else
  {
    $self->{'YAML'}->[0] = {};
  }
  $self->{'DB'} = \%{$self->{'YAML'}->[0]};
  
} # }}} 

 sub PutData($$$) { # {{{
    my ($self, $key, $data)  = @_;
    $self->{'DB'}->{$self->EncodeKey($key)}   = $data;
    $self->{'CHANGED'} = 1;
} # }}}

sub GetData($$) { # {{{
  my ($self, $key) = @_;
  return $self->{'DB'}->{$self->EncodeKey($key)}
} # }}}

sub GetDBKeys() { # {{{
  my $self = shift;
  my @keys = grep { ! m|^/internal/| } keys %{$self->{'DB'}};   
  map { $_ = $self->DecodeKey($_) } @keys if $self->{'ENCKEY'};
  return @keys;
} # }}} 

sub _SaveDB() { # {{{ 
  my $self = shift;
  my $file = $self->{'FILE'};
  Debug(_g("Saving `%s' (%d)."), $file, $self->{'CHANGED'});
  return unless $self->{'CHANGED'};
  my $readonly = $> != 0;
  Fatal($ERR_PROCESSING, _g("Needs to be root for this operation.")) if $readonly;
  (my $newfile = $file) =~ s/^[^\.]+/$&-new/g;
  (my $oldfile = $file) =~ s/^[^\.]+/$&-old/g;


  eval { $self->{'YAML'}->write($newfile) }  
    or Fatal($ERR_DATABASE, _g("Cannot save file `%s': %s."), $newfile, $@);
  unlink $oldfile if -f $oldfile;
  rename $file, $oldfile if -f $file;
  rename $newfile, $file 
    or Fatal($ERR_DATABASE, _g("Cannot rename file `%s' to `%s': %s."), $newfile, $file, $!);
  $self->{'CHANGED'} = 0;
} # }}}

sub RemoveData($$) # {{{
{
  my ($self, $key) = @_;
  delete $self->{'DB'}->{$self->EncodeKey($key)};
  $self->{'CHANGED'} = 1;
} # }}}

sub Exists($) { # {{{
  my ($self, $key) = @_;
  my $data = $self->{'DB'}->{$self->EncodeKey($key)};
  return $data and %{$data};
} # }}}

sub DumpDB($) { # {{{
  my $self = shift;
  my $db   = $self->{'DB'};

  Inform(_g("Contents of file `%s':")."\n", $self->{'FILE'});
  print STDOUT YAML::Tiny::Dump($db);
} # }}}

sub EncodeKey($$) { # {{{
  my ($self, $key) = @_;
  return $key unless $self->{'ENCKEY'};
  $key =~ s/\/+/\//go;
  $key =~ s/^~/~~/o;
  $key =~ s/^$CONTROL_DIR/~1/o;
  $key =~ s/^$LOCAL_CONTROL_DIR/~2/o;
  return $key;
 } # }}}

 sub DecodeKey($$) { # {{{ 
  my ($self, $key) = @_;
  return $key unless $self->{'ENCKEY'};

  $key =~ s/^~1/$CONTROL_DIR/o;
  $key =~ s/^~2/$LOCAL_CONTROL_DIR/o;
  $key =~ s/^~~/~/o;
  return $key;
} # }}}

### STATIC FUNCTIONS
sub GetFilesDB() { # {{{
  $filesdb     = Debian::DocBase::DB->new($DB_FILES, 1) unless $filesdb;
  return $filesdb;
} # }}} 

sub GetStatusDB() { # {{{
  $statusdb     = Debian::DocBase::DB->new($DB_STATUS, 0) unless $statusdb;
  return $statusdb;
} # }}} 

sub SaveDatabases()
{
  IgnoreSignals();
  $statusdb->_SaveDB() if $statusdb;
  $filesdb->_SaveDB()  if $filesdb;
  RestoreSignals();
}
1
