import locale
from tkinter import font as tk_font

import PySimpleGUI as sg
from tracking.tracker import TrackerState

from . import popup
from .events import Events, Keys
from .localization import TXT
from .theme import TH
from .tracker_widget import TrackerWidget

# locale parser info for printing date
locale.setlocale(locale.LC_TIME, TXT.locale_setting)  # date in correct language


class TrackerWidgetsHandler:
    def __init__(self, window, trackers, splash):
        self.widgets = []
        self.trackers = trackers

        self.widgets_frame = window[Keys.all_tracker_widgets]
        self.old_trackers = window[Keys.old_tracker_widgets]
        self.new_trackers = window[Keys.new_tracker_widgets]
        self.widget_menu = window[Keys.menu]
        self.archives_button = window[Events.archives]
        self.refresh_button = window[Events.refresh]
        self.deleted_button = window[Events.trash]
        self.its_empty = window[Keys.its_empty]

        self.archives_updated()
        self.deleted_updated()

        n_trackers = len(trackers.trackers)
        for i, tracker in enumerate(trackers.trackers):
            splash(f"{TXT.tracker_creation} {i + 1}/{n_trackers}")
            self._create_widget(window, tracker, new=False)

        self.update_window_size(window)
        self.recenter(window, True)

    def _create_widget(self, window, tracker, new=False):
        widget = TrackerWidget(tracker)
        self.widgets.append(widget)

        where = self.new_trackers if new else self.old_trackers
        window.extend_layout(where, widget.create_layout())

        # finalize only shown trackers to speed up startup
        if widget.tracker.state == TrackerState.shown:
            widget.finalize(window)
            widget.update(window)

    def new(self, window):
        popup_edit = popup.Edit(
            TXT.new, "", TXT.new, [], self.trackers.couriers_handler, window
        )
        ok, *tracker_params = popup_edit.loop()
        if ok:
            tracker = self.trackers.new(*tracker_params)
            self._create_widget(window, tracker, new=True)

    def _get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def _get_sorted(self, widgets):
        return self.trackers.sort(widgets, get_tracker=lambda widget: widget.tracker)

    def _choose(self, window, title, state, ok_name, added_button=None):
        widgets = self._get_sorted(self._get_widgets_with_state(state))
        w_desc = (
            max(len(widget.get_description()) for widget in widgets) if widgets else 0
        )
        w_date = (
            max(len(widget.get_creation_date()) for widget in widgets) if widgets else 0
        )

        choices = []
        for widget in widgets:
            color = TH.ok_color if widget.get_delivered() else TH.warn_color
            date = f"{widget.get_creation_date()},".ljust(w_date + 1)
            txt = f"{date} {widget.get_description().ljust(w_desc)} - {widget.get_idship()}"
            choices.append((txt, color))

        popup_choices = popup.Choices(choices, title, window, ok_name, added_button)
        exit_result, chosen = popup_choices.loop()
        return exit_result, [widgets[i] for i in chosen]

    def show_archives(self, window):
        exit_result, chosen = self._choose(
            window, TXT.unarchive, TrackerState.archived, ok_name=TXT.unarchive
        )
        if exit_result:
            for widget in chosen:
                widget.unarchive(window)

    def show_deleted(self, window):
        def_delete_button_key = "-definitly delete-"
        def_delete_button = dict(
            txt=TXT.delete_definitly,
            mouse_over_color=TH.warn_color,
            key=def_delete_button_key,
        )
        exit_result, chosen = self._choose(
            window,
            TXT.restore,
            TrackerState.deleted,
            ok_name=TXT.restore,
            added_button=def_delete_button,
        )
        if exit_result == def_delete_button_key and chosen:
            w_desc = max(len(widget.get_description()) for widget in chosen)
            txt = "\n".join(
                f"{widget.get_description().ljust(w_desc)} - {widget.get_idship()}"
                for widget in chosen
            )
            popup_warn = popup.AskConfirmation(
                TXT.delete_definitly,
                txt,
                window,
            )
            definitly_delete = popup_warn.loop()
            if definitly_delete:
                for widget in chosen:
                    widget.definitly_delete(window)

        else:
            for widget in chosen:
                widget.undelete(window)

    def archives_updated(self):
        n_archives = self.trackers.count_state(TrackerState.archived)
        color = TH.archives_color if n_archives else TH.archives_color_empty
        self.archives_button.update(
            f"{TXT.archives}({n_archives})", button_color=(color, None)
        )

    def deleted_updated(self):
        n_deleted = self.trackers.count_state(TrackerState.deleted)
        color = TH.trash_color if n_deleted else TH.trash_color_empty
        self.deleted_button.update(
            f"{TXT.trash}({n_deleted})", button_color=(color, None)
        )

    def update(self, window):
        for widget in self._get_widgets_with_state(TrackerState.shown):
            widget.update(window)

    def _count_has_something_to_update(self):
        shown = self._get_widgets_with_state(TrackerState.shown)
        return [widget.has_something_to_update for widget in shown].count(True)

    def updating_changed(self):
        n_has_something_to_update = self._count_has_something_to_update()
        self.refresh_button.update(disabled=n_has_something_to_update == 0)

    def _set_min_width(self, min_width):
        for widget in self._get_widgets_with_state(TrackerState.shown):
            widget.set_min_width(min_width)

    def update_window_size(self, window):
        shown = self._get_widgets_with_state(TrackerState.shown)

        # needed to get the actual sizes
        window.refresh()  # or visibility_changed() that produces different glitches

        self.widgets_frame.contents_changed()
        self.its_empty.update(visible=not shown)

        menu_w = self.widget_menu.Widget.winfo_reqwidth()
        menu_h = self.widget_menu.Widget.winfo_reqheight()
        self._set_min_width(menu_w)

        # wanted size
        scrollbar = self.widgets_frame.TKColFrame.vscrollbar
        if shown:
            w = max(widget.get_pixel_width() for widget in shown)
            h = sum(widget.get_pixel_height() for widget in self.widgets) + menu_h + 5

            # need a scrollbar ?
            screen_w, screen_h = window.get_screen_size()
            max_h = screen_h - TH.window_height_screen_margin

            if h > max_h:
                scrollbar.pack(side=sg.tk.RIGHT, fill="y")
                w += int(scrollbar["width"])

            else:
                scrollbar.pack_forget()

            window.size = min(w, screen_w), min(h, max_h)
            self.recenter(window)

        else:
            scrollbar.pack_forget()

            # needed to set height because the scrollbar missing prevents the right height computation in pySimpleGUI
            window.size = (
                menu_w,
                menu_h
                + self.its_empty.Widget.winfo_reqheight()
                + self.its_empty.Pad[1] * 2,
            )

            # add spaces in its_empty to fit w
            wfont = tk_font.Font(self.its_empty.ParentForm.TKroot, self.its_empty.Font)
            n_spaces = round(menu_w / wfont.measure(" "))
            self.its_empty.update(TXT.empty.center(n_spaces))

    @staticmethod
    def recenter(window, force=False):
        W, H = window.get_screen_size()
        w, h = window.size
        x, y = window.current_location()
        if force:
            x = max(0, int((W - w) * 0.5))
            y = max(0, int((H - h) * 0.5))
        else:
            y = max(0, int((H - h) * 0.5)) if y + h > H else y
        window.move(x, y)
