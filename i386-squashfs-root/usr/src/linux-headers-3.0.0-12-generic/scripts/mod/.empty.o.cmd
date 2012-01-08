cmd_scripts/mod/empty.o := gcc -Wp,-MD,scripts/mod/.empty.o.d  -nostdinc -isystem /usr/lib/gcc/i686-linux-gnu/4.6.1/include -I/usr/src/linux-headers-lbm-3.0.0-12-generic -I/build/buildd/linux-3.0.0/arch/x86/include -Iarch/x86/include/generated -Iinclude  -I/build/buildd/linux-3.0.0/include -include include/generated/autoconf.h -Iubuntu/include -I/build/buildd/linux-3.0.0/ubuntu/include  -I/build/buildd/linux-3.0.0/scripts/mod -Iscripts/mod -D__KERNEL__ -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -Werror-implicit-function-declaration -Wno-format-security -fno-delete-null-pointer-checks -O2 -m32 -msoft-float -mregparm=3 -freg-struct-return -mpreferred-stack-boundary=2 -march=i686 -mtune=generic -maccumulate-outgoing-args -Wa,-mtune=generic32 -ffreestanding -fstack-protector -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 -pipe -Wno-sign-compare -fno-asynchronous-unwind-tables -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -Wframe-larger-than=1024 -Wno-unused-but-set-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -pg -fno-inline-functions-called-once -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fconserve-stack -DCC_HAVE_ASM_GOTO    -D"KBUILD_STR(s)=\#s" -D"KBUILD_BASENAME=KBUILD_STR(empty)"  -D"KBUILD_MODNAME=KBUILD_STR(empty)" -c -o scripts/mod/.tmp_empty.o /build/buildd/linux-3.0.0/scripts/mod/empty.c

source_scripts/mod/empty.o := /build/buildd/linux-3.0.0/scripts/mod/empty.c

deps_scripts/mod/empty.o := \

scripts/mod/empty.o: $(deps_scripts/mod/empty.o)

$(deps_scripts/mod/empty.o):
