import PySimpleGUI as sg

TrackersFile = 'Trackers' # either .trck or .json 

Refresh_color = '#408040'
Archives_color = '#B2560D'
Edit_color = '#6060FF'

LOAD_AS_JSON = True

#---------------------------------
def three_char_month(date_txt, i):
    txts = date_txt.split()
    month = txts[i]
    txts[i] =  month[:3] if 'ju' not in month else month[:2] + month[3:]
    return ' '.join(txts)

#------------------
class SavedTracker:
    def __init__(self, tracker):
        with tracker.critical:
            # tracker attribute to save
            for attr in ('idship', 'description', 'used_couriers', 'state', 'contents'):
                self.__dict__[attr] = tracker.__dict__[attr]

#-------------
class Tracker:
    def __init__(self, idship, description, used_couriers, available_couriers, state = 'ok', contents = None):
        self.set_id(idship, description, used_couriers)
        self.state = state
        self.contents = contents or {}

        self.available_couriers = available_couriers
        self.critical = threading.Lock()
        self.couriers_error = {}
        self.couriers_updating = {}

        self.set_current_events()

    def set_id(self, idship, description, used_couriers):
        self.used_couriers = used_couriers
        self.description = description.title()
        self.idship = idship.strip()
    
    def set_current_events(self):
        self.current_events = set()
        for content in self.contents.values():
            self.current_events |= set( frozenset(evt.items()) for evt in content.get('events', []) ) # can't hash dict

    def update_events_new(self, events):
        for event in events:
            event['new'] = frozenset(event.items()) not in self.current_events
        return events

    def prepare_update(self):
        with self.critical:
            for courier_name in self.used_couriers:
                self.couriers_error[courier_name] = True
                self.couriers_updating[courier_name] = True

    def update(self):
        content_queue = queue.Queue()
        for courier_name in self.used_couriers:
            _log (f'update START {self.description} {self.idship} {courier_name}')
            threading.Thread(target = self.update_thread, args = (courier_name, content_queue)).start()

        for _ in range(len(self.used_couriers)):
            courier_name, new_content = content_queue.get()
            _log (f'update DONE {self.description} {self.idship} {courier_name}')

            with self.critical:
                if new_content is not None:
                    if new_content['ok'] or courier_name not in self.contents:
                        new_content['courier_name'] = courier_name
                        self.contents[courier_name] = new_content

                self.couriers_error[courier_name] = not(new_content and new_content['ok'])
                self.couriers_updating[courier_name] = False

            yield self.get_consolidated_content()

    def update_thread(self, courier_name, content_queue):
        try:
            courier = self.available_couriers.get(courier_name)
            if courier:
                content = courier.update(self.idship) if self.idship else {'ok' : False}
                content_queue.put((courier_name, content))
            else:
                content_queue.put((courier_name, None))
        
        except:
            _log (traceback.format_exc(), error = True)
            content_queue.put((courier_name, None))

    def get_consolidated_content(self):
        consolidated = {}

        with self.critical:
            contents_ok = [copy.deepcopy(content) for courier_name, content in self.contents.items() if courier_name in self.used_couriers and content['ok'] and content.get('idship') == self.idship]

            if len(contents_ok) > 0:
                contents_ok.sort(key = lambda c : c['status']['date'], reverse = True)
                consolidated = contents_ok[0]
                
                events = sum((content['events'] for content in contents_ok), [])
                events.sort(key = lambda evt : evt['date'], reverse = True)
                consolidated['events'] = self.update_events_new(events) 
                
                delivered = consolidated['status'].get('delivered')
                consolidated['elapsed'] = events and (events[0]['date'] if delivered else get_local_now()) - events[-1]['date']
                consolidated['status']['date'] = self.no_future(consolidated['status']['date'])
            
        consolidated['courier_update'] = self.get_courrier_update()
        
        return consolidated
    
    def get_courrier_update(self):
        with self.critical:
            couriers_update = {}
            for courier_name in self.used_couriers:
                content = self.contents.get(courier_name)
                ok_date = self.no_future(content.get('status',{}).get('ok_date') if content else None)
                error = self.couriers_error.get(courier_name, True)
                updating = self.couriers_updating.get(courier_name, False)
                couriers_update[courier_name] = (ok_date, error, updating)

            return couriers_update

    def no_future(self, date):
        if date : # not in future
            return min(date, get_local_now())

    def get_last_event(self):
        content = self.get_consolidated_content() or {}
        return content.get('status', {}).get('date', get_local_now())

    def get_pretty_last_event(self):
        last_event = self.get_last_event()
        if last_event:
            date = f'{last_event:%a %d %b %y}'.replace('.', '')
            return three_char_month(date, 2)
        else:
            return 'Pas de date'

    def get_pretty_idship(self):
        return self.idship.strip() or 'N° indéfini'

    def get_delivered(self):
        content = self.get_consolidated_content() 
        return content and content.get('status', {}).get('delivered')

