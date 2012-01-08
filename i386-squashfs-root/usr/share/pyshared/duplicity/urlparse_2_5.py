# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-

"""Parse (absolute and relative) URLs.

See RFC 1808: "Relative Uniform Resource Locators", by R. Fielding,
UC Irvine, June 1995.
"""

__all__ = ["urlparse", "urlunparse", "urljoin", "urldefrag",
           "urlsplit", "urlunsplit"]

# A classification of schemes ('' means apply by default)
uses_relative = ['ftp', 'ftps', 'http', 'gopher', 'nntp',
                 'wais', 'file', 'https', 'shttp', 'mms',
                 'prospero', 'rtsp', 'rtspu', '', 'sftp', 'imap', 'imaps']
uses_netloc = ['ftp', 'ftps', 'http', 'gopher', 'nntp', 'telnet',
               'wais', 'file', 'mms', 'https', 'shttp',
               'snews', 'prospero', 'rtsp', 'rtspu', 'rsync', '',
               'svn', 'svn+ssh', 'sftp', 'imap', 'imaps']
non_hierarchical = ['gopher', 'hdl', 'mailto', 'news',
                    'telnet', 'wais', 'snews', 'sip', 'sips', 'imap', 'imaps']
uses_params = ['ftp', 'ftps', 'hdl', 'prospero', 'http',
               'https', 'shttp', 'rtsp', 'rtspu', 'sip', 'sips',
               'mms', '', 'sftp', 'imap', 'imaps']
uses_query = ['http', 'wais', 'https', 'shttp', 'mms',
              'gopher', 'rtsp', 'rtspu', 'sip', 'sips', 'imap', 'imaps', '']
uses_fragment = ['ftp', 'ftps', 'hdl', 'http', 'gopher', 'news',
                 'nntp', 'wais', 'https', 'shttp', 'snews',
                 'file', 'prospero', '']

# Characters valid in scheme names
scheme_chars = ('abcdefghijklmnopqrstuvwxyz'
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                '0123456789'
                '+-.')

MAX_CACHE_SIZE = 20
_parse_cache = {}

def clear_cache():
    """Clear the parse cache."""
    global _parse_cache
    _parse_cache = {}

import string
def _rsplit(str, delim, numsplit):
    parts = string.split(str, delim)
    if len(parts) <= numsplit + 1:
        return parts
    else:
        left = string.join(parts[0:-numsplit], delim)
        right = string.join(parts[len(parts)-numsplit:], delim)
        return [left, right]

class BaseResult(tuple):
    """Base class for the parsed result objects.

    This provides the attributes shared by the two derived result
    objects as read-only properties.  The derived classes are
    responsible for checking the right number of arguments were
    supplied to the constructor.

    """

    __slots__ = ()

    # Attributes that access the basic components of the URL:

    def get_scheme(self):
        return self[0]
    scheme = property(get_scheme)

    def get_netloc(self):
        return self[1]
    netloc = property(get_netloc)

    def get_path(self):
        return self[2]
    path = property(get_path)

    def get_query(self):
        return self[-2]
    query = property(get_query)

    def get_fragment(self):
        return self[-1]
    fragment = property(get_fragment)

    # Additional attributes that provide access to parsed-out portions
    # of the netloc:

    def get_username(self):
        netloc = self.netloc
        if "@" in netloc:
            userinfo = _rsplit(netloc, "@", 1)[0]
            if ":" in userinfo:
                userinfo = userinfo.split(":", 1)[0]
            return userinfo
        return None
    username = property(get_username)

    def get_password(self):
        netloc = self.netloc
        if "@" in netloc:
            userinfo = _rsplit(netloc, "@", 1)[0]
            if ":" in userinfo:
                return userinfo.split(":", 1)[1]
        return None
    password = property(get_password)

    def get_hostname(self):
        netloc = self.netloc
        if "@" in netloc:
            netloc = _rsplit(netloc, "@", 1)[1]
        if ":" in netloc:
            netloc = netloc.split(":", 1)[0]
        return netloc.lower() or None
    hostname = property(get_hostname)

    def get_port(self):
        netloc = self.netloc
        if "@" in netloc:
            netloc = _rsplit(netloc, "@", 1)[1]
        if ":" in netloc:
            port = netloc.split(":", 1)[1]
            return int(port, 10)
        return None
    port = property(get_port)


