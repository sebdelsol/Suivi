import locale
from tkinter import TclError

import PySimpleGUI as sg
from tracking.trackers_handler import TrackersHandler

from .events import Events, Keys, Shortcuts
from .localization import TXT
from .log import log
from .theme import TH
from .tracker_widgets_handler import TrackerWidgetsHandler
from .widgets import ButtonMouseOver, ButtonTxtAndImg, ShowInTaskbarWindow

SHOW_EVENTS = False

locale.setlocale(locale.LC_TIME, TXT.locale_setting)  # date in correct language


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
        self.followed_window.TKroot.bind(
            "<Configure>", self.followed_window_changed, add="+"
        )

    @staticmethod
    def is_visible(window):
        return window.TKroot.attributes("-alpha") > 0.0

    def enable(self, enable):
        if enable:
            if not self.is_visible(self.window) and self.is_visible(
                self.followed_window
            ):
                if not self.followed_window.KeepOnTop:
                    root = self.window.TKroot
                    root.lower()
                    root.lift()
                else:
                    self.window.bring_to_front()
                self.window.set_alpha(TH.greyed_alpha)

        elif self.is_visible(self.window):
            self.window.set_alpha(0)

    def followed_window_changed(self, event):  # pylint: disable=unused-argument
        if self.window.TKroot:
            w, h = self.followed_window.size
            x, y = self.followed_window.current_location()
            root = self.window.TKroot
            root.geometry(f"{w}x{h}+{x}+{y}")

            if not self.followed_window.KeepOnTop:
                # raise the greyed window above self.followed_window if needed
                if self.is_visible(self.window):
                    if root.tk.eval(
                        "wm stackorder "
                        + str(root)
                        + " isbelow "
                        + str(self.followed_window.TKroot)
                    ):
                        root.lift()

    def close(self):
        self.enable(False)
        self.window.close()


