#!/usr/bin/env python

def X_is_running():
    '''Returns true if X.org is running'''
    from gi.repository.Gdk import Screen
    try:
        if Screen().get_default():
            return True
    except RuntimeError:
        pass
    return False
