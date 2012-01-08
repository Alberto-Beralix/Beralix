from const import *

import ctypes
import gnomekeyring
import exceptions

def get_secret(id):
  value = ""
  try:
    value = gnomekeyring.find_items_sync(
        gnomekeyring.ITEM_GENERIC_SECRET,
        {"id": str(id)})[0].secret
    mlock(value)
  except gnomekeyring.NoMatchError:
    print id
    raise exceptions.GwibberServiceError("keyring")

  return value

libc = ctypes.CDLL("libc.so.6")

def mlock(var):
    libc.mlock(var, len(var))

def munlock(var):
    libc.munlock(var, len(var))
