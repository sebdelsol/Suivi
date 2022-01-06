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
import io
from PIL import Image  ,ImageOps
import base64
import textwrap

from mylog import mylog, _log
from mybutton import MyButton
from couriers import Couriers, get_local_now
import popup

import locale
locale.setlocale(locale.LC_ALL, 'fr_FR.utf8') # date in French

TrackersFile = 'Trackers.trck'

#-------------------------------------------------------
def resize_and_colorize_gif(image64, height, color):
    buffer = io.BytesIO(base64.b64decode(image64))
    im = Image.open(buffer)

    resize_to = (im.size[0] * height / im.size[1], height)
    frames = []

    try:
        while True:
            frame = ImageOps.colorize(ImageOps.grayscale(im), white = 'white', black = color)
            frame = frame.convert('RGBA')
            frame.thumbnail(resize_to)
            frames.append(frame)
            im.seek(im.tell() + 1)
    
    except EOFError:
        pass

    buffer = io.BytesIO()
    frames[0].save(buffer, optimize = False, save_all = True, append_images = frames[1:], loop = 0, format = 'GIF', transparency = 0)
    return base64.b64encode(buffer.getvalue())

def resize_and_colorize_img(image, height, color):
    im = Image.open(image)

    alpha = im.split()[3]
    im = ImageOps.colorize(ImageOps.grayscale(im), white = 'white', black = color) 
    im.putalpha(alpha)
    im.thumbnail((im.size[0] * height / im.size[1], height))

    buffer = io.BytesIO()
    im.save(buffer, format = 'PNG')
    return base64.b64encode(buffer.getvalue())

#-----------------------
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

#---------------------------------
def three_char_month(date_txt, i):
    txts = date_txt.split()
    month = txts[i]
    txts[i] =  month[:3] if 'ju' not in month else month[:2] + month[3:]
    return ' '.join(txts)

#----------------------------------
def trigger_event(window, *events):
    if window and window.TKroot:
        window.write_event_value(*events)

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
            return 'Pas de date'

    def get_pretty_idship(self):
        return self.idship.strip() or 'Pas de N°'

    def get_delivered(self):
        content = self.get_consolidated_content() 
        return content and content.get('status', {}).get('delivered')

#--------------
class Trackers:
    def __init__(self, filename, splash_update):
        self.filename = filename
        self.couriers = Couriers(splash_update)

        trackers = None
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

