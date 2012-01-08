__all__ = ('version', '__version__')

# src/_version.py.  Generated from _version.py.in by configure.
version = (0, 15, 19)

# Append a 1 to the version string only if this is *not* a released version.
if not 1:
    version += (1,)

__version__ = '.'.join(str(x) for x in version)
