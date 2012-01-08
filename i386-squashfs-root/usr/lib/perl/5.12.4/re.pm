package re;

# pragma for controlling the regexp engine
use strict;
use warnings;

our $VERSION     = "0.11";
our @ISA         = qw(Exporter);
our @EXPORT_OK   = ('regmust',
                    qw(is_regexp regexp_pattern
                       regname regnames regnames_count));
our %EXPORT_OK = map { $_ => 1 } @EXPORT_OK;

my %bitmask = (
    taint   => 0x00100000, # HINT_RE_TAINT
    eval    => 0x00200000, # HINT_RE_EVAL
);

sub setcolor {
 eval {				# Ignore errors
  require Term::Cap;

  my $terminal = Tgetent Term::Cap ({OSPEED => 9600}); # Avoid warning.
  my $props = $ENV{PERL_RE_TC} || 'md,me,so,se,us,ue';
  my @props = split /,/, $props;
  my $colors = join "\t", map {$terminal->Tputs($_,1)} @props;

  $colors =~ s/\0//g;
  $ENV{PERL_RE_COLORS} = $colors;
 };
 if ($@) {
    $ENV{PERL_RE_COLORS} ||= qq'\t\t> <\t> <\t\t';
 }

}

my %flags = (
    COMPILE         => 0x0000FF,
    PARSE           => 0x000001,
    OPTIMISE        => 0x000002,
    TRIEC           => 0x000004,
    DUMP            => 0x000008,
    FLAGS           => 0x000010,

    EXECUTE         => 0x00FF00,
    INTUIT          => 0x000100,
    MATCH           => 0x000200,
    TRIEE           => 0x000400,

    EXTRA           => 0xFF0000,
    TRIEM           => 0x010000,
    OFFSETS         => 0x020000,
    OFFSETSDBG      => 0x040000,
    STATE           => 0x080000,
    OPTIMISEM       => 0x100000,
    STACK           => 0x280000,
    BUFFERS         => 0x400000,
    GPOS            => 0x800000,
);
$flags{ALL} = -1 & ~($flags{OFFSETS}|$flags{OFFSETSDBG}|$flags{BUFFERS});
$flags{All} = $flags{all} = $flags{DUMP} | $flags{EXECUTE};
$flags{Extra} = $flags{EXECUTE} | $flags{COMPILE} | $flags{GPOS};
$flags{More} = $flags{MORE} = $flags{All} | $flags{TRIEC} | $flags{TRIEM} | $flags{STATE};
$flags{State} = $flags{DUMP} | $flags{EXECUTE} | $flags{STATE};
$flags{TRIE} = $flags{DUMP} | $flags{EXECUTE} | $flags{TRIEC};

if (defined &DynaLoader::boot_DynaLoader) {
    require XSLoader;
    XSLoader::load( __PACKAGE__, $VERSION);
}
# else we're miniperl
# We need to work for miniperl, because the XS toolchain uses Text::Wrap, which
# uses re 'taint'.

sub _load_unload {
    my ($on)= @_;
    if ($on) {
	# We call install() every time, as if we didn't, we wouldn't
	# "see" any changes to the color environment var since
	# the last time it was called.

	# install() returns an integer, which if casted properly
	# in C resolves to a structure containing the regexp
	# hooks. Setting it to a random integer will guarantee
	# segfaults.
	$^H{regcomp} = install();
    } else {
        delete $^H{regcomp};
    }
}

sub bits {
    my $on = shift;
    my $bits = 0;
    unless (@_) {
	require Carp;
	Carp::carp("Useless use of \"re\" pragma"); 
    }
    foreach my $idx (0..$#_){
        my $s=$_[$idx];
        if ($s eq 'Debug' or $s eq 'Debugcolor') {
            setcolor() if $s =~/color/i;
            ${^RE_DEBUG_FLAGS} = 0 unless defined ${^RE_DEBUG_FLAGS};
            for my $idx ($idx+1..$#_) {
                if ($flags{$_[$idx]}) {
                    if ($on) {
                        ${^RE_DEBUG_FLAGS} |= $flags{$_[$idx]};
                    } else {
                        ${^RE_DEBUG_FLAGS} &= ~ $flags{$_[$idx]};
                    }
                } else {
                    require Carp;
                    Carp::carp("Unknown \"re\" Debug flag '$_[$idx]', possible flags: ",
                               join(", ",sort keys %flags ) );
                }
            }
            _load_unload($on ? 1 : ${^RE_DEBUG_FLAGS});
            last;
        } elsif ($s eq 'debug' or $s eq 'debugcolor') {
	    setcolor() if $s =~/color/i;
	    _load_unload($on);
	    last;
        } elsif (exists $bitmask{$s}) {
	    $bits |= $bitmask{$s};
	} elsif ($EXPORT_OK{$s}) {
	    require Exporter;
	    re->export_to_level(2, 're', $s);
	} else {
	    require Carp;
	    Carp::carp("Unknown \"re\" subpragma '$s' (known ones are: ",
                       join(', ', map {qq('$_')} 'debug', 'debugcolor', sort keys %bitmask),
                       ")");
	}
    }
    $bits;
}

sub import {
    shift;
    $^H |= bits(1, @_);
}

sub unimport {
    shift;
    $^H &= ~ bits(0, @_);
}

1;

__END__

