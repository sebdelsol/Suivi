from collections import namedtuple

import PySimpleGUI as sg

import localization as TXT
import theme as TH
from couriers import Courier
from widget import ButtonMouseOver, HLine


class Popup(sg.Window):
    def __init__(self, title, body_layout, main_window):
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
            [HLine(p=5, color=TH.popup_sep_color)],
        ]
        layout.extend(body_layout)
        layout.append([HLine(p=5, color=TH.popup_sep_color)])

        b_colors = dict(button_color=TH.button_color, mouseover_color=TH.popup_bg_color)
        layout.append(
            [
                ButtonMouseOver(TXT.ok, font=(TH.var_font, 12), bind_return_key=True, **b_colors),
                ButtonMouseOver(TXT.cancel, font=(TH.var_font, 12), **b_colors),
            ]
        )
        layout = [[sg.Col(layout, p=5)]]

        args, kwargs = TH.get_window_params(layout)
        super().__init__(*args, modal=True, **kwargs)
        ButtonMouseOver.finalize_all(self)

    def loop(self):
        while True:
            # to keep main_window correctly refreshing
            exit = self.main_window.event_handler()
            if exit is not None:
                return exit

    def event_handler(self, event):
        if event in (None, TXT.cancel, "Escape:27"):
            return False

        elif event == TXT.ok:
            return True

    def close(self):
        self.main_window.grey_all(False)
        super().close()


class Edit(Popup):
    def __init__(self, title, idship, description, used_couriers, couriers, main_window):
        self.couriers_names = couriers.get_names()
        self.couriers_names.sort()
        layout = [
            [
                sg.T(TXT.description, font=(TH.fix_font, 10)),
                sg.Input(description, font=(TH.fix_font, 10), key="description"),
            ],
            [
                sg.T(TXT.idship, font=(TH.fix_font, 10)),
                sg.Input(idship, font=(TH.fix_font, 10), enable_events=True, key="idship"),
            ],
        ]

        self.check_colors = {True: "black", False: "grey60"}
        self.msg_font = {True: (TH.fix_font_bold, 8), False: (TH.fix_font, 8)}

        self.idship_widgets = []
        for name in self.couriers_names:
            courier = couriers.get(name)

            is_checked = name in used_couriers
            cb = sg.CB(
                f" {name}",
                default=is_checked,
                text_color=self.check_colors[is_checked],
                font=(TH.fix_font, 12),
                enable_events=True,
                k=name,
            )
            msg = sg.T(
                f"({courier.idship_validation_msg})",
                font=self.msg_font[is_checked],
                expand_x=True,
                justification="r",
                k=f"{name}msg",
            )
            button = ButtonMouseOver("voir", font=(TH.fix_font, 8), button_color="grey90", k=courier)

            self.idship_widgets.append((msg, button))
            layout.append([cb, msg, sg.vcenter(button)])

        super().__init__(title, layout, main_window)

        self.idship_updated(idship)

    def idship_updated(self, idship):
        for msg, button in self.idship_widgets:
            courier = button.Key

            disabled = not courier.get_valid_url_for_browser(idship)
            button.update(disabled=disabled, visible=not disabled)

            valid = courier.validate_idship(idship)
            msg.update(text_color="green" if valid else "red")

    def event_handler(self, event):
        if event == "idship":
            self.idship_updated(self["idship"].get())

        elif isinstance(event, Courier):
            courier, idship = event, self["idship"].get()
            courier.open_in_browser(idship)

        elif event in self.couriers_names:
            is_checked = self[event].get()
            self[event].update(text_color=self.check_colors[is_checked])
            self[f"{event}msg"].update(font=self.msg_font[is_checked])

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
    selected_font, unselected_font = (TH.fix_font_bold, 9), (TH.fix_font, 9)

    def __init__(self, choices, title, main_window):
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
                        text_color="red",
                        justification="center",
                    )
                ]
            ]

        self.choices = choices
        super().__init__(title, layout, main_window)

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

        if super().loop():
            chosen = [i for i in range(len(self.choices)) if self[f"cb_choice{i}"].get()]

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
                font=(TH.var_font_bold, 20),
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


class Warning(Popup):
    def __init__(self, title, text, main_window):
        layout = [[sg.Image(filename=TH.warn_img), sg.T(text, font=(TH.var_font, 15))]]
        super().__init__(title, layout, main_window)

    def loop(self):
        ok = super().loop()

        self.close()
        return ok
