import imageshack, ubuntuone_uploader
from gi.repository import Gio


IMAGESHACK_KEY = "168DEFKRd9cb284c67a29e715a3abcd19d3884a7"

gsettings = Gio.Settings.new("org.gwibber.preferences")

def upload_imageshack(path, uploader, success_callback, failure_callback):
  u = imageshack.Uploader(IMAGESHACK_KEY)

  try:
    if path.startswith("http://"):
      imgUrl = u.uploadURL(path)
    else:
      imgUrl = u.uploadFile(path)
    if uploader == "imageshack":
      img = imgUrl.split('image_link')[1].split('>')[1].split('<')[0]
    else:
      img = imgUrl.split('yfrog_link')[1].split('>')[1].split('<')[0]
  except imageshack.ServerException, e:
    print str(e)
    img = None
    failure_callback(path, str(e))
  else:
    success_callback(path, img)

def upload_ubuntuone(path, success_callback, failure_callback):
    try:
        u = ubuntuone_uploader.Uploader(success_callback, failure_callback)
        if path.startswith("http://") or path.startswith("https://"):
            raise Exception("Cannot publish web URLs to Ubuntu One")
        u.uploadFile(path) # u will call success_callback or failure_callback
    except e:
        failure_callback(path, str(e))

def upload(path, success_callback, failure_callback):
  uploader = gsettings.get_string("image-uploader") or "imageshack"
  if uploader == "imageshack" or uploader == "yfrog":
    return upload_imageshack(path, uploader, success_callback, failure_callback)
  elif uploader == "ubuntuone":
    return upload_ubuntuone(path, success_callback, failure_callback)
  return upload_imageshack(path)


