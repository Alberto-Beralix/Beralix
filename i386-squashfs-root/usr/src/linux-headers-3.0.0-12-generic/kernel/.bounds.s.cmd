cmd_kernel/bounds.s := gcc -Wp,-MD,kernel/.bounds.s.d  -nostdinc -isystem /usr/lib/gcc/i686-linux-gnu/4.6.1/include -I/usr/src/linux-headers-lbm- -I/build/buildd/linux-3.0.0/arch/x86/include -Iarch/x86/include/generated -Iinclude  -I/build/buildd/linux-3.0.0/include -include include/generated/autoconf.h -Iubuntu/include -I/build/buildd/linux-3.0.0/ubuntu/include  -I/build/buildd/linux-3.0.0/. -I. -D__KERNEL__ -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -Werror-implicit-function-declaration -Wno-format-security -fno-delete-null-pointer-checks -O2 -m32 -msoft-float -mregparm=3 -freg-struct-return -mpreferred-stack-boundary=2 -march=i686 -mtune=generic -maccumulate-outgoing-args -Wa,-mtune=generic32 -ffreestanding -fstack-protector -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 -pipe -Wno-sign-compare -fno-asynchronous-unwind-tables -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -Wframe-larger-than=1024 -Wno-unused-but-set-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -pg -fno-inline-functions-called-once -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fconserve-stack -DCC_HAVE_ASM_GOTO    -D"KBUILD_STR(s)=\#s" -D"KBUILD_BASENAME=KBUILD_STR(bounds)"  -D"KBUILD_MODNAME=KBUILD_STR(bounds)" -fverbose-asm -S -o kernel/bounds.s /build/buildd/linux-3.0.0/kernel/bounds.c

source_kernel/bounds.s := /build/buildd/linux-3.0.0/kernel/bounds.c

deps_kernel/bounds.s := \
  /build/buildd/linux-3.0.0/include/linux/page-flags.h \
    $(wildcard include/config/pageflags/extended.h) \
    $(wildcard include/config/mmu.h) \
    $(wildcard include/config/arch/uses/pg/uncached.h) \
    $(wildcard include/config/memory/failure.h) \
    $(wildcard include/config/transparent/hugepage.h) \
    $(wildcard include/config/highmem.h) \
    $(wildcard include/config/swap.h) \
    $(wildcard include/config/s390.h) \
  /build/buildd/linux-3.0.0/include/linux/types.h \
    $(wildcard include/config/uid16.h) \
    $(wildcard include/config/lbdaf.h) \
    $(wildcard include/config/arch/dma/addr/t/64bit.h) \
    $(wildcard include/config/phys/addr/t/64bit.h) \
    $(wildcard include/config/64bit.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/types.h \
  /build/buildd/linux-3.0.0/include/asm-generic/types.h \
  /build/buildd/linux-3.0.0/include/asm-generic/int-ll64.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/bitsperlong.h \
  /build/buildd/linux-3.0.0/include/asm-generic/bitsperlong.h \
  /build/buildd/linux-3.0.0/include/linux/posix_types.h \
  /build/buildd/linux-3.0.0/include/linux/stddef.h \
  /build/buildd/linux-3.0.0/include/linux/compiler.h \
    $(wildcard include/config/sparse/rcu/pointer.h) \
    $(wildcard include/config/trace/branch/profiling.h) \
    $(wildcard include/config/profile/all/branches.h) \
    $(wildcard include/config/enable/must/check.h) \
    $(wildcard include/config/enable/warn/deprecated.h) \
  /build/buildd/linux-3.0.0/include/linux/compiler-gcc.h \
    $(wildcard include/config/arch/supports/optimized/inlining.h) \
    $(wildcard include/config/optimize/inlining.h) \
  /build/buildd/linux-3.0.0/include/linux/compiler-gcc4.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/posix_types.h \
    $(wildcard include/config/x86/32.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/posix_types_32.h \
  /build/buildd/linux-3.0.0/include/linux/mmzone.h \
    $(wildcard include/config/force/max/zoneorder.h) \
    $(wildcard include/config/smp.h) \
    $(wildcard include/config/numa.h) \
    $(wildcard include/config/zone/dma.h) \
    $(wildcard include/config/zone/dma32.h) \
    $(wildcard include/config/memory/hotplug.h) \
    $(wildcard include/config/sparsemem.h) \
    $(wildcard include/config/compaction.h) \
    $(wildcard include/config/arch/populates/node/map.h) \
    $(wildcard include/config/discontigmem.h) \
    $(wildcard include/config/flat/node/mem/map.h) \
    $(wildcard include/config/cgroup/mem/res/ctlr.h) \
    $(wildcard include/config/no/bootmem.h) \
    $(wildcard include/config/have/memory/present.h) \
    $(wildcard include/config/have/memoryless/nodes.h) \
    $(wildcard include/config/need/node/memmap/size.h) \
    $(wildcard include/config/need/multiple/nodes.h) \
    $(wildcard include/config/have/arch/early/pfn/to/nid.h) \
    $(wildcard include/config/flatmem.h) \
    $(wildcard include/config/sparsemem/extreme.h) \
    $(wildcard include/config/have/arch/pfn/valid.h) \
    $(wildcard include/config/nodes/span/other/nodes.h) \
    $(wildcard include/config/holes/in/zone.h) \
    $(wildcard include/config/arch/has/holes/memorymodel.h) \
  /build/buildd/linux-3.0.0/include/linux/kbuild.h \
  /build/buildd/linux-3.0.0/include/linux/page_cgroup.h \
    $(wildcard include/config/cgroup/mem/res/ctlr/swap.h) \

kernel/bounds.s: $(deps_kernel/bounds.s)

$(deps_kernel/bounds.s):
