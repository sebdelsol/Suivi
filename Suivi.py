import PySimpleGUI as sg
from packaging.specifiers import SpecifierSet
from local_txts import *
from theme import *

Python_version = '>=3.8, <3.9'
TrackersFile = 'Trackers'
LOAD_AS_JSON = True
SHOW_EVENTS = False

Recenter_event = '-Recenter-'
Updating_event = '-Updating Changed-'
Archives_updated_event = '-Archives updated-'
Trash_updated_event = '-Trash Updated-'
Update_widgets_size_event = '-Update Widgets Size-'

New_event = '-New-'
Refresh_event = '-Refresh-'
Archives_event = '-Archives-'
Trash_event = '-Trash-'
Log_event = '-Log-'
Exit_event = '-Exit-'

Menu_key = '-Menu-'
Its_empty_key = '-Empty-'
All_Tracker_widgets_key = '-Tracks-'
Old_Tracker_widgets_key = '-Old Tracks-'
New_Tracker_widgets_key = '-New Tracks-'

Exit_shorcuts = ('Escape:27', )
Log_shorcut = 'l'


class TrackerWidget:
    min_events_shown = widget_min_events_shown
    days_intervals = widget_elpapse_days_intervals
    days_colors = widget_elpased_days_colors

    max_event_width = widget_event_max_width  # chars

    button_size = (widget_button_size, widget_button_size)
    updating_gif, refresh_img, edit_img, archive_img = None, None, None, None

    def __init__(self, tracker):
        self.tracker = tracker
        self.min_events_shown = self.min_events_shown
        self.reset_size()
        self.free_to_update = True
        self.min_width = 0

        # faster startup
        if not TrackerWidget.updating_gif:
            TrackerWidget.updating_gif = resize_and_colorize_gif(sg.DEFAULT_BASE64_LOADING_GIF, widget_updating_gif_height, widget_updating_color)

            height = widget_button_size - widget_button_img_margin * 2
            size = (widget_button_size, widget_button_size)
            TrackerWidget.refresh_img = resize_and_colorize_img(Refresh_img, height, Refresh_color, size)
            TrackerWidget.edit_img = resize_and_colorize_img(Edit_img, height, Edit_color, size)
            TrackerWidget.archive_img = resize_and_colorize_img(Archives_img, height, Archives_color, size)

    def reset_size(self):
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self, new):
        bg_color_h = widget_background_title_color
        bg_color = widget_background_event_color

        b_p = widget_button_pad
        b_colors = dict(button_color=bg_color_h, mouseover_color='grey95')

        edit_button = MyButton('', image_data=self.edit_img, p=(0, b_p), **b_colors, k=self.edit)
        self.refresh_button = MyButton('', image_data=self.refresh_img, p=0, **b_colors, k=self.update)
        archive_button = MyButton('', image_data=self.archive_img, p=(0, b_p), **b_colors, k=self.archive_or_delete)

        self.buttons = [edit_button, self.refresh_button, archive_button]

        self.courier_fsize = widget_courier_font_size
        self.events_f = (FixFont, widget_event_font_size)
        self.events_fb = (FixFontBold, widget_event_font_size)

        self.days_size = widget_elapsed_days_box_size
        self.days_font = (FixFontBold, widget_elapsed_days_font_size)
        self.days_widget = MyGraph(canvas_size=(self.days_size, self.days_size), graph_bottom_left=(0, 0), graph_top_right=(self.days_size, self.days_size), p=(10, 0), background_color=bg_color_h)
        self.desc_widget = sg.T('', p=0, font=(VarFont, widget_description_font_size), text_color='grey40', background_color=bg_color_h, expand_x=False, justification='l')

        self.updating_widget = sg.Image(data=self.updating_gif, p=((10, 0), (0, 0)), visible=False, background_color=bg_color_h, k=lambda w: self.toggle_expand(w))
        updating_widget_pin = sg.pin(self.updating_widget)
        updating_widget_pin.BackgroundColor = bg_color_h
        to_expand = sg.T('', p=0, background_color=bg_color_h, expand_x=True)

        self.id_widget = sg.MLine('', p=0, font=(FixFont, widget_idship_font_size), disabled=True, border_width=0, no_scrollbar=True, background_color=bg_color_h, expand_x=True, justification='r')
        self.couriers_widget = sg.MLine('', p=0, font=(FixFont, self.courier_fsize), disabled=True, border_width=0, no_scrollbar=True, background_color=bg_color_h, expand_x=True, justification='r')
        id_couriers_widget = sg.Col([[self.id_widget], [self.couriers_widget]], p=((5, 0), (b_p, b_p)), background_color=bg_color_h, expand_x=True, vertical_alignment='top')
        buttons = sg.Col([[button] for button in self.buttons], p=(10, 0), background_color=bg_color_h, expand_x=False)

        self.ago_widget = sg.T('', p=0, font=(VarFont, widget_status_font_size), expand_x=False, background_color=bg_color, text_color='grey50', k=lambda w: self.toggle_expand(w))
        self.status_widget = sg.T('', p=0, font=(VarFont, widget_status_font_size), expand_x=False, background_color=bg_color, k=lambda w: self.toggle_expand(w))
        self.expand_button = MyButton('▼', p=(4, 0), font=(VarFont, widget_expand_font_size), button_color=('grey70', bg_color), mouseover_color='grey95', k=lambda w: self.toggle_expand(w))

        self.events_widget = sg.MLine('', p=((5, 5), (0, 5)), font=self.events_f, visible=False, disabled=True, border_width=0, background_color=bg_color,
                                      no_scrollbar=True, s=(None, self.min_events_shown), expand_x=True, k=self.toggle_expand)
        events_widget_pin = sg.pin(sg.Col([[self.events_widget]], p=(10, 0), background_color=bg_color, expand_x=True), expand_x=True)
        events_widget_pin.BackgroundColor = bg_color_h if new else bg_color

        self.title_col = sg.Col([[self.days_widget, self.desc_widget, updating_widget_pin, to_expand, id_couriers_widget, buttons]], p=0, background_color=bg_color_h, expand_x=True)
        self.status_col = sg.Col([[self.ago_widget, self.status_widget, self.expand_button]], p=(10, 0), background_color=bg_color, expand_x=True)

        layout = [[self.title_col],
                  [self.status_col],
                  [events_widget_pin]]

        self.layout = sg.Col(layout, expand_x=True, p=0, visible=self.tracker.state == TrackerState.shown, background_color=bg_color)
        self.pin = sg.pin(self.layout, expand_x=True)  # collapse when hidden
        self.pin.BackgroundColor = bg_color
        return [[self.pin]]

    def finalize(self, window):
        size = (widget_button_size, widget_button_size)
        for button in self.buttons:
            button.set_size(size)
            button.finalize()

        self.expand_button.finalize()

        for widget in (self.id_widget, self.events_widget, self.couriers_widget):
            widget.grab_anywhere_include()
            # prevent selection https://stackoverflow.com/questions/54792599/how-can-i-make-a-tkinter-text-widget-unselectable?noredirect=1&lq=1
            widget.Widget.bindtags((str(widget.Widget), str(window.TKroot), 'all'))

        # toggle expand
        for widget in (self.events_widget, self.status_widget, self.ago_widget, self.updating_widget):
            widget.bind('<Button-1>', '')

        self.show_current_content(window)

    def toggle_expand(self, window):
        self.expand_events = not self.expand_events
        self.update_expand_button()

        window.trigger_event(Update_widgets_size_event)

    def update_expand_button(self):
        is_visible = self.is_events_visible() and self.height_events > self.min_events_shown
        self.expand_button.update(('▲' if self.expand_events else '▼') if is_visible else '', disabled=not is_visible)

    def is_events_visible(self):
        return self.height_events > 0

    def set_min_width(self, width):
        self.min_width = width

    def get_pixel_width(self):
        return max(self.min_width, self.layout.Widget.winfo_reqwidth())
        # max_w = 0
        # if self.layout.visible:
        #     rows = (self.title_col, self.status_col, self.events_widget)
        #     for row in rows:
        #         w = row.Widget.winfo_reqwidth()
        #         padx = row.Pad[0]
        #         w += sum(padx) if isinstance(padx, tuple) else (padx * 2)
        #         max_w = max(w, max_w)

        # print ('W', self.tracker.description, max_w, self.layout.Widget.winfo_reqwidth())
        # return max(self.min_width, max_w)
        # # return max(self.min_width, self.layout.Widget.winfo_reqwidth())

    def get_pixel_height(self):
        return self.pin.Widget.winfo_height()  # get_size()[1]
        # return self.layout.Widget.winfo_reqheight()

        # if self.layout.visible:
        #     rows = (self.title_col, self.status_col, self.events_widget)
        #     h = 0
        #     for row in rows:
        #         h += row.Widget.winfo_reqheight()
        #         pady = row.Pad[1]
        #         h += sum(pady) if isinstance(pady, tuple) else (pady * 2)

        #     print ('H', self.tracker.description, h, self.layout.Widget.winfo_reqheight())
        #     # return self.layout.Widget.winfo_reqheight()
        #     return h
        # else:
        #     return 1

    def update_size(self, w):
        nb_events_shown = float('inf') if self.expand_events else self.min_events_shown
        h = min(nb_events_shown, self.height_events)
        self.events_widget.set_size((w, h))

        self.update_couriers_id_size()

        # print ('UPDATE SIZE', self.tracker.description, w, h)

        # tell frame not to let its children control its size
        # self.layout.Widget.pack_propagate(0) # size not controlled by its children
        # self.layout.set_size((self.get_pixel_width(), self.get_pixel_height()))

    def update_couriers_id_size(self):
        txts = [t for t in self.couriers_widget.get().split('\n')]
        self.couriers_widget.set_size((max(len(t) + 1 for t in txts), len(txts)))

        txt = self.id_widget.get()
        self.id_widget.set_size((len(txt), 1))

    def show_current_content(self, window):
        self.show(self.tracker.get_consolidated_content(), window)

    def show_current_courier_widget(self):
        couriers_update = self.tracker.get_courrier_update()
        self.show_couriers(couriers_update)
        self.update_couriers_id_size()

    def update(self, window):
        if self.tracker.state == TrackerState.shown:
            self.free_to_update = False
            if couriers := self.tracker.get_idle_couriers():
                self.disable_buttons(True)
                window.trigger_event(Updating_event)

                self.show_current_courier_widget()
                self.updating_widget.update(visible=True)

                threading.Thread(target=self.update_idle_couriers, args=(window, couriers), daemon=True).start()
            else:
                self.refresh_button.update(disabled=True)
                self.show_current_content(window)

    def update_idle_couriers(self, window, couriers):
        content = None
        for content in self.tracker.update_idle_couriers(couriers):
            # https://stackoverflow.com/questions/10452770/python-lambdas-binding-to-local-values
            window.trigger_event(lambda window, content=content: self.update_one_courier_done(content, window))

        window.trigger_event(lambda window: self.update_done(window))

    def update_one_courier_done(self, content, window):
        self.show(content, window)
        self.refresh_button.update(disabled=False)
        self.free_to_update = True
        window.trigger_event(Updating_event)

    def update_done(self, window):
        self.disable_buttons(False)
        self.updating_widget.update(visible=self.tracker.is_courier_still_updating())
        window.trigger_event(Updating_event)

    def animate(self, animation_step):
        if self.updating_widget.visible:
            self.updating_widget.update_animation(self.updating_gif, time_between_frames=animation_step)

    def show(self, content, window):
        if self.tracker.state == TrackerState.shown:

            delivered = '✔' if content.get('status', {}).get('delivered') else ''
            self.desc_widget.update(f'{self.get_description()}{delivered}')
            self.events_widget.update('')

            if content.get('ok'):
                self.show_events(content)

                status_warn = content['status'].get('warn', False)
                status_delivered = content['status'].get('delivered', False)
                status_label = content['status']['label'].replace('.', '')
                color = 'red' if status_warn else ('green' if status_delivered else None)
                self.status_widget.update(status_label, text_color=color)
                self.desc_widget.update(text_color=color)

            else:
                self.width_events = 0
                self.height_events = 0
                self.status_widget.update(Unkown_status_txt, text_color='red')
                self.desc_widget.update(text_color='grey70')

            self.show_id(content)

            couriers_update = content.get('courier_update')
            self.show_couriers(couriers_update)

            elapsed = content.get('elapsed')
            if elapsed:
                round_elapsed_days = elapsed.days + (1 if elapsed.seconds >= 43200 else 0)  # half a day in sec
                elapsed_color = self.days_colors[bisect(self.days_intervals, round_elapsed_days)]
                elapsed_txt = f"{round_elapsed_days}{'j' if round_elapsed_days <= 100 else ''}"
            else:
                elapsed_color = 'grey70'
                elapsed_txt = '?'

            self.days_widget.erase()
            self.days_widget.draw_rounded_box(self.days_size * .5, self.days_size * .5, self.days_size, self.days_size * .9, self.days_size * .15, 'grey90')
            self.days_widget.draw_text(elapsed_txt, (self.days_size * .5, self.days_size * .5), color=elapsed_color, font=self.days_font, text_location='center')

            status_date = content.get('status', {}).get('date')
            status_ago = f"{timeago.format(status_date, get_local_now(), 'fr')}, " if status_date else ''
            self.ago_widget.update(status_ago)

            self.events_widget.update(visible=self.is_events_visible())
            self.update_expand_button()

            window.trigger_event(Update_widgets_size_event)

    def show_events(self, content):
        events = content['events']
        self.width_events = 0
        self.height_events = 0

        if events:
            event_dates = [f"{evt['date']:{Long_date_format}}".replace('.', '').split(',') for evt in events]
            date_w = max(len(date) for date in event_dates)
            courier_w = max(len(evt['courier']) for evt in events)
            previous_day = None
            previous_hour = None

            prt = self.events_widget.print
            for i, event in enumerate(events):
                event_courier = f"{event['courier'].rjust(courier_w)}, "

                day, hour = event_dates[i]

                hour = hour.strip()
                same_day, previous_day = day == previous_day, day
                same_hour, previous_hour = hour == previous_hour, hour
                if same_day:
                    day = ' ' * len(previous_day)
                    if same_hour:
                        hour = ' ' * len(previous_hour)

                event_date = f"{day}{' ' if same_day else ','} {hour}{' ' if same_hour and same_day else ','} ".ljust(date_w)
                event_status = f"{event['status']}, " if event['status'] else ''
                event_label = f"{event['label']}."
                if event_label:
                    event_label = event_label.capitalize() if not event_status else (event_label[0].lower() + event_label[1:])

                # create a fake status if missing with firstwords of label
                if event_label and not event_status:
                    wrap = textwrap.wrap(event_label, 25)
                    event_status, event_label = (wrap[0] + ' ', ' '.join(wrap[1:])) if len(wrap) > 1 else (event_label, '')

                event_warn = event.get('warn')
                event_delivered = event.get('delivered')
                event_color = 'red' if event_warn else ('green' if event_delivered else None)
                event_new, f = ('(new) ', self.events_fb) if event.get('new') else ('', self.events_f)

                width = sum(len(txt) for txt in (event_courier, event_date, event_new))

                event_labels = textwrap.wrap(event_label, self.max_event_width - len(event_status), drop_whitespace=False) or ['']
                if len(event_labels) > 1:
                    next_labels = textwrap.wrap(''.join(event_labels[1:]), self.max_event_width)
                    event_labels[1:] = [f"{' '* width}{label.strip()}" for label in next_labels]
                event_labels[0] = event_labels[0].strip()

                prt(event_date, font=f, autoscroll=False, t='grey', end='')
                prt(event_courier, font=f, autoscroll=False, t='grey70', end='')
                prt(event_new, font=f, autoscroll=False, t='black', end='')
                prt(event_status, font=self.events_fb if event_warn or event_delivered else f, autoscroll=False, t=event_color or 'black', end='')
                for event_label in event_labels:
                    prt(event_label, font=f, autoscroll=False, t=event_color or 'grey50')

                width += sum(len(txt) for txt in (event_status, event_labels[0]))
                self.width_events = max(width, self.width_events)
                self.height_events += len(event_labels)

    def show_id(self, content):
        self.id_widget.update('')

        product = content.get('product', Default_product_txt)
        fromto = content.get('fromto')
        fromto = f' {fromto.lower()} ' if fromto else ' '

        prt = self.id_widget.print
        prt(f'{product}', autoscroll=False, t='grey50', end='')
        prt(fromto, autoscroll=False, t='grey70', end='')
        prt(self.get_idship(), autoscroll=False, t='blue', end='')

    def show_couriers(self, couriers_update):
        if couriers_update:
            couriers_update_names = list(couriers_update.keys())
            couriers_update_names.sort()

            self.couriers_widget.update('')

            txts = []
            for name in couriers_update_names:
                date, error, updating = couriers_update[name]
                ago_color, ago = ('green', f"{timeago.format(date, get_local_now(), 'fr').replace(Ago_txt, '').strip()}") if date else ('red', Never_txt)
                name_color, name_font = ('red', FixFontBold) if error else ('green', FixFont)
                txts.append((updating, ago, ago_color, name, name_color, name_font))

            width_name = max(len(txt[3]) for txt in txts)
            width_ago = max(len(txt[1]) for txt in txts)

            prt = self.couriers_widget.print
            for updating, ago, ago_color, name, name_color, name_font in txts:
                maj_txt = Updating_txt if updating else ' ' * len(Updating_txt)
                prt(maj_txt, autoscroll=False, font=(FixFontBold, self.courier_fsize), t=Refresh_color, end='')
                prt(name.rjust(width_name), autoscroll=False, t=name_color, font=(name_font, self.courier_fsize), end='')
                prt(f', {Updated_txt} ', autoscroll=False, t='grey60', end='')
                prt(ago.ljust(width_ago), autoscroll=False, t=ago_color)

        else:
            self.couriers_widget.update(No_couriers_txt, text_color='red')

    def disable_buttons(self, disabled):
        for button in self.buttons:
            button.update(disabled=disabled)

    def edit(self, window):
        popup_edit = popup.edit(Do_edit_txt, self.tracker.idship, self.tracker.description, self.tracker.used_couriers, self.tracker.available_couriers, window)
        ok, idship, description, used_couriers = popup_edit.loop()

        if ok:
            self.tracker.set_id(idship, description, used_couriers)
            self.reset_size()
            self.update(window)

    def update_visiblity(self):
        self.layout.update(visible=self.tracker.state == TrackerState.shown)

    def archive_or_delete(self, window):
        self.disable_buttons(True)

        choices = {Do_archive_txt: self.archive, Do_delete_txt: self.delete}
        choices_colors = {Do_archive_txt: 'green', Do_delete_txt: 'red', False: 'grey75'}

        popup_one_choice = popup.one_choice(choices.keys(), choices_colors, f'{self.get_description()} - {self.get_idship()}', window)
        choice = popup_one_choice.loop()

        if choice:
            choices[choice](window)

        self.disable_buttons(False)

    def set_state(self, state, window, ask, event, do_update=False):
        do_it = True
        if ask:
            popup_warning = popup.warning(ask.capitalize(), f'{self.get_description()} - {self.get_idship()}', window)
            do_it = popup_warning.loop()

        if do_it:
            self.tracker.state = state

            self.update_visiblity()
            self.reset_size()

            window.trigger_event(Update_widgets_size_event)
            window.trigger_event(event)

            if do_update:
                self.update(window)

    def delete(self, window):
        self.set_state(TrackerState.deleted, window, Do_delete_txt, Trash_updated_event)

    def undelete(self, window):
        self.set_state(TrackerState.shown, window, False, Trash_updated_event, True)

    def archive(self, window):
        self.set_state(TrackerState.archived, window, False, Archives_updated_event)

    def unarchive(self, window):
        self.set_state(TrackerState.shown, window, False, Archives_updated_event, True)

    def get_creation_date(self):
        return f'{self.tracker.creation_date:{Short_date_format}}'.replace('.', '')

    def get_idship(self):
        return self.tracker.idship.strip() or No_idship_txt

    def get_description(self):
        return self.tracker.description.strip().title() or No_idship_txt

    def get_delivered(self):
        return self.tracker.get_delivered()


