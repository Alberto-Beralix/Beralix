#!/usr/bin/perl

# vim:cindent:ts=2:sw=2:et:fdm=marker:cms=\ #\ %s
#
# $Id: InstallDocs.pm 228 2011-03-06 17:51:46Z robert $

package Debian::DocBase::InstallDocs;

use warnings;
use strict;

use base qw(Exporter);
use vars qw(@EXPORT);
our @EXPORT = qw(SetMode InstallDocsMain
                 $MODE_INSTALL $MODE_REMOVE $MODE_STATUS $MODE_REMOVE_ALL $MODE_INSTALL_ALL
                 $MODE_INSTALL_CHANGED $MODE_DUMP_DB $MODE_CHECK  $verbose $debug);

use Debian::DocBase::Common;
use Debian::DocBase::Utils;
use Debian::DocBase::Document;
use Debian::DocBase::DocBaseFile;
use Debian::DocBase::DB;
use Debian::DocBase::Programs::Dhelp;
use Debian::DocBase::Programs::Dwww;
use Debian::DocBase::Programs::Scrollkeeper;
use Debian::DocBase::Gettext;


# constants
our $MODE_INSTALL         = 1;
our $MODE_REMOVE          = 2;
our $MODE_INSTALL_ALL     = 3;
our $MODE_REMOVE_ALL      = 4;
our $MODE_STATUS          = 5;
our $MODE_CHECK           = 6;
our $MODE_INSTALL_CHANGED = 7;
our $MODE_DUMP_DB         = 8;

# global module variables
our $mode                 = undef;
our @arguments            = undef;

#################################################
###        PUBLIC STATIC FUNCTIONS            ###
#################################################

# Sets work mode
sub SetMode($@) { # {{{
  my $newmode = shift;
  my @args    = @_;


  Fatal($ERR_INTERNAL, _g("Mode already set: %s, %s."), $mode, $newmode) if (defined $mode);

  $mode = $newmode;

  Inform(_g("Value of the `%s' option ignored."), "--rootdir")
    if ($mode != $MODE_CHECK) and ($opt_rootdir ne "");
  $opt_rootdir = "" if ($mode != $MODE_CHECK);

  if ($#args == 0 and $args[0] eq '-') {
    # get list from stdin
    @arguments = map {+chomp} <STDIN>;
  }
  else {
    @arguments = @args;
  }

} # }}}

# Main procedure that gets called by install-docs
sub InstallDocsMain() { # {{{

  Fatal($ERR_INTERNAL, _g("Unknown mode.")) unless defined $mode;

  if ($mode == $MODE_CHECK) {
    _HandleCheck();
  } elsif ($mode == $MODE_STATUS) {
    _HandleStatus();
  } elsif ($mode == $MODE_DUMP_DB) {
    _HandleDumpDB();
  } elsif ($mode == $MODE_REMOVE_ALL) {
    _HandleRemovalOfAllDocs();
  } else {
    _HandleRegistrationAndUnregistation();
  }

  # don't fail on reregistering docs
  $exitval = 0 if    $mode == $MODE_INSTALL_ALL
                  or $mode == $MODE_REMOVE_ALL
                  or $mode == $MODE_INSTALL_CHANGED;

} # }}}

#################################################
###        PRIVATE STATIC FUNCTIONS           ###
#################################################

# Check correctness of doc-base file
sub _HandleCheck() { # {{{
  foreach my $file (@arguments) {
    if (! -f $file) {
      Error(_g("Doc-base file `%s' does not exist."), $file);
      next;
    }

    my $docfile = Debian::DocBase::DocBaseFile->new($file, 1);
    $docfile->Parse();
    if ($docfile->Invalid()) {
        Inform(_g("%s: Fatal error found, the file won't be registered."), $file);
    } elsif ((my $cnt = $docfile->GetWarnErrCount()) > 0) {
        my $msg = _ng("%d warning or non-fatal error found.",
                   "%d warnings or non-fatal errors found.",
                   $cnt);
        Inform("%s: $msg", $file, $cnt);
    } else {
        Inform(_g("%s: No problems found."), $file);
    }
  }
} # }}}