#--------------
class Trackers:
    def __init__(self, filename, splash):
        self.filename = filename
        self.couriers = Couriers(splash)

        trackers = None

        ext, mode = ('.json', 'r') if LOAD_AS_JSON else ('.trck', 'rb')
        filename += ext
        if os.path.exists(filename):
            with open(filename, mode) as f:
                if LOAD_AS_JSON:
                    trackers = json.load(f, object_hook = json_decode_datetime)
                else:
                    trackers = pickle.load(f)

            _log(f'trackers LOADED from "{filename}"')

        if trackers:
            trackers = [Tracker(tracker['idship'], tracker['description'], tracker['used_couriers'], self.couriers, tracker['state'], tracker['contents']) for tracker in trackers]

        self.trackers = trackers or []
        self.trackers.sort(key = lambda t : t.get_last_event(), reverse = True)

    def save(self):
        self.trackers = self.get_not_deleted()

        saved_trackers = [SavedTracker(tracker).__dict__ for tracker in self.trackers]

        filename = self.filename + '.trck' 
        with open(filename, 'wb') as f:
            pickle.dump(saved_trackers, f)
            _log(f'trackers SAVED to "{filename}"')

        filename = self.filename + '.json' 
        with open(filename, 'w') as f:
            json.dump(saved_trackers, f, default = json_encode_datetime, indent = 4)
            _log(f'trackers SAVED to "{filename}"')

    def new(self, idship, description, used_couriers):
        if idship is not None:
            tracker = Tracker(idship, description, used_couriers, self.couriers)
            self.trackers.append(tracker)
            return tracker

    def clean_couriers(self):
        not_deleted = self.get_not_deleted()
        archived = self.get_archived()
        
        for courier_name in self.couriers.get_names():
            valid_idships = [tracker.idship for tracker in not_deleted if courier_name in tracker.used_couriers]
            if valid_idships:
                archived_idships = [tracker.idship for tracker in archived if courier_name in tracker.used_couriers]
                courier = self.couriers.get(courier_name)
                if courier:
                    courier.clean(valid_idships, archived_idships)

    def get_not_deleted(self):
        return [tracker for tracker in self.trackers if tracker.state != 'deleted']
    
    def get_archived(self):
        return [tracker for tracker in self.trackers if tracker.state == 'archived']

    def count_archived(self):
        return len(self.get_archived())

    def close(self):
        self.couriers.close()

