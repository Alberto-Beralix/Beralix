	.file	"bounds.c"
# GNU C (Ubuntu/Linaro 4.6.1-9ubuntu3) version 4.6.1 (i686-linux-gnu)
#	compiled by GNU C version 4.6.1, GMP version 5.0.1, MPFR version 3.0.1-p3, MPC version 0.9
# GGC heuristics: --param ggc-min-expand=100 --param ggc-min-heapsize=131072
# options passed:  -nostdinc -I /usr/src/linux-headers-lbm-
# -I /build/buildd/linux-3.0.0/arch/x86/include
# -I arch/x86/include/generated -I include
# -I /build/buildd/linux-3.0.0/include -I ubuntu/include
# -I /build/buildd/linux-3.0.0/ubuntu/include
# -I /build/buildd/linux-3.0.0/. -I . -imultilib .
# -imultiarch i386-linux-gnu -D __KERNEL__ -D CONFIG_AS_CFI=1
# -D CONFIG_AS_CFI_SIGNAL_FRAME=1 -D CONFIG_AS_CFI_SECTIONS=1
# -D CC_HAVE_ASM_GOTO -D KBUILD_STR(s)=#s
# -D KBUILD_BASENAME=KBUILD_STR(bounds)
# -D KBUILD_MODNAME=KBUILD_STR(bounds)
# -isystem /usr/lib/gcc/i686-linux-gnu/4.6.1/include
# -include include/generated/autoconf.h -MD kernel/.bounds.s.d
# /build/buildd/linux-3.0.0/kernel/bounds.c -m32 -msoft-float -mregparm=3
# -mpreferred-stack-boundary=2 -march=i686 -mtune=generic
# -maccumulate-outgoing-args -mno-sse -mno-mmx -mno-sse2 -mno-3dnow
# -auxbase-strip kernel/bounds.s -O2 -Wall -Wundef -Wstrict-prototypes
# -Wno-trigraphs -Werror=implicit-function-declaration -Wno-format-security
# -Wno-sign-compare -Wframe-larger-than=1024 -Wno-unused-but-set-variable
# -Wdeclaration-after-statement -Wno-pointer-sign -p -fno-strict-aliasing
# -fno-common -fno-delete-null-pointer-checks -freg-struct-return
# -ffreestanding -fstack-protector -fno-asynchronous-unwind-tables
# -fno-omit-frame-pointer -fno-optimize-sibling-calls
# -fno-inline-functions-called-once -fno-strict-overflow -fconserve-stack
# -fverbose-asm
# options enabled:  -fauto-inc-dec -fbranch-count-reg -fcaller-saves
# -fcombine-stack-adjustments -fcompare-elim -fcprop-registers
# -fcrossjumping -fcse-follow-jumps -fdefer-pop -fdevirtualize
# -fdwarf2-cfi-asm -fearly-inlining -feliminate-unused-debug-types
# -fexpensive-optimizations -fforward-propagate -ffunction-cse -fgcse
# -fgcse-lm -fguess-branch-probability -fident -fif-conversion
# -fif-conversion2 -findirect-inlining -finline -finline-small-functions
# -fipa-cp -fipa-profile -fipa-pure-const -fipa-reference -fipa-sra
# -fira-share-save-slots -fira-share-spill-slots -fivopts
# -fkeep-static-consts -fleading-underscore -fmath-errno -fmerge-constants
# -fmerge-debug-strings -fmove-loop-invariants -foptimize-register-move
# -fpartial-inlining -fpeephole -fpeephole2 -fprefetch-loop-arrays
# -fprofile -freg-struct-return -fregmove -freorder-blocks
# -freorder-functions -frerun-cse-after-loop
# -fsched-critical-path-heuristic -fsched-dep-count-heuristic
# -fsched-group-heuristic -fsched-interblock -fsched-last-insn-heuristic
# -fsched-rank-heuristic -fsched-spec -fsched-spec-insn-heuristic
# -fsched-stalled-insns-dep -fschedule-insns2 -fshow-column -fsigned-zeros
# -fsplit-ivs-in-unroller -fsplit-wide-types -fstack-protector
# -fstrict-volatile-bitfields -fthread-jumps -ftoplevel-reorder
# -ftrapping-math -ftree-bit-ccp -ftree-builtin-call-dce -ftree-ccp
# -ftree-ch -ftree-copy-prop -ftree-copyrename -ftree-cselim -ftree-dce
# -ftree-dominator-opts -ftree-dse -ftree-forwprop -ftree-fre
# -ftree-loop-if-convert -ftree-loop-im -ftree-loop-ivcanon
# -ftree-loop-optimize -ftree-parallelize-loops= -ftree-phiprop -ftree-pre
# -ftree-pta -ftree-reassoc -ftree-scev-cprop -ftree-sink
# -ftree-slp-vectorize -ftree-sra -ftree-switch-conversion -ftree-ter
# -ftree-vect-loop-version -ftree-vrp -funit-at-a-time -fvect-cost-model
# -fverbose-asm -fzero-initialized-in-bss -m32 -m96bit-long-double
# -maccumulate-outgoing-args -malign-stringops -mglibc -mieee-fp
# -mno-fancy-math-387 -mno-red-zone -mno-sse4 -mpush-args -msahf
# -mtls-direct-seg-refs

# Compiler executable checksum: 4563c158c7f73de3aa3de4c02c58d3f9

	.text
	.p2align 4,,15
	.globl	foo
	.type	foo, @function
foo:
	pushl	%ebp	#
	movl	%esp, %ebp	#,
	call	mcount
#APP
# 17 "/build/buildd/linux-3.0.0/kernel/bounds.c" 1
	
->NR_PAGEFLAGS $26 __NR_PAGEFLAGS	#
# 0 "" 2
# 18 "/build/buildd/linux-3.0.0/kernel/bounds.c" 1
	
->MAX_NR_ZONES $4 __MAX_NR_ZONES	#
# 0 "" 2
# 19 "/build/buildd/linux-3.0.0/kernel/bounds.c" 1
	
->NR_PCG_FLAGS $7 __NR_PCG_FLAGS	#
# 0 "" 2
#NO_APP
	popl	%ebp	#
	ret
	.size	foo, .-foo
	.ident	"GCC: (Ubuntu/Linaro 4.6.1-9ubuntu3) 4.6.1"
	.section	.note.GNU-stack,"",@progbits
