cmd_arch/x86/kernel/asm-offsets.s := gcc -Wp,-MD,arch/x86/kernel/.asm-offsets.s.d  -nostdinc -isystem /usr/lib/gcc/i686-linux-gnu/4.6.1/include -I/usr/src/linux-headers-lbm- -I/build/buildd/linux-3.0.0/arch/x86/include -Iarch/x86/include/generated -Iinclude  -I/build/buildd/linux-3.0.0/include -include include/generated/autoconf.h -Iubuntu/include -I/build/buildd/linux-3.0.0/ubuntu/include  -I/build/buildd/linux-3.0.0/. -I. -D__KERNEL__ -Wall -Wundef -Wstrict-prototypes -Wno-trigraphs -fno-strict-aliasing -fno-common -Werror-implicit-function-declaration -Wno-format-security -fno-delete-null-pointer-checks -O2 -m32 -msoft-float -mregparm=3 -freg-struct-return -mpreferred-stack-boundary=2 -march=i686 -mtune=generic -maccumulate-outgoing-args -Wa,-mtune=generic32 -ffreestanding -fstack-protector -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 -pipe -Wno-sign-compare -fno-asynchronous-unwind-tables -mno-sse -mno-mmx -mno-sse2 -mno-3dnow -Wframe-larger-than=1024 -Wno-unused-but-set-variable -fno-omit-frame-pointer -fno-optimize-sibling-calls -pg -fno-inline-functions-called-once -Wdeclaration-after-statement -Wno-pointer-sign -fno-strict-overflow -fconserve-stack -DCC_HAVE_ASM_GOTO    -D"KBUILD_STR(s)=\#s" -D"KBUILD_BASENAME=KBUILD_STR(asm_offsets)"  -D"KBUILD_MODNAME=KBUILD_STR(asm_offsets)" -fverbose-asm -S -o arch/x86/kernel/asm-offsets.s /build/buildd/linux-3.0.0/arch/x86/kernel/asm-offsets.c

source_arch/x86/kernel/asm-offsets.s := /build/buildd/linux-3.0.0/arch/x86/kernel/asm-offsets.c

