import re
import textwrap
import threading
from bisect import bisect

import PySimpleGUI as sg
import timeago
from tools.img_tool import resize_and_colorize_gif, resize_and_colorize_img
from tracking.couriers import get_local_now
from tracking.trackers import TrackerState

from windows import popup
from windows.events import Events
from windows.localization import TXT
from windows.theme import TH
from windows.widgets import (
    AnimatedGif,
    BindToFunction,
    ButtonMouseOver,
    GraphRounded,
    HLine,
    MlineButtonsComponent,
    MlinePulsingComponent,
    TextFit,
    TextPulsingComponent,
)


class EventDates:
    def __init__(self, events):
        self.dates = []
        for evt in events:
            date = f"{evt['date']:{TXT.long_date_format}}".replace(".", "")
            day, hour = date.split(",")
            self.dates.append((day, hour))

    def get_iterator(self):
        return iter(self._get_event_date())

    def _get_event_date(self):
        day_width = max(len(date[0]) for date in self.dates)
        hour_width = max(len(date[1]) for date in self.dates)
        day_spaces = " " * day_width
        hour_spaces = " " * hour_width
        previous_day = None
        previous_hour = None

        for day, hour in self.dates:
            same_day, previous_day = day == previous_day, day
            same_hour, previous_hour = hour == previous_hour, hour
            if same_day:
                day = day_spaces
                if same_hour:
                    hour = hour_spaces

            day = f"{day.ljust(day_width)}{' ' if same_day else ','}"
            hour = f"{hour}{' ' if same_hour and same_day else ','}"
            yield f"{day}{hour} "


def get_event_labels(event, tab_width):
    """
    create an event status if missing
    wrap the label to not exceed widget_event_max_width
    add tab spaces for each lines
    """
    event_status = f"{event['status']}, " if event["status"] else ""
    event_label = f"{event['label']}."
    if event_label:
        if event_status:
            event_label = event_label[0].lower() + event_label[1:]

        else:
            event_label = event_label.capitalize()

    # create a fake status if missing with firstwords of label
    status_length = 25
    if event_label and not event_status:
        wrap = textwrap.wrap(event_label, status_length)
        if len(wrap) > 1:
            event_status = f"{wrap[0]} "
            event_label = " ".join(wrap[1:])

        else:
            event_status = event_label
            event_label = " "

    # wrap event label and align with previous line(s)
    event_labels = textwrap.wrap(
        event_label,
        TH.widget_event_max_width - len(event_status),
        drop_whitespace=False,
    ) or [""]

    if len(event_labels) > 1:
        next_labels = textwrap.wrap(
            "".join(event_labels[1:]), TH.widget_event_max_width
        )
        event_labels[1:] = [f"{' '* tab_width}{label.strip()}" for label in next_labels]
    event_labels[0] = event_labels[0].strip()

    return event_status, event_labels


