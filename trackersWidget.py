import textwrap
import threading
from bisect import bisect
from tkinter import font as tk_font

import PySimpleGUI as sg
import timeago

import localization as TXT
import popup
import theme as TH
from couriers import get_local_now
from events import Events, Keys
from imgtool import resize_and_colorize_gif, resize_and_colorize_img
from log import log
from trackers import TrackerState
from widget import (
    AnimatedGif,
    ButtonMouseOver,
    GraphRounded,
    HLine,
    MlineButtonsComponent,
    MlinePulsingComponent,
    TextFit,
)


class TrackerWidget:
    button_size = (TH.widget_button_size, TH.widget_button_size)
    updating_gif, refresh_img, edit_img, archive_img = None, None, None, None

    def __init__(self, tracker):
        self.tracker = tracker
        self.reset_size()
        self.free_to_update = True

        # faster startup
        if not TrackerWidget.updating_gif:
            TrackerWidget.updating_gif = resize_and_colorize_gif(
                sg.DEFAULT_BASE64_LOADING_GIF,
                TH.widget_updating_gif_height,
                TH.refresh_color,
            )

            height = TH.widget_button_size - TH.widget_button_img_margin * 2
            size = (TH.widget_button_size, TH.widget_button_size)
            TrackerWidget.refresh_img = resize_and_colorize_img(TH.refresh_img, height, TH.refresh_color, size)
            TrackerWidget.edit_img = resize_and_colorize_img(TH.edit_img, height, TH.edit_color, size)
            TrackerWidget.archive_img = resize_and_colorize_img(TH.archives_img, height, TH.archives_color, size)

    def reset_size(self):
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self):
        self.hline = HLine(color=TH.widget_separator_color)
        self.layout = sg.Col([[self.hline]], p=0, expand_x=True, visible=False)  # to be extended, see finalize
        self.pin = sg.pin(self.layout, expand_x=True)  # collapse when hidden

        # return minimum layout to be extended in finalize()
        return [[self.pin]]

    def finalize(self, window):
        title_color = TH.widget_title_bg_color
        event_color = TH.widget_event_bg_color
        mline_kwargs = dict(write_only=True, no_scrollbar=True, disabled=True)
        padx = TH.widget_padx
        b_pad = TH.widget_button_pad

        b_colors = dict(
            button_color=title_color,
            mouse_over_color=TH.widget_button_mouse_over_color,
        )
        b_size = (TH.widget_button_size, TH.widget_button_size)
        edit_button = ButtonMouseOver("", image_data=self.edit_img, p=(0, b_pad), **b_colors, size=b_size, k=self.edit)
        self.refresh_button = ButtonMouseOver(
            "", image_data=self.refresh_img, p=0, **b_colors, size=b_size, k=self.update
        )
        archive_button = ButtonMouseOver(
            "",
            image_data=self.archive_img,
            p=(0, b_pad),
            **b_colors,
            size=b_size,
            k=self.archive_or_delete,
        )

        self.buttons = [edit_button, self.refresh_button, archive_button]
        buttons = sg.Col(
            [[button] for button in self.buttons],
            p=(padx, 0),
            background_color=title_color,
        )

        self.days_size = TH.widget_elapsed_days_box_size
        self.days_font = (TH.fix_font_bold, TH.widget_elapsed_days_font_size)
        graph_size = (self.days_size, self.days_size)
        self.days_widget = GraphRounded(
            canvas_size=graph_size,
            graph_bottom_left=(0, 0),
            graph_top_right=graph_size,
            p=(padx, 0),
            background_color=title_color,
        )

        desc_font = (TH.var_font, TH.widget_description_font_size)
        self.desc_widget = TextFit(
            "",
            p=0,
            font=desc_font,
            text_color=TH.widget_descrition_text_color,
            background_color=title_color,
            expand_x=True,
            justification="l",
        )

        id_font = (TH.fix_font, TH.widget_idship_font_size)
        self.id_widget = sg.MLine(
            "",
            p=0,
            font=id_font,
            background_color=title_color,
            justification="r",
            **mline_kwargs,
        )

        self.couriers_font = (TH.fix_font, TH.widget_courier_font_size)
        self.couriers_font_bold = (TH.fix_font_bold, TH.widget_courier_font_size)
        self.couriers_widget = sg.MLine(
            "",
            p=0,
            font=self.couriers_font,
            background_color=title_color,
            expand_x=True,
            justification="r",
            **mline_kwargs,
        )

        self.updating_widget = AnimatedGif(
            data=self.updating_gif,
            p=0,
            background_color=title_color,
            visible=False,
            speed=1,
        )
        updating_widget_col = sg.Col(
            [[self.updating_widget]],
            p=0,
            background_color=title_color,
            vertical_alignment="center",
        )
        push = sg.Push(background_color=title_color)

        id_couriers_widget_layout = [
            [push, updating_widget_col, self.id_widget],
            [self.couriers_widget],
        ]
        id_couriers_widget = sg.Col(
            id_couriers_widget_layout,
            p=((padx * 2, 0), (b_pad, b_pad)),
            expand_x=True,
            background_color=title_color,
            vertical_alignment="top",
        )

        ago_font = (TH.var_font, TH.widget_status_font_size)
        self.ago_widget = sg.T(
            "",
            p=0,
            font=ago_font,
            text_color=TH.widget_ago_color,
            k=lambda w: self.toggle_expand(w),
        )

        status_font = (TH.var_font, TH.widget_status_font_size)
        self.status_widget = sg.T(
            "",
            p=0,
            font=status_font,
            text_color=TH.widget_status_text_color,
            expand_x=True,
            k=lambda w: self.toggle_expand(w),
        )

        expand_font = (TH.fix_font, TH.widget_expand_font_size)
        expand_button_color = dict(
            button_color=(TH.widget_expand_color, event_color),
            mouse_over_color=title_color,
        )
        self.expand_button = ButtonMouseOver(
            "",
            p=0,
            font=expand_font,
            **expand_button_color,
            k=lambda w: self.toggle_expand(w),
        )

        self.events_font = (TH.fix_font, TH.widget_event_font_size)
        self.events_font_bold = (TH.fix_font_bold, TH.widget_event_font_size)
        self.events_widget = sg.MLine(
            "",
            p=0,
            font=self.events_font,
            background_color=event_color,
            visible=False,
            k=self.toggle_expand,
            **mline_kwargs,
        )
        events_widget_pin = sg.pin(self.events_widget, expand_x=True)  # collapse when hidden

        title_col = sg.Col(
            [[self.days_widget, self.desc_widget, id_couriers_widget, buttons]],
            p=0,
            background_color=title_color,
            expand_x=True,
        )
        status_col = sg.Col(
            [[self.ago_widget, self.status_widget, self.expand_button]],
            p=0,
            expand_x=True,
        )
        event_col = sg.Col(
            [[status_col], [events_widget_pin]],
            p=(padx, TH.widget_event_pady),
            expand_x=True,
        )

        # extend the layout & finalize
        window.extend_layout(self.layout, [[title_col], [event_col]])

        for widget in (self.id_widget, self.events_widget, self.couriers_widget):
            widget.grab_anywhere_include()
            # prevent selection https://stackoverflow.com/questions/54792599/how-can-i-make-a-tkinter-text-widget-unselectable?noredirect=1&lq=1
            widget.Widget.bindtags((str(widget.Widget), str(window.TKroot), "all"))

        # toggle expand
        for widget in (self.events_widget, self.status_widget, self.ago_widget):
            widget.bind("<Button-1>", "")

        buttons = MlineButtonsComponent(self.couriers_widget)
        buttons.init(mouse_over_color=TH.widget_courier_mouse_over_color, on_click=self.on_courrier_click)
        self.couriers_widget.buttons = buttons

        pulsing = MlinePulsingComponent(self.couriers_widget)
        pulsing.init(TH.refresh_color, TH.widget_title_bg_color)
        self.couriers_widget.pulsing = pulsing

        pulsing = MlinePulsingComponent(self.id_widget)
        pulsing.init("blue", TH.widget_title_bg_color)
        self.id_widget.pulsing = pulsing

        self.show_current_content(window)

        # no more finalization needed
        self.finalize = self.dummy_finalize
        return True

    def dummy_finalize(self, window):
        return False

    def toggle_expand(self, window):
        self.expand_events = not self.expand_events
        self.update_expand_button()

        self.update_size()
        window.trigger_event(Events.update_window_size)

    def update_expand_button(self):
        visible = self.is_events_visible() and self.height_events > TH.widget_min_events_shown
        self.expand_button.update("▲" if self.expand_events else "▼", visible=visible)

    def is_events_visible(self):
        return self.height_events > 0

    def set_min_width(self, min_width):
        self.hline.set_width(width=min_width)

    def get_pixel_width(self):
        return self.pin.Widget.winfo_reqwidth()

    def get_pixel_height(self):
        return self.pin.Widget.winfo_height()

    def disable_buttons(self, disabled):
        for button in self.buttons:
            button.update(disabled=disabled)

    def fit_description(self):
        if self.tracker.state == TrackerState.shown:
            size = self.desc_widget.font_fit_to_txt(
                self.get_description(),
                TH.widget_description_max_width,
                TH.widget_description_font_size,
                7,
            )
            log(f"set font {size=} for {self.get_description()}")

    def update_visibility(self):
        self.layout.update(visible=self.tracker.state == TrackerState.shown)

    # https://stackoverflow.com/questions/11544187/tkinter-resize-text-to-contents/11545159
    def update_size(self):
        nb_events_shown = float("inf") if self.expand_events else TH.widget_min_events_shown
        h = min(nb_events_shown, self.height_events)
        self.events_widget.set_size((self.width_events, h))

        self.update_couriers_id_size()

    def update_couriers_id_size(self):
        txts = self.couriers_widget.get().split("\n")
        self.couriers_widget.set_size((max(len(t) for t in txts), len(txts)))

        txt = self.id_widget.get()
        self.id_widget.set_size((len(txt) + 1, 1))  # arrow character is not fixed size, so add 1

    def show_current_content(self, window):
        if self.tracker.state == TrackerState.shown:
            self.show(self.tracker.get_consolidated_content(), window)

    def show_current_courier_widget(self):
        couriers_update = self.tracker.get_couriers_update()
        self.show_couriers(couriers_update)
        self.update_couriers_id_size()

    def update(self, window):
        if self.tracker.state == TrackerState.shown:
            self.free_to_update = False

            if couriers := self.tracker.get_idle_couriers():
                self.couriers_widget.pulsing.start(couriers)
                self.id_widget.pulsing.start()

                self.disable_buttons(True)
                window.trigger_event(Events.updating)

                self.show_current_courier_widget()
                self.updating_widget.update(visible=True)

                # daemon threads that'll be killed when exiting
                threading.Thread(
                    target=self.update_idle_couriers,
                    args=(window, couriers),
                    daemon=True,
                ).start()

            else:
                self.refresh_button.update(disabled=True)
                self.show_current_content(window)

    def update_idle_couriers(self, window, couriers):
        for content in self.tracker.update_idle_couriers(couriers):
            # https://stackoverflow.com/questions/10452770/python-lambdas-binding-to-local-values
            window.trigger_event(lambda window, content=content: self.update_one_courier_done(content, window))

        window.trigger_event(lambda window: self.update_done(window))

    def update_one_courier_done(self, content, window):
        self.show(content, window)
        self.refresh_button.update(disabled=False)
        self.free_to_update = True
        window.trigger_event(Events.updating)

    def update_done(self, window):
        if not self.tracker.is_courier_still_updating():
            self.id_widget.pulsing.stop()
            self.couriers_widget.pulsing.stop()
            self.disable_buttons(False)
            self.updating_widget.update(visible=False)

        window.trigger_event(Events.updating)

    def show(self, content, window):
        if self.tracker.state == TrackerState.shown:

            delivered = "✔" if content.get("status", {}).get("delivered") else ""
            self.desc_widget.update(f"{self.get_description()}{delivered}")
            self.events_widget.update("")

            if content.get("ok"):
                self.show_events(content)

                status_warn = content["status"].get("warn", False)
                status_delivered = content["status"].get("delivered", False)
                status_label = content["status"]["label"].replace(".", "")
                color = "red" if status_warn else ("green" if status_delivered else None)
                self.status_widget.update(status_label, text_color=color or TH.widget_status_text_color)
                self.desc_widget.update(text_color=color or TH.widget_descrition_text_color)

            else:
                self.width_events = 0
                self.height_events = 0
                self.status_widget.update(TXT.unknown_status, text_color="red")
                self.desc_widget.update(text_color=TH.widget_descrition_error_text_color)

            self.show_id(content)

            couriers_update = content.get("couriers_update")
            self.show_couriers(couriers_update)

            elapsed = content.get("elapsed")
            if elapsed:
                round_elapsed_days = elapsed.days + (1 if elapsed.seconds >= 43200 else 0)  # half a day in sec
                elapsed_color = TH.widget_elapsed_days_colors[
                    bisect(TH.widget_elapsed_days_intervals, round_elapsed_days)
                ]
                elapsed_txt = f"{round_elapsed_days}{'j' if round_elapsed_days <= 100 else ''}"
            else:
                elapsed_color = TH.widget_elapsed_days_default_color
                elapsed_txt = "?"

            self.days_widget.erase()
            self.days_widget.draw_rounded_box(
                self.days_size * 0.5,
                self.days_size * 0.5,
                self.days_size,
                self.days_size * 0.9,
                self.days_size * 0.15,
                TH.widget_elapsed_days_bg_color,
            )
            self.days_widget.draw_text(
                elapsed_txt,
                (self.days_size * 0.5, self.days_size * 0.5),
                color=elapsed_color,
                font=self.days_font,
                text_location="center",
            )

            status_date = content.get("status", {}).get("date")
            status_ago = f"{timeago.format(status_date, get_local_now(), 'fr')}, " if status_date else ""
            self.ago_widget.update(status_ago)

            self.events_widget.update(visible=self.is_events_visible())
            self.update_expand_button()

            self.update_size()
            self.fit_description()
            self.update_visibility()
            window.trigger_event(Events.update_window_size)

    def show_events(self, content):
        events = content["events"]
        self.width_events = 0
        self.height_events = 0

        if events:
            events_date = [f"{evt['date']:{TXT.Long_date_format}}".replace(".", "").split(",") for evt in events]
            day_w, hour_w = max((len(date[0]), len(date[1])) for date in events_date)
            day_spaces, hour_spaces = " " * day_w, " " * hour_w
            previous_day, previous_hour = None, None

            events_courier = [f"{evt['courier']}, " for evt in events]
            courier_w = max(len(courier) for courier in events_courier)

            prt = self.events_widget.print
            for i, event in enumerate(events):
                event_courier = events_courier[i].center(courier_w)

                day, hour = events_date[i]
                same_day, previous_day = day == previous_day, day
                same_hour, previous_hour = hour == previous_hour, hour
                if same_day:
                    day = day_spaces
                    if same_hour:
                        hour = hour_spaces

                event_date = f"{day}{' ' if same_day else ','}".ljust(day_w + 1)
                event_date += f"{hour}{' ' if same_hour and same_day else ','} "
                event_status = f"{event['status']}, " if event["status"] else ""
                event_label = f"{event['label']}."
                if event_label:
                    event_label = (
                        event_label.capitalize() if not event_status else (event_label[0].lower() + event_label[1:])
                    )

                # create a fake status if missing with firstwords of label
                if event_label and not event_status:
                    wrap = textwrap.wrap(event_label, 25)
                    event_status, event_label = (
                        (wrap[0] + " ", " ".join(wrap[1:])) if len(wrap) > 1 else (event_label, "")
                    )

                event_warn = event.get("warn")
                event_delivered = event.get("delivered")
                event_color = "red" if event_warn else ("green" if event_delivered else None)
                event_new, f = ("(new) ", self.events_font_bold) if event.get("new") else ("", self.events_font)

                width = sum(len(txt) for txt in (event_courier, event_date, event_new))

                event_labels = (
                    textwrap.wrap(
                        event_label,
                        TH.widget_event_max_width - len(event_status),
                        drop_whitespace=False,
                    )
                    or [""]
                )
                if len(event_labels) > 1:
                    next_labels = textwrap.wrap("".join(event_labels[1:]), TH.widget_event_max_width)
                    event_labels[1:] = [f"{' '* width}{label.strip()}" for label in next_labels]
                event_labels[0] = event_labels[0].strip()

                prt(event_date, font=f, autoscroll=False, t="grey", end="")
                prt(event_courier, font=f, autoscroll=False, t="grey70", end="")
                prt(event_new, font=f, autoscroll=False, t="black", end="")
                prt(
                    event_status,
                    font=self.events_font_bold if event_warn or event_delivered else f,
                    autoscroll=False,
                    t=event_color or "black",
                    end="",
                )
                for event_label in event_labels:
                    prt(event_label, font=f, autoscroll=False, t=event_color or "grey50")

                width += sum(len(txt) for txt in (event_status, event_labels[0]))
                self.width_events = max(width, self.width_events)
                self.height_events += len(event_labels)

    def show_id(self, content):
        self.id_widget.update("")

        product = content.get("product", TXT.default_product)
        fromto = content.get("fromto")
        fromto = f" {fromto.lower()} " if fromto else " "

        prt = self.id_widget.print
        prt(product, autoscroll=False, t="grey50", end="")
        prt(fromto, autoscroll=False, t="grey70", end="")
        empty, idship = self.get_idship(check_empty=True)
        prt(idship, autoscroll=False, t="red" if empty else "blue")

        start_col = len(self.id_widget.get()) - len(idship)
        self.id_widget.pulsing.add_tag("", f"1.{start_col}", "end")

    def show_couriers(self, couriers_update):
        if couriers_update:
            couriers_update_names = list(couriers_update.keys())
            couriers_update_names.sort()

            self.couriers_widget.update("")

            txts = []
            for name in couriers_update_names:
                date, error, updating, valid_idship, exists = couriers_update[name]
                ago_color, ago = (
                    (
                        "green",
                        f"{timeago.format(date, get_local_now(), 'fr').replace(TXT.ago, '').strip()}",
                    )
                    if date
                    else ("red", TXT.never)
                )
                name_color, name_font = ("red", self.couriers_font_bold) if error else ("green", self.couriers_font)

                error_msg = ""
                update_msg = ""

                if not exists:
                    error_msg = TXT.courier_doesnt_exist

                elif updating:
                    update_msg = TXT.updating

                elif not valid_idship:
                    empty_idship, _ = self.get_idship(check_empty=True)
                    error_msg = TXT.no_idship if empty_idship else TXT.invalid_idship

                elif error:
                    error_msg = TXT.error_courier_update

                if error_msg:
                    error_msg += ":"

                txts.append((ago, ago_color, name, name_color, name_font, update_msg, error_msg, valid_idship))

            width_name = max(len(txt[2]) for txt in txts)
            width_ago = max(len(txt[0]) for txt in txts)
            prt = self.couriers_widget.print

            for i, (ago, ago_color, name, name_color, name_font, update_msg, error_msg, valid_idship) in enumerate(
                txts
            ):
                prt(update_msg, autoscroll=False, font=self.couriers_font_bold, end="")
                prt(
                    error_msg,
                    autoscroll=False,
                    font=self.couriers_font,
                    t="red",
                    end="",
                )
                name_txt = f" {name.center(width_name)}"
                prt(name_txt, autoscroll=False, t=name_color, font=name_font, end="")
                prt(f" {TXT.updated} ", autoscroll=False, t="grey60", end="")
                prt(ago.ljust(width_ago), autoscroll=False, t=ago_color)

                if update_msg:
                    # https://stackoverflow.com/questions/14786507/how-to-change-the-color-of-certain-words-in-the-tkinter-text-widget/30339009
                    end_col = len(update_msg) + len(name_txt)
                    self.couriers_widget.pulsing.add_tag(name, f"{i + 1}.0", f"{i + 1}.{end_col}")

                if valid_idship:
                    start_col = len(update_msg) + len(error_msg) + 1
                    end_col = start_col + len(name_txt) - 1
                    self.couriers_widget.buttons.add_tag(name, f"{i + 1}.{start_col}", f"{i + 1}.{end_col}")

        else:
            self.couriers_widget.update(TXT.no_couriers, text_color="red")

    def on_courrier_click(self, key):
        self.tracker.open_in_browser(key)  # key is courier_name see couriers_widget.buttons.add_tag

    def edit(self, window):
        popup_edit = popup.Edit(
            TXT.edit,
            self.tracker.idship,
            self.tracker.description,
            self.tracker.used_couriers,
            self.tracker.available_couriers,
            window,
        )
        ok, idship, description, used_couriers = popup_edit.loop()
        if ok:
            self.tracker.set_id(idship, description, used_couriers)
            self.update(window)

    def archive_or_delete(self, window):
        self.disable_buttons(True)
        choices = {TXT.archive: self.archive, TXT.delete: self.delete}
        choices_colors = {TXT.archive: "green", TXT.delete: "red", False: "grey75"}
        popup_one_choice = popup.OneChoice(
            choices.keys(),
            choices_colors,
            f"{self.get_description()} - {self.get_idship()}",
            window,
        )
        choice = popup_one_choice.loop()
        if choice:
            choices[choice](window)

        self.disable_buttons(False)

    def set_state(self, state, window, ask, event, reappear=False):
        do_it = True
        if ask:
            popup_warning = popup.Warning(
                ask.capitalize(),
                f"{self.get_description()} - {self.get_idship()}",
                window,
            )
            do_it = popup_warning.loop()

        if do_it:
            self.tracker.state = state

            if reappear:
                self.reset_size()
                if not self.finalize(window):
                    self.show_current_content(window)
                self.update(window)

            else:
                self.update_visibility()
                window.trigger_event(Events.update_window_size)

            window.trigger_event(event)

    def delete(self, window):
        self.set_state(TrackerState.deleted, window, TXT.delete, Events.trash_updated)

    def undelete(self, window):
        self.set_state(TrackerState.shown, window, False, Events.trash_updated, reappear=True)

    def archive(self, window):
        self.set_state(TrackerState.archived, window, False, Events.archives_updated)

    def unarchive(self, window):
        self.set_state(TrackerState.shown, window, False, Events.archives_updated, reappear=True)

    def get_creation_date(self):
        return f"{self.tracker.creation_date:{TXT.Short_date_format}}".replace(".", "")

    def get_idship(self, check_empty=False):
        idship = self.tracker.idship.strip()
        if check_empty:
            return (False, idship) if idship else (True, TXT.no_idship)

        else:
            return idship or TXT.no_idship

    def get_description(self):
        return self.tracker.description.strip().title() or TXT.no_description

    def get_delivered(self):
        return self.tracker.get_delivered()