deps_arch/x86/kernel/asm-offsets.s := \
    $(wildcard include/config/xen.h) \
    $(wildcard include/config/x86/32.h) \
    $(wildcard include/config/paravirt.h) \
  /build/buildd/linux-3.0.0/include/linux/crypto.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/atomic.h \
    $(wildcard include/config/m386.h) \
    $(wildcard include/config/x86/64.h) \
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
  /build/buildd/linux-3.0.0/arch/x86/include/asm/posix_types.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/posix_types_32.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/processor.h \
    $(wildcard include/config/x86/vsmp.h) \
    $(wildcard include/config/smp.h) \
    $(wildcard include/config/cc/stackprotector.h) \
    $(wildcard include/config/m486.h) \
    $(wildcard include/config/x86/debugctlmsr.h) \
    $(wildcard include/config/cpu/sup/amd.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/processor-flags.h \
    $(wildcard include/config/vm86.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/vm86.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ptrace.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ptrace-abi.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/segment.h \
  /build/buildd/linux-3.0.0/include/linux/const.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/page_types.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/page_32_types.h \
    $(wildcard include/config/highmem4g.h) \
    $(wildcard include/config/highmem64g.h) \
    $(wildcard include/config/page/offset.h) \
    $(wildcard include/config/x86/pae.h) \
  /build/buildd/linux-3.0.0/include/linux/init.h \
    $(wildcard include/config/modules.h) \
    $(wildcard include/config/hotplug.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/ptrace.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/math_emu.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/sigcontext.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/current.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/percpu.h \
    $(wildcard include/config/x86/64/smp.h) \
    $(wildcard include/config/x86/cmpxchg64.h) \
  /build/buildd/linux-3.0.0/include/linux/kernel.h \
    $(wildcard include/config/preempt/voluntary.h) \
    $(wildcard include/config/debug/spinlock/sleep.h) \
    $(wildcard include/config/prove/locking.h) \
    $(wildcard include/config/ring/buffer.h) \
    $(wildcard include/config/tracing.h) \
    $(wildcard include/config/numa.h) \
    $(wildcard include/config/compaction.h) \
    $(wildcard include/config/ftrace/mcount/record.h) \
  /usr/lib/gcc/i686-linux-gnu/4.6.1/include/stdarg.h \
  /build/buildd/linux-3.0.0/include/linux/linkage.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/linkage.h \
    $(wildcard include/config/x86/alignment/16.h) \
  /build/buildd/linux-3.0.0/include/linux/stringify.h \
  /build/buildd/linux-3.0.0/include/linux/bitops.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/bitops.h \
    $(wildcard include/config/x86/cmov.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/alternative.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/asm.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cpufeature.h \
    $(wildcard include/config/x86/invlpg.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/required-features.h \
    $(wildcard include/config/x86/minimum/cpu/family.h) \
    $(wildcard include/config/math/emulation.h) \
    $(wildcard include/config/x86/use/3dnow.h) \
    $(wildcard include/config/x86/p6/nop.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/bitops/find.h \
    $(wildcard include/config/generic/find/first/bit.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/bitops/sched.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/arch_hweight.h \
  /build/buildd/linux-3.0.0/include/asm-generic/bitops/const_hweight.h \
  /build/buildd/linux-3.0.0/include/asm-generic/bitops/fls64.h \
  /build/buildd/linux-3.0.0/include/asm-generic/bitops/le.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/byteorder.h \
  /build/buildd/linux-3.0.0/include/linux/byteorder/little_endian.h \
  /build/buildd/linux-3.0.0/include/linux/swab.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/swab.h \
    $(wildcard include/config/x86/bswap.h) \
  /build/buildd/linux-3.0.0/include/linux/byteorder/generic.h \
  /build/buildd/linux-3.0.0/include/linux/log2.h \
    $(wildcard include/config/arch/has/ilog2/u32.h) \
    $(wildcard include/config/arch/has/ilog2/u64.h) \
  /build/buildd/linux-3.0.0/include/linux/typecheck.h \
  /build/buildd/linux-3.0.0/include/linux/printk.h \
    $(wildcard include/config/printk.h) \
    $(wildcard include/config/dynamic/debug.h) \
  /build/buildd/linux-3.0.0/include/linux/dynamic_debug.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/bug.h \
    $(wildcard include/config/bug.h) \
    $(wildcard include/config/debug/bugverbose.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/bug.h \
    $(wildcard include/config/generic/bug.h) \
    $(wildcard include/config/generic/bug/relative/pointers.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/div64.h \
  /build/buildd/linux-3.0.0/include/asm-generic/percpu.h \
    $(wildcard include/config/debug/preempt.h) \
    $(wildcard include/config/have/setup/per/cpu/area.h) \
  /build/buildd/linux-3.0.0/include/linux/threads.h \
    $(wildcard include/config/nr/cpus.h) \
    $(wildcard include/config/base/small.h) \
  /build/buildd/linux-3.0.0/include/linux/percpu-defs.h \
    $(wildcard include/config/debug/force/weak/per/cpu.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/system.h \
    $(wildcard include/config/ia32/emulation.h) \
    $(wildcard include/config/x86/32/lazy/gs.h) \
    $(wildcard include/config/x86/ppro/fence.h) \
    $(wildcard include/config/x86/oostore.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cmpxchg.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cmpxchg_32.h \
    $(wildcard include/config/x86/cmpxchg.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/nops.h \
    $(wildcard include/config/mk7.h) \
  /build/buildd/linux-3.0.0/include/linux/irqflags.h \
    $(wildcard include/config/trace/irqflags.h) \
    $(wildcard include/config/irqsoff/tracer.h) \
    $(wildcard include/config/preempt/tracer.h) \
    $(wildcard include/config/trace/irqflags/support.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/irqflags.h \
    $(wildcard include/config/debug/lock/alloc.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/paravirt.h \
    $(wildcard include/config/transparent/hugepage.h) \
    $(wildcard include/config/paravirt/spinlocks.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable_types.h \
    $(wildcard include/config/kmemcheck.h) \
    $(wildcard include/config/compat/vdso.h) \
    $(wildcard include/config/proc/fs.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable_32_types.h \
    $(wildcard include/config/highmem.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable-2level_types.h \
  /build/buildd/linux-3.0.0/include/asm-generic/pgtable-nopud.h \
  /build/buildd/linux-3.0.0/include/asm-generic/pgtable-nopmd.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/paravirt_types.h \
    $(wildcard include/config/x86/local/apic.h) \
    $(wildcard include/config/paravirt/debug.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/desc_defs.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/kmap_types.h \
    $(wildcard include/config/debug/highmem.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/kmap_types.h \
  /build/buildd/linux-3.0.0/include/linux/cpumask.h \
    $(wildcard include/config/cpumask/offstack.h) \
    $(wildcard include/config/hotplug/cpu.h) \
    $(wildcard include/config/debug/per/cpu/maps.h) \
    $(wildcard include/config/disable/obsolete/cpumask/functions.h) \
  /build/buildd/linux-3.0.0/include/linux/bitmap.h \
  /build/buildd/linux-3.0.0/include/linux/string.h \
    $(wildcard include/config/binary/printf.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/string.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/string_32.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/page.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/page_32.h \
    $(wildcard include/config/hugetlb/page.h) \
    $(wildcard include/config/debug/virtual.h) \
    $(wildcard include/config/flatmem.h) \
    $(wildcard include/config/x86/3dnow.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/memory_model.h \
    $(wildcard include/config/discontigmem.h) \
    $(wildcard include/config/sparsemem/vmemmap.h) \
    $(wildcard include/config/sparsemem.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/getorder.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/msr.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/msr-index.h \
  /build/buildd/linux-3.0.0/include/linux/ioctl.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ioctl.h \
  /build/buildd/linux-3.0.0/include/asm-generic/ioctl.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/errno.h \
  /build/buildd/linux-3.0.0/include/asm-generic/errno.h \
  /build/buildd/linux-3.0.0/include/asm-generic/errno-base.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cpumask.h \
  /build/buildd/linux-3.0.0/include/linux/personality.h \
  /build/buildd/linux-3.0.0/include/linux/cache.h \
    $(wildcard include/config/arch/has/cache/line/size.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cache.h \
    $(wildcard include/config/x86/l1/cache/shift.h) \
    $(wildcard include/config/x86/internode/cache/shift.h) \
  /build/buildd/linux-3.0.0/include/linux/math64.h \
  /build/buildd/linux-3.0.0/include/linux/err.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/atomic64_32.h \
  /build/buildd/linux-3.0.0/include/asm-generic/atomic-long.h \
  /build/buildd/linux-3.0.0/include/linux/module.h \
    $(wildcard include/config/symbol/prefix.h) \
    $(wildcard include/config/sysfs.h) \
    $(wildcard include/config/modversions.h) \
    $(wildcard include/config/unused/symbols.h) \
    $(wildcard include/config/kallsyms.h) \
    $(wildcard include/config/tracepoints.h) \
    $(wildcard include/config/event/tracing.h) \
    $(wildcard include/config/module/unload.h) \
    $(wildcard include/config/constructors.h) \
    $(wildcard include/config/debug/set/module/ronx.h) \
  /build/buildd/linux-3.0.0/include/linux/list.h \
    $(wildcard include/config/debug/list.h) \
  /build/buildd/linux-3.0.0/include/linux/poison.h \
    $(wildcard include/config/illegal/pointer/value.h) \
  /build/buildd/linux-3.0.0/include/linux/stat.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/stat.h \
  /build/buildd/linux-3.0.0/include/linux/time.h \
    $(wildcard include/config/arch/uses/gettimeoffset.h) \
  /build/buildd/linux-3.0.0/include/linux/seqlock.h \
  /build/buildd/linux-3.0.0/include/linux/spinlock.h \
    $(wildcard include/config/debug/spinlock.h) \
    $(wildcard include/config/generic/lockbreak.h) \
    $(wildcard include/config/preempt.h) \
  /build/buildd/linux-3.0.0/include/linux/preempt.h \
    $(wildcard include/config/preempt/notifiers.h) \
  /build/buildd/linux-3.0.0/include/linux/thread_info.h \
    $(wildcard include/config/compat.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/thread_info.h \
    $(wildcard include/config/debug/stack/usage.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ftrace.h \
    $(wildcard include/config/function/tracer.h) \
    $(wildcard include/config/dynamic/ftrace.h) \
  /build/buildd/linux-3.0.0/include/linux/bottom_half.h \
  /build/buildd/linux-3.0.0/include/linux/spinlock_types.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/spinlock_types.h \
  /build/buildd/linux-3.0.0/include/linux/lockdep.h \
    $(wildcard include/config/lockdep.h) \
    $(wildcard include/config/lock/stat.h) \
    $(wildcard include/config/prove/rcu.h) \
  /build/buildd/linux-3.0.0/include/linux/rwlock_types.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/spinlock.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/rwlock.h \
  /build/buildd/linux-3.0.0/include/linux/rwlock.h \
  /build/buildd/linux-3.0.0/include/linux/spinlock_api_smp.h \
    $(wildcard include/config/inline/spin/lock.h) \
    $(wildcard include/config/inline/spin/lock/bh.h) \
    $(wildcard include/config/inline/spin/lock/irq.h) \
    $(wildcard include/config/inline/spin/lock/irqsave.h) \
    $(wildcard include/config/inline/spin/trylock.h) \
    $(wildcard include/config/inline/spin/trylock/bh.h) \
    $(wildcard include/config/inline/spin/unlock.h) \
    $(wildcard include/config/inline/spin/unlock/bh.h) \
    $(wildcard include/config/inline/spin/unlock/irq.h) \
    $(wildcard include/config/inline/spin/unlock/irqrestore.h) \
  /build/buildd/linux-3.0.0/include/linux/rwlock_api_smp.h \
    $(wildcard include/config/inline/read/lock.h) \
    $(wildcard include/config/inline/write/lock.h) \
    $(wildcard include/config/inline/read/lock/bh.h) \
    $(wildcard include/config/inline/write/lock/bh.h) \
    $(wildcard include/config/inline/read/lock/irq.h) \
    $(wildcard include/config/inline/write/lock/irq.h) \
    $(wildcard include/config/inline/read/lock/irqsave.h) \
    $(wildcard include/config/inline/write/lock/irqsave.h) \
    $(wildcard include/config/inline/read/trylock.h) \
    $(wildcard include/config/inline/write/trylock.h) \
    $(wildcard include/config/inline/read/unlock.h) \
    $(wildcard include/config/inline/write/unlock.h) \
    $(wildcard include/config/inline/read/unlock/bh.h) \
    $(wildcard include/config/inline/write/unlock/bh.h) \
    $(wildcard include/config/inline/read/unlock/irq.h) \
    $(wildcard include/config/inline/write/unlock/irq.h) \
    $(wildcard include/config/inline/read/unlock/irqrestore.h) \
    $(wildcard include/config/inline/write/unlock/irqrestore.h) \
  /build/buildd/linux-3.0.0/include/linux/kmod.h \
  /build/buildd/linux-3.0.0/include/linux/gfp.h \
    $(wildcard include/config/zone/dma.h) \
    $(wildcard include/config/zone/dma32.h) \
  /build/buildd/linux-3.0.0/include/linux/mmzone.h \
    $(wildcard include/config/force/max/zoneorder.h) \
    $(wildcard include/config/memory/hotplug.h) \
    $(wildcard include/config/arch/populates/node/map.h) \
    $(wildcard include/config/flat/node/mem/map.h) \
    $(wildcard include/config/cgroup/mem/res/ctlr.h) \
    $(wildcard include/config/no/bootmem.h) \
    $(wildcard include/config/have/memory/present.h) \
    $(wildcard include/config/have/memoryless/nodes.h) \
    $(wildcard include/config/need/node/memmap/size.h) \
    $(wildcard include/config/need/multiple/nodes.h) \
    $(wildcard include/config/have/arch/early/pfn/to/nid.h) \
    $(wildcard include/config/sparsemem/extreme.h) \
    $(wildcard include/config/have/arch/pfn/valid.h) \
    $(wildcard include/config/nodes/span/other/nodes.h) \
    $(wildcard include/config/holes/in/zone.h) \
    $(wildcard include/config/arch/has/holes/memorymodel.h) \
  /build/buildd/linux-3.0.0/include/linux/wait.h \
  /build/buildd/linux-3.0.0/include/linux/numa.h \
    $(wildcard include/config/nodes/shift.h) \
  /build/buildd/linux-3.0.0/include/linux/nodemask.h \
  /build/buildd/linux-3.0.0/include/linux/pageblock-flags.h \
    $(wildcard include/config/hugetlb/page/size/variable.h) \
  include/generated/bounds.h \
  /build/buildd/linux-3.0.0/include/linux/memory_hotplug.h \
    $(wildcard include/config/memory/hotremove.h) \
    $(wildcard include/config/have/arch/nodedata/extension.h) \
  /build/buildd/linux-3.0.0/include/linux/notifier.h \
  /build/buildd/linux-3.0.0/include/linux/errno.h \
  /build/buildd/linux-3.0.0/include/linux/mutex.h \
    $(wildcard include/config/debug/mutexes.h) \
    $(wildcard include/config/have/arch/mutex/cpu/relax.h) \
  /build/buildd/linux-3.0.0/include/linux/rwsem.h \
    $(wildcard include/config/rwsem/generic/spinlock.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/rwsem.h \
  /build/buildd/linux-3.0.0/include/linux/srcu.h \
  /build/buildd/linux-3.0.0/include/linux/topology.h \
    $(wildcard include/config/sched/smt.h) \
    $(wildcard include/config/sched/mc.h) \
    $(wildcard include/config/sched/book.h) \
    $(wildcard include/config/use/percpu/numa/node/id.h) \
  /build/buildd/linux-3.0.0/include/linux/smp.h \
    $(wildcard include/config/use/generic/smp/helpers.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/smp.h \
    $(wildcard include/config/x86/io/apic.h) \
    $(wildcard include/config/x86/32/smp.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/mpspec.h \
    $(wildcard include/config/x86/numaq.h) \
    $(wildcard include/config/mca.h) \
    $(wildcard include/config/eisa.h) \
    $(wildcard include/config/x86/mpparse.h) \
    $(wildcard include/config/acpi.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/mpspec_def.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/x86_init.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/bootparam.h \
  /build/buildd/linux-3.0.0/include/linux/screen_info.h \
  /build/buildd/linux-3.0.0/include/linux/apm_bios.h \
  /build/buildd/linux-3.0.0/include/linux/edd.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/e820.h \
    $(wildcard include/config/efi.h) \
    $(wildcard include/config/intel/txt.h) \
    $(wildcard include/config/hibernation.h) \
    $(wildcard include/config/memtest.h) \
  /build/buildd/linux-3.0.0/include/linux/ioport.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ist.h \
  /build/buildd/linux-3.0.0/include/video/edid.h \
    $(wildcard include/config/x86.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/apicdef.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/apic.h \
    $(wildcard include/config/x86/x2apic.h) \
  /build/buildd/linux-3.0.0/include/linux/pm.h \
    $(wildcard include/config/pm.h) \
    $(wildcard include/config/pm/sleep.h) \
    $(wildcard include/config/pm/runtime.h) \
  /build/buildd/linux-3.0.0/include/linux/workqueue.h \
    $(wildcard include/config/debug/objects/work.h) \
    $(wildcard include/config/freezer.h) \
  /build/buildd/linux-3.0.0/include/linux/timer.h \
    $(wildcard include/config/timer/stats.h) \
    $(wildcard include/config/debug/objects/timers.h) \
  /build/buildd/linux-3.0.0/include/linux/ktime.h \
    $(wildcard include/config/ktime/scalar.h) \
  /build/buildd/linux-3.0.0/include/linux/jiffies.h \
  /build/buildd/linux-3.0.0/include/linux/timex.h \
  /build/buildd/linux-3.0.0/include/linux/param.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/param.h \
  /build/buildd/linux-3.0.0/include/asm-generic/param.h \
    $(wildcard include/config/hz.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/timex.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/tsc.h \
    $(wildcard include/config/x86/tsc.h) \
  /build/buildd/linux-3.0.0/include/linux/debugobjects.h \
    $(wildcard include/config/debug/objects.h) \
    $(wildcard include/config/debug/objects/free.h) \
  /build/buildd/linux-3.0.0/include/linux/completion.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/fixmap.h \
    $(wildcard include/config/provide/ohci1394/dma/init.h) \
    $(wildcard include/config/x86/visws/apic.h) \
    $(wildcard include/config/x86/f00f/bug.h) \
    $(wildcard include/config/x86/cyclone/timer.h) \
    $(wildcard include/config/pci/mmconfig.h) \
    $(wildcard include/config/x86/mrst.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/acpi.h \
    $(wildcard include/config/acpi/numa.h) \
  /build/buildd/linux-3.0.0/include/acpi/pdc_intel.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/numa.h \
    $(wildcard include/config/numa/emu.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/topology.h \
    $(wildcard include/config/x86/ht.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/topology.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/numa_32.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/mmu.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/trampoline.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/io.h \
  /build/buildd/linux-3.0.0/include/xen/xen.h \
    $(wildcard include/config/xen/dom0.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/iomap.h \
  /build/buildd/linux-3.0.0/include/linux/vmalloc.h \
    $(wildcard include/config/mmu.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/io_apic.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/irq_vectors.h \
    $(wildcard include/config/sparse/irq.h) \
  /build/buildd/linux-3.0.0/include/linux/percpu.h \
    $(wildcard include/config/need/per/cpu/embed/first/chunk.h) \
    $(wildcard include/config/need/per/cpu/page/first/chunk.h) \
  /build/buildd/linux-3.0.0/include/linux/pfn.h \
  /build/buildd/linux-3.0.0/include/linux/mmdebug.h \
    $(wildcard include/config/debug/vm.h) \
  /build/buildd/linux-3.0.0/include/linux/sysctl.h \
  /build/buildd/linux-3.0.0/include/linux/rcupdate.h \
    $(wildcard include/config/rcu/torture/test.h) \
    $(wildcard include/config/tree/rcu.h) \
    $(wildcard include/config/tree/preempt/rcu.h) \
    $(wildcard include/config/preempt/rcu.h) \
    $(wildcard include/config/no/hz.h) \
    $(wildcard include/config/tiny/rcu.h) \
    $(wildcard include/config/tiny/preempt/rcu.h) \
    $(wildcard include/config/debug/objects/rcu/head.h) \
    $(wildcard include/config/preempt/rt.h) \
  /build/buildd/linux-3.0.0/include/linux/rcutree.h \
  /build/buildd/linux-3.0.0/include/linux/elf.h \
  /build/buildd/linux-3.0.0/include/linux/elf-em.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/elf.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/user.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/user_32.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/auxvec.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/vdso.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/desc.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ldt.h \
  /build/buildd/linux-3.0.0/include/linux/mm_types.h \
    $(wildcard include/config/split/ptlock/cpus.h) \
    $(wildcard include/config/want/page/debug/flags.h) \
    $(wildcard include/config/aio.h) \
    $(wildcard include/config/mm/owner.h) \
    $(wildcard include/config/mmu/notifier.h) \
  /build/buildd/linux-3.0.0/include/linux/auxvec.h \
  /build/buildd/linux-3.0.0/include/linux/prio_tree.h \
  /build/buildd/linux-3.0.0/include/linux/rbtree.h \
  /build/buildd/linux-3.0.0/include/linux/page-debug-flags.h \
    $(wildcard include/config/page/poisoning.h) \
    $(wildcard include/config/page/debug/something/else.h) \
  /build/buildd/linux-3.0.0/include/linux/kobject.h \
  /build/buildd/linux-3.0.0/include/linux/sysfs.h \
  /build/buildd/linux-3.0.0/include/linux/kobject_ns.h \
  /build/buildd/linux-3.0.0/include/linux/kref.h \
  /build/buildd/linux-3.0.0/include/linux/moduleparam.h \
    $(wildcard include/config/alpha.h) \
    $(wildcard include/config/ia64.h) \
    $(wildcard include/config/ppc64.h) \
  /build/buildd/linux-3.0.0/include/linux/tracepoint.h \
  /build/buildd/linux-3.0.0/include/linux/jump_label.h \
    $(wildcard include/config/jump/label.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/jump_label.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/module.h \
    $(wildcard include/config/m586.h) \
    $(wildcard include/config/m586tsc.h) \
    $(wildcard include/config/m586mmx.h) \
    $(wildcard include/config/mcore2.h) \
    $(wildcard include/config/matom.h) \
    $(wildcard include/config/m686.h) \
    $(wildcard include/config/mpentiumii.h) \
    $(wildcard include/config/mpentiumiii.h) \
    $(wildcard include/config/mpentiumm.h) \
    $(wildcard include/config/mpentium4.h) \
    $(wildcard include/config/mk6.h) \
    $(wildcard include/config/mk8.h) \
    $(wildcard include/config/melan.h) \
    $(wildcard include/config/mcrusoe.h) \
    $(wildcard include/config/mefficeon.h) \
    $(wildcard include/config/mwinchipc6.h) \
    $(wildcard include/config/mwinchip3d.h) \
    $(wildcard include/config/mcyrixiii.h) \
    $(wildcard include/config/mviac3/2.h) \
    $(wildcard include/config/mviac7.h) \
    $(wildcard include/config/mgeodegx1.h) \
    $(wildcard include/config/mgeode/lx.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/module.h \
  /build/buildd/linux-3.0.0/include/trace/events/module.h \
  /build/buildd/linux-3.0.0/include/trace/define_trace.h \
  /build/buildd/linux-3.0.0/include/linux/slab.h \
    $(wildcard include/config/slab/debug.h) \
    $(wildcard include/config/failslab.h) \
    $(wildcard include/config/slub.h) \
    $(wildcard include/config/slob.h) \
    $(wildcard include/config/debug/slab.h) \
    $(wildcard include/config/slab.h) \
  /build/buildd/linux-3.0.0/include/linux/slub_def.h \
    $(wildcard include/config/slub/stats.h) \
    $(wildcard include/config/slub/debug.h) \
  /build/buildd/linux-3.0.0/include/linux/kmemleak.h \
    $(wildcard include/config/debug/kmemleak.h) \
  /build/buildd/linux-3.0.0/include/linux/uaccess.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/uaccess.h \
    $(wildcard include/config/x86/wp/works/ok.h) \
    $(wildcard include/config/x86/intel/usercopy.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/uaccess_32.h \
    $(wildcard include/config/debug/strict/user/copy/checks.h) \
  /build/buildd/linux-3.0.0/include/linux/sched.h \
    $(wildcard include/config/sched/debug.h) \
    $(wildcard include/config/lockup/detector.h) \
    $(wildcard include/config/detect/hung/task.h) \
    $(wildcard include/config/core/dump/default/elf/headers.h) \
    $(wildcard include/config/sched/autogroup.h) \
    $(wildcard include/config/virt/cpu/accounting.h) \
    $(wildcard include/config/bsd/process/acct.h) \
    $(wildcard include/config/taskstats.h) \
    $(wildcard include/config/audit.h) \
    $(wildcard include/config/cgroups.h) \
    $(wildcard include/config/inotify/user.h) \
    $(wildcard include/config/fanotify.h) \
    $(wildcard include/config/epoll.h) \
    $(wildcard include/config/posix/mqueue.h) \
    $(wildcard include/config/keys.h) \
    $(wildcard include/config/perf/events.h) \
    $(wildcard include/config/schedstats.h) \
    $(wildcard include/config/task/delay/acct.h) \
    $(wildcard include/config/fair/group/sched.h) \
    $(wildcard include/config/rt/group/sched.h) \
    $(wildcard include/config/blk/dev/io/trace.h) \
    $(wildcard include/config/rcu/boost.h) \
    $(wildcard include/config/compat/brk.h) \
    $(wildcard include/config/sysvipc.h) \
    $(wildcard include/config/auditsyscall.h) \
    $(wildcard include/config/generic/hardirqs.h) \
    $(wildcard include/config/rt/mutexes.h) \
    $(wildcard include/config/block.h) \
    $(wildcard include/config/task/xacct.h) \
    $(wildcard include/config/cpusets.h) \
    $(wildcard include/config/futex.h) \
    $(wildcard include/config/fault/injection.h) \
    $(wildcard include/config/latencytop.h) \
    $(wildcard include/config/function/graph/tracer.h) \
    $(wildcard include/config/have/hw/breakpoint.h) \
    $(wildcard include/config/have/unstable/sched/clock.h) \
    $(wildcard include/config/irq/time/accounting.h) \
    $(wildcard include/config/stack/growsup.h) \
    $(wildcard include/config/cgroup/sched.h) \
  /build/buildd/linux-3.0.0/include/linux/capability.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/cputime.h \
  /build/buildd/linux-3.0.0/include/asm-generic/cputime.h \
  /build/buildd/linux-3.0.0/include/linux/sem.h \
  /build/buildd/linux-3.0.0/include/linux/ipc.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ipcbuf.h \
  /build/buildd/linux-3.0.0/include/asm-generic/ipcbuf.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/sembuf.h \
  /build/buildd/linux-3.0.0/include/linux/signal.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/signal.h \
  /build/buildd/linux-3.0.0/include/asm-generic/signal-defs.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/siginfo.h \
  /build/buildd/linux-3.0.0/include/asm-generic/siginfo.h \
  /build/buildd/linux-3.0.0/include/linux/pid.h \
  /build/buildd/linux-3.0.0/include/linux/proportions.h \
  /build/buildd/linux-3.0.0/include/linux/percpu_counter.h \
  /build/buildd/linux-3.0.0/include/linux/seccomp.h \
    $(wildcard include/config/seccomp.h) \
    $(wildcard include/config/seccomp/filter.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/seccomp.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/seccomp_32.h \
  /build/buildd/linux-3.0.0/include/linux/unistd.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/unistd.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/unistd_32.h \
  /build/buildd/linux-3.0.0/include/linux/rculist.h \
  /build/buildd/linux-3.0.0/include/linux/rtmutex.h \
    $(wildcard include/config/debug/rt/mutexes.h) \
  /build/buildd/linux-3.0.0/include/linux/plist.h \
    $(wildcard include/config/debug/pi/list.h) \
  /build/buildd/linux-3.0.0/include/linux/resource.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/resource.h \
  /build/buildd/linux-3.0.0/include/asm-generic/resource.h \
  /build/buildd/linux-3.0.0/include/linux/hrtimer.h \
    $(wildcard include/config/high/res/timers.h) \
    $(wildcard include/config/timerfd.h) \
  /build/buildd/linux-3.0.0/include/linux/timerqueue.h \
  /build/buildd/linux-3.0.0/include/linux/task_io_accounting.h \
    $(wildcard include/config/task/io/accounting.h) \
  /build/buildd/linux-3.0.0/include/linux/latencytop.h \
  /build/buildd/linux-3.0.0/include/linux/cred.h \
    $(wildcard include/config/debug/credentials.h) \
    $(wildcard include/config/security.h) \
    $(wildcard include/config/user/ns.h) \
  /build/buildd/linux-3.0.0/include/linux/key.h \
    $(wildcard include/config/sysctl.h) \
  /build/buildd/linux-3.0.0/include/linux/selinux.h \
    $(wildcard include/config/security/selinux.h) \
  /build/buildd/linux-3.0.0/include/linux/aio.h \
  /build/buildd/linux-3.0.0/include/linux/aio_abi.h \
  /build/buildd/linux-3.0.0/include/linux/uio.h \
  /build/buildd/linux-3.0.0/include/linux/hardirq.h \
  /build/buildd/linux-3.0.0/include/linux/ftrace_irq.h \
    $(wildcard include/config/ftrace/nmi/enter.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/hardirq.h \
    $(wildcard include/config/x86/thermal/vector.h) \
    $(wildcard include/config/x86/mce/threshold.h) \
  /build/buildd/linux-3.0.0/include/linux/irq.h \
    $(wildcard include/config/s390.h) \
    $(wildcard include/config/irq/release/method.h) \
    $(wildcard include/config/generic/pending/irq.h) \
  /build/buildd/linux-3.0.0/include/linux/irqreturn.h \
  /build/buildd/linux-3.0.0/include/linux/irqnr.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/irq.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/irq_regs.h \
  /build/buildd/linux-3.0.0/include/linux/irqdesc.h \
    $(wildcard include/config/irq/preflow/fasteoi.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/hw_irq.h \
    $(wildcard include/config/intr/remap.h) \
  /build/buildd/linux-3.0.0/include/linux/profile.h \
    $(wildcard include/config/profiling.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/sections.h \
    $(wildcard include/config/debug/rodata.h) \
  /build/buildd/linux-3.0.0/include/asm-generic/sections.h \
  /build/buildd/linux-3.0.0/include/linux/suspend.h \
    $(wildcard include/config/vt.h) \
    $(wildcard include/config/vt/console.h) \
    $(wildcard include/config/suspend.h) \
    $(wildcard include/config/hibernate/callbacks.h) \
  /build/buildd/linux-3.0.0/include/linux/swap.h \
    $(wildcard include/config/migration.h) \
    $(wildcard include/config/memory/failure.h) \
    $(wildcard include/config/swap.h) \
    $(wildcard include/config/cgroup/mem/res/ctlr/swap.h) \
  /build/buildd/linux-3.0.0/include/linux/memcontrol.h \
    $(wildcard include/config/cgroup/mem/cont.h) \
  /build/buildd/linux-3.0.0/include/linux/cgroup.h \
  /build/buildd/linux-3.0.0/include/linux/cgroupstats.h \
  /build/buildd/linux-3.0.0/include/linux/taskstats.h \
  /build/buildd/linux-3.0.0/include/linux/prio_heap.h \
  /build/buildd/linux-3.0.0/include/linux/idr.h \
  /build/buildd/linux-3.0.0/include/linux/cgroup_subsys.h \
    $(wildcard include/config/cgroup/debug.h) \
    $(wildcard include/config/cgroup/cpuacct.h) \
    $(wildcard include/config/cgroup/device.h) \
    $(wildcard include/config/cgroup/freezer.h) \
    $(wildcard include/config/net/cls/cgroup.h) \
    $(wildcard include/config/blk/cgroup.h) \
    $(wildcard include/config/cgroup/perf.h) \
  /build/buildd/linux-3.0.0/include/linux/vm_event_item.h \
  /build/buildd/linux-3.0.0/include/linux/node.h \
    $(wildcard include/config/memory/hotplug/sparse.h) \
    $(wildcard include/config/hugetlbfs.h) \
  /build/buildd/linux-3.0.0/include/linux/sysdev.h \
  /build/buildd/linux-3.0.0/include/linux/mm.h \
    $(wildcard include/config/ksm.h) \
    $(wildcard include/config/debug/pagealloc.h) \
  /build/buildd/linux-3.0.0/include/linux/debug_locks.h \
    $(wildcard include/config/debug/locking/api/selftests.h) \
  /build/buildd/linux-3.0.0/include/linux/range.h \
  /build/buildd/linux-3.0.0/include/linux/bit_spinlock.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable_32.h \
    $(wildcard include/config/highpte.h) \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable_32_types.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/pgtable-2level.h \
  /build/buildd/linux-3.0.0/include/asm-generic/pgtable.h \
  /build/buildd/linux-3.0.0/include/linux/page-flags.h \
    $(wildcard include/config/pageflags/extended.h) \
    $(wildcard include/config/arch/uses/pg/uncached.h) \
  /build/buildd/linux-3.0.0/include/linux/huge_mm.h \
  /build/buildd/linux-3.0.0/include/linux/vmstat.h \
    $(wildcard include/config/vm/event/counters.h) \
  /build/buildd/linux-3.0.0/include/linux/kbuild.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/sigframe.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/ucontext.h \
  /build/buildd/linux-3.0.0/include/asm-generic/ucontext.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/suspend.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/suspend_32.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/i387.h \
    $(wildcard include/config/as/fxsaveq.h) \
  /build/buildd/linux-3.0.0/include/linux/kernel_stat.h \
  /build/buildd/linux-3.0.0/include/linux/interrupt.h \
    $(wildcard include/config/irq/forced/threading.h) \
    $(wildcard include/config/generic/irq/probe.h) \
  /build/buildd/linux-3.0.0/include/trace/events/irq.h \
  /build/buildd/linux-3.0.0/include/linux/regset.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/xsave.h \
  /build/buildd/linux-3.0.0/arch/x86/kernel/asm-offsets_32.c \
    $(wildcard include/config/lguest.h) \
    $(wildcard include/config/lguest/guest.h) \
  /build/buildd/linux-3.0.0/include/linux/lguest.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/lguest_hcall.h \
  /build/buildd/linux-3.0.0/arch/x86/kernel/../../../drivers/lguest/lg.h \
  /build/buildd/linux-3.0.0/include/linux/lguest_launcher.h \
  /build/buildd/linux-3.0.0/arch/x86/include/asm/lguest.h \

arch/x86/kernel/asm-offsets.s: $(deps_arch/x86/kernel/asm-offsets.s)

$(deps_arch/x86/kernel/asm-offsets.s):
