'''
Copyright (C) 2020 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson, and Patrick Moore

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import os
import re
import bpy

from ...addon_common.common import ui
from ...addon_common.common.globals import Globals
from ...addon_common.common.utils import delay_exec
from ...addon_common.common.ui_styling import load_defaultstylings

from ...config.options import options, retopoflow_helpdocs_url
from ...config.keymaps import get_keymaps

class RetopoFlow_HelpSystem:
    @staticmethod
    def reload_stylings():
        load_defaultstylings()
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'ui.css')
        try:
            Globals.ui_draw.load_stylesheet(path)
        except AssertionError as e:
            # TODO: show proper dialog to user here!!
            print('could not load stylesheet "%s"' % path)
            print(e)
        Globals.ui_document.body.dirty(cause='Reloaded stylings', children=True)
        Globals.ui_document.body.dirty_styling()
        Globals.ui_document.body.dirty_flow()

    def substitute_keymaps(self, mdown, wrap='`', pre='', post='', separator=', ', onlyfirst=None):
        if type(wrap) is str: wrap_pre, wrap_post = wrap, wrap
        else: wrap_pre, wrap_post = wrap
        while True:
            m = re.search(r'{{(?P<action>[^}]+)}}', mdown)
            if not m: break
            action = { s.strip() for s in m.group('action').split(',') }
            sub = f'{pre}{wrap_pre}' + self.actions.to_human_readable(action, join=f'{wrap_post}{separator}{wrap_pre}', onlyfirst=onlyfirst) + f'{wrap_post}{post}'
            mdown = mdown[:m.start()] + sub + mdown[m.end():]
        return mdown

    def substitute_options(self, mdown, wrap='', pre='', post='', separator=', ', onlyfirst=None):
        if type(wrap) is str: wrap_pre, wrap_post = wrap, wrap
        else: wrap_pre, wrap_post = wrap
        while True:
            m = re.search(r'{\[(?P<option>[^\]]+)\]}', mdown)
            if not m: break
            opts = { s.strip() for s in m.group('option').split(',') }
            sub = f'{pre}{wrap_pre}' + separator.join(str(options[opt]) for opt in opts) + f'{wrap_post}{post}'
            mdown = mdown[:m.start()] + sub + mdown[m.end():]
        return mdown

    def substitute_python(self, mdown, wrap='', pre='', post=''):
        if type(wrap) is str: wrap_pre, wrap_post = wrap, wrap
        else: wrap_pre, wrap_post = wrap
        while True:
            m = re.search(r'{`(?P<python>[^`]+)`}', mdown)
            if not m: break
            pyret = eval(m.group('python'), globals(), locals())
            sub = f'{pre}{wrap_pre}{pyret}{wrap_post}{post}'
            mdown = mdown[:m.start()] + sub + mdown[m.end():]
        return mdown

    def helpsystem_open(self, mdown_path, done_on_esc=False, closeable=True):
        ui_markdown = self.document.body.getElementById('helpsystem-mdown')
        if not ui_markdown:
            keymaps = get_keymaps()
            def close():
                nonlocal done_on_esc
                if done_on_esc:
                    self.done()
                else:
                    e = self.document.body.getElementById('helpsystem')
                    if not e: return
                    self.document.body.delete_child(e)
            def key(e):
                nonlocal keymaps, self
                if e.key in keymaps['all help']:
                    self.helpsystem_open('table_of_contents.md')
                elif e.key in keymaps['general help']:
                    self.helpsystem_open('general.md')
                elif e.key in keymaps['tool help']:
                    if hasattr(self, 'rftool'):
                        self.helpsystem_open(self.rftool.help)
                elif e.key == 'ESC':
                    close()
            ui_help = ui.framed_dialog(
                label='RetopoFlow Help System',
                id='helpsystem',
                resizable=False,
                closeable=closeable,
                moveable=False,
                parent=self.document.body,
            )
            ui_markdown = ui.markdown(id='helpsystem-mdown', parent=ui_help)
            ui.div(id='helpsystem-buttons', parent=ui_help, children=[
                ui.button(
                    innerText='Table of Contents',
                    title='Click to open table of contents for help.',
                    on_mouseclick=delay_exec("self.helpsystem_open('table_of_contents.md')"),
                ),
                ui.button(
                    innerText='View Online Docs',
                    title='Click to open online help documents.  Note: this is an experimental feature.',
                    on_mouseclick=delay_exec('''bpy.ops.wm.url_open(url=retopoflow_helpdocs_url)'''),
                ),
                ui.button(
                    innerText='Close (Esc)',
                    title='Click to close this help dialog.',
                    on_mouseclick=close,
                )
            ])
            ui_help.add_eventListener('on_keypress', key)
            self.document.body.dirty()

        ui.set_markdown(
            ui_markdown,
            mdown_path=mdown_path,
            preprocess_fns=[
                self.substitute_keymaps,
                self.substitute_options,
                self.substitute_python
            ],
        )