# Show document status
sub _HandleStatus() { # {{{
  foreach my $docid (@arguments) {
    unless (Debian::DocBase::Document::IsRegistered($docid)) {
      Inform (_g("Document `%s' is not registered."), $docid);
      next;
    }
    my $doc = Debian::DocBase::Document->new($docid);
    $doc -> DisplayStatusInformation();
  }
} # }}}

# Dump our databases
sub _HandleDumpDB() { # {{{
  foreach my $arg (@arguments) {
    if ($arg eq "files.db") {
      Debian::DocBase::DB::GetFilesDB()->DumpDB();
    } elsif ($arg eq "status.db") {
      Debian::DocBase::DB::GetStatusDB()->DumpDB();
    } else {
      Error(_g("Invalid argument `%s' passed to the `%s' option."), $arg, "--dump-db");
      exit (1);
    }
  }
} # }}}

# Remove all docs simply by deleting our db and other created files
sub _HandleRemovalOfAllDocs() { # {{{
  my $suffix  = ".removed.$$";
  my @dbdirs  = ($OMF_DIR, $VAR_CTRL_DIR);

  unlink $DB_FILES or Fatal($ERR_FSACCESS, _g("Cannot remove file `%s': %s."), $DB_FILES, $!) if -f $DB_FILES;
  foreach my $d (@dbdirs) {
    next unless -d $d;
    rename ($d, $d.$suffix) or Fatal($ERR_FSACCESS, _g("Cannot rename file `%s' to `%s': %s."), $d, ${d}.${suffix}, $!);
    system ('mkdir', '-m', '0755', '-p', $d);
    system ('rm', '-r', $d.$suffix);
  }
  unlink $DB_STATUS or Fatal($ERR_FSACCESS, _g("Cannot remove file `%s': %s."), $DB_STATUS, $!) if -f $DB_STATUS;

  my @documents = ();
  RegisterDwww(1, @documents);
  RegisterDhelp(1, 1, @documents);
  RegisterScrollkeeper(1, @documents);

} # }}}