class SplitResult(BaseResult):

    __slots__ = ()

    def __new__(cls, scheme, netloc, path, query, fragment):
        return BaseResult.__new__(
            cls, (scheme, netloc, path, query, fragment))

    def geturl(self):
        return urlunsplit(self)


class ParseResult(BaseResult):

    __slots__ = ()

    def __new__(cls, scheme, netloc, path, params, query, fragment):
        return BaseResult.__new__(
            cls, (scheme, netloc, path, params, query, fragment))

    def get_params(self):
        return self[3]
    params = property(get_params)

    def geturl(self):
        return urlunparse(self)


def urlparse(url, scheme='', allow_fragments=True):
    """Parse a URL into 6 components:
    <scheme>://<netloc>/<path>;<params>?<query>#<fragment>
    Return a 6-tuple: (scheme, netloc, path, params, query, fragment).
    Note that we don't break the components up in smaller bits
    (e.g. netloc is a single string) and we don't expand % escapes."""
    tuple = urlsplit(url, scheme, allow_fragments)
    scheme, netloc, url, query, fragment = tuple
    if scheme in uses_params and ';' in url:
        url, params = _splitparams(url)
    else:
        params = ''
    return ParseResult(scheme, netloc, url, params, query, fragment)

def _splitparams(url):
    if '/'  in url:
        i = url.find(';', url.rfind('/'))
        if i < 0:
            return url, ''
    else:
        i = url.find(';')
    return url[:i], url[i+1:]

def _splitnetloc(url, start=0):
    for c in '/?#': # the order is important!
        delim = url.find(c, start)
        if delim >= 0:
            break
    else:
        delim = len(url)
    return url[start:delim], url[delim:]

def urlsplit(url, scheme='', allow_fragments=True):
    """Parse a URL into 5 components:
    <scheme>://<netloc>/<path>?<query>#<fragment>
    Return a 5-tuple: (scheme, netloc, path, query, fragment).
    Note that we don't break the components up in smaller bits
    (e.g. netloc is a single string) and we don't expand % escapes."""
    allow_fragments = bool(allow_fragments)
    key = url, scheme, allow_fragments
    cached = _parse_cache.get(key, None)
    if cached:
        return cached
    if len(_parse_cache) >= MAX_CACHE_SIZE: # avoid runaway growth
        clear_cache()
    netloc = query = fragment = ''
    i = url.find(':')
    if i > 0:
        if url[:i] == 'http': # optimize the common case
            scheme = url[:i].lower()
            url = url[i+1:]
            if url[:2] == '//':
                netloc, url = _splitnetloc(url, 2)
            if allow_fragments and '#' in url:
                url, fragment = url.split('#', 1)
            if '?' in url:
                url, query = url.split('?', 1)
            v = SplitResult(scheme, netloc, url, query, fragment)
            _parse_cache[key] = v
            return v
        for c in url[:i]:
            if c not in scheme_chars:
                break
        else:
            scheme, url = url[:i].lower(), url[i+1:]
    if scheme in uses_netloc and url[:2] == '//':
        netloc, url = _splitnetloc(url, 2)
    if allow_fragments and scheme in uses_fragment and '#' in url:
        url, fragment = url.split('#', 1)
    if scheme in uses_query and '?' in url:
        url, query = url.split('?', 1)
    v = SplitResult(scheme, netloc, url, query, fragment)
    _parse_cache[key] = v
    return v

def urlunparse((scheme, netloc, url, params, query, fragment)):
    """Put a parsed URL back together again.  This may result in a
    slightly different, but equivalent URL, if the URL that was parsed
    originally had redundant delimiters, e.g. a ? with an empty query
    (the draft states that these are equivalent)."""
    if params:
        url = "%s;%s" % (url, params)
    return urlunsplit((scheme, netloc, url, query, fragment))

def urlunsplit((scheme, netloc, url, query, fragment)):
    if netloc or (scheme and scheme in uses_netloc and url[:2] != '//'):
        if url and url[:1] != '/': url = '/' + url
        url = '//' + (netloc or '') + url
    if scheme:
        url = scheme + ':' + url
    if query:
        url = url + '?' + query
    if fragment:
        url = url + '#' + fragment
    return url

