'''
Copyright (C) 2020 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson

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
import sys
import math
import time
import random
import inspect
import traceback
import contextlib
from math import floor, ceil
from inspect import signature
from itertools import dropwhile
from concurrent.futures import ThreadPoolExecutor

import bpy
import bgl
import blf
import gpu

from .ui_proxy import UI_Proxy

from mathutils import Vector, Matrix

from .boundvar import BoundVar
from .debug import debugger, dprint, tprint
from .decorators import debug_test_call, blender_version_wrapper, add_cache
from .maths import Vec2D, Color, mid, Box2D, Size1D, Size2D, Point2D, RelPoint2D, Index2D, clamp, NumberUnit
from .useractions import is_keycode
from .utils import iter_head, any_args, join, delay_exec


def setup_scrub(ui_element, value):
    '''
    must be a BoundInt or BoundFloat with min_value and max_value set
    '''
    if not type(value) in {BoundInt, BoundFloat}: return
    if not value.is_bounded and not value.step_size: return

    state = {}
    def reset_state():
        nonlocal state
        state = {
            'can scrub': True,
            'pressed': False,
            'scrubbing': False,
            'down': None,
            'initval': None,
            'cancelled': False,
        }
    reset_state()

    def cancel():
        nonlocal state
        if not state['scrubbing']: return
        value.value = state['initval']
        state['cancelled'] = True

    def mousedown(e):
        nonlocal state
        if not ui_element.document: return
        if ui_element.document.activeElement and ui_element.document.activeElement.is_descendant_of(ui_element):
            # do not scrub if descendant of ui_element has focus
            return
        if e.button[2] and state['scrubbing']:
            # right mouse button cancels
            value.value = state['initval']
            state['cancelled'] = True
            e.stop_propagation()
        elif e.button[0]:
            state['pressed'] = True
            state['down'] = e.mouse
            state['initval'] = value.value
    def mouseup(e):
        nonlocal state
        if e.button[0]: return
        if state['scrubbing']: e.stop_propagation()
        reset_state()
    def mousemove(e):
        nonlocal state
        if not state['pressed']: return
        if e.button[2]:
            cancel()
            e.stop_propagation()
        if state['cancelled']: return
        state['scrubbing'] |= (e.mouse - state['down']).length > Globals.drawing.scale(5)
        if not state['scrubbing']: return

        if ui_element._document:
            ui_element._document.blur()

        if value.is_bounded:
            m, M = value.min_value, value.max_value
            p = (e.mouse.x - state['down'].x) / ui_element.width_pixels
            v = clamp(state['initval'] + (M - m) * p, m, M)
            value.value = v
        else:
            delta = Globals.drawing.unscale(e.mouse.x - state['down'].x)
            value.value = state['initval'] + delta * value.step_size
        e.stop_propagation()
    def keypress(e):
        nonlocal state
        if not state['pressed']: return
        if state['cancelled']: return
        if type(e.key) is int and is_keycode(e.key, 'ESC'):
            cancel()
            e.stop_propagation()

    ui_element.add_eventListener('on_mousemove', mousemove, useCapture=True)
    ui_element.add_eventListener('on_mousedown', mousedown, useCapture=True)
    ui_element.add_eventListener('on_mouseup',   mouseup,   useCapture=True)
    ui_element.add_eventListener('on_keypress',  keypress,  useCapture=True)



class UI_Element_Elements():
    def _process_input_text(self):
        if self._ui_marker is None:
            # just got focus, so create a cursor element
            self._ui_marker = self._generate_new_ui_elem(
                tagName=self._tagName,
                type=self._type,
                classes=self._classes_str,
                pseudoelement='marker',
            )
            self._ui_marker.is_visible = False

            data = {'orig':None, 'text':None, 'idx':0, 'pos':None}

            def preclean():
                nonlocal data
                if data['text'] is None:
                    if type(self.value) is float:
                        self.innerText = '%0.4f' % self.value
                    else:
                        self.innerText = str(self.value)
                else:
                    self.innerText = data['text']
                self.dirty_content(cause='preclean called')

            def postflow():
                nonlocal data
                if data['text'] is None: return
                data['pos'] = self.get_text_pos(data['idx'])
                if self._ui_marker._absolute_size:
                    self._ui_marker.reposition(
                        left=data['pos'].x - self._mbp_left - self._ui_marker._absolute_size.width / 2,
                        top=data['pos'].y + self._mbp_top,
                        clamp_position=False,
                    )
                    cursor_postflow()
            def cursor_postflow():
                nonlocal data
                if data['text'] is None: return
                self._setup_ltwh()
                self._ui_marker._setup_ltwh()
                vl = self._l + self._mbp_left
                vr = self._r - self._mbp_right
                vw = self._w - self._mbp_width
                if self._ui_marker._r > vr:
                    dx = self._ui_marker._r - vr + 2
                    self.scrollLeft = self.scrollLeft + dx
                    self._setup_ltwh()
                if self._ui_marker._l < vl:
                    dx = self._ui_marker._l - vl - 2
                    self.scrollLeft = self.scrollLeft + dx
                    self._setup_ltwh()

            def set_cursor(e):
                nonlocal data
                data['idx'] = self.get_text_index(e.mouse)
                data['pos'] = self.get_text_pos(data['idx'])
                self.dirty_flow()

            def focus(e):
                s = f'{self.value:0.4f}' if type(self.value) is float else str(self.value)
                data['orig'] = data['text'] = s
                self._ui_marker.is_visible = True
                set_cursor(e)
            def blur(e):
                nonlocal data
                changed = self.value == data['text']
                self.value = data['text']
                data['text'] = None
                self._ui_marker.is_visible = False
                if changed: self.dispatch('on_change')

            def mouseup(e):
                nonlocal data
                if not e.button[0]: return
                # if not self.is_focused: return
                set_cursor(e)
            def mousemove(e):
                nonlocal data
                if data['text'] is None: return
                if not e.button[0]: return
                set_cursor(e)
            def mousedown(e):
                nonlocal data
                if data['text'] is None: return
                if not e.button[0]: return
                set_cursor(e)

            def keypress(e):
                nonlocal data
                if data['text'] == None: return
                if type(e.key) is int:
                    if is_keycode(e.key, 'BACK_SPACE'):
                        if data['idx'] == 0: return
                        data['text'] = data['text'][0:data['idx']-1] + data['text'][data['idx']:]
                        data['idx'] -= 1
                    elif is_keycode(e.key, 'RET'):
                        self.blur()
                    elif is_keycode(e.key, 'ESC'):
                        data['text'] = data['orig']
                        self.blur()
                    elif is_keycode(e.key, 'END'):
                        data['idx'] = len(data['text'])
                        self.dirty_flow()
                    elif is_keycode(e.key, 'HOME'):
                        data['idx'] = 0
                        self.dirty_flow()
                    elif is_keycode(e.key, 'LEFT_ARROW'):
                        data['idx'] = max(data['idx'] - 1, 0)
                        self.dirty_flow()
                    elif is_keycode(e.key, 'RIGHT_ARROW'):
                        data['idx'] = min(data['idx'] + 1, len(data['text']))
                        self.dirty_flow()
                    elif is_keycode(e.key, 'DEL'):
                        if data['idx'] == len(data['text']): return
                        data['text'] = data['text'][0:data['idx']] + data['text'][data['idx']+1:]
                    else:
                        return
                else:
                    data['text'] = data['text'][0:data['idx']] + e.key + data['text'][data['idx']:]
                    data['idx'] += 1
                preclean()

            self.preclean = preclean
            self.postflow = postflow

            self.add_eventListener('on_focus',     focus)
            self.add_eventListener('on_blur',      blur)
            self.add_eventListener('on_keypress',  keypress)
            self.add_eventListener('on_mousedown', mousedown)
            self.add_eventListener('on_mousemove', mousemove)
            self.add_eventListener('on_mouseup',   mouseup)

            preclean()
        else:
            self._new_content = True
            self._children_gen += [self._ui_marker]

        return [*self._children, self._ui_marker]

        is_focused, was_focused = self.is_focused, getattr(self, '_was_focused', None)
        self._was_focused = is_focused

        if not is_focused:
            # not focused, so no cursor!
            if was_focused:
                self._ui_marker = None
                self._selectionStart = None
                self._selectionEnd = None
            return self._children

        if not was_focused:
            # was not focused, but has focus now
            # store current text in case ESC is pressed to cancel (revert to original)
            self._innerText_original = self._innerText

        if not self._ui_marker:
            # just got focus, so create a cursor element
            self._ui_marker = self._generate_new_ui_elem(
                tagName=self._tagName,
                type=self._type,
                classes=self._classes_str,
                pseudoelement='marker',
            )
        else:
            self._new_content = True
            self._children_gen += [self._ui_marker]

        return [*self._children, self._ui_marker]


    def _process_input_checkbox(self):
        if self._ui_marker is None:
            self._ui_marker = self._generate_new_ui_elem(
                tagName=self._tagName,
                type=self._type,
                checked=self.checked,
                classes=self._classes_str,
                pseudoelement='marker',
            )
            self.add_eventListener('on_mouseclick', delay_exec('''self.checked = not bool(self.checked)'''))
        else:
            self._children_gen += [self._ui_marker]
            self._new_content = True
        return [self._ui_marker, *self._children]

    def _process_input_radio(self):
        if self._ui_marker is None:
            self._ui_marker = self._generate_new_ui_elem(
                tagName=self._tagName,
                type=self._type,
                checked=self.checked,
                classes=self._classes_str,
                pseudoelement='marker',
            )
            def on_input(e):
                if not self.checked: return
                ui_elements = self.get_root().getElementsByName(self.name)
                for ui_element in ui_elements:
                    if ui_element != self:
                        ui_element.checked = False
            def on_click(e):
                self.checked = True
            self.add_eventListener('on_mouseclick', on_click)
            self.add_eventListener('on_input', on_input)
        else:
            self._children_gen += [self._ui_marker]
            self._new_content = True
        return [self._ui_marker, *self._children]

    def _process_details(self):
        is_open, was_open = self.open, getattr(self, '_was_open', None)
        self._was_open = is_open

        if not getattr(self, '_processed_details', False):
            self._processed_details = True
            def mouseclick(e):
                doit = False
                doit |= e.target == self                                              # clicked on <details>
                doit |= e.target.tagName == 'summary' and e.target._parent == self    # clicked on <summary> of <details>
                if not doit: return
                self.open = not self.open
            self.add_eventListener('on_mouseclick', mouseclick)

        if self._get_child_tagName(0) != 'summary':
            # <details> does not have a <summary>, so create a default one
            if self._ui_marker is None:
                self._ui_marker = self._generate_new_ui_elem(tagName='summary', innerText='Details')
            summary = self._ui_marker
            contents = self._children if is_open else []
        else:
            summary = self._children[0]
            contents = self._children[1:] if is_open else []

        # set _new_content to show contents if open is toggled
        self._new_content |= was_open != is_open
        return [summary, *contents]

    def _process_summary(self):
        marker = self._generate_new_ui_elem(
            tagName='summary',
            classes=self._classes_str,
            pseudoelement='marker'
        )
        return [marker, *self._children]

    def _process_children(self):
        if self._innerTextAsIs is not None: return []
        if self._pseudoelement == 'marker': return self._children

        tagtype = f'{self._tagName}{f" {self._type}" if self._type else ""}'
        processor = {
            'input radio':    self._process_input_radio,
            'input checkbox': self._process_input_checkbox,
            'input text':     self._process_input_text,
            'details':        self._process_details,
            'summary':        self._process_summary,
        }.get(tagtype, None)

        return processor() if processor else self._children