#-------------------
class TrackerWidget:
    min_events_shown = 1
    days_intervals = [10, 20, 30]
    days_colors = ['lime green', 'dark orange', 'red', 'black']

    max_event_width = 110 # chars

    bg_color = 'grey90'
    bg_color_h = 'grey85'

    button_size = (22, 22)
    img_per = .6
    loading_gif, refresh_img, edit_img, archive_img = None, None, None, None

    def __init__(self, tracker):
        self.tracker = tracker
        self.lock = threading.Lock()
        self.min_events_shown = self.min_events_shown
        self.reset_size()
        self.updating = False

        # faster startup
        if not TrackerWidget.loading_gif:
            TrackerWidget.loading_gif = resize_and_colorize_gif(sg.DEFAULT_BASE64_LOADING_GIF, 20, Refresh_color)

            height = self.button_size[1] * self.img_per
            TrackerWidget.refresh_img = resize_and_colorize_img('icon/refresh.png', height, Refresh_color, self.button_size)
            TrackerWidget.edit_img = resize_and_colorize_img('icon/edit.png', height, Edit_color, self.button_size)
            TrackerWidget.archive_img = resize_and_colorize_img('icon/archive.png', height, Archives_color, self.button_size)

    def reset_size(self):
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self, first = False):
        b_p = 4
        b_colors = dict(button_color = self.bg_color_h, mouseover_color = 'grey95')
        self.buttons = [ MyButton('', image_data = self.edit_img, p = (0, b_p), **b_colors, k = self.edit),
                         MyButton('', image_data = self.refresh_img, p = 0, **b_colors, k = self.update),
                         MyButton('', image_data = self.archive_img, p = (0, b_p), **b_colors, k = self.archive_or_delete) ]

        self.courier_fsize = 8
        self.events_f = (FixFont, 8)
        self.events_fb = (FixFontBold, 8)
        
        self.days_size = 50
        self.days_font = (FixFontBold, 15) 
        self.days_widget = MyGraph(canvas_size=(self.days_size, self.days_size), graph_bottom_left=(0, 0), graph_top_right=(self.days_size, self.days_size), p = (10, 0), background_color=self.bg_color_h)
        self.desc_widget = sg.T('', p = 0, font = (VarFont, 40), text_color = 'grey40', background_color = self.bg_color_h, expand_x = True, justification = 'l') 

        self.id_widget = sg.MLine('', p = 0, font = (FixFont, 10), disabled = True, border_width = 0, no_scrollbar = True, background_color = self.bg_color_h, expand_x = True, justification = 'r')
        self.couriers_widget = sg.MLine('', p = 0, font = (FixFont, self.courier_fsize), disabled = True, border_width = 0, no_scrollbar = True, background_color = self.bg_color_h, expand_x = True, justification = 'r')
        id_couriers_widget = sg.Col([[ self.id_widget ], [ self.couriers_widget ]], p = ((5, 0), (b_p, b_p)), background_color = self.bg_color_h, expand_x = True, vertical_alignment = 'top')
        buttons = sg.Col([[button] for button in self.buttons], p = (10, 0), background_color = self.bg_color_h, expand_x = False)

        self.loading_widget = sg.Image(data = self.loading_gif, p = 3, background_color = self.bg_color, k = lambda w : self.toggle_expand(w))
        loading_widget_pin = sg.pin(self.loading_widget)
        loading_widget_pin.BackgroundColor = self.bg_color

        self.ago_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = False, background_color = self.bg_color, text_color = 'grey50', k = lambda w : self.toggle_expand(w))
        self.status_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = True, background_color = self.bg_color, k = lambda w : self.toggle_expand(w))
        self.expand_button = MyButton('▼', p = (b_p, 0), font = (VarFont, 10), button_color = ('grey70', self.bg_color), mouseover_color = 'grey95', k = lambda w : self.toggle_expand(w))

        self.events_widget = sg.MLine('', p = ((5, 5), (0, 5)), font = self.events_f, visible = False, disabled = True, border_width = 0, background_color = self.bg_color, no_scrollbar = True, s = (None, 1), expand_x = True, k = self.toggle_expand)
        events_widget_pin = sg.pin(sg.Col([ [self.events_widget] ], p = (10, 0), background_color = self.bg_color, expand_x = True), expand_x = True)
        events_widget_pin.BackgroundColor = self.bg_color

        layout = [ [ sg.Col([[ self.days_widget, self.desc_widget, id_couriers_widget, buttons ]], p = 0, background_color = self.bg_color_h, expand_x = True) ],
                   [ sg.Col([[ loading_widget_pin, self.ago_widget, self.status_widget, self.expand_button ]], p = (10, 0), background_color = self.bg_color, expand_x = True) ],
                   [ events_widget_pin ] ]

        self.layout = sg.Col(layout, expand_x = True, p = 0, visible = self.tracker.state == 'ok', background_color = self.bg_color)
        self.pin = sg.pin(self.layout, expand_x = True) # collapse when hidden
        self.pin.BackgroundColor = self.bg_color_h if first else self.bg_color
        return [ self.pin ] 

    def finalize(self, window):
        for button in  self.buttons:
            button.set_size(self.button_size) 
            button.finalize()

        self.expand_button.finalize()

        for widget in (self.id_widget, self.events_widget, self.couriers_widget):
            widget.grab_anywhere_include()
            # prevent selection https://stackoverflow.com/questions/54792599/how-can-i-make-a-tkinter-text-widget-unselectable?noredirect=1&lq=1
            widget.Widget.bindtags((str(widget.Widget), str(window.TKroot), 'all'))
        
        # toggle expand
        for widget in (self.events_widget, self.status_widget, self.ago_widget, self.loading_widget):
            widget.bind('<Button-1>', '')
        
        self.show_current_content(window)

    def toggle_expand(self, window):
        self.expand_events = not self.expand_events
        self.update_expand_button()

        window.trigger_event('-UPDATE WIDGETS SIZE-', '')

    def update_expand_button(self):
        is_visible = self.is_events_visible() and self.height_events >  self.min_events_shown
        self.expand_button.update(('▲' if self.expand_events else '▼') if is_visible else '', disabled = not is_visible)

    def is_events_visible(self):
        return self.height_events > 0

    def get_pixel_size(self):
        return self.pin.get_size()

    def update_size(self, w):
        nb_events_shown =  float('inf') if self.expand_events else self.min_events_shown
        h = min(nb_events_shown, self.height_events)
        self.events_widget.set_size((w, h))

        self.update_couriers_id_size()

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
        if self.tracker.state == 'ok' and self.lock.acquire(blocking = False):

            self.disable_buttons(True)
            self.updating = True
            window.trigger_event('-UPDATING CHANGED-', '')
            
            self.tracker.prepare_update()
            self.show_current_courier_widget()
            self.loading_widget.update(visible = True)

            threading.Thread(target = self.update_thread, args = (window,), daemon = True).start()

    def update_thread(self, window): 
        try:
            content = None
            for content in self.tracker.update(): # generator multithreaded
                window.trigger_event(lambda window: self.show(content, window), '')

            # nothing updated
            if content is None:
                window.trigger_event(lambda window: self.show({}, window), '')

        except:
            _log (traceback.format_exc(), error = True)

        finally:
            self.lock.release()
            window.trigger_event(lambda window: self.update_done(window), '')

    def update_done(self, window):
        self.disable_buttons(False)
        self.loading_widget.update(visible = False)
        self.updating = False
        window.trigger_event('-UPDATING CHANGED-', '')

    def animate(self, animation_step):
        if self.loading_widget.visible:
            self.loading_widget.update_animation(self.loading_gif, time_between_frames = animation_step)

    def show(self, content, window):
        tracker = self.tracker
        if tracker.state == 'ok':
            
            delivered = '✔' if content.get('status', {}).get('delivered') else ''
            self.desc_widget.update(f'{tracker.description.strip()}{delivered}') 
            self.events_widget.update('')

            if content.get('ok'):
                events = content['events']
                width_events = 0
                self.height_events = len(events)

                if events:
                    courier_w = max(len(evt['courier']) for evt in events)
                    previous_day = None
                    previous_hour = None

                    prt = self.events_widget.print
                    for event in events:
                        event_courier = f"{event['courier'].rjust(courier_w)}. "
                        
                        day, hour = f"{event['date']:%a %d %b %y, %Hh%M}".replace('.', '').split(',')
                        day = three_char_month(day, 2)

                        hour = hour.strip()
                        same_day, previous_day = day == previous_day, day
                        same_hour, previous_hour = hour == previous_hour, hour
                        if same_day:
                            day = ' ' * len(previous_day)
                            if same_hour:
                                hour = ' ' * len(previous_hour)

                        event_date = f"{day}{' ' if same_day else ','} {hour}{' ' if same_hour and same_day else ','} "
                        event_status = f"{event['status'].capitalize()}, " if event['status'] else ''
                        event_label = f"{event['label']}."
                        if event_label:
                            event_label = event_label.capitalize() if not event_status else (event_label[0].lower() + event_label[1:])

                        # create a fake status if missing with firstwords of label
                        if event_label and not event_status:
                            wrap = textwrap.wrap(event_label, 25)
                            event_status, event_label = (wrap[0]+ ' ', ' '.join(wrap[1:]))  if len(wrap) > 1 else (event_label, '')

                        event_warn = event.get('warn')
                        event_delivered = event.get('delivered')
                        event_color ='red' if event_warn else ('green' if event_delivered else None)
                        event_new, f = ('(new) ', self.events_fb) if event.get('new') else ('', self.events_f)

                        width = sum( len(txt) for txt in (event_courier, event_date, event_new) )
                        event_labels = textwrap.wrap(event_label, self.max_event_width - len(event_status), subsequent_indent = ' '* width) or ['']

                        prt(event_date, font = f, autoscroll = False, t = 'grey', end = '')
                        prt(event_courier, font = f, autoscroll = False, t = 'light slate blue', end = '')
                        prt(event_new, font = f, autoscroll = False, t = 'black', end = '')
                        prt(event_status, font = self.events_fb if event_warn or event_delivered else f, autoscroll = False, t = event_color or 'black', end = '')
                        for event_label in event_labels:
                            prt(event_label, font = f, autoscroll = False, t = event_color or 'grey50')
                        
                        width += sum( len(txt) for txt in (event_status, event_labels[0]) )
                        width_events = max(width, width_events)

                self.width_events = width_events
                
                status_warn = content['status'].get('warn', False)
                status_delivered = content['status'].get('delivered', False)
                status_label = content['status']['label'].replace('.', '')
                color = 'red' if status_warn else ('green' if status_delivered else None)
                self.status_widget.update(status_label, text_color = color)
                self.desc_widget.update(text_color = color)

            else:
                self.width_events = 0
                self.height_events = 0
                self.status_widget.update('Status inconnu', text_color = 'red')
                self.desc_widget.update(text_color = 'grey70')

            self.show_id(content)

            couriers_update = content.get('courier_update')
            self.show_couriers(couriers_update)

            elapsed = content.get('elapsed')
            if elapsed:
                round_elapsed_days = elapsed.days + (1 if elapsed.seconds >= 43200 else 0)
                elapsed_color = self.days_colors[bisect(self.days_intervals, round_elapsed_days)]
                elapsed_txt = f"{round_elapsed_days}{'j' if round_elapsed_days <= 100 else ''}"
            else:
                elapsed_color = 'grey70'
                elapsed_txt = '?'

            self.days_widget.erase()
            self.days_widget.draw_rounded_box(self.days_size*.5, self.days_size*.5, self.days_size, self.days_size*.9, self.days_size*.15, 'grey90')
            self.days_widget.draw_text(elapsed_txt, (self.days_size*.5, self.days_size*.5), color = elapsed_color, font = self.days_font, text_location = 'center')

            status_date = content.get('status', {}).get('date')
            status_ago = f"{timeago.format(status_date, get_local_now(), 'fr')}, " if status_date else ''
            self.ago_widget.update(status_ago)

            self.events_widget.update(visible = self.is_events_visible())
            self.update_expand_button()

            window.trigger_event('-UPDATE WIDGETS SIZE-', '')

    def show_id(self, content):
        self.id_widget.update('') 

        product = content.get('product', 'Envoi')
        fromto = content.get('fromto')
        fromto = f' {fromto.lower()} ' if fromto else ' '

        prt = self.id_widget.print
        prt(f'{product}', autoscroll = False, t = 'grey50', end = '')
        prt(fromto, autoscroll = False, t = 'grey70', end = '')
        prt(self.tracker.get_pretty_idship(), autoscroll = False, t = 'blue', end = '')

    def show_couriers(self, couriers_update):
        if couriers_update:
            couriers_update_names = list(couriers_update.keys())
            couriers_update_names.sort()

            self.couriers_widget.update('') 
            
            maj = 'Mise à jour... '
            txts = []
            for name in couriers_update_names:
                date, error, updating = couriers_update[name]
                ago_color, ago = ('green', f"{timeago.format(date, get_local_now(), 'fr').replace('il y a', '').strip()}") if date else ('red' , 'jamais')
                name_color, name_font = ('red', FixFontBold) if error else ('green', FixFont)
                txts.append((updating, ago, ago_color, name, name_color, name_font))

            width_name = max(len(txt[3]) for txt in txts)
            width_ago = max(len(txt[1]) for txt in txts)

            prt = self.couriers_widget.print
            for updating, ago, ago_color, name, name_color, name_font in txts:
                maj_txt = maj if updating else ' ' * len(maj)
                prt(maj_txt, autoscroll = False, font = (FixFontBold, self.courier_fsize), t = Refresh_color, end = '')
                prt(name.rjust(width_name), autoscroll = False, t = name_color, font = (name_font, self.courier_fsize), end = '')
                prt(', MàJ ', autoscroll = False, t = 'grey60', end = '')
                prt(ago.ljust(width_ago), autoscroll = False, t = ago_color)
        
        else:
            self.couriers_widget.update('Pas de trackers', text_color = 'red')

    def disable_buttons(self, disabled):
        for button in  self.buttons:
            button.update(disabled = disabled)

    def edit(self, window):
        self.disable_buttons(True)

        popup_edit = popup.edit('Édition', self.tracker.idship, self.tracker.description, self.tracker.used_couriers, self.tracker.available_couriers, window)
        idship, description, used_couriers = popup_edit.loop()
        
        if idship is not None:
            self.tracker.set_id(idship, description, used_couriers)
            self.reset_size()
            self.update(window)

        self.disable_buttons(False)

    def set_state(self, state, window, ask, visible):
        tracker = self.tracker

        if ask: 
            popup_warning = popup.warning(ask.capitalize(), f'{tracker.description} - {tracker.get_pretty_idship()}', window)
            doit = popup_warning.loop()
        
        else:
            doit = True

        if doit:
            if self.lock.acquire(blocking=False): # needed ?
                tracker.state = state

                self.layout.update(visible = visible)
                self.reset_size()

                window.trigger_event('-UPDATE WIDGETS SIZE-', '')
                self.lock.release()

    def archive_or_delete(self, window):
        self.disable_buttons(True)

        choices = {'Archiver': self.archive, 'Supprimer': self.delete}
        choices_colors = {'Archiver':'green', 'Supprimer':'red', False:'grey75'}
        tracker = self.tracker
        
        popup_one_choice = popup.one_choice(choices.keys(), choices_colors, f'{tracker.description} - {tracker.get_pretty_idship()}', window)
        choice = popup_one_choice.loop()
        
        if choice:
            choices[choice](window)

        self.disable_buttons(False)

    def delete(self, window):
        self.set_state('deleted', window, ask = 'Supprimer', visible = False)

    def archive(self, window):
        self.set_state('archived', window, ask = False, visible = False)
        window.trigger_event('-ARCHIVE UPDATED-', '')

    def unarchive(self, window):
        self.set_state('ok', window, ask = False, visible = True)
        window.trigger_event('-ARCHIVE UPDATED-', '')
        self.update(window)

