import locale
from tkinter import TclError

import PySimpleGUI as sg

import localization as TXT
import theme as TH
from events import Events, Keys
from log import log
from trackers import Trackers
from trackersWidget import TrackerWidgets
from widget import ButtonMouseOver, ButtonTxtAndImg, ShowInTaskbarWindow

locale.setlocale(locale.LC_ALL, TXT.Locale_setting)  # date in correct language

Show_events = False
Exit_shorcuts = ("Escape:27",)
Log_shorcut = "l"


class GreyWindow:
    def __init__(self, window):
        self.followed_window = window

        kwargs = dict(
            **TH.no_frame_kwargs,
            margins=(0, 0),
            debugger_enabled=False,
            background_color="black",
            alpha_channel=0,
            finalize=True,
        )
        kwargs["keep_on_top"] = self.followed_window.KeepOnTop
        self.window = sg.Window("", [[]], size=(0, 0), location=(0, 0), **kwargs)
        self.window.disable()
        self.followed_window.TKroot.bind("<Configure>", self.followed_window_changed, add="+")

    def is_visible(self, window):
        return window.TKroot.attributes("-alpha") > 0.0

    def enable(self, enable):
        if enable:
            if not self.is_visible(self.window) and self.is_visible(self.followed_window):
                if not self.followed_window.KeepOnTop:
                    root = self.window.TKroot
                    root.lower()
                    root.lift()
                else:
                    self.window.bring_to_front()
                self.window.set_alpha(TH.greyed_alpha)

        elif self.is_visible(self.window):
            self.window.set_alpha(0)

    def followed_window_changed(self, event):
        if self.window.TKroot:
            w, h = self.followed_window.size
            x, y = self.followed_window.current_location()
            root = self.window.TKroot
            root.geometry(f"{w}x{h}+{x}+{y}")

            if not self.followed_window.KeepOnTop:
                # raise the greyed window above self.followed_window if needed
                if self.is_visible(self.window):
                    if root.tk.eval("wm stackorder " + str(root) + " isbelow " + str(self.followed_window.TKroot)):
                        root.lift()

    def close(self):
        self.enable(False)
        self.window.close()