class EventsWidget:
    def __init__(self, mline_kwargs, remove_new_event, remove_all_new_events):
        self.reset_size()
        self.remove_new_event = remove_new_event
        self.remove_all_new_events = remove_all_new_events

        self.n_event_font = (TH.var_font, TH.n_event_font_size)
        self.n_new_event_font = (TH.var_font_bold, TH.n_new_event_font_size)
        self.n_event_text = sg.T(
            "",
            p=0,
            font=self.n_event_font,
            text_color=TH.widget_expand_color,
        )

        self.remove_button = ButtonMouseOver(
            TXT.I_have_seen,
            p=(TH.remove_new_events_padx, 0),
            font=(TH.var_font_bold, TH.remove_new_events_font_size),
            button_color=(
                TH.remove_new_events_text_color,
                TH.remove_new_events_button_color,
            ),
            mouse_over_color=TH.widget_event_bg_color,
            visible=False,
            k=self.remove_all_new_events,
        )
        self.remove_new_pin = sg.pin(self.remove_button)

        self.expand_button = ButtonMouseOver(
            "",
            p=0,
            font=(TH.fix_font, TH.widget_expand_font_size),
            button_color=(TH.widget_expand_color, TH.widget_event_bg_color),
            mouse_over_color=TH.widget_title_bg_color,
            k=self.toggle_expand,
        )

        self.events_font = (TH.fix_font, TH.widget_event_font_size)
        self.events_font_bold = (TH.fix_font_bold, TH.widget_event_font_size)
        self.events_widget = sg.MLine(
            "",
            p=0,
            font=self.events_font,
            background_color=TH.widget_event_bg_color,
            visible=False,
            **mline_kwargs,
        )
        self.widget = sg.pin(self.events_widget, expand_x=True)  # collapse when hidden
        self.status_layout = [
            self.remove_new_pin,
            self.n_event_text,
            self.expand_button,
        ]

    def finalize(self, window):
        toggle_expand = lambda event, window=window: self.toggle_expand(window)
        self.bind_to_expand = BindToFunction("<Button-1>", toggle_expand)
        self.bind_to_expand.bind(self.events_widget, self.widget, self.n_event_text)

        buttons = MlineButtonsComponent(self.events_widget)
        buttons.init(
            mouse_over_color=TH.widget_event_mouse_over_color,
            on_click=lambda key, window=window: self.remove_new_event(key, window),
        )
        self.events_widget.buttons = buttons

        pulsing = MlinePulsingComponent(self.events_widget)
        pulsing.init(TH.event_new_color, TH.widget_event_bg_color)
        self.events_widget.pulsing = pulsing

        pulsing = TextPulsingComponent(self.n_event_text)
        pulsing.init(TH.event_new_color, TH.widget_event_bg_color)
        self.n_event_text.pulsing = pulsing

    def reset_size(self):
        self.n_events = 0
        self.n_new_events = 0
        self.width_events = 0
        self.height_events = 0
        self.are_events_expanded = False

    def toggle_expand(self, window):
        self.are_events_expanded = not self.are_events_expanded
        self._update_expand_button()
        self._update_remove_button_visibility()
        self._update_bind_to_expand()
        self._update_size()
        window.trigger_event(Events.update_window_size)

    def _update_new_event(self):
        visible = self.height_events > TH.widget_min_events_shown
        self.n_event_text.update(visible=visible)

        if self.n_events > 0 and self.n_new_events > 0:
            plural = TXT.several_new if self.n_events > 1 else TXT.new
            n_txt = f"{self.n_new_events} {plural}"
            self.n_event_text.update(n_txt, font=self.n_new_event_font)
            self.n_event_text.pulsing.start()
            self.events_widget.pulsing.start()

        else:
            plural = TXT.events if self.n_events > 1 else TXT.event
            n_txt = f"{self.n_events} {plural}"
            self.n_event_text.update(
                n_txt, font=self.n_event_font, text_color=TH.widget_expand_color
            )
            self.n_event_text.pulsing.stop()
            self.events_widget.pulsing.stop()

    def _update_bind_to_expand(self):
        unbind = (
            self.are_events_expanded and self.n_events > 0 and self.n_new_events > 0
        )
        if unbind:
            self.bind_to_expand.unbind(self.events_widget)
        else:
            self.bind_to_expand.bind(self.events_widget)

    def _update_remove_button_visibility(self):
        visible = (
            self.are_events_expanded and self.n_events > 0 and self.n_new_events > 0
        )
        self.remove_button.update(visible=visible)

    def _update_expand_button(self):
        visible = self.height_events > TH.widget_min_events_shown
        self.expand_button.update(
            "▲" if self.are_events_expanded else "▼", visible=visible
        )

    def _update_size(self):
        self.events_widget.update(visible=self.height_events > 0)
        height = (
            self.height_events
            if self.are_events_expanded
            else TH.widget_min_events_shown
        )
        self.events_widget.set_size((self.width_events, height))

    def _get_event_new(self, event):
        if event.get("new"):
            self.n_new_events += 1
            return f"{TXT.new} ", self.events_font_bold
        return "", self.events_font

    def show(self, content):
        self.events_widget.update("")

        self.width_events = 0
        self.height_events = 0
        self.n_events = 0
        self.n_new_events = 0

        if content.get("ok"):
            if events := content["events"]:
                self.n_events = len(events)

                events_dates = EventDates(events).get_iterator()
                events_couriers = [f"{evt['courier']}, " for evt in events]
                courier_w = max(len(courier) for courier in events_couriers)

                prt = self.events_widget.print
                prt_kw = dict(autoscroll=False, end="")

                for event, event_courier in zip(events, events_couriers):
                    event_courier = event_courier.center(courier_w)
                    event_date = next(events_dates)
                    event_new, font = self._get_event_new(event)
                    width = sum(len(txt) for txt in (event_courier, event_date))
                    event_status, event_labels = get_event_labels(event, width)
                    event_warn = event.get("warn")
                    event_delivered = event.get("delivered")
                    event_color = (
                        TH.warn_color
                        if event_warn
                        else (TH.ok_color if event_delivered else None)
                    )
                    status_color = event_color or TH.event_status_color
                    label_color = event_color or TH.event_label_color
                    status_font = (
                        self.events_font_bold if event_warn or event_delivered else font
                    )

                    prt(event_date, font=font, t=TH.event_date_color, **prt_kw)
                    prt(event_courier, font=font, t=TH.event_courier_color, **prt_kw)
                    prt(event_new, font=font, **prt_kw)
                    prt(event_status, font=status_font, t=status_color, **prt_kw)
                    for event_label in event_labels:
                        prt(event_label, font=font, t=label_color, autoscroll=False)

                    width += sum(
                        len(txt) for txt in (event_new, event_status, event_labels[0])
                    )
                    self.width_events = max(width, self.width_events)

                    if event_new:
                        start_line = self.height_events + 1
                        start_col = len(event_courier) + len(event_date)
                        end_col = start_col + len(event_new)
                        self.events_widget.pulsing.add_tag(
                            "", f"{start_line}.{start_col}", f"{start_line}.{end_col}"
                        )

                        end_line = start_line + len(event_labels) - 1
                        self.events_widget.buttons.add_tag(
                            event, f"{start_line}.{0}", f"{end_line}.{width}"
                        )

                    self.height_events += len(event_labels)

            if not self.n_new_events:
                self.events_widget.buttons.remove_tags()

        self._update_new_event()
        self._update_bind_to_expand()
        self._update_expand_button()
        self._update_remove_button_visibility()
        self._update_size()