# -------------------
class TrackerWidgets:
    def __init__(self, window, trackers,splash):
        self.widgets = []
        self.trackers = trackers
        self.widgets_frame = window['TRACKS']

        n_trackers = len(trackers.trackers)
        for i, tracker in enumerate(trackers.trackers):
            splash.update(f'création suivi {i + 1}/{n_trackers}')
            self.create_widget(window, tracker, i==0)

        window.trigger_event('-ARCHIVE UPDATED-', '')
        self.update_size(window)
        self.recenter(window, True)

    def create_widget(self, window, tracker, first = False):
        widget = TrackerWidget(tracker)

        window.extend_layout(self.widgets_frame, [widget.create_layout(first)])
        self.widgets.append(widget)

        widget.finalize(window)
        widget.update(window)

    def new(self, window):
        popup_edit = popup.edit('Nouveau', '', 'Nouveau', [], self.trackers.couriers, window)
        tracker_params = popup_edit.loop()
        
        tracker = self.trackers.new(*tracker_params)
        if tracker:
            self.create_widget(window, tracker)

    def get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def show_archives(self, window):
        archived = self.get_widgets_with_state('archived')
        archived.sort(key = lambda w : w.tracker.get_last_event(), reverse = True)

        w_desc = max(len(widget.tracker.description) for widget in archived)
        choices = []
        for widget in archived:
            tracker = widget.tracker
            color = 'green' if tracker.get_delivered() else 'red'
            txt = f'{tracker.get_pretty_last_event()}, {tracker.description.ljust(w_desc)} - {tracker.get_pretty_idship()}'
            choices.append((txt, color))

        popup_choices = popup.choices(choices, 'Désarchiver', window)
        chosen = popup_choices.loop()

        for i in chosen:
            widget = archived[i]
            widget.unarchive(window)

    def archives_updated(self, archives_button):
        n_archives = self.trackers.count_archived()
        txt, disabled = (f'Archives ({n_archives})', False) if n_archives > 0 else ('Archives', True)
        archives_button.update(txt, disabled = disabled)

    def count_not_updating(self):
        return [widget.updating for widget in self.get_widgets_with_state('ok')].count(False)

    def update(self, window):
        for widget in self.get_widgets_with_state('ok'):
            widget.update(window)

    def updating_changed(self, refresh_button):
        n_updating = self.count_not_updating()
        refresh_button.update(disabled = n_updating == 0)

    def animate(self, animation_step):
        for widget in self.get_widgets_with_state('ok'):
            widget.animate(animation_step)
    
    def update_size(self, window):
        ok = self.get_widgets_with_state('ok')

        # resize all widgets with the max width & and change pin color
        max_width = max(widget.width_events for widget in ok) if ok else 0
        for widget in ok:
            widget.update_size(max_width)

        window.refresh()
        self.widgets_frame.contents_changed()

        # wanted size
        if ok:
            w = max(widget.get_pixel_size()[0] for widget in ok) 
            h = sum(widget.get_pixel_size()[1] for widget in self.widgets) + window['MENU'].get_size()[1] + 3
        else:
            w, h = 400, 200

        # need scrollbar ?
        screen_w, screen_h = window.get_screen_size()
        h_screen_margin = 0 #400

        if h > screen_h - h_screen_margin:
            self.widgets_frame.Widget.vscrollbar.pack(side=sg.tk.RIGHT, fill='y')
            w += 15 # size of scrollbar

        else:
            self.widgets_frame.Widget.vscrollbar.pack_forget()

        # min size
        window.set_min_size((min(w, screen_w), min(h, screen_h - h_screen_margin)))

        # shrink window if needed
        window_w, window_h = window.size
        window.size = min(w, window_w), min(h, window_h)

        self.recenter(window)

    def recenter(self, window, force = False):
        W, H = window.get_screen_size()
        w, h = window.size
        x, y = window.current_location()
        if force:
            x = max(0, int((W-w)*.5))
            y = max(0, int((H-h)*.5))
        else:
            y = max(0, int((H-h)*.5)) if y+h > H else y
        window.move(x, y)
        window.refresh()

