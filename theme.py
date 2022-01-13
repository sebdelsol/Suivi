import sys
import PySimpleGUI as sg

is_debugger = sys.gettrace()

frame_kwargs = dict(p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True)
window_kwargs = dict(keep_on_top = not is_debugger, no_titlebar = not is_debugger, return_keyboard_events = True, grab_anywhere = True, margins = (0, 0), debugger_enabled = False, finalize = True)

def Is_debugger():
    return is_debugger

def Get_window_params(layout, **new_kwargs):
    args = ('', [ [ sg.Frame('', layout, **frame_kwargs) ] ])
    kwargs = window_kwargs.copy()
    kwargs.update(new_kwargs) 
    return args, kwargs

#----------------------------
Main_theme = 'GrayGrayGray'

FixFont = 'Roboto Mono Light'
FixFontBold = 'Roboto Mono Bold'
VarFont = 'Roboto Light'
VarFontBold = 'Roboto Bold'

Refresh_color = '#408040'
Archives_color = '#B2560D'
Edit_color = '#6060FF'
Trash_color = '#909090'
Log_color = 'grey'

Log_img = 'icon/log.png'
Edit_img = 'icon/edit.png'
Refresh_img = 'icon/refresh.png'
Archives_img = 'icon/archive.png'
Trash_img = 'icon/trash.png'
Mail_img = 'icon/mail.png'

menu_color = 'grey75'
empty_color = 'grey90'
empty_font_size = 20
menu_button_pad = 5
menu_button_font_size = 12
menu_button_height = 20
menu_button_img_margin = 5

widget_background_title_color = 'grey85'
widget_background_event_color = 'grey90'
widget_courier_font_size = 8
widget_event_font_size = 8
widget_elapsed_days_box_size = 50
widget_elapsed_days_font_size = 15
widget_description_font_size = 40
widget_idship_font_size = 10
widget_status_font_size = 15
widget_expand_font_size = 10
widget_button_pad = 4
widget_button_size = 22
widget_button_img_percent = .6
widget_updating_gif_height = 20
widget_event_max_width = 90
widget_min_events_shown = 1
widget_elpapse_days_intervals = [10, 20, 30]
widget_elpased_days_colors = ['lime green', 'dark orange', 'red', 'black']