def urljoin(base, url, allow_fragments=True):
    """Join a base URL and a possibly relative URL to form an absolute
    interpretation of the latter."""
    if not base:
        return url
    if not url:
        return base
    bscheme, bnetloc, bpath, bparams, bquery, bfragment = urlparse(base, '', allow_fragments) #@UnusedVariable
    scheme, netloc, path, params, query, fragment = urlparse(url, bscheme, allow_fragments)
    if scheme != bscheme or scheme not in uses_relative:
        return url
    if scheme in uses_netloc:
        if netloc:
            return urlunparse((scheme, netloc, path,
                               params, query, fragment))
        netloc = bnetloc
    if path[:1] == '/':
        return urlunparse((scheme, netloc, path,
                           params, query, fragment))
    if not (path or params or query):
        return urlunparse((scheme, netloc, bpath,
                           bparams, bquery, fragment))
    segments = bpath.split('/')[:-1] + path.split('/')
    # XXX The stuff below is bogus in various ways...
    if segments[-1] == '.':
        segments[-1] = ''
    while '.' in segments:
        segments.remove('.')
    while 1:
        i = 1
        n = len(segments) - 1
        while i < n:
            if (segments[i] == '..'
                and segments[i-1] not in ('', '..')):
                del segments[i-1:i+1]
                break
            i = i+1
        else:
            break
    if segments == ['', '..']:
        segments[-1] = ''
    elif len(segments) >= 2 and segments[-1] == '..':
        segments[-2:] = ['']
    return urlunparse((scheme, netloc, '/'.join(segments),
                       params, query, fragment))

def urldefrag(url):
    """Removes any existing fragment from URL.

    Returns a tuple of the defragmented URL and the fragment.  If
    the URL contained no fragments, the second element is the
    empty string.
    """
    if '#' in url:
        s, n, p, a, q, frag = urlparse(url)
        defrag = urlunparse((s, n, p, a, q, ''))
        return defrag, frag
    else:
        return url, ''


test_input = """
      http://a/b/c/d

      g:h        = <URL:g:h>
      http:g     = <URL:http://a/b/c/g>
      http:      = <URL:http://a/b/c/d>
      g          = <URL:http://a/b/c/g>
      ./g        = <URL:http://a/b/c/g>
      g/         = <URL:http://a/b/c/g/>
      /g         = <URL:http://a/g>
      //g        = <URL:http://g>
      ?y         = <URL:http://a/b/c/d?y>
      g?y        = <URL:http://a/b/c/g?y>
      g?y/./x    = <URL:http://a/b/c/g?y/./x>
      .          = <URL:http://a/b/c/>
      ./         = <URL:http://a/b/c/>
      ..         = <URL:http://a/b/>
      ../        = <URL:http://a/b/>
      ../g       = <URL:http://a/b/g>
      ../..      = <URL:http://a/>
      ../../g    = <URL:http://a/g>
      ../../../g = <URL:http://a/../g>
      ./../g     = <URL:http://a/b/g>
      ./g/.      = <URL:http://a/b/c/g/>
      /./g       = <URL:http://a/./g>
      g/./h      = <URL:http://a/b/c/g/h>
      g/../h     = <URL:http://a/b/c/h>
      http:g     = <URL:http://a/b/c/g>
      http:      = <URL:http://a/b/c/d>
      http:?y         = <URL:http://a/b/c/d?y>
      http:g?y        = <URL:http://a/b/c/g?y>
      http:g?y/./x    = <URL:http://a/b/c/g?y/./x>
"""

def test():
    import sys
    base = ''
    if sys.argv[1:]:
        fn = sys.argv[1]
        if fn == '-':
            fp = sys.stdin
        else:
            fp = open(fn)
    else:
        try:
            from cStringIO import StringIO
        except ImportError:
            from StringIO import StringIO
        fp = StringIO(test_input)
    while 1:
        line = fp.readline()
        if not line: break
        words = line.split()
        if not words:
            continue
        url = words[0]
        parts = urlparse(url)
        print '%-10s : %s' % (url, parts)
        abs = urljoin(base, url)
        if not base:
            base = abs
        wrapped = '<URL:%s>' % abs
        print '%-10s = %s' % (url, wrapped)
        if len(words) == 3 and words[1] == '=':
            if wrapped != words[2]:
                print 'EXPECTED', words[2], '!!!!!!!!!!'

if __name__ == '__main__':
    test()