# ---------------------------------------------
class Splash:
    def __init__(self):
        self.log = sg.T('', font = (VarFont, 10))
        layout = [[sg.Image(filename = 'icon/mail.png')], [self.log]]
        args, kwargs = Get_window_args(layout, grab_anywhere = False)
        self.window = sg.Window(*args, **kwargs)

    def update(self, txt):
        self.log.update(f'{txt.capitalize()} ...')
        self.window.refresh()

    def close(self):
        self.window.close()

# ---------------------
class Fake_grey_window:
    def __init__(self, window):
        self.window = window

        is_debugger = Is_debugger()
        self.kwargs = dict(keep_on_top = not is_debugger, no_titlebar = not is_debugger, margins = (0, 0), debugger_enabled = False, background_color = 'black', alpha_channel =.5, finalize = True)
        self.bind_id = None
    
    def enable(self, enable):
        if enable:
            if self.bind_id is None and self.window.TKroot.attributes('-alpha') == 1.0: # test visibility
                self.already_bound = self.window.TKroot.bind('<Configure>') # bug with unbind that remove all
                self.bind_id = self.window.TKroot.bind('<Configure>', self.window_changed, add='+')
                self.fake = sg.Window('', [[]], size = self.window.size, location = self.window.current_location(), **self.kwargs)    
                self.fake.disable()
        else:
            if self.bind_id is not None:
                self.window.TKroot.unbind('<Configure>', self.bind_id) 
                if self.already_bound not in self.window.TKroot.bind('<Configure>'): # bug with unbind that remove all
                    self.window.TKroot.bind('<Configure>', self.already_bound)
                self.bind_id = None
                self.fake.close()
                del self.fake

    def window_changed(self, evt):
        w, h = self.window.size
        x, y = self.window.current_location()
        self.fake.TKroot.geometry(f'{w}x{h}+{x}+{y}')

