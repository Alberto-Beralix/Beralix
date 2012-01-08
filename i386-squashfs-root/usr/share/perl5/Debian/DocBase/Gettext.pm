#!/usr/bin/perl -w
# Copied from /usr/share/perl5/Debconf/Gettext.pm
# $Id: Gettext.pm 160 2008-11-11 14:06:15Z robert $


package Debian::DocBase::Gettext;
use strict;


BEGIN {
	eval 'use Locale::gettext';
	if ($@) {
		eval q{
			sub _g {
				return shift;
			}
			sub _ng {
				my ($m1, $m2, $c) = @_;
				return $c == 1 ? $m1 : $m2;
			}
		};
	}
	else {
		textdomain('doc-base');
		eval q{
			sub _g {
				return gettext(shift);
			}
			sub _ng {
				my ($m1, $m2, $c) = @_;
				return ngettext($m1, $m2, $c);
			}
		};
	}
}

use base qw(Exporter);
our @EXPORT=qw(_g _ng);

1
