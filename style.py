import sys
import PySimpleGUI as sg

is_debugger = sys.gettrace()

frame_kwargs = dict(p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True)
window_kwargs = dict(keep_on_top = not is_debugger, no_titlebar = not is_debugger, return_keyboard_events = True, grab_anywhere = True, margins = (0, 0), debugger_enabled = False, finalize = True)

def Is_debugger():
    return is_debugger

def Get_window_args(layout, **new_kwargs):
    args = ('', [ [ sg.Frame('', layout, **frame_kwargs) ] ])
    kwargs = window_kwargs.copy()
    kwargs.update(new_kwargs) 
    return args, kwargs

FixFont = 'Roboto Mono Light'
FixFontBold = 'Roboto Mono Bold'

VarFont = 'Roboto Light'
VarFontBold = 'Roboto Bold'

