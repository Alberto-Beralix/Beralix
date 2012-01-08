#!/usr/bin/python
import sys
import telepathy
from telepathy.interfaces import CONN_MGR_INTERFACE
from telepathy.constants import CONN_MGR_PARAM_FLAG_REQUIRED, \
                                CONN_MGR_PARAM_FLAG_REGISTER, \
                                CONN_MGR_PARAM_FLAG_HAS_DEFAULT, \
                                CONN_MGR_PARAM_FLAG_SECRET, \
                                CONN_MGR_PARAM_FLAG_DBUS_PROPERTY

if len(sys.argv) >= 2:
    manager_name = sys.argv[1]
else:
    manager_name = "haze"
service_name = "org.freedesktop.Telepathy.ConnectionManager.%s" % manager_name
object_path = "/org/freedesktop/Telepathy/ConnectionManager/%s" % manager_name

object = telepathy.client.ConnectionManager(service_name, object_path)
manager = object[CONN_MGR_INTERFACE]

print "[ConnectionManager]"
print "BusName=%s" % service_name
print "ObjectPath=%s" % object_path
print

protocols = manager.ListProtocols()
protocols.sort()
for protocol in protocols:
    defaults = []
    print "[Protocol %s]" % protocol
    for param in manager.GetParameters(protocol):
        (name, flags, type, default) = param

        print "param-%s=%s" % (name, type),
        if flags & CONN_MGR_PARAM_FLAG_REQUIRED:
            print "required",
        if flags & CONN_MGR_PARAM_FLAG_REGISTER:
            print "register",
        if flags & CONN_MGR_PARAM_FLAG_SECRET:
            print "secret",
        if flags & CONN_MGR_PARAM_FLAG_DBUS_PROPERTY:
            print "dbus-property",
        print

        if flags & CONN_MGR_PARAM_FLAG_HAS_DEFAULT:
            defaults.append( (name, type, default) )
    for default in defaults:
        if default[1] == "b":
            if default[2]:
                value = "true"
            else:
                value = "false"
        else:
            value = str(default[2])
        print "default-%s=%s" % (default[0], value)
    print