#-------------------
class TrackerWidget:
    min_events_shown = 1
    days_intervals = [10, 20, 30]
    days_colors = ['green', 'dark orange', 'red', 'black']

    layout_pad = 10 # pixels
    max_event_width = 110 # chars

    loading_gif = resize_and_colorize_gif(sg.DEFAULT_BASE64_LOADING_GIF, 25, 'red')
    
    button_size = (20, 20)
    img_per =.6
    refresh_img = resize_and_colorize_img('icon/refresh.png', button_size[1] * img_per, 'green')
    edit_img = resize_and_colorize_img('icon/edit.png', button_size[1] * img_per, 'blue')
    archive_img = resize_and_colorize_img('icon/archive.png', button_size[1] * img_per, 'red')

    def __init__(self, tracker):
        self.tracker = tracker
        self.lock = threading.Lock()
        self.min_events_shown = self.min_events_shown
        self.reset_size()
        self.updating = False

    def reset_size(self):
        self.width_events = 0
        self.height_events = 0
        self.expand_events = False

    def create_layout(self):
        bg_color = 'grey90'
        bg_color_h = 'grey85'
        bg_color_b = 'grey95'

        b_p = 4
        self.buttons = [ MyButton('', image_data = self.refresh_img, p = ((0, b_p), (b_p, b_p)), button_color = bg_color_b, mouseover_color = bg_color_h, k = self.update),
                         MyButton('', image_data = self.edit_img, p = ((0, b_p), (0, 0)), button_color = bg_color_b, mouseover_color = bg_color_h, k = self.edit),
                         MyButton('', image_data = self.archive_img, p = ((0, b_p), (b_p, b_p)), button_color = bg_color_b, mouseover_color = bg_color_h, k = self.archive_or_delete) ]

        self.courier_fsize = 7
        self.events_f = (FixFont, 8)
        self.events_fb = (FixFontBold, 8)
        # multiline needs to be visible = False @ the beginning to prevents mousewheel to be catched and hinder whole window scrolling
        self.desc_widget = sg.T('', p = 0, font = (VarFont, 40), text_color = 'grey40', background_color = bg_color_h, expand_x = True, justification = 'l') 
        self.days_size = 60
        self.days_font = (FixFont, 20) 
        self.days_widget = MyGraph(canvas_size=(self.days_size, self.days_size), graph_bottom_left=(0, 0), graph_top_right=(self.days_size, self.days_size), p = (5,0), background_color=bg_color_h)

        self.loading_widget = sg.Image(data = self.loading_gif, p = 3, background_color = bg_color, k = lambda w : self.toggle_expand(w))
        self.loading_widget_col = sg.Col([[self.loading_widget]], p = 0, visible = False, background_color = bg_color)

        self.id_widget = sg.MLine('', p = 0, font = (FixFont, 10), disabled = True, border_width = 0, no_scrollbar = True, background_color = bg_color_h, expand_x = True, justification = 'r')
        self.couriers_widget = sg.MLine('', p = 0, font = (FixFont, self.courier_fsize), disabled = True, border_width = 0, no_scrollbar = True, background_color = bg_color_h, expand_x = True, justification = 'r')
        self.status_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = True, background_color = bg_color, k = lambda w : self.toggle_expand(w))
        self.ago_widget = sg.T('', p = 0, font = (VarFont, 15), expand_x = False, background_color = bg_color, text_color = 'grey50', k = lambda w : self.toggle_expand(w))
        self.events_widget = sg.MLine('', p = ((5, 5), (0, 5)), font = self.events_f, visible = False, disabled = True, border_width = 0, background_color = bg_color, no_scrollbar = True, s = (None, 1), expand_x = True, k = self.toggle_expand)
        self.expand_button = MyButton('▼', p = 0, font = (VarFont, 15), button_color = ('grey70', bg_color), mouseover_color = bg_color_h, k = lambda w : self.toggle_expand(w))

        buttons = sg.Col([[button] for button in self.buttons], p = 0, background_color = bg_color_h)
        id_couriers_widget = sg.Col([[self.id_widget], [self.couriers_widget]], p = ((0, 10), (0, 0)), background_color = bg_color_h, expand_x = False)
        layout = [[ sg.Col([ [sg.Col([ [ self.days_widget, self.desc_widget, id_couriers_widget, buttons ] ], p = ((2, 0), (0, 0)), background_color = bg_color_h, expand_x = True) ]], p = 0, expand_x = True, background_color = bg_color_h) ],
                 [  sg.pin(self.loading_widget_col), sg.Col([ [self.ago_widget, self.status_widget, self.expand_button] ], p = ((3, 0), (5, 0)), background_color = bg_color, expand_x = True) ],
                 [  sg.pin(sg.Col([ [self.events_widget] ], p = 0, background_color = bg_color, expand_x = True), expand_x = True) ]]

        self.layout = sg.Col(layout, expand_x = True, p = ((self.layout_pad, self.layout_pad), (self.layout_pad, 0)), visible = self.tracker.state == 'ok', background_color = bg_color)
        self.pin = sg.pin(self.layout, expand_x = True) # collapse when hidden
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

        trigger_event(window, '-UPDATE WIDGETS SIZE-', '')

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
            trigger_event(window, '-UPDATING CHANGED-', '')
            
            self.tracker.prepare_update()
            self.show_current_courier_widget()
            self.loading_widget_col.update(visible = True)

            threading.Thread(target = self.update_thread, args = (window,), daemon = True).start()

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
            trigger_event(window, lambda window: self.update_done(window), '')

    def update_done(self, window):
        self.disable_buttons(False)
        self.loading_widget_col.update(visible = False)
        self.updating = False
        trigger_event(window, '-UPDATING CHANGED-', '')

    def animate(self, animation_step):
        if self.loading_widget_col.visible:
            self.loading_widget.update_animation(self.loading_gif, time_between_frames = animation_step)

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

            trigger_event(window, '-UPDATE WIDGETS SIZE-', '')

    def show_id(self, content):
        self.id_widget.update('') 

        # fromto = content and content.get('fromto')
        # fromto = f'{fromto}  ' if fromto else ''
        # self.id_widget.print(fromto, autoscroll = False, t = 'grey71', end = '')

        product = (content and content.get('product')) or 'Envoi'
        self.id_widget.print(f' {product}', autoscroll = False, t = 'grey50', end = '')

        idship = self.tracker.idship if self.tracker.idship else 'Pas de N°'
        self.id_widget.print(f' {idship}', autoscroll = False, t = 'blue', end = '')

    def show_couriers(self, couriers_update):
        if couriers_update:
            couriers_update_names = list(couriers_update.keys())
            couriers_update_names.sort()

            self.couriers_widget.update('') 
            
            w_name = max(len(name) for name in couriers_update_names)
            for name in couriers_update_names:
                date, error, updating = couriers_update[name]
                ago = f" {timeago.format(date, get_local_now(), 'fr').replace('il y a', '').strip()}" if date else ' jamais'
                error_color, name_font = ('red', FixFontBold) if error else ('green', FixFont)
                
                maj = ' MàJ en cours...'
                if updating:
                    self.couriers_widget.print(maj, autoscroll = False, font = (FixFontBold, self.courier_fsize), t = 'red', end = '')
                    spaces = ''
                else:
                    spaces = ' ' * len(maj)

                self.couriers_widget.print(f'{spaces}{ago}', autoscroll = False, t = 'grey60', end = '')
                self.couriers_widget.print(' ⟳ ', autoscroll = False, t = 'grey55', end = '')
                self.couriers_widget.print(f'{name.rjust(w_name)}', autoscroll = False, t = error_color, font = (name_font, self.courier_fsize))
        
        else:
            self.couriers_widget.update('Pas de trackers', text_color = 'red')

    def disable_buttons(self, disabled):
        for button in  self.buttons:
            button.update(disabled = disabled)

    def edit(self, window, main_loop):
        self.disable_buttons(True)

        idship, description, used_couriers = popup.edit('Édition', self.tracker.idship, self.tracker.description, self.tracker.used_couriers, self.tracker.available_couriers, not is_debugger, main_loop)
        if idship is not None:
            self.tracker.set_id(idship, description, used_couriers)
            self.reset_size()
            self.update(window)

        self.disable_buttons(False)

    def set_state(self, state, window, main_loop, ask, visible):
        if not ask or popup.warning(ask.capitalize(), self.tracker.description, not is_debugger, main_loop):
            if self.lock.acquire(blocking=False): # needed ?
                self.tracker.state = state

                self.layout.update(visible = visible)
                self.reset_size()

                trigger_event(window, '-UPDATE WIDGETS SIZE-', '')
                self.lock.release()

    def archive_or_delete(self, window, main_loop):
        self.disable_buttons(True)

        choices = { 'Archiver': self.archive, 'Supprimer': self.delete }
        colors = ('green', 'red')
        choice = popup.one_choice(choices.keys(), colors, f'{self.tracker.description} - {self.tracker.idship}', not is_debugger, main_loop)
        if choice:
            choices[choice](window, main_loop)

        self.disable_buttons(False)

    def delete(self, window, main_loop):
        self.set_state('deleted', window, main_loop, ask = 'Supprimer', visible = False)

    def archive(self, window, main_loop):
        self.set_state('archived', window, main_loop, ask = False, visible = False)
        trigger_event(window, '-ARCHIVE UPDATED-', '')

    def unarchive(self, window, main_loop):
        self.set_state('ok', window, main_loop, ask = False, visible = True)
        trigger_event(window, '-ARCHIVE UPDATED-', '')
        self.update(window)

