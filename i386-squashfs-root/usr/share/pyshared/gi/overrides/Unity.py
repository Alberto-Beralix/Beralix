from ..overrides import override
from ..importer import modules

Unity = modules['Unity']._introspection_module
from gi.repository import GLib

__all__ = []

#class Foo(Unity.Foo):
#
#    def __init__(self):
#        Unity.Foo.__init__(self)
#
#Foo = override(Foo)
#__all__.append('Foo')