class CouriersWidget:
    def __init__(self, mline_kwargs, get_idship, open_in_browser):
        self.get_idship = get_idship
        self.open_in_browser = open_in_browser

        self.n_courier_available = 0
        self.font = (TH.fix_font, TH.widget_courier_font_size)
        self.font_bold = (TH.fix_font_bold, TH.widget_courier_font_size)
        self.widget = sg.MLine(
            "",
            p=0,
            font=self.font,
            background_color=TH.widget_title_bg_color,
            expand_x=True,
            justification="r",
            **mline_kwargs,
        )

    def is_any_courier(self):
        return self.n_courier_available > 0

    def finalize(self):
        buttons = MlineButtonsComponent(self.widget)
        buttons.init(
            mouse_over_color=TH.widget_courier_mouse_over_color,
            on_click=self.open_in_browser,
        )
        self.widget.buttons = buttons

        pulsing = MlinePulsingComponent(self.widget)
        pulsing.init(TH.refresh_color, TH.widget_title_bg_color)
        self.widget.pulsing = pulsing

    def _update_size(self):
        txts = self.widget.get().split("\n")
        self.widget.set_size((max(len(t) for t in txts), len(txts)))

    @staticmethod
    def _get_agos(couriers_status):
        for status in couriers_status:
            if ok_date := status["ok_date"]:
                yield (
                    timeago.format(ok_date, get_local_now(), TXT.locale_country_code)
                    .replace(TXT.ago, "")
                    .strip()
                )

            else:
                yield TXT.never

    def _get_error_msg(self, status):
        error_msg = None
        if not status["updating"]:
            if not status["exists"]:
                error_msg = TXT.courier_doesnt_exist

            elif not status["valid_idship"]:
                empty_idship, _ = self.get_idship(check_empty=True)
                error_msg = TXT.no_idship if empty_idship else TXT.invalid_idship

            elif status["error"]:
                error_msg = TXT.error_courier_update

        return f"{error_msg}:" if error_msg else ""

    def show(self, content=None, couriers_status=None):
        self.n_courier_available = 0
        if not couriers_status:
            couriers_status = content.get("couriers_status")

        if couriers_status:
            self.n_courier_available = len(couriers_status)
            self.widget.update("")
            prt = self.widget.print
            prt_kw = dict(autoscroll=False, end="")

            agos = tuple(self._get_agos(couriers_status))
            width_ago = max(len(ago) for ago in agos)
            width_name = max(len(status["name"]) for status in couriers_status)

            for i, status in enumerate(couriers_status):
                name_txt = f" {status['name'].center(width_name)}"
                name_font = self.font_bold if status["error"] else self.font
                name_color = TH.warn_color if status["error"] else TH.ok_color
                ago = agos[i]
                ago_color = TH.ok_color if status["ok_date"] else TH.warn_color
                update_msg = TXT.updating if status["updating"] else ""
                error_msg = self._get_error_msg(status)

                prt(update_msg, font=self.font_bold, **prt_kw)
                prt(error_msg, font=self.font, t=TH.warn_color, **prt_kw)
                prt(name_txt, t=name_color, font=name_font, **prt_kw)
                prt(f" {TXT.updated} ", t=TH.courier_updated_color, **prt_kw)
                prt(ago.ljust(width_ago), t=ago_color, autoscroll=False)

                line = i + 1
                if status["updating"]:
                    # https://stackoverflow.com/a/14786570
                    end_col = len(update_msg) + len(name_txt)
                    self.widget.pulsing.add_tag(
                        status["name"], f"{line}.0", f"{line}.{end_col}"
                    )

                if status["valid_idship"]:
                    start = len(update_msg) + len(error_msg)
                    name_chr = list(re.finditer(r"\w+", name_txt))
                    start_col = start + name_chr[0].start()
                    end_col = start + name_chr[-1].end()
                    self.widget.buttons.add_tag(
                        status["name"], f"{line}.{start_col}", f"{line}.{end_col}"
                    )

        else:
            self.widget.update(TXT.no_couriers, text_color=TH.warn_color)

        self._update_size()

    def start_updating(self):
        self.widget.pulsing.start()

    def done_updating(self):
        self.widget.pulsing.stop()