class MainWindow(ShowInTaskbarWindow):
    def __init__(self, trackers_filename, load_as_json, splash):
        p = TH.menu_button_pad
        fs = TH.menu_button_font_size
        b_kwargs = dict(
            im_height=TH.menu_button_height,
            im_margin=TH.menu_button_img_margin,
            font=(TH.var_font_bold, fs),
            mouse_over_color="grey90",
        )

        log_b = ButtonTxtAndImg(
            TXT.log,
            p=p,
            image_filename=TH.log_img,
            button_color=(TH.log_color, TH.menu_color),
            k=Events.log,
            **b_kwargs,
        )
        new_b = ButtonTxtAndImg(
            TXT.new,
            p=(0, p),
            image_filename=TH.edit_img,
            button_color=(TH.edit_color, TH.menu_color),
            k=Events.new,
            **b_kwargs,
        )
        refresh_b = ButtonTxtAndImg(
            TXT.refresh,
            p=p,
            image_filename=TH.refresh_img,
            button_color=(TH.refresh_color, TH.menu_color),
            k=Events.refresh,
            **b_kwargs,
        )
        archives_b = ButtonTxtAndImg(
            TXT.archives,
            p=(0, p),
            image_filename=TH.archives_img,
            button_color=(TH.archives_color_empty, TH.menu_color),
            k=Events.archives,
            **b_kwargs,
        )
        trash_b = ButtonTxtAndImg(
            TXT.trash,
            p=p,
            image_filename=TH.trash_img,
            button_color=(TH.trash_color_empty, TH.menu_color),
            k=Events.trash,
            **b_kwargs,
        )
        recenter_widget = sg.T(
            "",
            background_color=TH.menu_color,
            p=0,
            expand_x=True,
            expand_y=True,
            k=Events.recenter,
        )
        min_b = ButtonMouseOver(
            TXT.minimize,
            p=p,
            font=(TH.var_font_bold, fs),
            button_color=TH.menu_color,
            mouse_over_color="red",
            k=Events.minimize,
        )
        exit_b = ButtonMouseOver(
            TXT.exit,
            p=((0, p), (p, p)),
            font=(TH.var_font_bold, fs),
            button_color=TH.menu_color,
            mouse_over_color="red",
            focus=True,
            k=Events.exit,
        )

        its_empty = sg.T(
            TXT.empty,
            p=(0, 15),
            expand_x=True,
            expand_y=True,
            font=(TH.var_font_bold, TH.empty_font_size),
            text_color="grey",
            background_color=TH.empty_color,
            k=Keys.its_empty,
        )
        pin_empty = sg.pin(its_empty, expand_x=True)
        pin_empty.BackgroundColor = TH.empty_color

        menu = sg.Col(
            [[log_b, new_b, refresh_b, archives_b, trash_b, recenter_widget, min_b, exit_b]],
            p=0,
            background_color=TH.menu_color,
            expand_x=True,
            k=Keys.menu,
        )
        col_kwargs = dict(p=0, expand_x=True, expand_y=True, background_color=TH.widget_event_bg_color)
        new_trakers = sg.Col([[]], k=Keys.new_tracker_widgets, **col_kwargs)
        old_trakers = sg.Col([[]], k=Keys.old_tracker_widgets, **col_kwargs)
        all_trackers = sg.Col(
            [[new_trakers], [old_trakers]],
            scrollable=True,
            vertical_scroll_only=True,
            k=Keys.all_tracker_widgets,
            **col_kwargs,
        )
        layout = [[menu], [all_trackers], [pin_empty]]

        args, kwargs = TH.get_window_params(layout, alpha_channel=0)
        kwargs["keep_on_top"] = False
        kwargs["no_titlebar"] = True
        super().__init__(*args, **kwargs)

        recenter_widget.bind("<Double-Button-1>", "")

        self.trackers = Trackers(trackers_filename, load_as_json, splash)
        self.widgets = TrackerWidgets(self, self.trackers, splash)

        self.grey_windows = [GreyWindow(self)]
        self.reappear()

    def addlog(self, log):
        self.log = log
        log.link_to(self)
        self.grey_windows.append(GreyWindow(log))

    def close(self):
        for grey_window in self.grey_windows:
            grey_window.close()

        super().close()
        self.trackers.close()

    def trigger_event(self, evt):
        if self.TKroot:
            self.write_event_value(evt, "")

    def grey_all(self, enable):
        for grey_window in self.grey_windows:
            grey_window.enable(enable)

    def loop(self):
        try:
            while True:
                if self.event_handler():
                    break
        except TclError as e:
            log(f"TCL error ({e})", error=True)

    # return True when exit
    def event_handler(self):
        window, event, values = sg.read_all_windows()

        if Show_events and isinstance(event, str) and "MouseWheel" not in event:
            log(f"{event = }" + (f", {value = }" if (value := values and values.get(event)) else ""))

        if callable(event):
            event(window)

        elif isinstance(event, tuple) and callable(event[0]):
            event[0](window)

        elif window == self:

            if event in (None, Events.exit, *Exit_shorcuts):
                return True

            elif event == Events.minimize:
                self.minimize()

            elif event in (Events.log, Log_shorcut):
                self.log.toggle()

            elif event == Events.recenter:
                self.widgets.recenter(window, force=True)

            elif event == Events.updating:
                self.widgets.updating_changed()

            elif event == Events.archives_updated:
                self.widgets.archives_updated()

            elif event == Events.trash_updated:
                self.widgets.deleted_updated()

            elif event == Events.update_window_size:
                self.widgets.update_window_size(window)

            elif event == Events.new:
                self.widgets.new(window)

            elif event == Events.refresh:
                self.widgets.update(window)

            elif event == Events.archives:
                self.widgets.show_archives(window)

            elif event == Events.trash:
                self.widgets.show_deleted(window)

        else:
            return window.event_handler(event) if event else False  # exit, see Popup.loop
