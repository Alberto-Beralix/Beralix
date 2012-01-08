"""Module with little helper functions and classes:

deprecated - decorator to emit a warning if a depreacted function is used
"""
#Copyright (C) 2008-2009 Sebastian Heinlein <sevel@glatzor.de>
#
#Licensed under the GNU General Public License Version 2
#
#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

__author__ = "Sebastian Heinlein <devel@glatzor.de>"

__all__ = ("deprecated",)

import functools
import warnings

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    Taken from http://wiki.python.org/moin/PythonDecoratorLibrary
    #GeneratingDeprecationWarnings
    """
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.warn_explicit(
            "Call to deprecated function %(funcname)s." % {
                'funcname': func.__name__,
            },
            category=DeprecationWarning,
            filename=func.func_code.co_filename,
            lineno=func.func_code.co_firstlineno + 1
        )
        return func(*args, **kwargs)
    return new_func

# vim:ts=4:sw=4:et
