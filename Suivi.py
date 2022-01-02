TrackersFile = 'Trackers.trck'

# --------------------------------------------------------------------------
import traceback
import threading
import queue
import os
import copy
import PySimpleGUI as sg
import pickle as pickle
import timeago
from datetime import datetime
from bisect import bisect
import textwrap
import locale
locale.setlocale(locale.LC_ALL, 'fr_FR.utf8') # date in French

from mylog import mylog, _log, trigger_event
from mybutton import MyButton
from couriers import Couriers, get_local_now
import popup

#------------------------------------------------------------------------------
class MyGraph(sg.Graph):
    def draw_rounded_box(self, x, y, w, h, r, color):
        w2, h2, r2 = w * .5, h * .5, r * 2
        # cross
        self.draw_rectangle((x-w2, y+h2-r), (x+w2, y-h2+r), fill_color = color, line_color = color)
        self.draw_rectangle((x-w2+r, y+h2), (x+w2-r, y-h2), fill_color = color, line_color = color)
        # corners
        self.draw_arc((x-w2, y+h2-r2),    (x-w2+r2, y+h2),    90, 90,  fill_color = color, arc_color = color) 
        self.draw_arc((x+w2-r2, y+h2-r2), (x+w2, y+h2),       90, 0,   fill_color = color, arc_color = color)
        self.draw_arc((x-w2, y-h2),       (x-w2+r2, y-h2+r2), 90, 180, fill_color = color, arc_color = color) 
        self.draw_arc((x+w2-r2, y-h2),    (x+w2, y-h2+r2),    90, 270, fill_color = color, arc_color = color)
        # bounding box
        # self.draw_rectangle((x-w2, y+h2), (x+w2, y-h2), fill_color = None, line_color = 'black')

def three_char_month(date_txt, i):
    txts = date_txt.split()
    month = txts[i]
    txts[i] =  month[:3] if 'ju' not in month else month[:2] + month[3:]
    return ' '.join(txts)

#-------------------------------------------------------------------------------------------
class SavedTracker:
    def __init__(self, tracker):
        with tracker.critical:
            # tracker attribute to save
            for attr in ('idship', 'description', 'used_couriers', 'state', 'contents'):
                self.__dict__[attr] = tracker.__dict__[attr]

#-----------
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
            # self.update_thread(courier_name, content_queue))

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
            
        consolidated['courier_update'] = self.get_courrier_update()
        
        return consolidated
    
    def get_courrier_update(self):
        with self.critical:
            couriers_update = {}
            for courier_name in self.used_couriers:
                content = self.contents.get(courier_name)
                ok_date = content.get('status',{}).get('ok_date') if content else None
                error = self.couriers_error.get(courier_name, True)
                updating = self.couriers_updating.get(courier_name, False)
                couriers_update[courier_name] = (ok_date, error, updating)

            return couriers_update

    def get_last_event(self):
        content = self.get_consolidated_content() or {}
        return content.get('status', {}).get('date', get_local_now())

    def get_pretty_last_event(self):
        last_event = self.get_last_event()
        if last_event:
            date = f'{last_event:%a %d %b %y}'.replace('.', '')
            return three_char_month(date, 2)
        else:
            return ''

    def get_delivered(self):
        content = self.get_consolidated_content() 
        return content and content.get('status', {}).get('delivered')

#------------
class Trackers:
    def __init__(self, filename, trackers = None):
        self.filename = filename
        self.couriers = Couriers()

        if trackers is None:
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    trackers = pickle.load(f)
                    _log(f'trackers loaded from {filename}')

        if trackers:
            trackers = [Tracker(tracker.idship, tracker.description, tracker.used_couriers, self.couriers, tracker.state, tracker.contents) for tracker in trackers]

        self.trackers = trackers or []
        self.trackers.sort(key = lambda t : t.get_last_event(), reverse = True)

    def save(self):
        self.trackers = self.get_not_deleted()

        saved_trackers = [SavedTracker(tracker) for tracker in self.trackers]

        with open(self.filename, 'wb') as f:
            pickle.dump(saved_trackers, f)
            _log(f'trackers saved from {self.filename}')

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