class TrackerWidgets:
    def __init__(self, window, trackers, splash):
        self.widgets = []
        self.trackers = trackers

        self.widgets_frame = window[All_Tracker_widgets_key]
        self.old_trackers = window[Old_Tracker_widgets_key]
        self.new_trackers = window[New_Tracker_widgets_key]
        self.widget_menu = window[Menu_key]
        self.archives_button = window[Archives_event]
        self.refresh_button = window[Refresh_event]
        self.deleted_button = window[Trash_event]
        self.its_empty = window[Its_empty_key]

        self.archives_updated()
        self.deleted_updated()

        n_trackers = len(trackers.trackers)
        for i, tracker in enumerate(trackers.trackers):
            splash.update(f'{Tracker_creation_txt} {i + 1}/{n_trackers}')
            self.create_widget(window, tracker, new=False)

        self.update_size(window)
        self.recenter(window, True)

    def create_widget(self, window, tracker, new=False):
        widget = TrackerWidget(tracker)

        where = self.new_trackers if new else self.old_trackers
        window.extend_layout(where, widget.create_layout(new))
        self.widgets.append(widget)

        widget.finalize(window)
        widget.update(window)

    def new(self, window):
        popup_edit = popup.edit(New_txt, '', New_txt, [], self.trackers.couriers, window)
        ok, *tracker_params = popup_edit.loop()

        if ok:
            tracker = self.trackers.new(*tracker_params)
            self.create_widget(window, tracker, new=True)

    def get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def show_archives(self, window):
        widgets = self.choose(window, Do_unarchive_txt, TrackerState.archived)

        for widget in widgets:
            widget.unarchive(window)

    def show_deleted(self, window):
        widgets = self.choose(window, Do_restore_txt, TrackerState.deleted)

        for widget in widgets:
            widget.undelete(window)

    def choose(self, window, title, state):
        widgets = self.get_sorted(self.get_widgets_with_state(state))

        w_desc = max(len(widget.get_description()) for widget in widgets) if widgets else 0
        w_date = max(len(widget.get_creation_date()) for widget in widgets) if widgets else 0
        choices = []
        for widget in widgets:
            color = 'green' if widget.get_delivered() else 'red'
            date = f'{widget.get_creation_date()},'.ljust(w_date + 1)
            txt = f'{date} {widget.get_description().ljust(w_desc)} - {widget.get_idship()}'
            choices.append((txt, color))

        popup_choices = popup.choices(choices, title, window)
        chosen = popup_choices.loop()

        return [widgets[i] for i in chosen]

    def archives_updated(self):
        n_archives = self.trackers.count_state(TrackerState.archived)
        self.archives_button.update(f'{Archives_txt}({n_archives})')

    def deleted_updated(self):
        n_deleted = self.trackers.count_state(TrackerState.deleted)
        self.deleted_button.update(f'{Trash_txt}({n_deleted})')

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

    def animate(self, animation_step):
        for widget in self.get_widgets_with_state(TrackerState.shown):
            widget.animate(animation_step)

    def set_min_width(self, width):
        for widget in self.get_widgets_with_state(TrackerState.shown):
            widget.set_min_width(width)

    def update_size(self, window):
        shown = self.get_widgets_with_state(TrackerState.shown)

        menu_w = self.widget_menu.Widget.winfo_reqwidth()
        menu_h = self.widget_menu.Widget.winfo_reqheight()
        self.set_min_width(menu_w)

        # resize all widgets with the max width & and change pin color
        max_width_shown = max(widget.width_events for widget in shown) if shown else 0
        for widget in shown:
            widget.update_size(max_width_shown)

        self.its_empty.update(visible=False if shown else True)

        window.visibility_changed()
        self.widgets_frame.contents_changed()
        # window.refresh() # needed to get correct req width & height after MLines.setsize....

        # wanted size
        if shown:
            w = max(widget.get_pixel_width() for widget in shown)
            h = sum(widget.get_pixel_height() for widget in self.widgets) + menu_h + 4

            # need scrollbar ?
            screen_w, screen_h = window.get_screen_size()
            h_screen_margin = 0
            max_h = screen_h - h_screen_margin

            if h > max_h:
                self.widgets_frame.Widget.vscrollbar.pack(side=sg.tk.RIGHT, fill='y')
                w += int(self.widgets_frame.Widget.vscrollbar['width'])

            else:
                self.widgets_frame.Widget.vscrollbar.pack_forget()

            window.size = max(menu_w, min(w, screen_w)), min(h, max_h)

            self.recenter(window)

        else:
            self.widgets_frame.Widget.vscrollbar.pack_forget()

            # need to set height because the scrollbar missing prevents the right height computation in pySimpleGUI
            window.size = menu_w, menu_h + self.its_empty.Widget.winfo_reqheight() + self.its_empty.Pad[1] * 2

            # add spaces in its_empty to fit w
            wfont = font.Font(self.its_empty.ParentForm.TKroot, self.its_empty.Font)
            n_spaces = round(menu_w / wfont.measure(' '))
            self.its_empty.update(Empty_txt.center(n_spaces))

    def recenter(self, window, force=False):
        W, H = window.get_screen_size()
        w, h = window.size
        x, y = window.current_location()
        if force:
            x = max(0, int((W - w) * .5))
            y = max(0, int((H - h) * .5))
        else:
            y = max(0, int((H - h) * .5)) if y + h > H else y
        window.move(x, y)