class IdShipWidget:
    updating_gif = None

    def __init__(self, mline_kwargs, get_idship):
        self.get_idship = get_idship

        # faster startup
        if not IdShipWidget.updating_gif:
            IdShipWidget.updating_gif = resize_and_colorize_gif(
                sg.DEFAULT_BASE64_LOADING_GIF,
                TH.widget_updating_gif_height,
                TH.refresh_color,
            )

        self.widget = sg.MLine(
            "",
            p=0,
            font=(TH.fix_font, TH.widget_idship_font_size),
            background_color=TH.widget_title_bg_color,
            justification="r",
            **mline_kwargs,
        )

        self.updating_widget = AnimatedGif(
            data=self.updating_gif,
            p=0,
            background_color=TH.widget_title_bg_color,
            visible=False,
            speed=1,
        )
        updating_widget_col = sg.Col(
            [[self.updating_widget]],
            p=0,
            background_color=TH.widget_title_bg_color,
            vertical_alignment="center",
        )
        push = sg.Push(background_color=TH.widget_title_bg_color)

        self.layout = [push, updating_widget_col, self.widget]

    def finalize(self):
        pulsing = MlinePulsingComponent(self.widget)
        pulsing.init(TH.idship_color, TH.widget_title_bg_color)
        self.widget.pulsing = pulsing

    def _update_size(self):
        txt = self.widget.get()
        # arrow character is not fixed size, so add 1
        self.widget.set_size((len(txt) + 1, 1))

    def show(self, content):
        self.widget.update("")

        product = content.get("product", TXT.default_product)
        fromto = content.get("fromto")
        fromto = f" {fromto.lower()} " if fromto else " "
        empty, idship = self.get_idship(check_empty=True)

        prt = self.widget.print
        prt(product, autoscroll=False, t=TH.product_color, end="")
        prt(fromto, autoscroll=False, t=TH.from_to_color, end="")
        prt(idship, autoscroll=False, t=TH.warn_color if empty else TH.idship_color)

        start_col = len(self.widget.get()) - len(idship)
        self.widget.pulsing.add_tag("", f"1.{start_col}", "end")

        self._update_size()

    def start_updating(self):
        self.updating_widget.update(visible=True)
        self.widget.pulsing.start()

    def done_updating(self):
        self.updating_widget.update(visible=False)
        self.widget.pulsing.stop()