# -------------------
class TrackerWidgets:
    def __init__(self, window, trackers, splash_update):
        self.widgets = []
        self.trackers = trackers

        n_trackers = len(trackers.trackers)
        for i, tracker in enumerate(trackers.trackers):
            splash_update(f'création suivi {i + 1}/{n_trackers}')
            self.create_widget(window, tracker)

        trigger_event(window, '-ARCHIVE UPDATED-', '')
        self.update_size(window)
        self.recenter(window, True)

    def create_widget(self, window, tracker):
        widget = TrackerWidget(tracker)

        window.extend_layout(window['TRACKS'], [widget.create_layout()])
        self.widgets.append(widget)

        widget.finalize(window)
        widget.update(window)

    def new(self, window, main_loop):
        tracker_params = popup.edit('Nouveau', '', 'Nouveau', [], self.trackers.couriers, not is_debugger, main_loop)
        tracker = self.trackers.new(*tracker_params)
        if tracker:
            self.create_widget(window, tracker)

    def get_widgets_with_state(self, state):
        return [widget for widget in self.widgets if widget.tracker.state == state]

    def show_archives(self, window, main_loop):
        archived = self.get_widgets_with_state('archived')
        archived.sort(key = lambda w : w.tracker.get_last_event(), reverse = True)

        w_idship = max(len(widget.tracker.get_pretty_idship()) for widget in archived)

        choices = []
        for widget in archived:
            tracker = widget.tracker
            color = 'green' if tracker.get_delivered() else 'red'
            txt = f'{tracker.get_pretty_last_event()} - {tracker.get_pretty_idship().ljust(w_idship)} - {tracker.description}'
            choices.append((txt, color))

        chosen = popup.choices(choices, 'Désarchiver', not is_debugger, main_loop)

        for i in chosen:
            widget = archived[i]
            widget.unarchive(window, main_loop)

    def count_not_updating(self):
        return [widget.updating for widget in self.get_widgets_with_state('ok')].count(False)

    def update(self, window):
        for widget in self.get_widgets_with_state('ok'):
            widget.update(window)

    def animate(self, animation_step):
        for widget in self.get_widgets_with_state('ok'):
            widget.animate(animation_step)
    
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
            w = max(widget.get_pixel_size()[0] for widget in ok) 
            h = sum(widget.get_pixel_size()[1] for widget in self.widgets) + window['MENU'].get_size()[1] + 3
        else:
            w, h = 400, 200

        # need scrollbar ?
        screen_w, screen_h = window.get_screen_size()
        h_screen_margin = 0 #400

        if h > screen_h - h_screen_margin:
            window['TRACKS'].Widget.vscrollbar.pack(side=sg.tk.RIGHT, fill='y')
            w += 15 # size of scrollbar

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
        window.refresh()

