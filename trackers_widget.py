import re
import textwrap
import threading
from bisect import bisect
from tkinter import font as tk_font

import PySimpleGUI as sg
import timeago

import popup
from couriers import get_local_now
from events import Events, Keys
from imgtool import resize_and_colorize_gif, resize_and_colorize_img
from localization import TXT
from theme import TH
from trackers import TrackerState
from widget import (
    AnimatedGif,
    ButtonMouseOver,
    GraphRounded,
    HLine,
    MlineButtonsComponent,
    MlinePulsingComponent,
    TextFit,
    TextPulsingComponent,
)


class TrackerWidget:
    button_size = (TH.widget_button_size, TH.widget_button_size)
    updating_gif, refresh_img, edit_img, archive_img = None, None, None, None

    def __init__(self, tracker):
        self.tracker = tracker
        self.reset_size()
        self.free_to_update = True
        self.finalized = False

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
        self.n_events = 0
        self.n_new_events = 0
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self):
        self.hline = HLine(color=TH.widget_separator_color)
        # to be extended, see finalize
        self.layout = sg.Col([[self.hline]], p=0, expand_x=True, visible=False)
        self.pin = sg.pin(self.layout, expand_x=True)  # collapse when hidden

        # return minimum layout to be extended in finalize()
        return [[self.pin]]

    def finalize(self, window):
        if self.finalized:
            return False

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

        self.days_size = TH.elapsed_days_box_size
        self.days_font = (TH.fix_font_bold, TH.elapsed_days_font_size)
        graph_size = (self.days_size, self.days_size)
        self.days_widget = GraphRounded(
            canvas_size=graph_size,
            graph_bottom_left=(0, 0),
            graph_top_right=graph_size,
            p=(padx, 0),
            background_color=title_color,
        )

        self.desc_widget = TextFit(
            "",
            p=0,
            font=(TH.var_font, TH.widget_description_font_size),
            text_color=TH.widget_descrition_text_color,
            background_color=title_color,
            expand_x=True,
            justification="l",
        )

        self.id_widget = sg.MLine(
            "",
            p=0,
            font=(TH.fix_font, TH.widget_idship_font_size),
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

        self.ago_widget = sg.T(
            "",
            p=0,
            font=(TH.var_font, TH.widget_status_font_size),
            text_color=TH.widget_ago_color,
        )

        self.status_widget = sg.T(
            "",
            p=0,
            font=(TH.var_font, TH.widget_status_font_size),
            text_color=TH.widget_status_text_color,
            expand_x=True,
        )

        self.n_event_font = (TH.var_font, TH.n_event_font_size)
        self.n_new_event_font = (TH.var_font_bold, TH.n_new_event_font_size)
        self.n_event_widget = sg.T(
            "",
            p=0,
            font=self.n_event_font,
            text_color=TH.widget_expand_color,
        )

        self.remove_new_events_button = ButtonMouseOver(
            TXT.I_have_seen,
            p=(TH.remove_new_events_padx, 0),
            font=(TH.var_font_bold, TH.remove_new_events_font_size),
            button_color=(TH.remove_new_events_text_color, TH.remove_new_events_button_color),
            mouse_over_color=event_color,
            visible=False,
            k=self.remove_all_new_events,
        )
        remove_new_pin = sg.pin(self.remove_new_events_button)

        self.expand_button = ButtonMouseOver(
            "",
            p=0,
            font=(TH.fix_font, TH.widget_expand_font_size),
            button_color=(TH.widget_expand_color, event_color),
            mouse_over_color=title_color,
            k=self.toggle_expand,
        )

        self.events_font = (TH.fix_font, TH.widget_event_font_size)
        self.events_font_bold = (TH.fix_font_bold, TH.widget_event_font_size)
        self.events_widget = sg.MLine(
            "",
            p=0,
            font=self.events_font,
            background_color=event_color,
            visible=False,
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
            [
                [
                    self.ago_widget,
                    self.status_widget,
                    remove_new_pin,
                    self.n_event_widget,
                    self.expand_button,
                ]
            ],
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

        # toggle expand are tkinter bound
        # to be able to remove them without removing all binds
        self.button1_bind_id = {}
        self.toggle_expand_bind = lambda event, window=window: self.toggle_expand(window)
        for widget in (self.events_widget, events_widget_pin, self.status_widget, self.ago_widget, self.n_event_widget):
            self.bind_button1_to_expand(widget, bind=True)

        buttons = MlineButtonsComponent(self.events_widget)
        buttons.init(
            mouse_over_color=TH.widget_event_mouse_over_color,
            on_click=lambda key, window=window: self.remove_new_event(key, window),
        )
        self.events_widget.buttons = buttons

        pulsing = MlinePulsingComponent(self.events_widget)
        pulsing.init(TH.event_new_color, event_color)
        self.events_widget.pulsing = pulsing

        buttons = MlineButtonsComponent(self.couriers_widget)
        buttons.init(mouse_over_color=TH.widget_courier_mouse_over_color, on_click=self.open_in_browser)
        self.couriers_widget.buttons = buttons

        pulsing = MlinePulsingComponent(self.couriers_widget)
        pulsing.init(TH.refresh_color, title_color)
        self.couriers_widget.pulsing = pulsing

        pulsing = MlinePulsingComponent(self.id_widget)
        pulsing.init(TH.idship_color, title_color)
        self.id_widget.pulsing = pulsing

        pulsing = TextPulsingComponent(self.n_event_widget)
        pulsing.init(TH.event_new_color, event_color)
        self.n_event_widget.pulsing = pulsing

        self.show_current_content(window)

        # no more finalization needed
        self.finalized = True
        return True

    def toggle_expand(self, window):
        self.expand_events = not self.expand_events
        self.update_new_event()
        self.update_expand_button()
        self.update_size()
        window.trigger_event(Events.update_window_size)

    def bind_button1_to_expand(self, element, bind=True):
        if bind:
            if not self.button1_bind_id.get(element):
                bind_id = element.Widget.bind("<Button-1>", self.toggle_expand_bind, add="+")
                self.button1_bind_id[element] = bind_id

        else:
            if bind_id := self.button1_bind_id.get(element):
                # should be : element.Widget.unbind("<Button-1>", bind_id)
                # but there's a bug with unbind that removes all
                binds = element.Widget.bind("<Button-1>").split("\n")
                new_binds = [l for l in binds if l[6 : 6 + len(bind_id)] != bind_id]
                element.Widget.bind("<Button-1>", "\n".join(new_binds))
                self.button1_bind_id[element] = None

    def update_new_event(self):
        if self.n_events > 0 and self.n_new_events > 0:
            plural = TXT.several_new if self.n_events > 1 else TXT.new
            n_txt = f"{self.n_new_events} {plural}"
            self.n_event_widget.update(n_txt, font=self.n_new_event_font)

            self.bind_button1_to_expand(self.events_widget, bind=not self.expand_events)
            self.remove_new_events_button.update(visible=self.expand_events)
            self.n_event_widget.pulsing.start()
            self.events_widget.pulsing.start()

        else:
            plural = TXT.events if self.n_events > 1 else TXT.event
            n_txt = f"{self.n_events} {plural}"
            self.n_event_widget.update(n_txt, font=self.n_event_font, text_color=TH.widget_expand_color)

            self.bind_button1_to_expand(self.events_widget, bind=True)
            self.remove_new_events_button.update(visible=False)
            self.n_event_widget.pulsing.stop()
            self.events_widget.pulsing.stop()

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
            self.desc_widget.font_fit_to_txt(
                self.get_description(),
                TH.widget_description_max_width,
                TH.widget_description_font_size,
                7,
            )

    def update_visibility(self):
        self.layout.update(visible=self.tracker.state == TrackerState.shown)

    # https://stackoverflow.com/questions/11544187/tkinter-resize-text-to-contents/11545159
    def update_size(self):
        n_events_shown = float("inf") if self.expand_events else TH.widget_min_events_shown
        height = min(n_events_shown, self.height_events)
        self.events_widget.set_size((self.width_events, height))

        self.update_couriers_id_size()

    def update_couriers_id_size(self):
        txts = self.couriers_widget.get().split("\n")
        self.couriers_widget.set_size((max(len(t) for t in txts), len(txts)))

        txt = self.id_widget.get()
        # arrow character is not fixed size, so add 1
        self.id_widget.set_size((len(txt) + 1, 1))

    def show_current_content(self, window):
        if self.tracker.state == TrackerState.shown:
            self.show(self.tracker.get_consolidated_content(), window)

    def show_current_courier_widget(self):
        couriers_status = self.tracker.get_couriers_status()
        self.show_couriers(couriers_status)
        self.update_couriers_id_size()

    def update(self, window):
        if self.tracker.state == TrackerState.shown:
            self.free_to_update = False

            if couriers := self.tracker.get_idle_couriers():
                self.couriers_widget.pulsing.start()
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
                color = TH.warn_color if status_warn else (TH.ok_color if status_delivered else None)
                self.status_widget.update(status_label, text_color=color or TH.widget_status_text_color)
                self.desc_widget.update(text_color=color or TH.widget_descrition_text_color)

            else:
                self.n_events = 0
                self.n_new_events = 0
                self.width_events = 0
                self.height_events = 0
                self.status_widget.update(TXT.unknown_status, text_color=TH.warn_color)
                self.desc_widget.update(text_color=TH.widget_descrition_error_text_color)

            self.show_id(content)

            couriers_status = content.get("couriers_status")
            self.show_couriers(couriers_status)

            elapsed = content.get("elapsed")
            if elapsed:
                round_elapsed_days = elapsed.days + (1 if elapsed.seconds >= 43200 else 0)  # half a day in sec
                elapsed_color = TH.elapsed_days_colors[bisect(TH.elapsed_days_intervals, round_elapsed_days)]
                elapsed_txt = f"{round_elapsed_days}{'j' if round_elapsed_days <= 100 else ''}"
            else:
                elapsed_color = TH.elapsed_days_default_color
                elapsed_txt = "?"

            self.days_widget.erase()
            s = self.days_size
            self.days_widget.draw_rounded_box(s * 0.5, s * 0.5, s, s * 0.9, s * 0.15, TH.elapsed_days_bg_color)
            self.days_widget.draw_text(
                elapsed_txt, (s * 0.5, s * 0.5), color=elapsed_color, font=self.days_font, text_location="center"
            )

            status_date = content.get("status", {}).get("date")
            if status_date:
                status_ago = f"{timeago.format(status_date, get_local_now(), TXT.locale_country_code)}, "

            else:
                status_ago = ""

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
        self.n_events = 0
        self.n_new_events = 0

        if events:
            events_date = [f"{evt['date']:{TXT.long_date_format}}".replace(".", "").split(",") for evt in events]
            day_w, hour_w = max((len(date[0]), len(date[1])) for date in events_date)
            day_spaces, hour_spaces = " " * day_w, " " * hour_w
            previous_day, previous_hour = None, None

            events_courier = [f"{evt['courier']}, " for evt in events]
            courier_w = max(len(courier) for courier in events_courier)

            current_line = 1
            self.n_events = len(events)
            prt = self.events_widget.print
            prt_kw = dict(autoscroll=False, end="")
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
                event_color = TH.warn_color if event_warn else (TH.ok_color if event_delivered else None)

                if event.get("new"):
                    self.n_new_events += 1
                    event_new = f"{TXT.new} "
                    font = self.events_font_bold
                else:
                    event_new = ""
                    font = self.events_font

                # wrap event label and align with previous line(s)
                event_labels = textwrap.wrap(
                    event_label,
                    TH.widget_event_max_width - len(event_status),
                    drop_whitespace=False,
                ) or [""]

                width = sum(len(txt) for txt in (event_courier, event_date, event_new))

                if len(event_labels) > 1:
                    next_labels = textwrap.wrap("".join(event_labels[1:]), TH.widget_event_max_width)
                    event_labels[1:] = [f"{' '* width}{label.strip()}" for label in next_labels]
                event_labels[0] = event_labels[0].strip()

                prt(event_date, font=font, t=TH.event_date_color, **prt_kw)
                prt(event_courier, font=font, t=TH.event_courier_color, **prt_kw)
                prt(event_new, font=font, **prt_kw)
                status_font = self.events_font_bold if event_warn or event_delivered else font
                prt(event_status, font=status_font, t=event_color or TH.event_status_color, **prt_kw)
                for event_label in event_labels:
                    prt(event_label, font=font, t=event_color or TH.event_label_color, autoscroll=False)

                width += sum(len(txt) for txt in (event_status, event_labels[0]))
                self.width_events = max(width, self.width_events)
                self.height_events += len(event_labels)

                if event_new:
                    start_line = current_line
                    start_col = len(event_courier) + len(event_date)
                    end_col = start_col + len(event_new)
                    self.events_widget.pulsing.add_tag("", f"{start_line}.{start_col}", f"{start_line}.{end_col}")

                    end_line = start_line + len(event_labels) - 1
                    self.events_widget.buttons.add_tag(event, f"{start_line}.{0}", f"{end_line}.{width}")

                current_line += len(event_labels)

        if not self.n_new_events:
            self.events_widget.buttons.remove_tags()

        self.update_new_event()

    def remove_new_event(self, key, window):
        if self.expand_events:
            # key is event see events_widget.buttons.add_tag
            self.tracker.remove_new_event(key)
            self.show_current_content(window)  # show_events instead ??
        else:
            self.toggle_expand(window)

    def remove_all_new_events(self, window):
        self.tracker.remove_all_new_event()
        self.show_current_content(window)  # show_events instead ??

    def show_id(self, content):
        self.id_widget.update("")

        product = content.get("product", TXT.default_product)
        fromto = content.get("fromto")
        fromto = f" {fromto.lower()} " if fromto else " "

        prt = self.id_widget.print
        prt(product, autoscroll=False, t=TH.product_color, end="")
        prt(fromto, autoscroll=False, t=TH.from_to_color, end="")
        empty, idship = self.get_idship(check_empty=True)
        prt(idship, autoscroll=False, t=TH.warn_color if empty else TH.idship_color)

        start_col = len(self.id_widget.get()) - len(idship)
        self.id_widget.pulsing.add_tag("", f"1.{start_col}", "end")

    def show_couriers(self, couriers_status):
        if couriers_status:
            self.couriers_widget.update("")
            prt = self.couriers_widget.print
            prt_kw = dict(autoscroll=False, end="")

            agos = []
            for status in couriers_status:
                if status.ok_date:
                    ago = (
                        timeago.format(status.ok_date, get_local_now(), TXT.locale_country_code)
                        .replace(TXT.ago, "")
                        .strip()
                    )

                else:
                    ago = TXT.never

                agos.append(ago)

            width_ago = max(len(ago) for ago in agos)
            width_name = max(len(status.name) for status in couriers_status)

            for i, status in enumerate(couriers_status):
                ago = agos[i]
                ago_color = TH.ok_color if status.ok_date else TH.warn_color

                name_color = TH.warn_color if status.error else TH.ok_color
                name_font = self.couriers_font_bold if status.error else self.couriers_font
                name_txt = f" {status.name.center(width_name)}"

                update_msg = TXT.updating if status.updating else ""

                error_msg = ""
                if not status.updating:
                    if not status.exists:
                        error_msg = TXT.courier_doesnt_exist

                    elif not status.valid_idship:
                        empty_idship, _ = self.get_idship(check_empty=True)
                        error_msg = TXT.no_idship if empty_idship else TXT.invalid_idship

                    elif status.error:
                        error_msg = TXT.error_courier_update

                if error_msg:
                    error_msg += ":"

                prt(update_msg, font=self.couriers_font_bold, **prt_kw)
                prt(error_msg, font=self.couriers_font, t=TH.warn_color, **prt_kw)
                prt(name_txt, t=name_color, font=name_font, **prt_kw)
                prt(f" {TXT.updated} ", t=TH.courier_updated_color, **prt_kw)
                prt(ago.ljust(width_ago), t=ago_color, autoscroll=False)

                if status.updating:
                    # https://stackoverflow.com/questions/14786507/how-to-change-the-color-of-certain-words-in-the-tkinter-text-widget/30339009
                    line = i + 1
                    end_col = len(update_msg) + len(name_txt)
                    self.couriers_widget.pulsing.add_tag(status.name, f"{line}.0", f"{line}.{end_col}")

                if status.valid_idship:
                    line = i + 1
                    start = len(update_msg) + len(error_msg)
                    name_chr = list(re.finditer(r"\w+", name_txt))
                    start_col = start + name_chr[0].start()
                    end_col = start + name_chr[-1].end()
                    self.couriers_widget.buttons.add_tag(status.name, f"{line}.{start_col}", f"{line}.{end_col}")

        else:
            self.couriers_widget.update(TXT.no_couriers, text_color=TH.warn_color)

    def open_in_browser(self, key):
        # key is courier_name see couriers_widget.buttons.add_tag
        self.tracker.open_in_browser(key)

    def edit(self, window):
        trk = self.tracker
        popup_edit = popup.Edit(TXT.edit, trk.idship, trk.description, trk.used_couriers, trk.couriers, window)
        ok, idship, description, used_couriers = popup_edit.loop()
        if ok:
            self.tracker.set_id(idship, description, used_couriers)
            self.update(window)

    def archive_or_delete(self, window):
        self.disable_buttons(True)
        choices = {TXT.archive: self.archive, TXT.delete: self.delete}
        choices_colors = {TXT.archive: TH.ok_color, TXT.delete: TH.warn_color, False: TH.unselected_color}
        popup_one_choice = popup.OneChoice(
            choices,
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
            popup_warn = popup.AskConfirmation(
                ask,
                f"{self.get_description()} - {self.get_idship()}",
                window,
            )
            do_it = popup_warn.loop()

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

    def definitly_delete(self, window):
        self.set_state(TrackerState.definitly_deleted, window, False, Events.trash_updated)

    def undelete(self, window):
        self.set_state(TrackerState.shown, window, False, Events.trash_updated, reappear=True)

    def archive(self, window):
        self.set_state(TrackerState.archived, window, False, Events.archives_updated)

    def unarchive(self, window):
        self.set_state(TrackerState.shown, window, False, Events.archives_updated, reappear=True)

    def get_creation_date(self):
        return f"{self.tracker.creation_date:{TXT.short_date_format}}".replace(".", "")

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
        exit_result, chosen = self.choose(window, TXT.unarchive, TrackerState.archived, ok_name=TXT.unarchive)
        if exit_result:
            for widget in chosen:
                widget.unarchive(window)

    def show_deleted(self, window):
        def_delete_button_key = "-definitly delete-"
        def_delete_button = dict(txt=TXT.delete_definitly, mouse_over_color=TH.warn_color, key=def_delete_button_key)
        exit_result, chosen = self.choose(
            window, TXT.restore, TrackerState.deleted, ok_name=TXT.restore, added_button=def_delete_button
        )
        if exit_result == def_delete_button_key and chosen:
            w_desc = max(len(widget.get_description()) for widget in chosen)
            txt = "\n".join(f"{widget.get_description().ljust(w_desc)} - {widget.get_idship()}" for widget in chosen)
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

    def choose(self, window, title, state, ok_name, added_button=None):
        widgets = self.get_sorted(self.get_widgets_with_state(state))
        w_desc = max(len(widget.get_description()) for widget in widgets) if widgets else 0
        w_date = max(len(widget.get_creation_date()) for widget in widgets) if widgets else 0

        choices = []
        for widget in widgets:
            color = TH.ok_color if widget.get_delivered() else TH.warn_color
            date = f"{widget.get_creation_date()},".ljust(w_date + 1)
            txt = f"{date} {widget.get_description().ljust(w_desc)} - {widget.get_idship()}"
            choices.append((txt, color))

        popup_choices = popup.Choices(choices, title, window, ok_name, added_button)
        exit_result, chosen = popup_choices.loop()
        return exit_result, [widgets[i] for i in chosen]

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

        # needed to get the actual sizes
        window.refresh()  # or visibility_changed() that produces different glitches

        self.widgets_frame.contents_changed()
        self.its_empty.update(visible=not shown)

        menu_w = self.widget_menu.Widget.winfo_reqwidth()
        menu_h = self.widget_menu.Widget.winfo_reqheight()
        self.set_min_width(menu_w)

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