class ElapsedWidget:
    def __init__(self):
        self.graph_size = TH.elapsed_days_box_size
        self.days_font = (TH.fix_font_bold, TH.elapsed_days_font_size)
        self.widget = GraphRounded(
            canvas_size=self.graph_size,
            graph_bottom_left=(0, 0),
            graph_top_right=self.graph_size,
            p=((0, TH.widget_padx), (0, 0)),
            background_color=TH.widget_title_bg_color,
        )

    def show(self, content):
        elapsed = content.get("elapsed")
        if elapsed:
            round_elapsed_days = elapsed.days
            if elapsed.seconds >= 43200:  # half a day in sec
                round_elapsed_days += 1
            color_index = bisect(TH.elapsed_days_intervals, round_elapsed_days)
            elapsed_color = TH.elapsed_days_colors[color_index]
            elapsed_txt = f"{round_elapsed_days}j"

        else:
            elapsed_color = TH.elapsed_days_default_color
            elapsed_txt = "?"

        w, h = self.graph_size
        self.widget.erase()
        self.widget.draw_rounded_box(
            w * 0.5, h * 0.5, w, h, h * 0.4, TH.elapsed_days_bg_color, corner="right"
        )
        self.widget.draw_text(
            elapsed_txt,
            (w * 0.5, h * 0.55),
            color=elapsed_color,
            font=self.days_font,
            text_location=sg.TEXT_LOCATION_CENTER,
        )


class ToolbarWidget:
    button_size = (TH.widget_button_size, TH.widget_button_size)
    refresh_img, edit_img, archive_img = None, None, None

    def __init__(self, edit, update, archive_or_delete):
        # faster startup
        if not ToolbarWidget.refresh_img:
            height = TH.widget_button_size - TH.widget_button_img_margin * 2
            size = (TH.widget_button_size, TH.widget_button_size)
            ToolbarWidget.refresh_img = resize_and_colorize_img(
                TH.refresh_img, height, TH.refresh_color, size
            )
            ToolbarWidget.edit_img = resize_and_colorize_img(
                TH.edit_img, height, TH.edit_color, size
            )
            ToolbarWidget.archive_img = resize_and_colorize_img(
                TH.archives_img, height, TH.archives_color, size
            )

        b_colors = dict(
            button_color=TH.widget_title_bg_color,
            mouse_over_color=TH.widget_button_mouse_over_color,
        )
        b_size = (TH.widget_button_size, TH.widget_button_size)
        edit_button = ButtonMouseOver(
            "",
            image_data=self.edit_img,
            p=(0, TH.widget_button_pad),
            **b_colors,
            size=b_size,
            k=edit,
        )

        self.refresh_button = ButtonMouseOver(
            "", image_data=self.refresh_img, p=0, **b_colors, size=b_size, k=update
        )

        archive_button = ButtonMouseOver(
            "",
            image_data=self.archive_img,
            p=(0, TH.widget_button_pad),
            **b_colors,
            size=b_size,
            k=archive_or_delete,
        )

        self.buttons = [edit_button, self.refresh_button, archive_button]
        self.widget = sg.Col(
            [[button] for button in self.buttons],
            p=(TH.widget_padx, 0),
            background_color=TH.widget_title_bg_color,
        )

    def disable(self, disabled):
        for button in self.buttons:
            button.update(disabled=disabled)

    def disable_refresh(self, disabled):
        self.refresh_button.update(disabled=disabled)


class DescriptionWidget:
    def __init__(self, get_description):
        self.get_description = get_description
        self.widget = TextFit(
            "",
            p=0,
            font=(TH.var_font, TH.widget_description_font_size),
            text_color=TH.widget_descrition_text_color,
            background_color=TH.widget_title_bg_color,
            expand_x=True,
            justification="l",
        )

    def _fit_text(self):
        self.widget.font_fit_to_txt(
            self.get_description(),
            TH.widget_description_max_width,
            TH.widget_description_font_size,
            7,
        )

    def show(self, content, status_color):
        delivered = "✔" if content.get("status", {}).get("delivered") else ""
        self.widget.update(f"{self.get_description()}{delivered}")
        self._fit_text()

        if content.get("ok"):
            self.widget.update(
                text_color=status_color or TH.widget_descrition_text_color
            )

        else:
            self.widget.update(text_color=TH.widget_descrition_error_text_color)


