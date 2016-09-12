import sublime
import sublime_plugin

import sys
import tempfile
import webbrowser

import requests
import mimetypes

import json

# todo make requests async

class BreadboardCommand(sublime_plugin.TextCommand):
    _pythonVersion = sys.version_info[0]

    def init_panel(self):
        if not hasattr(self, 'output_view'):
            self.output_view = self.window.create_output_panel("breadboard")

    def run(self, edit):
        if not hasattr(self, 'config'):
            self.config = sublime.load_settings('breadboard.sublime-settings')

        self.window = self.view.window()
        self.edit = edit

        self.init_panel()

        search_url = self.config.get("url") + "/script"

        req = requests.get(search_url, timeout=(2, 10))

        self.search_res = req.json()
        self.choose = list(map(lambda i: [i['title'], i['run_url']], self.search_res))

        self.window.show_quick_panel(self.choose, self.on_done)

    def on_done(self, value):
        if not value < 0:
            sel = self.view.sel()

            region1 = sel[0]
            selectionText = self.view.substr(region1)

            i = self.search_res[value]

            data = selectionText

            access_token = self.config.get('access_token')
            headers = { 'Content-Type': 'text/plain', "Accept": "*/*" }
            if access_token:
                headers['Authorization'] = 'Bearer ' + access_token

            req = requests.get(i['run_url'], data=data, headers=headers, timeout=(2, None))

            binary = req.encoding == None

            if binary:
                self.open(req)
            else:
                txt = req.text

                pragma = req.headers.get('manual-pragma')
                if not pragma:
                    if '\n' in txt:
                        txt = '\n' + txt + '\n'
                    self.view.run_command('append', { 'characters' : txt })
                else:
                    pragma = json.loads(pragma)
                    if "editor replace" in pragma:
                        self.view.run_command('insert', { 'characters' : txt })
                    else:
                        if '\n' in txt:
                            txt = '\n' + txt + '\n'
                        self.view.run_command('append', { 'characters' : txt })
        
    def open(self, req):
        fileToOpen = self.normalizePath(self.saveInTempFile(req))

        ctrl = webbrowser.get();
        if self._pythonVersion < 3:
            ctrl.open(fileToOpen.encode(sys.getfilesystemencoding()), 1, True)
        else:
            ctrl.open(fileToOpen, 1, True)

    def normalizePath(self, fileToOpen):
        fileToOpen = fileToOpen.replace("\\", "/")
        fileToOpen = "file:///%s" % fileToOpen.replace(" ", "%20")

        return fileToOpen

    def saveInTempFile(self, req):
        binary = req.encoding == None

        if binary:
            mode = 'wb'
        else:
            mode = 'w'

        ext = mimetypes.guess_extension(req.headers.get('content-type'), strict=True);
        tempFile = tempfile.NamedTemporaryFile(suffix = ext, delete = False, mode = mode)

        with tempFile as fd:
            for chunk in req.iter_content(1024):
                fd.write(chunk)

        tempFile.close()

        return tempFile.name