import sublime
import sublime_plugin

import os
import socket
import sys
import re
# import urllib2
import json
import tempfile
import webbrowser

# import urlparse

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

PY3 = sys.version > '3'

if PY3:
    from .settings import *
else:
    from settings import *

def is_ST3():
    ''' check if ST3 based on python version '''
    return sys.version_info >= (3, 0)

def url_path_join(*parts):
    """Normalize url parts and join them with a slash."""
    schemes, netlocs, paths, queries, fragments = zip(*(urlparse.urlsplit(part) for part in parts))
    scheme = first(schemes)
    netloc = first(netlocs)
    path = '/'.join(x.strip('/') for x in paths if x)
    query = first(queries)
    fragment = first(fragments)
    return urlparse.urlunsplit((scheme, netloc, path, query, fragment))

def first(sequence, default=''):
    return next((x for x in sequence if x), default)

# def plugin_loaded():
    # config = sublime.load_settings('TaskMill.sublime-settings')
    # settings.loaded_settings = sublime.load_settings('TaskMill.sublime-settings')
    # settings.get = settings.loaded_settings.get
    # settings.set = settings.loaded_settings.set

# https://github.com/braindamageinc/SublimeHttpRequester/blob/master/http_requester.py
FAKE_CURL_UA = "curl/7.21.0 (i486-pc-linux-gnu) libcurl/7.21.0 OpenSSL/0.9.8o zlib/1.2.3.4 libidn/1.15 libssh2/1.2.6"

class TaskmillCommand(sublime_plugin.TextCommand):
    _pythonVersion = sys.version_info[0]

    def init_panel(self):
        if not hasattr(self, 'output_view'):
            if is_ST3():
                self.output_view = self.window.create_output_panel("taskmill")
            else:
                self.output_view = self.window.get_output_panel("taskmill")
    def run(self, edit):
        if not hasattr(self, 'config'):
            self.config = sublime.load_settings('TaskMill.sublime-settings')

        self.window = self.view.window()
        self.edit = edit

        self.init_panel()

        search_url = self.config.get("url") + "/script/search"

        res = urllib2.urlopen(search_url).read()

        if is_ST3():
            res_str = res.decode()
        else:
            res_str = res

        obj = json.loads(res_str);

        self.search_res = obj
        self.choose = map(self.get_path, obj)

        if is_ST3():
            self.choose = list(self.choose)

        self.window.show_quick_panel(self.choose, self.on_done)

    def on_done(self, value):
        sel = self.view.sel()

        region1 = sel[0]
        selectionText = self.view.substr(region1)

        if not value < 0:
            i = self.search_res[value]

            url = url_path_join(self.config.get("url"), i['git']['owner']['login'], i['git']['repository']['name'], 'exec', i['git']['branch'], i['git']['path'])
            data = selectionText

            access_token = self.config.get('access_token')
            headers = { 'Content-Type': 'text/plain', "User-Agent": FAKE_CURL_UA, "Accept": "*/*" }
            if access_token:
                headers['Authorization'] = 'Bearer ' + access_token

            # url = "http://localhost:8787/fu"
            if is_ST3():
                data = data.encode('utf-8')

            req = urllib2.Request(url, data=data, headers=headers)
            try:
                #and this is the magic. Create a HTTPHandler object and put its debug level to 1
                # httpHandler = urllib2.HTTPSHandler()
                # httpHandler.set_http_debuglevel(1)

                #Instead of using urllib2.urlopen, create an opener, and pass the HTTPHandler
                #and any other handlers... to it.
                # opener = urllib2.build_opener(httpHandler)

                # res = opener.open(req, timeout = 10)
                res = urllib2.urlopen(req, timeout = 15)
                info = res.info()

                stream = res.read()
                res.close()

                if is_ST3():
                    _type = res.getheader('$type')
                    _ctype = res.getheader('content-type')
                else:
                    _type = info.getheader('$type')
                    _ctype = info.getheader('content-type')

                if not _ctype:
                    _ctype = ''

                if re.search('text/html.*', _ctype):
                    self.open(stream, '.html', False)
                elif _ctype == 'application/pdf':
                    self.open(stream, '.pdf', True)
                elif _ctype == 'audio/mpeg':
                    self.open(stream, '.mp3', True)
                else:
                    txt = stream.decode('utf-8')
                    # todo if transform then replace content; otherwise insert below
                    if _type == 'transform':
                        if is_ST3():
                            self.view.run_command('insert_snippet', { 'contents' : txt })
                        else:
                            self.view.run_command('insert', { 'characters' : txt })
                    else:
                        if '\n' in txt:
                            txt = '\n' + txt + '\n'
                        if is_ST3():
                            self.view.run_command('insert_snippet', { 'contents' : txt })
                        else:
                            self.view.run_command('insert', { 'characters' : txt })
            # except urllib2.URLError, e:
            #     # For Python 2.6
            #     if isinstance(e.reason, socket.timeout):
            #         raise MyException("There was an error: %r" % e)
            #     else:
            #         # reraise the original error
            #         raise
            except urllib2.URLError:
                # raise MyException("There was an error: %r" % e)
                print(sys.exc_info()[0])
            except socket.timeout:
                # For Python 2.7
                print(sys.exc_info()[0])
                # raise MyException("There was an error: %r" % e)


    def open(self, stream, ext, binary):
        fileToOpen = self.normalizePath(self.saveInTempFile(stream, ext, binary))

        ctrl = webbrowser.get();
        if self._pythonVersion < 3:
            ctrl.open(fileToOpen.encode(sys.getfilesystemencoding()), 1, True)
        else:
            ctrl.open(fileToOpen, 1, True)

    def normalizePath(self, fileToOpen):
        fileToOpen = fileToOpen.replace("\\", "/")
        fileToOpen = "file:///%s" % fileToOpen.replace(" ", "%20")

        return fileToOpen

    def saveInTempFile(self, stream, ext, binary):
        #
        # Create a temporary file to hold our contents
        #
        if is_ST3():
            binary = True

        if binary:
            mode = 'wb'
        else:
            mode = 'w'

        tempFile = tempfile.NamedTemporaryFile(suffix = ext, delete = False, mode = mode)

        if binary:
            tempFile.write(stream)
        else:
            txt = stream.decode('utf-8')
            tempFile.write(txt.encode("utf-8"))

        tempFile.close()

        return tempFile.name

    def get_path(self, i):
        name = i['git']['path']
        # path = i['git']['owner']['login'] + \
        #     "/" + i['git']['repository']['name'] + \
        #     "/" + i['git']['branch'] + i['git']['path']
        path = url_path_join(i['git']['owner']['login'], i['git']['repository']['name'], i['git']['branch'], i['git']['path'])
        return [ name, path ]