class StatusWidget:
    def __init__(self):
        self.ago_widget = sg.T(
            "",
            p=0,
            font=(TH.var_font, TH.widget_status_ago_font_size),
            text_color=TH.widget_ago_color,
        )

        self.status_widget = sg.T(
            "",
            p=0,
            font=(TH.var_font, TH.widget_status_font_size),
            text_color=TH.widget_status_text_color,
            expand_x=True,
        )

        self.layout = [self.ago_widget, self.status_widget]

    def show(self, content):
        if status_date := content.get("status", {}).get("date"):
            status_ago = f"{timeago.format(status_date, get_local_now(), TXT.locale_country_code)}, "
            self.ago_widget.update(status_ago)

        else:
            self.ago_widget.update("")

        if content.get("ok"):
            status_warn = content["status"].get("warn", False)
            status_delivered = content["status"].get("delivered", False)
            status_label = content["status"]["label"].replace(".", "")
            color = (
                TH.warn_color
                if status_warn
                else (TH.ok_color if status_delivered else None)
            )
            self.status_widget.update(
                status_label, text_color=color or TH.widget_status_text_color
            )

        else:
            color = None
            self.status_widget.update(TXT.unknown_status, text_color=TH.warn_color)

        return color


class TrackerWidget:
    def __init__(self, tracker):
        self.tracker = tracker
        self.has_something_to_update = True
        self.finalized = False

    def create_layout(self):
        """layout to be extended, see finalize"""

        self.hline = HLine(color=TH.widget_separator_color)
        self.layout = sg.Col([[self.hline]], p=0, expand_x=True, visible=False)
        self.pin = sg.pin(self.layout, expand_x=True)  # collapse when hidden

        # return minimum layout to be extended in finalize()
        return [[self.pin]]

    def finalize(self, window):
        if self.finalized:
            return False

        mline_kwargs = dict(write_only=True, no_scrollbar=True, disabled=True)

        self.description = DescriptionWidget(self.get_description)
        self.toolbar = ToolbarWidget(self.edit, self.update, self.archive_or_delete)
        self.elapsed_widget = ElapsedWidget()
        self.idship = IdShipWidget(mline_kwargs, self.get_idship)
        self.couriers = CouriersWidget(
            mline_kwargs, self.get_idship, self.open_in_browser
        )
        self.events = EventsWidget(
            mline_kwargs, self.remove_new_event, self.remove_all_new_events
        )
        self.status = StatusWidget()

        idship_couriers = sg.Col(
            [self.idship.layout, [self.couriers.widget]],
            p=((TH.widget_padx * 2, 0), (TH.widget_button_pad, TH.widget_button_pad)),
            expand_x=True,
            background_color=TH.widget_title_bg_color,
            vertical_alignment="top",
        )

        title_col = sg.Col(
            [
                [
                    self.elapsed_widget.widget,
                    self.description.widget,
                    idship_couriers,
                    self.toolbar.widget,
                ]
            ],
            p=0,
            background_color=TH.widget_title_bg_color,
            expand_x=True,
        )

        status_col = sg.Col(
            [self.status.layout + self.events.status_layout], p=0, expand_x=True
        )
        event_col = sg.Col(
            [[status_col], [self.events.widget]],
            p=(TH.widget_padx, TH.widget_event_pady),
            expand_x=True,
        )

        # extend the layout & finalize
        window.extend_layout(self.layout, [[title_col], [event_col]])

        self.idship.finalize()
        self.couriers.finalize()
        self.events.finalize(window)
        self.events.bind_to_expand.bind(
            self.status.status_widget, self.status.ago_widget
        )

        # grab anywher and prevent selection
        for widget in (
            self.idship.widget,
            self.events.events_widget,
            self.couriers.widget,
        ):
            widget.grab_anywhere_include()
            widget.Widget.bindtags((str(widget.Widget), str(window.TKroot), "all"))

        self._show_current_content(window)

        # no more finalization needed
        self.finalized = True
        return True

    def _update_visibility(self):
        self.layout.update(visible=self.tracker.state == TrackerState.shown)

    def _show_current_content(self, window):
        if self.tracker.state == TrackerState.shown:
            self._show(self.tracker.get_consolidated_content(), window)

    def _show_current_courier_widget(self):
        self.couriers.show(couriers_status=self.tracker.get_couriers_status())

    def update(self, window):
        if self.tracker.state == TrackerState.shown:
            self.has_something_to_update = False

            if couriers := self.tracker.start_updating_idle_couriers():
                self.couriers.start_updating()
                self.idship.start_updating()
                self.toolbar.disable(True)
                window.trigger_event(Events.updating)
                self._show_current_courier_widget()

                # daemon threads that'll be killed when exiting
                threading.Thread(
                    target=self._update_idle_couriers,
                    args=(window, couriers),
                    daemon=True,
                ).start()

            else:
                self.toolbar.disable_refresh(disabled=True)
                self._show_current_content(window)

    def _update_idle_couriers(self, window, couriers):
        for content in self.tracker.update_idle_couriers(couriers):
            # https://stackoverflow.com/a/10452819
            window.trigger_event(
                lambda window, content=content: self._update_one_courier_done(
                    content, window
                )
            )

        window.trigger_event(self._update_done)

    def _update_one_courier_done(self, content, window):
        self._show(content, window)
        self.has_something_to_update = self.couriers.is_any_courier()
        self.toolbar.disable_refresh(disabled=not self.has_something_to_update)
        window.trigger_event(Events.updating)

    def _update_done(self, window):
        if not self.tracker.is_still_updating():
            self.idship.done_updating()
            self.couriers.done_updating()
            self.toolbar.disable(False)

        window.trigger_event(Events.updating)

    def _show(self, content, window):
        if self.tracker.state == TrackerState.shown:

            self.elapsed_widget.show(content)
            status_color = self.status.show(content)
            self.description.show(content, status_color)
            self.couriers.show(content)
            self.idship.show(content)
            self.events.show(content)

            self._update_visibility()
            window.trigger_event(Events.update_window_size)

    def set_min_width(self, min_width):
        self.hline.set_width(width=min_width)

    def get_pixel_width(self):
        return self.pin.Widget.winfo_reqwidth()

    def get_pixel_height(self):
        return self.pin.Widget.winfo_height()

    def open_in_browser(self, courier_name):
        self.tracker.open_in_browser(courier_name)

    def remove_new_event(self, event, window):
        self.tracker.remove_new_event(event)
        self._show_current_content(window)  # show_events instead ??

    def remove_all_new_events(self, window):
        self.tracker.remove_all_new_events()
        self._show_current_content(window)  # show_events instead ??

    def edit(self, window):
        trk = self.tracker
        popup_edit = popup.Edit(
            TXT.edit,
            trk.idship,
            trk.description,
            trk.used_couriers,
            trk.couriers_handler,
            window,
        )
        ok, idship, description, used_couriers = popup_edit.loop()
        if ok:
            self.tracker.set(
                idship=idship, description=description, used_couriers=used_couriers
            )
            self._show_current_content(window)
            self.update(window)

    def archive_or_delete(self, window):
        choices = {TXT.archive: self.archive, TXT.delete: self.delete}
        choices_colors = {
            TXT.archive: TH.ok_color,
            TXT.delete: TH.warn_color,
            False: TH.unselected_color,
        }
        popup_one_choice = popup.OneChoice(
            choices,
            choices_colors,
            f"{self.get_description()} - {self.get_idship()}",
            window,
        )
        choice = popup_one_choice.loop()
        if choice:
            choices[choice](window)

    def _set_state(self, state, window, ask, event):
        do_it = True
        if ask:
            popup_ask = popup.AskConfirmation(
                ask,
                f"{self.get_description()} - {self.get_idship()}",
                window,
            )
            do_it = popup_ask.loop()

        if do_it:
            self.tracker.state = state

            if state == TrackerState.shown:
                if not self.finalize(window):
                    self.events.reset_size()
                    self._show_current_content(window)
                self.update(window)

            else:
                self._update_visibility()
                window.trigger_event(Events.update_window_size)

            window.trigger_event(event)

    def delete(self, window):
        self._set_state(TrackerState.deleted, window, TXT.delete, Events.trash_updated)

    def definitly_delete(self, window):
        self._set_state(
            TrackerState.definitly_deleted, window, False, Events.trash_updated
        )

    def undelete(self, window):
        self._set_state(TrackerState.shown, window, False, Events.trash_updated)

    def archive(self, window):
        self._set_state(TrackerState.archived, window, False, Events.archives_updated)

    def unarchive(self, window):
        self._set_state(TrackerState.shown, window, False, Events.archives_updated)

    def get_creation_date(self):
        return f"{self.tracker.creation_date:{TXT.short_date_format}}".replace(".", "")

    def get_idship(self, check_empty=False):
        idship = self.tracker.idship.strip()
        if check_empty:
            return (False, idship) if idship else (True, TXT.no_idship)

        return idship or TXT.no_idship

    def get_description(self):
        return self.tracker.description.strip() or TXT.no_description

    def get_delivered(self):
        return self.tracker.get_delivered()
