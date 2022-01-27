import sys

import PySimpleGUI as sg

_is_debugger = sys.gettrace()
no_frame_kwargs = dict(keep_on_top=not _is_debugger, no_titlebar=not _is_debugger)
frame_kwargs = dict(p=0, border_width=1, relief=sg.RELIEF_SOLID, expand_x=True, expand_y=True)
window_kwargs = dict(
    **no_frame_kwargs,
    return_keyboard_events=True,
    grab_anywhere=True,
    margins=(0, 0),
    debugger_enabled=False,
    finalize=True
)


def get_window_params(layout, **new_kwargs):
    args = ("", [[sg.Frame("", layout, **frame_kwargs)]])
    kwargs = window_kwargs.copy()
    kwargs.update(new_kwargs)
    return args, kwargs


# def is_debugger():
#     return _is_debugger


fix_font = "Roboto Mono Light"
fix_font_bold = "Roboto Mono Bold"
var_font = "Roboto Light"
var_font_bold = "Roboto Bold"

splash_color = "#404060"
splash_alpha = 0.25
refresh_color = "#408040"
archives_color = "#B2560D"
archives_color_empty = "#909090"
edit_color = "#6060FF"
trash_color = "#000000"
trash_color_empty = "#909090"
log_color = "grey"

log_img = "icons/log.png"
edit_img = "icons/edit.png"
refresh_img = "icons/refresh.png"
archives_img = "icons/archive.png"
trash_img = "icons/trash.png"
mail_img = "icons/mail.png"
warn_img = "icons/warn.png"

popup_bg_color = "grey90"
popup_title_color = "grey40"
popup_sep_color = "grey20"
popup_title_font_size = 25

button_color = "grey75"
separator_color = "grey50"

menu_color = "grey75"
empty_color = "grey90"
empty_font_size = 20
menu_button_pad = 7
menu_button_font_size = 13
menu_button_height = 20
menu_button_img_margin = 1, 5

widget_padx = 10
widget_title_bg_color = "grey85"
widget_event_bg_color = "grey90"
widget_event_pady = 5
widget_separator_color = "grey70"
widget_descrition_text_color = "grey40"
widget_descrition_error_text_color = "grey70"
widget_ago_color = "grey50"
widget_status_text_color = "grey10"
widget_courier_font_size = 8
widget_courier_mouse_over_color = "grey70"
widget_event_font_size = 8
widget_description_font_size = 40
widget_description_max_width = 400
widget_idship_font_size = 10
widget_status_font_size = 15
widget_expand_font_size = 12
widget_expand_color = "grey50"
widget_button_mouse_over_color = "grey95"
widget_button_pad = 4
widget_button_size = 22
widget_button_img_margin = 5
widget_updating_gif_height = 15
widget_event_max_width = 90
widget_min_events_shown = 1
widget_elapsed_days_intervals = [10, 20, 30]
widget_elapsed_days_colors = ["lime green", "dark orange", "red", "black"]
widget_elapsed_days_default_color = "grey70"
widget_elapsed_days_bg_color = "grey90"
widget_elapsed_days_box_size = 50
widget_elapsed_days_font_size = 15

popup_max_choices = 20

_theme = {
    "BACKGROUND": widget_event_bg_color,
    "TEXT": "black",
    "INPUT": widget_title_bg_color,
    "TEXT_INPUT": "black",
    "SCROLL": widget_event_bg_color,
    "BUTTON": ("black", "grey60"),
    "PROGRESS": (widget_event_bg_color, widget_title_bg_color),
    "BORDER": 0,
    "SLIDER_DEPTH": 0,
    "PROGRESS_DEPTH": 0,
}

theme = "custom theme"
sg.theme_add_new(theme, _theme)
