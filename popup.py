from collections import namedtuple

import PySimpleGUI as sg

from events import Shortcuts
from localization import TXT
from theme import TH
from widget import ButtonMouseOver, HLine, Window


class Popup(Window):
    def __init__(self, title, body_layout, main_window, added_buttons=None):
        self.main_window = main_window
        self.main_window.grey_all(True)

        title_font = (TH.fix_font_bold, TH.popup_title_font_size)
        layout = [
            [
                sg.T(
                    title,
                    p=0,
                    font=title_font,
                    text_color=TH.popup_title_color,
                    justification="center",
                    expand_x=True,
                )
            ],
            [HLine(p=TH.popup_sep_padx, color=TH.popup_sep_color)],
        ]
        layout.extend(body_layout)
        layout.append([HLine(p=TH.popup_sep_padx, color=TH.popup_sep_color)])

        b_kwargs = dict(
            button_color=TH.popup_button_color,
            mouse_over_color=TH.popup_bg_color,
            font=(TH.var_font, TH.popup_button_font_size),
        )
        buttons = [
            ButtonMouseOver(TXT.ok, bind_return_key=True, **b_kwargs),
            ButtonMouseOver(TXT.cancel, **b_kwargs),
        ]
        self.added_buttons = added_buttons or ()
        if added_buttons:
            buttons.append(sg.Push())
            for txt in added_buttons:
                buttons.append(ButtonMouseOver(txt, **b_kwargs))

        layout.append(buttons)
        layout = [[sg.Col(layout, p=5)]]

        args, kwargs = TH.get_window_params(layout)
        super().__init__(*args, modal=True, **kwargs)

    def loop(self):
        while True:
            # to keep main_window correctly refreshing
            do_exit = self.main_window.event_handler()
            if do_exit is not None:
                return do_exit

    def event_handler(self, event):
        if event in (None, TXT.cancel, *Shortcuts.exit):
            return False

        if event == TXT.ok:
            return True

        if event in self.added_buttons:
            return event

    def close(self):
        self.main_window.grey_all(False)
        super().close()


class Edit(Popup):
    def __init__(self, title, idship, description, used_couriers, couriers, main_window):
        self.couriers = couriers
        self.couriers_names = couriers.get_names()
        self.couriers_names.sort()
        layout = [
            [
                sg.T(TXT.description, font=(TH.fix_font, TH.edit_font_size)),
                sg.Input(description, font=(TH.fix_font, TH.edit_font_size), key="description"),
            ],
            [
                sg.T(TXT.idship, font=(TH.fix_font, TH.edit_font_size)),
                sg.Input(idship, font=(TH.fix_font, TH.edit_font_size), enable_events=True, key="idship"),
            ],
        ]

        self.check_colors = {True: TH.edit_check_color, False: TH.edit_unchecked_color}
        self.msg_font = {True: (TH.fix_font_bold, TH.edit_msg_font_size), False: (TH.fix_font, TH.edit_msg_font_size)}

        self.idship_widgets = []
        for name in self.couriers_names:
            is_checked = name in used_couriers
            cb = sg.CB(
                f" {name}",
                default=is_checked,
                text_color=self.check_colors[is_checked],
                font=(TH.fix_font, TH.edit_courier_font_size),
                enable_events=True,
                k=name,
            )
            msg = sg.T(
                f"({self.couriers.get_idship_validation_msg(name)})",
                font=self.msg_font[is_checked],
                expand_x=True,
                justification="r",
                k=(name, "msg"),
            )
            button = ButtonMouseOver(
                TXT.show.lower(),
                font=(TH.fix_font, TH.edit_show_button_font_size),
                button_color=TH.edit_show_button_color,
                k=(name, "button"),
            )

            self.idship_widgets.append((msg, button))
            layout.append([cb, msg, sg.vcenter(button)])

        super().__init__(title, layout, main_window)

        self.idship_updated(idship)

    def idship_updated(self, idship):
        for msg, button in self.idship_widgets:
            name = button.Key[0]

            valid = self.couriers.validate_idship(name, idship)
            msg.update(text_color=TH.ok_color if valid else TH.warn_color)

            visible = valid and self.couriers.get_url_for_browser(name, idship)
            button.update(disabled=not visible, visible=visible)

    def event_handler(self, event):
        if event == "idship":
            self.idship_updated(self["idship"].get())

        elif isinstance(event, tuple) and len(event) > 1 and event[1] == "button":
            name, idship = event[0], self["idship"].get()
            self.couriers.open_in_browser(name, idship)

        elif event in self.couriers_names:
            is_checked = self[event].get()
            self[event].update(text_color=self.check_colors[is_checked])
            self[(event, "msg")].update(font=self.msg_font[is_checked])

        else:
            return super().event_handler(event)

    def loop(self):
        ok, idship, description, used_couriers = False, None, None, None

        if super().loop():
            ok = True
            idship = self["idship"].get()
            description = self["description"].get()
            used_couriers = [name for name in self.couriers_names if self[name].get()]

        self.close()
        return ok, idship, description, used_couriers