# ---------------------
class Main_window_loop:
    def __init__(self, main_window, trackers, widgets, mylog, animation_step = 100):
        self.main_window = main_window
    
        self.trackers = trackers
        self.widgets = widgets
        self.mylog = mylog

        main_window.TKroot.bind('<Configure>', lambda evt: self.mylog.stick_to_main())

        self.animation_step = animation_step
        main_window.TKroot.after(animation_step, self.animate)

    def animate(self):
        self.widgets.animate(self.animation_step)
        main_window.TKroot.after(self.animation_step, self.animate)

    def get_event(self):
        window, event, values = sg.read_all_windows()
        
        # if isinstance(event, str) and 'MouseWheel' not in event: 
        #     _log (f'{event = }' + (f', {value = }' if (value := values and values.get(event)) else ''))

        exit = False
        forward = None

        if mylog.catch_event(window, event):
            pass
        
        # clic event for multiline to expand collapse, see widget.bind in TrackerWidgets
        elif isinstance(event, tuple) and callable(event[0]):
            event[0](window)      

        # update, edit, delete, archive a tracker       
        elif callable(event):
            try:
                event(window, self) 
            
            except TypeError:
                event(window) 

        elif window == self.main_window:

            if event in (None, '-Exit-', 'Escape:27'):
                exit = True
            
            elif event in ('-Log-', 'l'):
                self.mylog.toggle()

            elif event == '-RECENTER-':
                self.widgets.recenter(window, force = True)

            elif event == '-UPDATING CHANGED-':
                n_updating = self.widgets.count_not_updating()
                window['-Refresh-'].update(disabled = n_updating == 0)

            elif event == '-ARCHIVE UPDATED-':
                n_archives = self.trackers.count_archived()
                txt, disabled = (f'Archives ({n_archives})', False) if n_archives > 0 else ('Archives', True)
                window['-Archives-'].update(txt, disabled = disabled)

            elif event == '-UPDATE WIDGETS SIZE-':
                self.widgets.update_size(window)

            elif event == '-New-':
                self.widgets.new(window, self)

            elif event == '-Refresh-':
                self.widgets.update(window)

            elif event == '-Archives-':
                self.widgets.show_archives(window, self)
            
            else:
                forward = window, event, values
        
        else:
            forward = window, event, values
        
        return exit, forward

