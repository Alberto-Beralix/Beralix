#define ATK_MAJOR_VERSION (2)
#define ATK_MINOR_VERSION (0)
#define ATK_MICRO_VERSION (1)
#define ATK_CHECK_VERSION(major,minor,micro) \
	(ATK_MAJOR_VERSION > (major) || \
	 (ATK_MAJOR_VERSION == (major) && ATK_MINOR_VERSION > (minor)) || \
	 (ATK_MAJOR_VERSION == (major) && ATK_MINOR_VERSION == (minor) && ATK_MICRO_VERSION >= (micro)))
