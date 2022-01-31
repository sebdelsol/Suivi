import sys

import PySimpleGUI as sg


class TH:
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

    @staticmethod
    def get_window_params(layout, **new_kwargs):
        args = ("", [[sg.Frame("", layout, **TH.frame_kwargs)]])
        kwargs = TH.window_kwargs.copy()
        kwargs.update(new_kwargs)
        return args, kwargs

    fix_font = "Roboto Mono Light"
    fix_font_bold = "Roboto Mono Bold"
    var_font = "Roboto Light"
    var_font_bold = "Roboto Bold"

    splash_color = "#404060"
    splash_img_height = 200
    splash_font_size = 10

    greyed_alpha = 0.25

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

    window_height_screen_margin = 0  # for recenter

    warn_color = "red"
    ok_color = "green"
    idship_color = "blue"
    unselected_color = "grey75"

    log_font_size = 8
    log_button_font_size = 12
    log_select_color = "grey75"
    log_button_mouse_over_color = "grey80"
    log_button_text_color = "grey60"
    log_button_color = "grey90"
    log_button_close_text_color = "red"

    popup_bg_color = "grey90"
    popup_button_color = "grey75"
    popup_title_color = "grey40"
    popup_title_font_size = 25
    popup_sep_color = "grey20"
    popup_sep_padx = 5
    popup_button_font_size = 12
    popup_max_choices = 20

    edit_font_size = 10
    edit_msg_font_size = 8
    edit_show_button_font_size = 8
    edit_show_button_color = "grey90"
    edit_courier_font_size = 12
    edit_check_color = "black"
    edit_unchecked_color = "grey60"

    choices_font_size = 9
    on_choice_font_size = 20
    ask_confirmation_font_size = 15

    empty_color = "grey90"
    empty_font_size = 20
    empty_font_color = "grey"
    empty_pady = 15

    menu_color = "grey90"
    menu_button_mouse_over_color = "grey80"
    menu_sys_button_mouse_over_color = "red"
    menu_button_padx = 15
    menu_button_pady = 7
    menu_button_font_size = 13
    menu_button_height = 20
    menu_button_img_margin = 1, 5

    widget_padx = 10
    widget_title_bg_color = "grey85"
    widget_event_bg_color = "grey90"
    widget_event_pady = 5
    widget_event_mouse_over_color = "grey80"
    widget_separator_color = "grey70"
    widget_descrition_text_color = "grey40"
    widget_descrition_error_text_color = "grey70"
    widget_ago_color = "grey50"
    widget_status_text_color = "grey10"
    widget_courier_font_size = 8
    widget_courier_mouse_over_color = "grey95"
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
    elapsed_days_intervals = [10, 20, 30]
    elapsed_days_colors = ["lime green", "dark orange", "red", "black"]
    elapsed_days_default_color = "grey70"
    elapsed_days_bg_color = "grey90"
    elapsed_days_box_size = 50
    elapsed_days_font_size = 15

    n_event_font_size = 7
    n_new_event_font_size = 10

    event_date_color = "grey"
    event_courier_color = "grey70"
    event_status_color = "black"
    event_label_color = "grey50"

    event_new_color = "red"
    remove_new_events_button_color = "white"
    remove_new_events_text_color = "black"
    remove_new_events_padx = 5
    remove_new_events_font_size = 10

    from_to_color = "grey65"
    product_color = "grey50"
    courier_updated_color = "grey60"

    _theme_definition = {
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

    theme = "suivi theme"
    sg.theme_add_new(theme, _theme_definition)