# ------------------------
if __name__ == "__main__":

    import sys
    from fonts import FixFont, FixFontBold, VarFont, VarFontBold

    is_debugger = sys.gettrace()

    sg.theme('GrayGrayGray')

    splash_log = sg.T('', font=(VarFont, 10))
    splash = sg.Window('Suivi...', [[sg.T('Suivi...')], [splash_log]], font=(VarFont, 75), keep_on_top = not is_debugger, no_titlebar = not is_debugger, finalize = True)
    def splash_update(txt):
        splash_log.update(f'{txt} ...'.capitalize())
        splash.refresh()

    splash_update('inititialisation')

    menu_color = MyButton.default_colors['Enter']
    button_pad, button_f_size = 10, 12

    recenter_widget = sg.T('', background_color = menu_color, p = 0, expand_x = True, expand_y = True, k = '-RECENTER-')

    menu =  [   MyButton('Rafraichir', p = button_pad, font = (VarFont, button_f_size), k = '-Refresh-'), 
                MyButton('Nouveau', p = ((0, 0), (button_pad, button_pad)), font = (VarFont, button_f_size), k = '-New-'), 
                MyButton('   Archives   ', p = ((button_pad, 0), (button_pad, button_pad)), disabled = True, font = (VarFont, button_f_size), k = '-Archives-'), 
                recenter_widget,
                MyButton('Log', p = 0, font = (VarFont, button_f_size), k = '-Log-'), 
                MyButton(' X ', p = button_pad, font = (VarFontBold, button_f_size), button_color = ('red', None), focus = True, k = '-Exit-') ]

    layout = [ [ sg.Col([menu], p = 0, background_color = menu_color, expand_x = True, k = 'MENU') ],
               [ sg.Col([[]], p = 0, scrollable = True, vertical_scroll_only = True, expand_x = True, expand_y = True, k = 'TRACKS') ] ]

    frame =  [ [ sg.Frame('', layout, p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True) ] ]

    main_window = sg.Window('Suivi', frame, grab_anywhere = True, resizable = True, keep_on_top = not is_debugger, no_titlebar = not is_debugger, return_keyboard_events = True, margins = (0, 0), debugger_enabled = False)
    main_window.finalize().disappear()

    MyButton.finalize_all(main_window)
    recenter_widget.bind('<Double-Button-1>', '')

    trackers = Trackers(TrackersFile, splash_update) 
    widgets = TrackerWidgets(main_window, trackers, splash_update) 

    mylog.create_window((FixFont, 7), (VarFont, 12), not is_debugger, main_window)
    splash.close()
    main_window.reappear()
    main_window_loop = Main_window_loop(main_window, trackers, widgets, mylog)

    while True:
        if main_window_loop.get_event()[0]:
            break

    main_window.close()

    try:
        trackers.save()
        trackers.clean_couriers()
    except:
        _log (traceback.format_exc(), error = True)

    mylog.close()
    trackers.close()
