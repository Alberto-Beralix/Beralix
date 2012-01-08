# ---------------------------------------------------------------------------
# dc-debconf-select.pl:
#  This file will be added to end of dictionaries-common.config-base
#  to make dictionaries-common.config, as well as installed under
#  /usr/share/dictionaries-common for single ispell dicts/wordlists use
# ---------------------------------------------------------------------------

use strict;

sub dico_get_packages (){
  # Get list of packages sharing the question
  my $class    = shift;
  my $question = "shared/packages-$class";
  my @pkglist  = ();

  my ($errorcode,$packages) = metaget ($question, "owners");
  @pkglist = split (/\s*,\s*/, $packages) unless $errorcode;
  return \@pkglist;
}

sub dico_parse_languages (){
  # Get a hash reference of package -> list of (e)languages provided by package
  my $class    = shift;
  my $variant  = shift;
  my $packages = shift;
  my %tmphash  = ();

  die "No variant (languages|elanguages) string supplied\n" unless $variant;

  $packages = &dico_get_packages($class) unless $packages;

  foreach my $pkg ( @$packages ){
    my ($errorcode, $entry ) = metaget("$pkg/$variant", "default");
    unless ( $errorcode ){
      $entry =~ s/^\s+//;
      $entry =~ s/\s+$//;
      $tmphash{$pkg} = $entry;
    }
  }
  return \%tmphash;
}

