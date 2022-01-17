import sys
import PySimpleGUI as sg

_is_debugger = sys.gettrace()

frame_kwargs = dict(p=0, border_width=1, relief=sg.RELIEF_SOLID, expand_x=True, expand_y=True)
window_kwargs = dict(keep_on_top=not _is_debugger, no_titlebar=not _is_debugger, return_keyboard_events=True, grab_anywhere=True, margins=(0, 0), debugger_enabled=False, finalize=True)


def is_debugger():
    return _is_debugger


def get_window_params(layout, **new_kwargs):
    args = ('', [[sg.Frame('', layout, **frame_kwargs)]])
    kwargs = window_kwargs.copy()
    kwargs.update(new_kwargs)
    return args, kwargs


fix_font = 'Roboto Mono Light'
fix_font_bold = 'Roboto Mono Bold'
var_font = 'Roboto Light'
var_font_bold = 'Roboto Bold'

refresh_color = '#408040'
archives_color = '#B2560D'
archives_color_empty = '#909090'
edit_color = '#6060FF'
trash_color = '#000000'
trash_color_empty = '#909090'
log_color = 'grey'

log_img = 'icons/log.png'
edit_img = 'icons/edit.png'
refresh_img = 'icons/refresh.png'
archives_img = 'icons/archive.png'
trash_img = 'icons/trash.png'
mail_img = 'icons/mail.png'
warn_img = 'icons/warn.png'

popup_background_color = 'grey90'
button_color = 'grey75'
separator_color = 'grey50'

menu_color = 'grey75'
empty_color = 'grey90'
empty_font_size = 20
menu_button_pad = 7
menu_button_font_size = 13
menu_button_height = 20
menu_button_img_margin = 5

widget_background_title_color = 'grey85'
widget_background_event_color = 'grey90'
widget_separator_color = 'grey70'
widget_descrition_text_color = 'grey40'
widget_descrition_error_text_color = 'grey70'
widget_status_text_color = 'grey10'
widget_courier_font_size = 8
widget_event_font_size = 8
widget_elapsed_days_box_size = 50
widget_elapsed_days_font_size = 15
widget_description_font_size = 40
widget_description_max_width = 400
widget_idship_font_size = 10
widget_status_font_size = 15
widget_expand_font_size = 10
widget_button_pad = 4
widget_button_size = 22
widget_button_img_margin = 5
widget_updating_gif_height = 22
widget_event_max_width = 90
widget_min_events_shown = 1
widget_elapsed_days_intervals = [10, 20, 30]
widget_elapsed_days_colors = ['lime green', 'dark orange', 'red', 'black']

popup_max_choices = 20

_theme = {'BACKGROUND': widget_background_event_color,
          'TEXT': 'black',
          'INPUT': widget_background_title_color,
          'TEXT_INPUT': 'black',
          'SCROLL': widget_background_event_color,
          'BUTTON': ('black', 'grey60'),
          'PROGRESS': (widget_background_event_color, widget_background_title_color),
          'BORDER': 0, 'SLIDER_DEPTH': 0, 'PROGRESS_DEPTH': 0}

theme = 'custom theme'
sg.theme_add_new(theme, _theme)


def horizontal_line(p, color=separator_color):
    return sg.Col([[]], p=p, s=(None, 1), background_color=color, expand_x=True)