class TrackerWidgets:
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
            splash.update(f"{TXT.tracker_creation} {i + 1}/{n_trackers}")
            self.create_widget(window, tracker, new=False)

        self.update_window_size(window)
        self.recenter(window, True)

    def create_widget(self, window, tracker, new=False):
        widget = TrackerWidget(tracker)
        self.widgets.append(widget)

        where = self.new_trackers if new else self.old_trackers
        window.extend_layout(where, widget.create_layout())

        # finalize only shown trackers to speed up startup
        if widget.tracker.state == TrackerState.shown:
            widget.finalize(window)
            widget.update(window)

    def new(self, window):
        popup_edit = popup.Edit(TXT.new, "", TXT.new, [], self.trackers.couriers, window)
        ok, *tracker_params = popup_edit.loop()
        if ok:
            tracker = self.trackers.new(*tracker_params)
            self.create_widget(window, tracker, new=True)

    def get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def show_archives(self, window):
        widgets = self.choose(window, TXT.unarchive, TrackerState.archived)
        for widget in widgets:
            widget.unarchive(window)

    def show_deleted(self, window):
        widgets = self.choose(window, TXT.restore, TrackerState.deleted)
        for widget in widgets:
            widget.undelete(window)

    def choose(self, window, title, state):
        widgets = self.get_sorted(self.get_widgets_with_state(state))
        w_desc = max(len(widget.get_description()) for widget in widgets) if widgets else 0
        w_date = max(len(widget.get_creation_date()) for widget in widgets) if widgets else 0

        choices = []
        for widget in widgets:
            color = "green" if widget.get_delivered() else "red"
            date = f"{widget.get_creation_date()},".ljust(w_date + 1)
            txt = f"{date} {widget.get_description().ljust(w_desc)} - {widget.get_idship()}"
            choices.append((txt, color))

        popup_choices = popup.Choices(choices, title, window)
        chosen = popup_choices.loop()
        return [widgets[i] for i in chosen]

    def archives_updated(self):
        n_archives = self.trackers.count_state(TrackerState.archived)
        color = TH.archives_color if n_archives else TH.archives_color_empty
        self.archives_button.update(f"{TXT.archives}({n_archives})", button_color=(color, None))

    def deleted_updated(self):
        n_deleted = self.trackers.count_state(TrackerState.deleted)
        color = TH.trash_color if n_deleted else TH.trash_color_empty
        self.deleted_button.update(f"{TXT.trash}({n_deleted})", button_color=(color, None))

    def update(self, window):
        for widget in self.get_widgets_with_state(TrackerState.shown):
            widget.update(window)

    def get_sorted(self, widgets):
        return self.trackers.sort(widgets, get_tracker=lambda widget: widget.tracker)

    def count_free_to_update(self):
        shown = self.get_widgets_with_state(TrackerState.shown)
        return [widget.free_to_update for widget in shown].count(True)

    def updating_changed(self):
        n_free_to_update = self.count_free_to_update()
        self.refresh_button.update(disabled=n_free_to_update == 0)

    def set_min_width(self, min_width):
        for widget in self.get_widgets_with_state(TrackerState.shown):
            widget.set_min_width(min_width)

    def update_window_size(self, window):
        shown = self.get_widgets_with_state(TrackerState.shown)

        menu_w = self.widget_menu.Widget.winfo_reqwidth()
        menu_h = self.widget_menu.Widget.winfo_reqheight()
        self.set_min_width(menu_w)

        self.its_empty.update(visible=False if shown else True)

        # needed to get the actual widgets MLines size
        window.refresh()  # or visibility_changed() that produces different glitches
        self.widgets_frame.contents_changed()

        # wanted size
        if shown:
            w = max(widget.get_pixel_width() for widget in shown)
            h = sum(widget.get_pixel_height() for widget in self.widgets) + menu_h + 5

            # need a scrollbar ?
            screen_w, screen_h = window.get_screen_size()
            h_screen_margin = 0
            max_h = screen_h - h_screen_margin

            tk_scrollable_frame = self.widgets_frame.TKColFrame
            if h > max_h:
                tk_scrollable_frame.vscrollbar.pack(side=sg.tk.RIGHT, fill="y")
                # tk_scrollable_frame.TKFrame.bind("<Enter>", tk_scrollable_frame.hookMouseWheel)
                w += int(tk_scrollable_frame.vscrollbar["width"])
                # print("scrollbar")

            else:
                # self.widgets_frame.contents_changed()
                # # tk_scrollable_frame.vscrollbar.pack(side=sg.tk.RIGHT, fill="y")
                # tk_scrollable_frame.canvas.yview_moveto(1.0)
                # # tk_scrollable_frame.canvas.yview_scroll(10, "unit")
                tk_scrollable_frame.vscrollbar.pack_forget()
                # tk_scrollable_frame.TKFrame.unbind("<Enter>")
                # tk_scrollable_frame.unhookMouseWheel(None)
                # print("NO scrollbar")

            window.size = min(w, screen_w), min(h, max_h)
            self.recenter(window)

        else:
            self.widgets_frame.Widget.vscrollbar.pack_forget()

            # needed to set height because the scrollbar missing prevents the right height computation in pySimpleGUI
            window.size = (
                menu_w,
                menu_h + self.its_empty.Widget.winfo_reqheight() + self.its_empty.Pad[1] * 2,
            )

            # add spaces in its_empty to fit w
            wfont = tk_font.Font(self.its_empty.ParentForm.TKroot, self.its_empty.Font)
            n_spaces = round(menu_w / wfont.measure(" "))
            self.its_empty.update(TXT.empty.center(n_spaces))

    def recenter(self, window, force=False):
        W, H = window.get_screen_size()
        w, h = window.size
        x, y = window.current_location()
        if force:
            x = max(0, int((W - w) * 0.5))
            y = max(0, int((H - h) * 0.5))
        else:
            y = max(0, int((H - h) * 0.5)) if y + h > H else y
        window.move(x, y)