sub dico_get_all_choices (){
  # Get $choices and $echoices parallel lists sorted after $echoices and formatted for debconf
  my $class       = shift;
  my $languages   = shift;
  my $debug       = 1 if exists $ENV{'DICT_COMMON_DEBUG'};
  my %mappinghash = ();
  my $debug_prefix = "[$class,dico_get_all_choices]";

  $languages   = &dico_parse_languages($class,"languages") unless $languages;

  my $elanguages  = &dico_parse_languages($class,"elanguages",[ keys %$languages ]);

  if ( $debug ){
    print STDERR "-------- $debug_prefix start --------\n";
    my $langlist  = join(', ',sort keys %{$languages});
    my $elanglist = join(', ',sort keys %{$elanguages});
    print STDERR " * Packages with languages: $langlist\n"  if $debug;
    print STDERR " * Packages with elanguages: $elanglist\n" if $debug;
  }

  foreach my $pkg ( keys %$languages ){
    my @langs  = split(/\s*,\s*/, $languages->{$pkg});
    my @elangs = @langs;
    if ( exists $elanguages->{$pkg} ){
      my @tmp = split(/\s*,\s*/, $elanguages->{$pkg});
      if ( $debug ){
	print STDERR " langs: $#langs, "  . join(', ',@langs)  . "\n";
	print STDERR " tmp:   $#tmp, "    . join(', ',@tmp)    . "\n";
      }
      @elangs = @tmp if ( $#langs == $#tmp );
    }
    foreach my $index ( 0 .. $#langs ){
      $mappinghash{$langs[$index]} = $elangs[$index];
    }
  }
  my $echoices = join(', ', sort {lc($a) cmp lc($b)} values %mappinghash);
  my $choices  = join(', ',
		      sort {lc($mappinghash{$a}) cmp lc($mappinghash{$b})}
		      keys %mappinghash);
  if ( $debug ){
    print STDERR " * Choices:\n   [$choices]\n";
    print STDERR " * Echoices:\n   [$echoices]\n";
    print STDERR "-------- $debug_prefix end --------\n";
  }
  return $choices, $echoices;
}

sub dc_debconf_select (){
  my $classinfo   = shift;
  my $debug       = 1 if exists $ENV{'DICT_COMMON_DEBUG'};
  my $reconfigure = 1 if exists $ENV{'DEBCONF_RECONFIGURE'};
  my $echoices;
  my %title       = ('ispell'   => "Dictionaries-common: Ispell dictionary",
		     'wordlist' => "Dictionaries-common: Wordlist dictionary"
    );

  my $class;
  my $priority;
  my $is_dcconfig;
  # If $classinfo is a hash reference, function is called from dictionaries-common.config
  if ( ref($classinfo) eq 'HASH' ){
    $class       = $classinfo->{'class'};
    $priority    = $classinfo->{'priority'} if ( defined $classinfo->{'priority'} );
    $is_dcconfig = 1;
  } else {
    # Otherwise is called from ispell dictionary/wordlist config
    $class = $classinfo;
  }

  my $packages     = &dico_get_packages($class);
  return unless $packages;

  my $question     = "dictionaries-common/default-$class";
  my $flagdir      = "/var/cache/dictionaries-common";
  my $newflag      = "$flagdir/flag-$class-new";
  my $debug_prefix = "[$class,dc_debconf_select]";

  print STDERR "----- $debug_prefix start -----------\n" if $debug;

  # Get new base list of provided languages
  my %newchoices  = ();
  my $languages = &dico_parse_languages($class,"languages",$packages);
  foreach my $pkg ( keys %$languages ) {
    foreach my $lang ( split(/\s*,\s*/, $languages->{$pkg}) ){
      $newchoices{$lang}++;
    }
  }
  my $choices = join (', ', sort {lc($a) cmp lc($b)} keys %newchoices);

  # Get old list of provided languages
  my @oldchoices  = split(/\s*,\s*/,metaget ($question, "choices-c"));
  pop @oldchoices;            # Remove the manual entry
  my $oldchoices = join (', ', sort {lc($a) cmp lc($b)} @oldchoices);

  # If dictionaries-common is already installed (-r $langscript),
  # there are elements for this class to be installed (%newchoices)
  # and there were none before (! $oldchoices), means that we are installing
  # for the first time elements in this class, with dictionaries-common
  # already installed. Try getting a reasonable default value
  my $langscript  = "/usr/share/dictionaries-common/dc-debconf-default-value.pl";
  if ( -r $langscript && %newchoices && ! $oldchoices ){
    print STDERR "$debug_prefix: Configuring class \"$class\" for the first time\n\n" if $debug;
    # If called from dictionaries-common.config we already have
    # $langscript, and probably more recent. Including it here will cause
    # some warnings about subroutine re-definitions and even errors.
    require $langscript unless $is_dcconfig;
    my $guessed = &dc_set_default_value_for_class($class);
    $priority = $guessed->{'priority'} if ( defined $guessed->{'priority'} );
  }

  # Read current value of default ispell dict / wordlist.
  my $curval  = get ($question) || "undefined";

  if ( scalar %newchoices ) {
    # If $priority is set &dc_set_default_value_for_class found something.
    # This will usually be as much "medium", so honour it.
    unless ( $priority ){
      if ( $curval =~ /^Manual.*/ or exists $newchoices{$curval} ){
	# Use priority "medium" if current value is in the new list or mode is set to manual.
	$priority = "medium";     #
      } else {
	# Otherwise we have a wrong value with no associated entry.
	# This is an *error* that needs to be signalled and acted upon.
	# For this reason priority must be higher than the standard one.
	# We leave it as "high" instead of "critical" so question can be
	# overriden in special cases until underlying bug is fixed.
	print STDERR "$debug_prefix error: [$curval] does not correspond to any package\n";
	$priority = "medium";
      }
    }
  } else {
    $priority = "low";
    print STDERR "$debug_prefix info: No elements in given class.\n" if $debug;
  }

  print STDERR
    "$debug_prefix:\n" .
    " * Class: $class, Priority: $priority\n" .
    " * Question: $question, Previous or guessed value: $curval\n" .
    " * New choices: [$choices]\n" .
    " * Old choices: [$oldchoices]\n" if $debug;

  # May ask question if there is no match
  if ( scalar %newchoices ) {
    if ( $choices ne $oldchoices) {
      fset ($question, "seen", "false");
      # Let future processes in this apt run know that a new $class element is to be installed
      if ( -d $flagdir ) {
	open (my $FLAG, "> $newflag")
	  or die "Could not open $newflag for write. Aborting ...\n";
	print $FLAG "1\n";
	close $FLAG;
      }
    }
    my ( $errorcode, $seen ) = fget($question, "seen");
    if ( $seen eq "false" or $reconfigure ){
      ($choices, $echoices ) = &dico_get_all_choices($class,$languages);
      subst ($question, "choices", $choices);
      subst ($question, "echoices", $echoices);
    }
    input ($priority, $question);
    title ($title{$class});
    go ();
    subst ($question, "echoices", $choices); # Be backwards consistent
  }

  # If called from dictionaries-common.config, check actual values in debug mode
  if ( $debug && $is_dcconfig ){
    print STDERR " * Checking really set values for $question:\n";
    print STDERR "   - Choices-C string: " . metaget ($question, "choices-c") . "\n";
    print STDERR "   - Really set value: " . get ($question) . "\n";
  }
  print STDERR "----- $debug_prefix end -----------\n" if $debug;
}

# Local Variables:
# perl-indent-level: 2
# End:

1;