#------------------------------------------------------------------------------
class TrackerWidget:

    min_events_shown = 1
    days_intervals = [10, 20, 30]
    days_colors = ['green', 'dark orange', 'red', 'black']

    layout_pad = 10 # pixels
    max_event_width = 110 # chars

    def __init__(self, tracker):
        self.tracker = tracker
        self.lock = threading.Lock()
        self.min_events_shown = self.min_events_shown
        self.reset_size()

    def reset_size(self):
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self):
        bg_color = 'grey90'
        bg_color_h = 'grey85'

        b_p = 5
        self.buttons = [ MyButton('', image_filename = 'icon/refresh.png', p = ((b_p*3, b_p), (b_p, b_p)), button_color = bg_color, mouseover_color = bg_color_h, k = self.update),
                         MyButton('', image_filename = 'icon/edit.png', p = b_p, button_color = bg_color, mouseover_color = bg_color_h, k = self.edit),
                         MyButton('', image_filename = 'icon/archive.png', p = b_p, button_color = bg_color, mouseover_color = bg_color_h, k = self.archive_or_delete) ]

        self.courier_fsize = 7
        self.events_f = (FixFont, 8)
        self.events_fb = (FixFontBold, 8)
        # multiline needs to be visible = False @ the beginning to prevents mousewheel to be catched and hinder whole window scrolling
        self.desc_widget = sg.T('', p = 0, font = (VarFont, 40), text_color = 'grey40', background_color = bg_color_h, expand_x = True, justification = 'l') 
        self.days_size = 60
        self.days_font = (FixFont, 20) 
        self.days_widget = MyGraph(canvas_size=(self.days_size, self.days_size), graph_bottom_left=(0, 0), graph_top_right=(self.days_size, self.days_size), p = 0, background_color=bg_color_h)

        self.id_widget = sg.MLine('', p = 0, font = (FixFont, 9), disabled = True, border_width = 0, no_scrollbar = True, background_color = bg_color_h, expand_x = True, justification = 'r', visible = False)
        self.couriers_widget = sg.MLine('', p = 0, font = (FixFont, self.courier_fsize), disabled = True, border_width = 0, no_scrollbar = True, background_color = bg_color_h, expand_x = True, justification = 'r', visible = False)
        self.status_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = True, background_color = bg_color, k = lambda w : self.toggle_expand(w))
        self.ago_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = False, background_color = bg_color, text_color = 'grey50', k = lambda w : self.toggle_expand(w))
        self.events_widget = sg.MLine('', p = ((5, 5), (0, 5)), font = self.events_f, visible = False, disabled = True, border_width = 0, background_color = bg_color, no_scrollbar = True, s = (None, 1), expand_x = True, k = self.toggle_expand)
        self.expand_button = MyButton('▼', p = 0, font = (VarFont, 15), button_color = ('grey70', bg_color), mouseover_color = bg_color_h, k = lambda w : self.toggle_expand(w))

        id_couriers_widget = sg.Col([[self.id_widget], [self.couriers_widget]], p = 0, background_color = bg_color_h, expand_x = False)
        layout = [[ sg.Col([ [sg.Col([ [ self.days_widget, self.desc_widget, id_couriers_widget ] + self.buttons ], p = 5, background_color = bg_color_h, expand_x = True) ]], p = 0, expand_x = True, background_color = bg_color_h) ],
                 [  sg.Col([ [self.ago_widget, self.status_widget, self.expand_button] ], p = ((3, 0), (5, 0)), background_color = bg_color, expand_x = True) ],
                 [  sg.pin(sg.Col([ [self.events_widget] ], p = 0, background_color = bg_color, expand_x = True), expand_x = False) ]]

        self.layout = sg.Col(layout, expand_x = True, p = ((self.layout_pad, self.layout_pad), (self.layout_pad, 0)), visible = self.tracker.state == 'ok', background_color = bg_color)
        return [ sg.pin(self.layout, expand_x = True) ] # collapse when hidden
    
    def finalize(self, window):
        button_size = (25, 40)
        for button in  self.buttons:
            button.set_size(button_size) 
            button.finalize()

        self.expand_button.finalize()

        for widget in (self.id_widget, self.events_widget, self.couriers_widget):
            widget.grab_anywhere_include()
            # prevent selection https://stackoverflow.com/questions/54792599/how-can-i-make-a-tkinter-text-widget-unselectable?noredirect=1&lq=1
            widget.Widget.bindtags((str(widget.Widget), str(window.TKroot), 'all'))
        
        # toggle expand
        for widget in (self.events_widget, self.status_widget, self.ago_widget):
            widget.bind('<Button-1>', '')
        
        self.show_current_content(window)

    def toggle_expand(self, window):
        self.expand_events = not self.expand_events
        self.update_expand_button()

        trigger_event(window, '-UPDATE WIDGETS SIZE-', '')

    def update_expand_button(self):
        is_visible = self.is_events_visible() and self.height_events >  self.min_events_shown
        self.expand_button.update(('▲' if self.expand_events else '▼') if is_visible else '', disabled = not is_visible)

    def is_events_visible(self):
        return self.height_events > 0

    def get_pixel_size(self):
        w, h = self.layout.get_size()
        return w, h

    def update_size(self, w):
        nb_events_shown =  float('inf') if self.expand_events else self.min_events_shown
        h = min(nb_events_shown, self.height_events)
        self.events_widget.set_size((w, h))

        self.update_couriers_id_size()

    def update_couriers_id_size(self):
        txts = [t for t in self.couriers_widget.get().split('\n')]
        txt = self.id_widget.get()
        w = max(len(txt), max(len(t) + 1 for t in txts))

        self.couriers_widget.set_size((w, len(txts)))
        self.id_widget.set_size((w, 1))

    def show_current_content(self, window):
        self.show(self.tracker.get_consolidated_content(), window)

    def show_current_courier_widget(self):
        couriers_update = self.tracker.get_courrier_update()
        self.show_couriers(couriers_update)
        self.update_couriers_id_size()

    def update(self, window):
        if self.tracker.state == 'ok' and self.lock.acquire(blocking = False):

            self.disable_buttons(True)
            
            self.tracker.prepare_update()
            self.show_current_courier_widget()

            threading.Thread(target = self.update_thread, args = (window,), daemon = True).start()
            # self.update_thread(window) 

    def update_thread(self, window): 
        try:
            content = None
            for content in self.tracker.update(): # generator multithreaded
                trigger_event(window, lambda window: self.show(content, window), '')

            # nothing updated
            if content is None:
                trigger_event(window, lambda window: self.show(None, window), '')

        except:
            _log (traceback.format_exc(), error = True)

        finally:
            self.lock.release()
            trigger_event(window, lambda window: self.update_done(), '')

    def update_done(self):
        self.disable_buttons(False)

    def show(self, content, window):
        if self.tracker.state == 'ok':
            
            delivered = '✔' if content and content.get('status', {}).get('delivered') else ''
            self.desc_widget.update(f'{self.tracker.description.strip()}{delivered}') 
            self.events_widget.update('')

            if content and content.get('ok'):
                events = content['events']
                width_events = 0
                self.height_events = len(events)

                if events:
                    courier_w = max(len(evt['courier']) for evt in events)
                    previous_day = None
                    previous_hour = None

                    for i, event in enumerate(events):
                        event_courier = f"{event['courier'].ljust(courier_w)}. "
                        
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

                        self.events_widget.print(event_date, font = f, autoscroll = False, t = 'grey', end = '')
                        self.events_widget.print(event_courier, font = f, autoscroll = False, t = 'light slate blue', end = '')
                        self.events_widget.print(event_new, font = f, autoscroll = False, t = 'black', end = '')
                        self.events_widget.print(event_status, font = self.events_fb if event_warn or event_delivered else f, autoscroll = False, t = event_color or 'black', end = '')
                        for event_label in event_labels:
                            self.events_widget.print(event_label, font = f, autoscroll = False, t = event_color or 'grey50')
                        
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

            self.show_id(content)

            couriers_update = (content or {}).get('courier_update')
            self.show_couriers(couriers_update)

            elapsed = content.get('elapsed') if content else None
            if elapsed:
                round_elapsed_days = elapsed.days + (1 if elapsed.seconds >= 43200 else 0)
                elapsed_color = self.days_colors[bisect(self.days_intervals, round_elapsed_days)]
                elapsed_txt = f"{round_elapsed_days}{'j' if round_elapsed_days <= 100 else ''}"
            else:
                elapsed_color = 'grey70'
                elapsed_txt = '?'

            self.days_widget.erase()
            self.days_widget.draw_rounded_box(self.days_size*.47, self.days_size*.47, self.days_size*.9, self.days_size*.7, self.days_size*.15, 'grey92')
            self.days_widget.draw_text(elapsed_txt, (self.days_size*.5, self.days_size*.5), color = elapsed_color, font = self.days_font, text_location = 'center')

            status_date = content and content.get('status', {}).get('date')
            status_ago = f"{timeago.format(status_date, get_local_now(), 'fr')}, " if status_date else ''
            self.ago_widget.update(status_ago)

            self.events_widget.update(visible = self.is_events_visible())
            self.update_expand_button()
            
            # invsible @ beginning to prevent mousewheel event that prevents whole window scroll
            self.id_widget.update(visible = True)
            self.couriers_widget.update(visible = True)
            self.id_widget.expand(True)
            self.couriers_widget.expand(True)
            
            # remove selection
            self.couriers_widget.Widget.tag_remove("sel", "1.0", "end")
            self.id_widget.Widget.tag_remove("sel", "1.0", "end")

            trigger_event(window, '-UPDATE WIDGETS SIZE-', '')

    def show_id(self, content):
        self.id_widget.update('') 

        # fromto = content and content.get('fromto')
        # fromto = f'{fromto}  ' if fromto else ''
        # self.id_widget.print(fromto, autoscroll = False, t = 'grey71', end = '')

        spaces = ' ' * 2
        product = (content and content.get('product')) or 'Envoi'
        self.id_widget.print(f'{spaces}{product}', autoscroll = False, t = 'grey50', end = '')

        idship = self.tracker.idship if self.tracker.idship else 'Pas de N°'
        self.id_widget.print(f' {idship}', autoscroll = False, t = 'blue', end = '')

    def show_couriers(self, couriers_update):
        if couriers_update:
            couriers_update_names = list(couriers_update.keys())
            couriers_update_names.sort()

            self.couriers_widget.update('') 
            spaces = ' ' * 2
            
            w_name = max(len(name) for name in couriers_update_names)
            for i, name in enumerate(couriers_update_names):
                date, error, updating = couriers_update[name]
                end = i+1 == len(couriers_update)
                ago = f" {timeago.format(date, get_local_now(), 'fr').replace('il y a', '').strip()}" if date else ' jamais'
                error_chr, error_color, name_font = (' ❗', 'red', (FixFontBold, self.courier_fsize)) if error else ('✔', 'green', None)
                
                if updating:
                    self.couriers_widget.print(f'{spaces}Mise à jour...', autoscroll = False, font = (FixFontBold, self.courier_fsize), t = 'red', end = '')
                    spaces = ''

                self.couriers_widget.print(f'{spaces}{ago}', autoscroll = False, t = 'grey60', end = '')
                self.couriers_widget.print(' ⟳ ', autoscroll = False, t = 'grey55', font = (FixFont, self.courier_fsize), end = '')
                self.couriers_widget.print(f'{name.center(w_name)} ', autoscroll = False, t = error_color, font = name_font, end = '')
                self.couriers_widget.print(f'{error_chr}', autoscroll = False, t = error_color, font = (VarFont, self.courier_fsize), end = ''  if end else '\n')
        
        else:
            self.couriers_widget.update('Pas de trackers', text_color = 'red')

    def disable_buttons(self, disabled):
        for button in  self.buttons:
            button.update(disabled = disabled)

    def edit(self, window):
        self.disable_buttons(True)

        idship, description, used_couriers = popup.edit('Édition', self.tracker.idship, self.tracker.description, self.tracker.used_couriers, self.tracker.available_couriers, not is_debugger)
        if idship is not None:
            self.tracker.set_id(idship, description, used_couriers)
            self.reset_size()
            self.update(window)

        self.disable_buttons(False)

    def set_state(self, state, action_name, window, ask, visible):
        if not ask or popup.warning(action_name.capitalize(), self.tracker.description, not is_debugger):
            if self.lock.acquire(blocking=False): # needed ?
                self.tracker.state = state

                self.layout.update(visible = visible)
                self.reset_size()

                trigger_event(window, '-UPDATE WIDGETS SIZE-', '')
                self.lock.release()

    def archive_or_delete(self, window):
        self.disable_buttons(True)

        choices = { 'Archiver': self.archive, 'Supprimer': self.delete }
        choice = popup.one_choice(choices.keys(), f'{self.tracker.description} {self.tracker.idship}', not is_debugger)
        if choice:
            choices[choice](window)

        self.disable_buttons(False)

    def delete(self, window):
        self.set_state('deleted', 'Supprimer', window, ask = True, visible = False)

    def archive(self, window):
        self.set_state('archived', 'Archiver', window, ask = False, visible = False)
        trigger_event(window, '-ARCHIVE UPDATED-', '')

    def unarchive(self, window):
        self.set_state('ok', 'Désarchiver', window, ask = False, visible = True)
        trigger_event(window, '-ARCHIVE UPDATED-', '')
        self.update(window)