class MainWindow(ShowInTaskbarWindow):
    def __init__(self, trackers_filename, translation_module, load_as_json, splash):
        self.log = None
        col_kwargs = dict(
            p=0, expand_x=True, expand_y=True, background_color=TH.widget_event_bg_color
        )
        new_trakers = sg.Col([[]], k=Keys.new_tracker_widgets, **col_kwargs)
        old_trakers = sg.Col([[]], k=Keys.old_tracker_widgets, **col_kwargs)
        all_trackers = sg.Col(
            [[new_trakers], [old_trakers]],
            scrollable=True,
            vertical_scroll_only=True,
            k=Keys.all_tracker_widgets,
            **col_kwargs,
        )

        menu_layout = self.get_menu_layout()
        menu = sg.Col(
            [menu_layout],
            p=0,
            background_color=TH.menu_color,
            expand_x=True,
            k=Keys.menu,
        )

        its_empty = sg.T(
            TXT.empty,
            p=(0, TH.empty_pady),
            expand_x=True,
            expand_y=True,
            font=(TH.var_font_bold, TH.empty_font_size),
            text_color=TH.empty_font_color,
            background_color=TH.empty_color,
            k=Keys.its_empty,
        )
        pin_empty = sg.pin(its_empty, expand_x=True)
        pin_empty.BackgroundColor = TH.empty_color

        layout = [[menu], [all_trackers], [pin_empty]]

        args, kwargs = TH.get_window_params(layout, alpha_channel=0)
        kwargs["keep_on_top"] = False
        kwargs["no_titlebar"] = True
        super().__init__(*args, **kwargs)

        self[Events.recenter].bind("<Double-Button-1>", "")
        self.trackers = TrackersHandler(
            filename=trackers_filename,
            translation_module=translation_module,
            load_as_json=load_as_json,
        )
        self.widgets = TrackerWidgetsHandler(self, self.trackers, splash)
        self.set_event_to_action()

        self.grey_windows = [GreyWindow(self)]
        self.reappear()

    @staticmethod
    def get_menu_layout():
        px = TH.menu_button_padx
        py = TH.menu_button_pady
        b_kwargs = dict(
            im_height=TH.menu_button_height,
            im_margin=TH.menu_button_img_margin,
            font=(TH.var_font_bold, TH.menu_button_font_size),
            mouse_over_color=TH.menu_button_mouse_over_color,
        )

        layout = []
        layout.append(
            ButtonTxtAndImg(
                TXT.log,
                p=((py, px), (py, py)),
                image_filename=TH.log_img,
                button_color=(TH.log_color, TH.menu_color),
                k=Events.log,
                **b_kwargs,
            )
        )
        layout.append(
            ButtonTxtAndImg(
                TXT.new,
                p=(0, py),
                image_filename=TH.edit_img,
                button_color=(TH.edit_color, TH.menu_color),
                k=Events.new,
                **b_kwargs,
            )
        )
        layout.append(
            ButtonTxtAndImg(
                TXT.refresh,
                p=(px, py),
                image_filename=TH.refresh_img,
                button_color=(TH.refresh_color, TH.menu_color),
                k=Events.refresh,
                **b_kwargs,
            )
        )
        layout.append(
            ButtonTxtAndImg(
                TXT.archives,
                p=(0, py),
                image_filename=TH.archives_img,
                button_color=(TH.archives_color_empty, TH.menu_color),
                k=Events.archives,
                **b_kwargs,
            )
        )
        layout.append(
            ButtonTxtAndImg(
                TXT.trash,
                p=(px, py),
                image_filename=TH.trash_img,
                button_color=(TH.trash_color_empty, TH.menu_color),
                k=Events.trash,
                **b_kwargs,
            )
        )
        layout.append(
            sg.T(
                "",
                background_color=TH.menu_color,
                p=0,
                expand_x=True,
                expand_y=True,
                k=Events.recenter,
            )
        )
        layout.append(
            ButtonMouseOver(
                TXT.minimize,
                p=(0, py),
                font=(TH.var_font_bold, TH.menu_button_font_size),
                button_color=TH.menu_color,
                mouse_over_color=TH.warn_color,
                k=Events.minimize,
            )
        )
        layout.append(
            ButtonMouseOver(
                TXT.exit,
                p=((0, py), (py, py)),
                font=(TH.var_font_bold, TH.menu_button_font_size),
                button_color=TH.menu_color,
                mouse_over_color=TH.warn_color,
                focus=True,
                k=Events.exit,
            )
        )
        return layout

    def addlog(self, log_):
        self.log = log_
        log_.link_to(self)
        self.grey_windows.append(GreyWindow(log_))

    def close(self):
        log("Exiting")
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

    def set_event_to_action(self):
        self.event_to_action = {
            Events.minimize: self.minimize,
            Events.recenter: lambda window=self: self.widgets.recenter(
                window, force=True
            ),
            Events.updating: self.widgets.updating_changed,
            Events.archives_updated: self.widgets.archives_updated,
            Events.trash_updated: self.widgets.deleted_updated,
            Events.update_window_size: lambda window=self: self.widgets.update_window_size(
                window
            ),
            Events.new: lambda window=self: self.widgets.new(window),
            Events.refresh: lambda window=self: self.widgets.update(window),
            Events.archives: lambda window=self: self.widgets.show_archives(window),
            Events.trash: lambda window=self: self.widgets.show_deleted(window),
        }

    def event_handler(self):
        """return True when exit"""
        window, event, values = sg.read_all_windows()

        if SHOW_EVENTS and isinstance(event, str) and "MouseWheel" not in event:
            value = values and values.get(event)
            log(f"{event = }" + (f", {value = }" if value else ""))

        if callable(event):
            event(window)

        elif isinstance(event, tuple) and callable(event[0]):
            event[0](window)

        elif window == self:

            if event in (None, Events.exit, *Shortcuts.exit):
                return True

            if event in (Events.log, Shortcuts.log):
                if self.log:
                    self.log.toggle()

            elif action := self.event_to_action.get(event):
                action()

        else:
            return (
                window.event_handler(event) if event else False
            )  # exit, see Popup.loop
        return None
