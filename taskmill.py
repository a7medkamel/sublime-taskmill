import sublime
import sublime_plugin

import os
import sys
import re
import urllib2
import json
import tempfile
import webbrowser

PY3 = sys.version > '3'

if PY3:
    from .settings import *
else:
    from settings import *


def is_ST3():
    ''' check if ST3 based on python version '''
    return sys.version_info >= (3, 0)

# def plugin_loaded():
    # config = sublime.load_settings('TaskMill.sublime-settings')
    # settings.loaded_settings = sublime.load_settings('TaskMill.sublime-settings')
    # settings.get = settings.loaded_settings.get
    # settings.set = settings.loaded_settings.set

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
            exe = '/' + i['git']['owner']['login'] + \
                '/' + i['git']['repository']['name'] + \
                '/exec/' + i['git']['branch'] + i['git']['path']
            # path = re.sub(r'^(\w+?)/(\w+?)/', r'/\1/\2/exec/', item)
            url = self.config.get("url") + exe
            data = selectionText

            access_token = self.config.get('access_token')
            headers = { 'Content-type': 'text/plain' }
            if access_token:
                headers['Authorization'] = 'Bearer ' + access_token
            # if headers
            req = urllib2.Request(url, data=data, headers=headers)
            res = urllib2.urlopen(req)
            info = res.info()
            # todo [akamel] if transform replace
            stream = res.read()

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
                if _type == 'transform':
                    # self.view.run_command('insert_my_text', { 'args' : { 'text' : txt }})
                    for region in self.view.sel():
                        if not region.empty():
                            # Replace the selection with transformed text
                            self.view.replace(self.edit, region, txt)
                else:
                    for region in self.view.sel():
                        if not region.empty():
                            # Replace the selection with transformed text
                            self.view.insert(self.edit, region.end(), '\n' + txt + '\n')

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