# Register or de-register particular docs or register all or only changed docs
sub _HandleRegistrationAndUnregistation() { # {{{
  my @toinstall     = ();       # list of files to install
  my @toremove      = ();       # list of files to remove
  my @toremovedocs  = ();       # list of docs to remove
  my $showregmsg    = $opt_verbose;

  $on_fatal_handler = \&Debian::DocBase::DB::SaveDatabases;
  SetupSignals();

  if ($mode != $MODE_INSTALL_ALL)
  {
    my $scStatus = ScrollkeeperStatusChanged();
    if ($scStatus != $SC_NOTCHANGED)
    {
      $mode = $MODE_INSTALL_ALL;
      Inform($scStatus == $SC_REMOVED
              ? _g("Scrollkeeper was removed, forcing re-registration of all documents.")
              : _g("Scrollkeeper was installed, forcing re-registration of all documents."));
    }
  }


  if ($mode == $MODE_INSTALL_CHANGED) {
    my @stats = Debian::DocBase::DocBaseFile::GetChangedDocBaseFiles(\@toremove, \@toinstall);
    my $msg   = "";

    # Translators: the following message will be used to replace `%s' in `Processing %s', e.g.
    #    `Processing 5 removed doc-base files...'
    #    `Processing 1 removed doc-base file, 4 changed doc-base files, 2 added doc-base files...'
    $msg      .=  _ng("%d removed doc-base file", "%d removed doc-base files", $stats[0]) if $stats[0];
    $msg      .= ", " if $msg and $stats[1];

    # Translators: the following message will be used to replace `%s' in `Processing %s', e.g.
    #    `Processing 5 changed doc-base files...'
    #    `Processing 1 removed doc-base file, 4 changed doc-base files, 2 added doc-base files...'
    $msg      .=  _ng("%d changed doc-base file", "%d changed doc-base files", $stats[1]) if $stats[1];
    $msg      .= ", " if $msg and $stats[2];

    # Translators: the following message will be used to replace `%s' in `Processing %s', e.g.
    #    `Processing 5 added doc-base files...'
    #    `Processing 1 removed doc-base file, 4 changed doc-base files, 2 added doc-base files...'
    $msg      .=  _ng("%d added doc-base file",   "%d added doc-base files",   $stats[2]) if $stats[2];
    $msg       = sprintf $msg, grep { $_ != 0 } @stats if $msg;

    Inform(_g("Processing %s..."), $msg) if $msg;
    $showregmsg = 1 if $stats[0] or $stats[1] or $stats[2];
  }

  elsif ($mode == $MODE_INSTALL_ALL) {
    @toremovedocs  = Debian::DocBase::Document::GetAllRegisteredDocumentIDs();
    @toinstall     = Debian::DocBase::DocBaseFile::GetAllDocBaseFiles() if $mode == $MODE_INSTALL_ALL;
    my @stats      = ($#toremovedocs+1, $#toinstall+1);

    if ($stats[0] and $stats[1]) {
      # Translators: the `Unregisteing %d doc-base files, ' and `re-registeing %d doc-base files...'
      # messages are used together.
      my $msg = _ng("Unregistering %d doc-base file, ",
                    "Unregistering %d doc-base files, ", $stats[0]);

      # Translators: the `Unregisteing %d doc-base files, ' and `re-registeing %d doc-base files...'
      # messages are used together.
      $msg .= _ng("re-registering %d doc-base file...",
                  "re-registering %d doc-base files...", $stats[1]);

      Inform($msg, $stats[0], $stats[1]);
    } elsif ($stats[0]) {
      Inform(_ng("Unregistering %d doc-base file...",
                 "Unregistering %d doc-base files...", $stats[0]), $stats[0]);
   } elsif ($stats[1]) {
      Inform(_ng("Registering %d doc-base file...",
                 "Registering %d doc-base files...", $stats[1]), $stats[1]);
   }
    $showregmsg = 1 if $stats[0] or $stats[1];
  }

  elsif  ($mode == $MODE_INSTALL) {
    @toinstall = @arguments;
  }

  elsif ($mode == $MODE_REMOVE)  {
    @toremove     = grep { /\//  } @arguments;
    @toremovedocs = grep { /^[^\/]+$/ } @arguments; # for backward compatibility  -> arguments are document-ids

  }

  foreach my $docid (@toremovedocs) {
    unless (Debian::DocBase::Document::IsRegistered($docid)) {
      Inform (_g("Ignoring unregistered document `%s'."), $docid);
      next;
    }
    Debug(_g("Trying to remove document `%s'."), $docid);
    my $doc   = Debian::DocBase::Document->new($docid);
    $doc->UnregisterAll();
  }

  foreach my $file (@toremove) {
    my $docid   = Debian::DocBase::DocBaseFile::GetDocIdFromRegisteredFile($file);
    unless ($docid) {
      Inform (_g("Ignoring unregistered file `%s'."), $file);
      next;
    }
    my $docfile = Debian::DocBase::DocBaseFile->new($file);
    my $doc     = Debian::DocBase::Document->new($docid);
    $doc->Unregister($docfile);
  }

  foreach my $file (@toinstall) {
    unless (-f $file) {
      Error(_g("Doc-base file `%s' does not exist."), $file);
      next;
    }
    Debug(_g("Trying to install file `%s'."), $file);
    my $docfile = Debian::DocBase::DocBaseFile->new($file,  $opt_verbose);
    $docfile->Parse();
    my $docid   = $docfile->GetDocumentID();
    next unless defined $docid;
    my $doc     = Debian::DocBase::Document->new($docid);

    $doc->Register($docfile);
  }

  my @documents = Debian::DocBase::Document::GetDocumentList();

  UnregisterDhelp(@documents) if @documents and $mode != $MODE_INSTALL_ALL;

  foreach my $doc (@documents) {
      $doc -> MergeCtrlFiles();
  }

  IgnoreSignals();
  foreach my $doc (@documents) {
    $doc -> WriteNewCtrlFile();
    $doc -> SaveStatusChanges();
  }
  Debian::DocBase::DB::SaveDatabases();
  RestoreSignals();

  Debian::DocBase::DocBaseFile::DisplayErrorNote() if $mode == $MODE_INSTALL_ALL or $mode == $MODE_INSTALL_CHANGED;

  if (@documents)
  {
    RegisterDwww($showregmsg,          @documents);
    RegisterDhelp($showregmsg,         $mode == $MODE_INSTALL_ALL, @documents);
    RegisterScrollkeeper($showregmsg,  @documents);
    Debian::DocBase::DB::SaveDatabases();
  }

  undef @toinstall;
  undef @toremove;
  undef @toremovedocs;

} # }}}

1;