# --------------------------------------------------
class Main_window(sg.Window):
    
    animation_step = 100

    def __init__(self):
        menu_color = 'grey75'
        b_pad, b_f_size = 10, 12
        im_height, im_margin = 20, 5
        b_kwargs = dict(im_height = im_height, im_margin = im_margin, font = (VarFontBold, b_f_size), mouseover_color = 'grey90')

        log_b = MyButtonImg('Log', p = b_pad, image_filename = 'icon/log.png', button_color = ('grey', menu_color), k = '-Log-', **b_kwargs)
        new_b = MyButtonImg('Nouveau', p = (0, b_pad), image_filename = 'icon/edit.png', button_color = (Edit_color, menu_color), k = '-New-', **b_kwargs)
        refresh_b = MyButtonImg('Rafraichir', p = b_pad, image_filename = 'icon/refresh.png', button_color = (Refresh_color, menu_color), k = '-Refresh-', **b_kwargs)
        archives_b = MyButtonImg('Archives', p = (0, b_pad), image_filename = 'icon/archive.png', button_color = (Archives_color, menu_color), disabled = True, k = '-Archives-', **b_kwargs)
        recenter_widget = sg.T('', background_color = menu_color, p = 0, expand_x = True, expand_y = True, k = '-RECENTER-')
        exit_b = MyButton(' X ', p = b_pad, font = (VarFontBold, b_f_size), button_color = menu_color, mouseover_color = 'red', focus = True, k = '-Exit-')

        layout = [[ sg.Col([[ log_b, new_b, refresh_b, archives_b, recenter_widget, exit_b ]], p = 0, background_color = menu_color, expand_x = True, k = 'MENU') ],
                  [ sg.Col([[]], p = 0, scrollable = True, vertical_scroll_only = True, expand_x = True, expand_y = True, background_color = menu_color, k = 'TRACKS') ]]

        args, kwargs = Get_window_args(layout, alpha_channel = 0, resizable = True)
        super().__init__(*args, **kwargs)

        MyButton.finalize_all(self)
        recenter_widget.bind('<Double-Button-1>', '')

        self.trackers = Trackers(TrackersFile, splash) 
        self.widgets = TrackerWidgets(self, self.trackers, splash) 

        self.greyed = [Fake_grey_window(self)]

        self.animation_step = self.animation_step
        self.TKroot.after(self.animation_step, self.animate)

        self.reappear()
    
    def add_log(self, log):
        self.log = log
        log.link_to(self)
        self.greyed.append(Fake_grey_window(log))
        self.TKroot.bind('<Configure>', lambda evt: log.stick_to_main())

    def close(self):
        self.do_greyed(False)
        super().close()

        try:
            self.trackers.save()
            self.trackers.clean_couriers()
        except:
            _log (traceback.format_exc(), error = True)

        self.log.close()
        self.trackers.close()

    def trigger_event(self, *evt):
        if self.TKroot:
            self.write_event_value(*evt)

    def animate(self):
        self.widgets.animate(self.animation_step)
        self.TKroot.after(self.animation_step, self.animate)

    def do_greyed(self, enable):
        for grey in self.greyed:
            grey.enable(enable)

    def loop(self):
        while True:
            if self.event_handler():
                break

    def event_handler(self):
        window, event, values = sg.read_all_windows()
        
        # if isinstance(event, str) and 'MouseWheel' not in event: 
        #     _log (f'{event = }' + (f', {value = }' if (value := values and values.get(event)) else ''))

        if callable(event):
            event(window) 

        elif isinstance(event, tuple) and callable(event[0]):
            event[0](window)      
        
        elif window == self:

            if event in (None, '-Exit-', 'Escape:27'):
                return True
            
            elif event in ('-Log-', 'l'):
                self.log.toggle()

            elif event == '-RECENTER-':
                self.widgets.recenter(window, force = True)

            elif event == '-UPDATING CHANGED-':
                self.widgets.updating_changed(window['-Refresh-'])

            elif event == '-ARCHIVE UPDATED-':
                self.widgets.archives_updated(window['-Archives-'])

            elif event == '-UPDATE WIDGETS SIZE-':
                self.widgets.update_size(window)

            elif event == '-New-':
                self.widgets.new(window)

            elif event == '-Refresh-':
                self.widgets.update(window)

            elif event == '-Archives-':
                self.widgets.show_archives(window)
        
        else:
            return window.event_handler(event)

# ------------------------
if __name__ == "__main__":

    # import sys
    from style import FixFont, FixFontBold, VarFont, VarFontBold, Get_window_args, Is_debugger

    sg.theme('GrayGrayGray')

    # create splash before importing to reduce startup time
    splash = Splash()
    splash.update('inititialisation')

    # import after splash has been created
    import traceback
    import threading
    import queue
    import os
    import copy
    import pickle as pickle
    import timeago
    from bisect import bisect
    import textwrap
    import json
    import locale
    locale.setlocale(locale.LC_ALL, 'fr_FR.utf8') # date in French

    from imgtool import resize_and_colorize_gif, resize_and_colorize_img
    from jsondate import json_decode_datetime, json_encode_datetime
    from couriers import Couriers, get_local_now
    from myWidget import MyButton, MyButtonImg, MyGraph
    from mylog import mylog, _log
    import popup

    # create main_window
    main_window = Main_window()
    main_window.add_log(mylog)
    splash.close()

    main_window.loop()
    main_window.close()
