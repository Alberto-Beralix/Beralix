cmd_scripts/genksyms/lex.o := gcc -Wp,-MD,scripts/genksyms/.lex.o.d -Iscripts/genksyms -Wall -Wmissing-prototypes -Wstrict-prototypes -O2 -fomit-frame-pointer  -I/build/buildd/linux-3.0.0/scripts/genksyms -Iscripts/genksyms -c -o scripts/genksyms/lex.o scripts/genksyms/lex.c

source_scripts/genksyms/lex.o := scripts/genksyms/lex.c

deps_scripts/genksyms/lex.o := \
  /usr/include/stdio.h \
  /usr/include/features.h \
  /usr/include/i386-linux-gnu/bits/predefs.h \
  /usr/include/i386-linux-gnu/sys/cdefs.h \
  /usr/include/i386-linux-gnu/bits/wordsize.h \
  /usr/include/i386-linux-gnu/gnu/stubs.h \
  /usr/include/i386-linux-gnu/gnu/stubs-32.h \
  /usr/lib/gcc/i686-linux-gnu/4.6.1/include/stddef.h \
  /usr/include/i386-linux-gnu/bits/types.h \
  /usr/include/i386-linux-gnu/bits/typesizes.h \
  /usr/include/libio.h \
  /usr/include/_G_config.h \
  /usr/include/wchar.h \
  /usr/lib/gcc/i686-linux-gnu/4.6.1/include/stdarg.h \
  /usr/include/i386-linux-gnu/bits/stdio_lim.h \
  /usr/include/i386-linux-gnu/bits/sys_errlist.h \
  /usr/include/i386-linux-gnu/bits/stdio.h \
  /usr/include/i386-linux-gnu/bits/stdio2.h \
  /usr/include/string.h \
  /usr/include/xlocale.h \
  /usr/include/i386-linux-gnu/bits/string.h \
  /usr/include/i386-linux-gnu/bits/string2.h \
  /usr/include/endian.h \
  /usr/include/i386-linux-gnu/bits/endian.h \
  /usr/include/i386-linux-gnu/bits/byteswap.h \
  /usr/include/stdlib.h \
  /usr/include/i386-linux-gnu/bits/string3.h \
  /usr/include/errno.h \
  /usr/include/i386-linux-gnu/bits/errno.h \
  /usr/include/linux/errno.h \
  /usr/include/i386-linux-gnu/asm/errno.h \
  /usr/include/asm-generic/errno.h \
  /usr/include/asm-generic/errno-base.h \
  /usr/include/i386-linux-gnu/bits/waitflags.h \
  /usr/include/i386-linux-gnu/bits/waitstatus.h \
  /usr/include/i386-linux-gnu/sys/types.h \
  /usr/include/time.h \
  /usr/include/i386-linux-gnu/sys/select.h \
  /usr/include/i386-linux-gnu/bits/select.h \
  /usr/include/i386-linux-gnu/bits/sigset.h \
  /usr/include/i386-linux-gnu/bits/time.h \
  /usr/include/i386-linux-gnu/sys/sysmacros.h \
  /usr/include/i386-linux-gnu/bits/pthreadtypes.h \
  /usr/include/alloca.h \
  /usr/include/i386-linux-gnu/bits/stdlib.h \
  /usr/lib/gcc/i686-linux-gnu/4.6.1/include-fixed/limits.h \
  /usr/lib/gcc/i686-linux-gnu/4.6.1/include-fixed/syslimits.h \
  /usr/include/limits.h \
  /usr/include/i386-linux-gnu/bits/posix1_lim.h \
  /usr/include/i386-linux-gnu/bits/local_lim.h \
  /usr/include/linux/limits.h \
  /usr/include/i386-linux-gnu/bits/posix2_lim.h \
  /usr/include/ctype.h \
  /build/buildd/linux-3.0.0/scripts/genksyms/genksyms.h \
  scripts/genksyms/parse.h \
  /usr/include/unistd.h \
  /usr/include/i386-linux-gnu/bits/posix_opt.h \
  /usr/include/i386-linux-gnu/bits/environments.h \
  /usr/include/i386-linux-gnu/bits/confname.h \
  /usr/include/getopt.h \
  /usr/include/i386-linux-gnu/bits/unistd.h \
  scripts/genksyms/keywords.c \

scripts/genksyms/lex.o: $(deps_scripts/genksyms/lex.o)

$(deps_scripts/genksyms/lex.o):
