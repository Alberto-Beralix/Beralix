#undef _LARGEFILE_SOURCE
#undef _FILE_OFFSET_BITS
#define _LARGEFILE_SOURCE
#define _FILE_OFFSET_BITS 64
#if defined (GRUB_UTIL) || !defined (GRUB_MACHINE)
#include <config-util.h>
#define NESTED_FUNC_ATTR
#else
/* Define if C symbols get an underscore after compilation. */
#define HAVE_ASM_USCORE 0
/* Define it to \"addr32\" or \"addr32;\" to make GAS happy.  */
#define ADDR32 addr32
/* Define it to \"data32\" or \"data32;\" to make GAS happy. */
#define DATA32 data32
/* Define it to one of __bss_start, edata and _edata.  */
#define BSS_START_SYMBOL __bss_start
/* Define it to either end or _end.  */
#define END_SYMBOL end
/* Name of package.  */
#define PACKAGE "grub"
/* Version number of package.  */
#define VERSION "1.99"
/* Define to the full name and version of this package. */
#define PACKAGE_STRING "GRUB 1.99-12ubuntu5"
/* Define to the version of this package. */
#define PACKAGE_VERSION "1.99-12ubuntu5"
/* Define to the full name of this package. */
#define PACKAGE_NAME "GRUB"
/* Define to the address where bug reports for this package should be sent. */
#define PACKAGE_BUGREPORT "bug-grub@gnu.org"
/* Default boot directory name" */
#define GRUB_BOOT_DIR_NAME "boot"
/* Default grub directory name */
#define GRUB_DIR_NAME "grub"
/* Define to 1 if GCC generates calls to __enable_execute_stack().  */
#define NEED_ENABLE_EXECUTE_STACK 0
/* Define to 1 if GCC generates calls to __register_frame_info().  */
#define NEED_REGISTER_FRAME_INFO 0

#if defined(__i386__)
#define NESTED_FUNC_ATTR __attribute__ ((__regparm__ (1)))
#else
#define NESTED_FUNC_ATTR
#endif

#endif
