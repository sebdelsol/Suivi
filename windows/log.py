import queue
import re
import threading
from tkinter import TclError

import PySimpleGUI as sg

from .events import Shortcuts
from .localization import TXT
from .theme import TH
from .widgets import ButtonMouseOver, Window


class _Logger(Window):
    link_txt = "\n".join("❱❱❱❱❱")
    unlink_txt = "\n".join("❰❰❰❰❰")
    close_txt = "\n".join(TXT.close.upper())
    listen_step = 20  # ms

    def __init__(self):
        self.print_only_lock = None
        self.prints = queue.Queue()
        self.linked = True
        self.resizing = False
        self.visible = False
        self.log_font_bold = (TH.fix_font_bold, TH.log_font_size)
        self.button_font_bold = (TH.var_font_bold, TH.log_button_font_size)

        self.output = sg.MLine(
            "",
            p=(5, 0),
            font=(TH.fix_font, TH.log_font_size),
            s=(80, 40),
            auto_refresh=True,
            autoscroll=True,
            disabled=True,
            expand_x=True,
            expand_y=True,
        )
        output_col = sg.Col(
            [[self.output]], p=0, background_color=TH.widget_title_bg_color
        )
        self.link_button = ButtonMouseOver(
            self.link_txt,
            p=0,
            font=(TH.var_font, TH.log_button_font_size),
            button_color=(TH.log_button_text_color, TH.log_button_color),
            mouse_over_color=TH.log_button_mouse_over_color,
            expand_x=True,
            expand_y=True,
            k="Link",
        )

        layout = [
            [
                output_col,
                sg.Col(
                    [[self.link_button], [sg.Sizegrip()]],
                    p=0,
                    expand_x=True,
                    expand_y=True,
                ),
            ]
        ]

        args, kwargs = TH.get_window_params(layout, alpha_channel=0, resizable=True)
        super().__init__(*args, **kwargs)

        self.TKroot.resizable(width=False, height=True)
        self.set_min_size(self.size)
        self.wanted_pos = None
        self.output.Widget.configure(selectbackground=TH.log_select_color)

    def link_to(self, main_window):
        self.main_window = main_window

        self.TKroot.bind("<Configure>", self.resize)
        self.main_window.TKroot.bind(
            "<Configure>", lambda evt: self.stick_to_main(), add="+"
        )

        self.listen()

    def listen(self, exiting=False):
        try:
            while True:
                args, error, kwargs = self.prints.get_nowait()
                print(*args, **kwargs)
                self.output.print(
                    *args,
                    **kwargs,
                    t=TH.warn_color if error else TH.ok_color,
                    font=self.log_font_bold if error else None,
                )

        except queue.Empty:
            if not exiting:
                self.TKroot.after(self.listen_step, self.listen)

    def resize(self, event):
        if self.linked and (
            (event.x == 0 and event.y == 0)
            or self.current_location() != self.wanted_pos
        ):
            self.stick_to_main()

    def event_handler(self, event):
        if event in (None, Shortcuts.log):
            self.toggle()

        elif event == "Link":
            self.linked = not self.linked
            if self.linked:
                self.output.Widget.tag_remove("sel", "1.0", "end")
                self.output.Widget.configure(selectbackground=TH.log_select_color)

                self.grab_any_where_off()
                self.output.grab_anywhere_exclude()
                self.link_button.update(self.link_txt)
                self.stick_to_main()

            else:
                # invisible selection
                self.output.Widget.configure(
                    selectbackground=self.output.Widget.cget("bg")
                )

                self.grab_any_where_on()
                self.output.grab_anywhere_include()
                self.link_button.update(self.unlink_txt)
                self.stick_to_main(gap=10, force=True)

    def stick_to_main(self, gap=0, force=False):
        if (self.visible and self.linked) or force:
            w, h = self.size
            _, H = self.main_window.size
            x, y = self.main_window.current_location()
            self.wanted_pos = int(x - w - gap) + 1, int(y + (H - h) * 0.5)
            self.move(*self.wanted_pos)

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.reappear()
            self.enable()
            self.stick_to_main()

        else:
            self.disappear()
            self.disable()

    def log(self, *args, error=False, **kwargs):
        if self.print_only_lock:
            with self.print_only_lock:
                print(*args, **kwargs)
        else:
            self.prints.put((args, error, kwargs))

    def print_only(self):
        self.print_only_lock = threading.Lock()

    def close(self):
        if self.visible:
            self.log("<< HIT a key to CLOSE >>", error=True)
            self.link_button.update(
                self.close_txt,
                button_color=(TH.log_button_close_text_color, TH.log_button_color),
            )
            self.link_button.Widget.config(font=self.button_font_bold)
            self.force_focus()
            self.TKroot.unbind("<Configure>")

            while True:
                event = self.read()[0]

                if (
                    event in (None, "Link")
                    or len(event) == 1
                    or re.match(r"\w+\:\d+", event)
                ):
                    break

        try:
            self.listen(exiting=True)
        except TclError as e:
            print(f"TCL error ({e})")

        self.print_only()
        super().close()


logger = _Logger()
log = logger.log