# -----------------------------------
class TrackerWidgets:
    def __init__(self, window, trackers):
        self.widgets = []

        for tracker in trackers.trackers:
            self.create_widget(window, tracker)

        trigger_event(window, '-ARCHIVE UPDATED-', '')

    def create_widget(self, window, tracker):
        widget = TrackerWidget(tracker)

        window.extend_layout(window['TRACKS'], [widget.create_layout()])
        self.widgets.append(widget)

        widget.finalize(window)
        widget.update(window) # TDO do not update archived

    def get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def show_archives(self, window):
        no_idship = 'Pas de N°'

        def get_label(widget, w_idship):
            t = widget.tracker
            color = 'green' if t.get_delivered() else 'red'
            return (f'{t.get_pretty_last_event()} - {(t.idship.strip() or no_idship).ljust(w_idship)} - {t.description}', color)

        archived = self.get_widgets_with_state('archived')
        archived.sort(key = lambda w : w.tracker.get_last_event(), reverse = True)

        w_idship = max(len(widget.tracker.idship.strip() or no_idship) for widget in archived)
        choices = [get_label(widget, w_idship) for widget in archived]
        chosen = popup.choices(choices, 'Désarchiver', not is_debugger)

        for i in chosen:
            widget = archived[i]
            widget.unarchive(window)

    def update(self, window):
        for widget in self.get_widgets_with_state('ok'):
            widget.update(window)

    def update_size(self, window):
        ok = self.get_widgets_with_state('ok')

        # resize all widgets with the max width
        max_width = max(widget.width_events for widget in ok) if ok else 0
        for widget in ok:
            widget.update_size(max_width)

        window.refresh()
        window['TRACKS'].contents_changed()

        # wanted size
        if ok:
            widths, heights = zip(*[widget.get_pixel_size() for widget in ok])
            w = max(widths) + TrackerWidget.layout_pad * 2
            h = sum(heights) + window['MENU'].get_size()[1] - 2 + (len(heights) + 1) * TrackerWidget.layout_pad
            h += len(self.widgets) - len(ok) # sg.pin = 1 pixel
        else:
            w, h = 400, 200

        # need scrollbar ?
        screen_w, screen_h = window.get_screen_size()
        h_screen_margin = 0 #400

        if h > screen_h - h_screen_margin:
            window['TRACKS'].Widget.vscrollbar.pack(side=sg.tk.RIGHT, fill='y')
            w += 15

        else:
            window['TRACKS'].Widget.vscrollbar.pack_forget()

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

