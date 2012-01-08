import sys

# very hackish way to avoid "import *" to satisfy pyflakes
# and to avoid import ubuntuone.platform.X as source (it wont work)

if sys.platform == "win32":
    from ubuntuone.platform import windows
    source = windows
else:
    from ubuntuone.platform import linux
    source = linux

from ubuntuone.platform import credentials

target = sys.modules[__name__]
for k in dir(source):
    setattr(target, k, getattr(source, k))