class Splash:
    def __init__(self):
        self.log = sg.T('', font=(VarFont, 10))
        layout = [[sg.Image(filename=Mail_img)], [self.log]]
        args, kwargs = Get_window_params(layout, grab_anywhere=False)
        self.window = sg.Window(*args, **kwargs)

    def update(self, txt):
        self.log.update(f'{txt.capitalize()} ...')
        self.window.refresh()  # needed since there's no window loop

    def close(self):
        self.window.close()


class Grey_window:
    alpha_grey = .4

    def __init__(self, window):
        self.followed_window = window

        is_debugger = Is_debugger()
        kwargs = dict(keep_on_top=not is_debugger, no_titlebar=not is_debugger, margins=(0, 0), debugger_enabled=False, background_color='black', alpha_channel=0, finalize=True)
        self.window = sg.Window('', [[]], size=(0, 0), location=(0, 0), **kwargs)
        self.window.disable()
        self.followed_window.TKroot.bind('<Configure>', lambda evt: self.followed_window_changed(), add='+')

    def is_visible(self, window):
        return window.TKroot.attributes('-alpha') > 0.0

    def enable(self, enable):
        if enable:
            if not self.is_visible(self.window) and self.is_visible(self.followed_window):
                self.window.bring_to_front()
                self.window.set_alpha(self.alpha_grey)

        elif self.is_visible(self.window):
            self.window.set_alpha(0)

    def followed_window_changed(self):
        w, h = self.followed_window.size
        x, y = self.followed_window.current_location()
        self.window.TKroot.geometry(f'{w}x{h}+{x}+{y}')

    def close(self):
        self.enable(False)
        self.window.close()


