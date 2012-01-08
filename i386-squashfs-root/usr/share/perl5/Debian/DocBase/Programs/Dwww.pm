# vim:cindent:ts=2:sw=2:et:fdm=marker:cms=\ #\ %s
#
# $Id: Dwww.pm 222 2011-02-28 22:18:55Z robert $
#

package Debian::DocBase::Programs::Dwww;

use Exporter();
use strict;
use warnings;

use vars qw(@ISA @EXPORT);
@ISA = qw(Exporter);
@EXPORT = qw(RegisterDwww);

use Debian::DocBase::Common;
use Debian::DocBase::Utils;
use Debian::DocBase::Gettext;

our $dwww_build_menu = "/usr/sbin/dwww-build-menu";

# Registering to dwww:
sub RegisterDwww($@) { # {{{
  my $showinfo = shift;
  my @documents = @_;

  Debug(_g("%s started."), "RegisterDwww");

  if (-x $dwww_build_menu) {
    Inform(_g("Registering documents with %s..."), "dwww") if $showinfo and $opt_update_menus;
    Execute($dwww_build_menu) if $opt_update_menus;
  } else {
    Debug(_g("Skipping execution of %s - %s package doesn't seem to be installed."), $dwww_build_menu, "dwww");
  }
  Debug(_g("%s finished."), "RegisterDwww");

} # }}}
