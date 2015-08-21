import sublime
import sublime_plugin

import os
import socket
import sys
import re
import urllib2
import json
import tempfile
import webbrowser

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

        obj = json.loads(res);

        self.search_res = obj
        self.choose = map(self.get_path, obj)

        self.window.show_quick_panel(self.choose, self.on_done)

    def on_done(self, value):
        sel = self.view.sel()

        region1 = sel[0]
        selectionText = self.view.substr(region1)

        if not value < 0:
            i = self.search_res[value]

            # exe = url_path_join(i['git']['owner']['login'], i['git']['repository']['name'], 'exec', i['git']['branch'], i['git']['path'])
            # exe = '/' + i['git']['owner']['login'] + \
            #     '/' + i['git']['repository']['name'] + \
            #     '/exec/' + i['git']['branch'] + i['git']['path']

            # path = re.sub(r'^(\w+?)/(\w+?)/', r'/\1/\2/exec/', item)
            # url = self.config.get("url") + exe
            url = url_path_join(self.config.get("url"), i['git']['owner']['login'], i['git']['repository']['name'], 'exec', i['git']['branch'], i['git']['path'])
            data = selectionText

            access_token = self.config.get('access_token')
            headers = { 'Content-Type': 'text/plain', "User-Agent": FAKE_CURL_UA, "Accept": "*/*" }
            if access_token:
                headers['Authorization'] = 'Bearer ' + access_token

            # url = "http://localhost:8787/fu"
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

                _type = info.getheader('$type')
                _ctype = info.getheader('content-type')

                if not _ctype:
                    _ctype = ''

                # print _ctype
                if re.search('text/html.*', _ctype):
                    self.open(stream, '.html', False)
                elif _ctype == 'application/pdf':
                    self.open(stream, '.pdf', True)
                elif _ctype == 'audio/mpeg':
                    self.open(stream, '.mp3', True)
                else:
                    txt = stream.decode('utf-8')
                    if _type == 'transform':
                        # self.view.run_command('insert_my_text', { 'args' : { 'text' : txt }})
                        for region in self.view.sel():
                            if not region.empty():
                                # print txt
                                # Replace the selection with transformed text
                                self.view.replace(self.edit, region, txt)
                    else:
                        for region in self.view.sel():
                            self.view.insert(self.edit, region.end(), '\n' + txt + '\n')
                            # if not region.empty():
                                # Replace the selection with transformed text
                                # self.view.insert(self.edit, region.end(), '\n' + txt + '\n')
            # except urllib2.URLError, e:
            #     # For Python 2.6
            #     if isinstance(e.reason, socket.timeout):
            #         raise MyException("There was an error: %r" % e)
            #     else:
            #         # reraise the original error
            #         raise
            except urllib2.URLError, e:
                # raise MyException("There was an error: %r" % e)
                print e
            except socket.timeout, e:
                # For Python 2.7
                print e
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
        path = i['git']['owner']['login'] + \
            "/" + i['git']['repository']['name'] + \
            "/" + i['git']['branch'] + i['git']['path']
        return [ name, path ]