class Main_window(sg.Window):
    animation_step = 100

    def __init__(self):
        p = menu_button_pad
        fs = menu_button_font_size
        b_kwargs = dict(im_height=menu_button_height, im_margin=menu_button_img_margin, font=(VarFontBold, fs), mouseover_color='grey90')

        log_b = MyButtonImg(Log_txt, p=p, image_filename=Log_img, button_color=(Log_color, menu_color), k=Log_event, **b_kwargs)
        new_b = MyButtonImg(New_txt, p=(0, p), image_filename=Edit_img, button_color=(Edit_color, menu_color), k=New_event, **b_kwargs)
        refresh_b = MyButtonImg(Refresh_Txt, p=p, image_filename=Refresh_img, button_color=(Refresh_color, menu_color), k=Refresh_event, **b_kwargs)
        archives_b = MyButtonImg(Archives_txt, p=(0, p), image_filename=Archives_img, button_color=(Archives_color, menu_color), k=Archives_event, **b_kwargs)
        trash_b = MyButtonImg(Trash_txt, p=p, image_filename=Trash_img, button_color=(Trash_color, menu_color), k=Trash_event, **b_kwargs)
        recenter_widget = sg.T('', background_color=menu_color, p=0, expand_x=True, expand_y=True, k=Recenter_event)
        exit_b = MyButton(Exit_txt, p=p, font=(VarFontBold, fs), button_color=menu_color, mouseover_color='red', focus=True, k=Exit_event)

        its_empty = sg.T(Empty_txt, p=(0, 15), expand_x=True, expand_y=True, font=(VarFontBold, empty_font_size), text_color='grey', background_color=empty_color, k=Its_empty_key)
        pin_empty = sg.pin(its_empty, expand_x=True)
        pin_empty.BackgroundColor = empty_color

        menu = sg.Col([[log_b, new_b, refresh_b, archives_b, trash_b, recenter_widget, exit_b]], p=0, background_color=menu_color, expand_x=True, k=Menu_key)
        new_trakers = sg.Col([[]], p=0, scrollable=False, expand_x=True, expand_y=True, background_color=menu_color, k=New_Tracker_widgets_key)
        old_trakers = sg.Col([[pin_empty]], p=0, scrollable=False, expand_x=True, expand_y=True, background_color=menu_color, k=Old_Tracker_widgets_key)

        all_trackers = sg.Col([[new_trakers], [old_trakers]], p=0, scrollable=True, vertical_scroll_only=True, expand_x=True, expand_y=True, background_color=menu_color, k=All_Tracker_widgets_key)
        layout = [[menu], [all_trackers]]

        args, kwargs = Get_window_params(layout, alpha_channel=0, resizable=True)
        super().__init__(*args, **kwargs)

        MyButton.finalize_all(self)
        recenter_widget.bind('<Double-Button-1>', '')

        self.trackers = Trackers(TrackersFile, LOAD_AS_JSON, splash)
        self.widgets = TrackerWidgets(self, self.trackers, splash)

        self.grey_windows = [Grey_window(self)]
        self.animate()
        self.reappear()

    def add_log(self, log):
        self.log = log
        log.link_to(self)
        self.grey_windows.append(Grey_window(log))

    def close(self):
        for grey_window in self.grey_windows:
            grey_window.close()

        super().close()
        self.trackers.close()

    def trigger_event(self, evt):
        if self.TKroot:
            self.write_event_value(evt, '')

    def animate(self):
        self.widgets.animate(self.animation_step)
        self.TKroot.after(self.animation_step, self.animate)

    def grey_all(self, enable):
        for grey_window in self.grey_windows:
            grey_window.enable(enable)

    def loop(self):
        while True:
            if self.event_handler():
                break

    def event_handler(self):
        window, event, values = sg.read_all_windows()

        if SHOW_EVENTS and isinstance(event, str) and 'MouseWheel' not in event:
            _log(f'{event = }' + (f', {value = }' if (value := values and values.get(event)) else ''))

        if callable(event):
            event(window)

        elif isinstance(event, tuple) and callable(event[0]):
            event[0](window)

        elif window == self:

            if event in (None, Exit_event, *Exit_shorcuts):
                return True

            elif event in (Log_event, Log_shorcut):
                self.log.toggle()

            elif event == Recenter_event:
                self.widgets.recenter(window, force=True)

            elif event == Updating_event:
                self.widgets.updating_changed()

            elif event == Archives_updated_event:
                self.widgets.archives_updated()

            elif event == Trash_updated_event:
                self.widgets.deleted_updated()

            elif event == Update_widgets_size_event:
                self.widgets.update_size(window)

            elif event == New_event:
                self.widgets.new(window)

            elif event == Refresh_event:
                self.widgets.update(window)

            elif event == Archives_event:
                self.widgets.show_archives(window)

            elif event == Trash_event:
                self.widgets.show_deleted(window)

        else:
            return window.event_handler(event)


if __name__ == "__main__":

    needs = SpecifierSet(Python_version)
    version = '.'.join(str(v) for v in sys.version_info[:3])

    if version not in needs:
        needs = ' and '.join(need for need in str(needs).split(','))
        print(f"Running Python version {version}, it needs Python {needs}")

    else:
        print(f'Python {version} running')

        sg.theme(Main_theme)

        # create splash before importing to reduce startup time
        splash = Splash()
        splash.update(Init_txt)

        # import after splash has been created
        import threading
        import timeago
        from bisect import bisect
        import textwrap
        from tkinter import font
        import locale
        locale.setlocale(locale.LC_ALL, Locale_setting)  # date in correct language

        from trackers import Trackers, TrackerState
        from imgtool import resize_and_colorize_gif, resize_and_colorize_img
        from couriers import get_local_now
        from myWidget import MyButton, MyButtonImg, MyGraph
        from mylog import mylog, _log
        import popup

        # create main_window
        main_window = Main_window()
        main_window.add_log(mylog)
        splash.close()

        main_window.loop()
        main_window.close()
        mylog.close()

    print('exiting')