class Choices(Popup):
    max_lines = TH.popup_max_choices
    selected_font = (TH.fix_font_bold, TH.choices_font_size)
    unselected_font = (TH.fix_font, TH.choices_font_size)

    def __init__(self, choices, title, main_window, added_buttons=None):
        row = namedtuple("row", "cb txt")
        rows = []
        for i, (choice, color) in enumerate(choices):
            cb = sg.CB("", p=0, default=False, enable_events=True, k=f"cb_choice{i}")
            t = sg.T(
                choice,
                p=0,
                font=self.unselected_font,
                text_color=color,
                enable_events=True,
                k=f"txt_choice{i}",
            )
            rows.append(row(cb, t))

        if rows:
            col = sg.Col(rows, scrollable=len(rows) > self.max_lines, vertical_scroll_only=True)
            layout = [[col]]

        else:
            layout = [
                [
                    sg.T(
                        TXT.empty,
                        expand_x=True,
                        font=self.selected_font,
                        text_color=TH.warn_color,
                        justification="center",
                    )
                ]
            ]

        self.choices = choices
        self.added_buttons = added_buttons or ()
        super().__init__(title, layout, main_window, added_buttons)

        if rows:
            for row in rows:
                row.txt.bind("<Button-1>", "")

            if col.Scrollable:
                cb_height = rows[0].cb.get_size()[1]
                height = cb_height * min(self.max_lines, len(rows))
                # https://github.com/PySimpleGUI/PySimpleGUI/issues/4407#issuecomment-860863915
                col.Widget.canvas.configure(width=None, height=height)

    def event_handler(self, event):
        if "cb_choice" in event:
            cb_widget, txt_widget = self[event], self[event.replace("cb", "txt")]
            txt_widget.update(font=self.selected_font if cb_widget.get() else self.unselected_font)

        elif "txt_choice" in event:
            cb_widget, txt_widget = self[event.replace("txt", "cb")], self[event]
            toggle_check = not cb_widget.get()
            cb_widget.update(value=toggle_check)
            txt_widget.update(font=self.selected_font if toggle_check else self.unselected_font)

        else:
            return super().event_handler(event)

    def loop(self):
        chosen = []

        exit_result = super().loop()
        if exit_result is True:
            chosen = [i for i in range(len(self.choices)) if self[f"cb_choice{i}"].get()]

        elif exit_result in self.added_buttons:
            chosen = exit_result

        self.close()
        return chosen


class OneChoice(Popup):
    def __init__(self, choices, choice_colors, title, main_window, default=0):
        layout = []
        for i, choice in enumerate(choices):
            color = choice_colors[choice if i == default else False]
            radio = sg.Radio(
                choice,
                group_id="choices",
                text_color=color,
                font=(TH.var_font_bold, TH.on_choice_font_size),
                enable_events=True,
                default=i == 0,
                k=choice,
            )
            layout.append([radio])

        self.choice_colors = choice_colors
        self.choices = choices
        super().__init__(title, layout, main_window)

    def event_handler(self, event):
        if event in self.choices:
            for choice in self.choices:
                color = self.choice_colors[choice if self[choice].get() else False]
                self[choice].update(text_color=color)

        else:
            return super().event_handler(event)

    def loop(self):
        choice = None

        if super().loop():
            # https://stackoverflow.com/questions/2361426/get-the-first-item-from-an-iterable-that-matches-a-condition
            choice = next(choice for choice in self.choices if self[choice].get())

        self.close()
        return choice


class AskConfirmation(Popup):
    def __init__(self, title, text, main_window):
        layout = [[sg.Image(filename=TH.warn_img), sg.T(text, font=(TH.var_font, TH.ask_confirmation_font_size))]]
        super().__init__(f"{title.capitalize()}?", layout, main_window)

    def loop(self):
        ok = super().loop()

        self.close()
        return ok
