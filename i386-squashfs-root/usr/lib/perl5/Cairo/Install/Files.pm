package Cairo::Install::Files;

$self = {
          'inc' => '-I. -Ibuild -pthread -I/usr/include/cairo -I/usr/include/glib-2.0 -I/usr/lib/i386-linux-gnu/glib-2.0/include -I/usr/include/pixman-1 -I/usr/include/freetype2 -I/usr/include/libpng12 -I/usr/include/libdrm   -pthread -I/usr/include/cairo -I/usr/include/freetype2 -I/usr/include/glib-2.0 -I/usr/lib/i386-linux-gnu/glib-2.0/include -I/usr/include/pixman-1 -I/usr/include/libpng12 -I/usr/include/libdrm  ',
          'typemaps' => [
                          'cairo-perl-auto.typemap',
                          'cairo-perl.typemap'
                        ],
          'deps' => [],
          'libs' => '-lcairo   -lcairo -lfreetype  '
        };


# this is for backwards compatiblity
@deps = @{ $self->{deps} };
@typemaps = @{ $self->{typemaps} };
$libs = $self->{libs};
$inc = $self->{inc};

	$CORE = undef;
	foreach (@INC) {
		if ( -f $_ . "/Cairo/Install/Files.pm") {
			$CORE = $_ . "/Cairo/Install/";
			last;
		}
	}

1;