# ------------------------------------------
if __name__ == "__main__":

    import sys
    from fonts import FixFont, FixFontBold, VarFont, VarFontBold

    is_debugger = sys.gettrace()

    sg.theme('GrayGrayGray')

    splash = sg.Window('Suivi...', [[sg.T('Suivi...')]], font=(VarFont, 75), keep_on_top = not is_debugger, no_titlebar = not is_debugger, finalize=True)

    mylog.set_window(log_font = (FixFont, 7), button_font = (VarFont, 12), no_border = not is_debugger)

    trackers = Trackers(TrackersFile) 

    menu_color = MyButton.default_colors['enter']

    button_log = 'Log'
    button_pad = 10
    button_f_size = 12
    recenter_widget = sg.T('', background_color = menu_color, p = 0, expand_x = True, expand_y = True, k = '-RECENTER-')

    menu =  [   MyButton('Rafraichir', p = button_pad, font = (VarFont, button_f_size)), 
                MyButton('Nouveau', p = ((0, 0), (button_pad, button_pad)), font = (VarFont, button_f_size)), 
                MyButton('Archives', p = ((button_pad, 0), (button_pad, button_pad)), disabled = True, font = (VarFont, button_f_size)), 
                MyButton(button_log, p = button_pad, font = (VarFont, button_f_size)), 
                recenter_widget,
                MyButton(' X ', p = button_pad, font = (VarFontBold, button_f_size), button_color = ('red', None), focus = True,) ]

    layout = [ [ sg.Col([menu], p = 0, background_color = menu_color, expand_x = True, k = 'MENU') ],
               [ sg.Col([[]], p = 0, scrollable = True, vertical_scroll_only = True, expand_x = True, expand_y = True, k = 'TRACKS') ] ]

    frame =  [ [ sg.Frame('', layout, p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True) ] ]

    window = sg.Window('Suivi', frame, size = (600, 600), grab_anywhere = True, resizable = True, keep_on_top = not is_debugger, no_titlebar = not is_debugger, return_keyboard_events = True, margins = (0, 0), finalize = True)
    window.disappear()

    MyButton.finalize_all(window)
    recenter_widget.bind('<Double-Button-1>', '')

    widgets = TrackerWidgets(window, trackers) 
    splash.close()

    window_pos = window.current_location()

    window.reappear()

    while True:
        event_window, event, values = sg.read_all_windows(timeout=20)
        # if event_window == window: _log (f'{event = }, value = {values and values.get(event)}')

        if event == '__TIMEOUT__':
            pos = window.current_location()
            if pos != window_pos:
                mylog.move_left_to(window)
                window_pos = pos
                
        elif mylog.catch_event(event_window, event, values, button_log, window):
            pass
        
        elif event in (None, ' X ', 'Escape:27'):
            break

        elif MyButton.catch_mouseover_event(event_window, event):
            pass

        # clic event for multiline to expand collapse & content update (see update in TrackerWidgets)
        elif isinstance(event, tuple) and callable(event[0]):
            event[0](event_window)      

        # update, edit, delete, archive a tracker       
        elif callable(event):
            event(event_window) 

        elif event == '-RECENTER-':
            widgets.recenter(event_window, force = True)
            event_window.refresh()
            mylog.move_left_to(event_window)

        elif event == '-ARCHIVE UPDATED-':
            event_window['Archives'].update(disabled = trackers.count_archived() == 0)

        elif event == '-UPDATE WIDGETS SIZE-':
            widgets.update_size(event_window)
            mylog.move_left_to(event_window)

        elif event == 'Nouveau':
            tracker_params = popup.edit('Nouveau', '', 'Nouveau', [], trackers.couriers, not is_debugger)
            tracker = trackers.new(*tracker_params)
            if tracker:
                widgets.create_widget(event_window, tracker)

        elif event == 'Rafraichir':
            widgets.update(event_window)

        elif event == 'Archives':
            widgets.show_archives(event_window)

    window.close()

    try:
        trackers.save()
        trackers.clean_couriers()
    except:
        _log (traceback.format_exc(), error = True)

    mylog.close()
    trackers.close()
