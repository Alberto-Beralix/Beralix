#!/usr/bin/env python

'''
Client API library to upload images and videos to imageshack.us

Using "Unified upload API" as described here:

http://reg.imageshack.us/content.php?page=developerpublic

'''

import urllib2_file
import urllib2
import socket
import httplib

from mimetypes import guess_type
from xml.dom.minidom import parseString
from os.path import exists
from urlparse import urlsplit

IMAGE_API_URL = 'http://www.imageshack.us/upload_api.php'
VIDEO_API_URL = 'http://render.imageshack.us/upload_api.php'
HTTP_UPLOAD_TIMEOUT = 300

class UploadException(Exception):
    ''' Exceptions of this class are raised for various upload based errors '''
    pass

class ServerException(Exception):
    ''' Exceptions of this class are raised for upload errors reported by server '''
    
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "ServerException:%s:%s" % (self.code, self.message)

class Uploader:
    ''' Class to upload images and video to imageshack.
    '''
    
    def __init__(self, dev_key, cookie=None, username=None, password=None, timeout=HTTP_UPLOAD_TIMEOUT):
        '''Creates uploader object.
        Args:
        dev_key: developer key (mandatory)
        cookie: imagesack user cookie (optional)
        username,password: imageshack user account credentials (optional)
        timeout: timeout in seconds for upload operation (optional)
        '''
        self.cookie = cookie
        self.username = username
        self.password = password
        self.dev_key = dev_key
        self.timeout = timeout


    def uploadFile(self,
                   filename,
                   optsize = None,
                   remove_bar = True,
                   tags = None,
                   public = None,
                   content_type = None,
                   frame_filename = None):
        ''' upload image or video file

        Args:
        filename: file name of image or video file to upload
        optizie: optional reisizing parameter in format of (widh, height) tuple
        remove_bar: remove information bar on thumbnail
        content_type: content type of file. (optional)
        tags: comma-separated list of tags (optional)
        public: whenever image is public or not. None means "user default" (optional)
        frame_filename: for video files optional video frame which will be shown in player while movie is loading. Must be in JPEG format.

        Returns:
        returns XML document with information on uploaded image.
        '''
        return self._upload(filename, None,
                            optsize, remove_bar,
                            tags, public,
                            content_type, frame_filename)

    def uploadURL(self,
                   url,
                   optsize = None,
                   remove_bar = True,
                   tags = None,
                   public = None,
                   frame_filename = None):
        ''' upload image or video file

        Args:
        url: URL pointing to image or video file to upload
        optizie: optional reisizing parameter in format of (widh, height) tuple
        remove_bar: remove information bar on thumbnail
        content_type: content type of file. (optional)
        tags: comma-separated list of tags (optional)
        public: whenever image is public or not. None means "user default"  (optional)
        frame_filename: for video files optional video frame which will be shown in player while movie is loading. Must be in JPEG format.

        Returns:
        returns XML document with information on uploaded image.
        '''
        return self._upload(None, url,
                            optsize, remove_bar,
                            tags, public,
                            None, frame_filename)

    def _upload(self,
                filename,
                url,
                optsize = None,
                remove_bar = True,
                tags = None,
                public = True,
                content_type = None,
                frame_filename = None):

        if not filename and not url:
            raise UploadException("No source specified")
        
        if (self.username and not self.password) or (self.password and not self.username):
            raise UploadException("Must specify both usernane and password")
            
        if self.username and self.cookie:
            raise UploadException("Must specify either usernane/password or cookie but not both")
        if frame_filename and not exists(frame_filename):
            raise UploadException("File %s does not exist" % frame_filename)
        
        if filename:
            if not exists(filename):
                raise UploadException("File %s does not exist" % filename)
            
            if content_type == None:
                (content_type, encoding) = guess_type(filename, False)
        else:
            content_type = self._getURLContentType(url)

        if content_type==None:
            raise UploadException("Could not guess content/type for input file %s" % filename)
        if content_type.lower().startswith("image/"):
            u = IMAGE_API_URL
            is_video=False
        elif content_type.lower().startswith("video/"):
            u = VIDEO_API_URL
            is_video=True
        else:
            raise UploadException("Unsupported content type %s" % content_type)

        # some sanity checks
        if is_video:
            if optsize:
                raise UploadException("Resizing is not supported for video files")
        else:
            if frame_filename:
                raise UploadException("Could not specify frame for image files")

        if filename:
            fd = open(filename,'rb')
        else:
            fd = None
        try:
            data = {'key' : self.dev_key,
                    'rembar' : self._yesno(remove_bar)
                    }
            if fd:
                data['fileupload']=urllib2_file.FileUpload(fd,content_type)
            else:
                data['url']=url
            if frame_filename!=None:
                tfd = open(frame_filename,'rb')
            else:
                tfd = None
            try:
                if tfd!=None:
                    data['frmupload'] = urllib2_file.FileUpload(tfd,"image/jpeg")

                # Some optional parameters
                if public:
                    data['public'] = self._yesno(public)
                if optsize:
                    data['optimage'] = '1'
                    data['optsize'] = "%dx%d" % optsize
                if self.cookie:
                    data['cookie'] = self.cookie
                if self.username:
                    data['a_username'] = self.username
                if self.password:
                    data['a_password'] = self.username
                if tags:
                    data['tags'] = tags

                req = urllib2.Request(u, data, {})
                socket.setdefaulttimeout(HTTP_UPLOAD_TIMEOUT)
                u = urllib2.urlopen(req)
                xmlres = u.read()
                return self._parseResponse(xmlres)
            finally:
                if tfd!=None:
                    tfd.close()
        finally:
            if fd:
                fd.close()

    def _yesno(self, x):
        if x:
            return 'yes'
        else:
            return 'no'

    def _parseErrorResponse(self, err):
        ia = err.attributes.get('id')
        if ia==None:
            raise UploadException("Cound not decode server error XML response (no id attriubute)")
        raise ServerException(ia.value, self._getText(err.childNodes))


    def _parseResponse(self, xmlres):
        d = parseString(xmlres)
        try:
            links = d.getElementsByTagName('links')
            if links==None or len(links)!=1:
                raise UploadException("Cound not decode server XML response (no links element)")
            error = links[0].getElementsByTagName('error')
            if error!=None and len(error)>0:
                return self._parseErrorResponse(error[0])
            else:
                return xmlres
        finally:
            d.unlink()

    def _getText(self, nodelist):
        rc = ""
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
        return rc

    def _getURLContentType(self, url):
        parsed_url = urlsplit(url)
        if parsed_url==None or parsed_url.hostname==None or len(parsed_url.hostname)==0:
            raise UploadException("Invalid URL %s" % url)
        c = httplib.HTTPConnection(parsed_url.hostname) 
        c.request('HEAD', url)
        r = c.getresponse()
        if r.status!=200:
            raise UploadException("Error %d fetching URL %s" % (r.status, url))
        return r.getheader("Content-Type")

