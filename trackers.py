import traceback
import threading
import queue
import os
import copy
import json
import pickle as pickle

from jsondate import json_decode_datetime, json_encode_datetime
from couriers import Couriers, get_local_now
from mylog import _log

#-----------------------
class TrackerState:
    deleted = 'deleted'
    archived = 'archived'
    shown = 'shown'

#------------------------
class SavedTracker(dict):
    def __init__(self, tracker):
        with tracker.critical:
            # tracker attribute to save
            for attr in ('idship', 'description', 'used_couriers', 'state', 'contents', 'creation_date'):
                self[attr] = tracker.__dict__[attr]

#-------------
class Tracker:
    def __init__(self, idship, description, used_couriers, available_couriers, state = TrackerState.shown, contents = None, creation_date = None):
        self.set_id(idship, description, used_couriers)
        self.state = state
        self.contents = contents or {}
        self.creation_date = creation_date or get_local_now()
        
        self.available_couriers = available_couriers
        self.critical = threading.Lock()
        self.couriers_error = {}
        self.couriers_updating = {}

        self.loaded_events = set()
        for content in self.contents.values():
            self.loaded_events |= set( frozenset(evt.items()) for evt in content.get('events', []) ) # can't hash dict

    def set_id(self, idship, description, used_couriers):
        self.used_couriers = used_couriers
        self.description = description.title()
        self.idship = idship.strip()

    def prepare_update(self):
        with self.critical:
            for courier_name in self.used_couriers:
                self.couriers_error[courier_name] = True
                self.couriers_updating[courier_name] = True

    def update_all_couriers(self):
        content_queue = queue.Queue()
        for courier_name in self.used_couriers:
            _log (f'update START - {self.description} - {self.idship}, {courier_name}')
            threading.Thread(target = self.update_courier, args = (courier_name, content_queue)).start()

        for _ in range(len(self.used_couriers)):
            courier_name, new_content = content_queue.get()
            _log (f'update DONE - {self.description} - {self.idship}, {courier_name}')

            with self.critical:
                if new_content is not None:
                    if new_content['ok'] or courier_name not in self.contents:
                        new_content['courier_name'] = courier_name
                        self.contents[courier_name] = new_content

                self.couriers_error[courier_name] = not(new_content and new_content['ok'])
                self.couriers_updating[courier_name] = False

            yield self.get_consolidated_content()

    def update_courier(self, courier_name, content_queue):
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
            contents_ok = []
            for courier_name, content in self.contents.items():
                if courier_name in self.used_couriers and content['ok'] and content.get('idship') == self.idship:
                    contents_ok.append(copy.deepcopy(content))

            if len(contents_ok) > 0:
                contents_ok.sort(key = lambda c : c['status']['date'], reverse = True)
                consolidated = contents_ok[0]
                
                events = sum((content['events'] for content in contents_ok), [])
                events.sort(key = lambda evt : evt['date'], reverse = True)

                for event in events:
                    event['new'] = frozenset(event.items()) not in self.loaded_events

                consolidated['events'] = events 
                
                delivered = any(c['status'].get('delivered') for c in contents_ok)
                consolidated['status']['delivered'] = delivered
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

    def get_delivered(self):
        content = self.get_consolidated_content() 
        return content and content.get('status', {}).get('delivered')


#--------------
class Trackers:
    def __init__(self, filename, load_as_json, splash):
        self.filename = filename
        self.couriers = Couriers(splash)

        if load_as_json:
            trackers = self._load('.json', 'r', lambda f: json.load(f, object_hook = json_decode_datetime))
        else:
            trackers = self._load('.trck', 'rb', lambda f: pickle.load(f))

        if trackers:
            trackers = [Tracker(trk['idship'], trk['description'], trk['used_couriers'], self.couriers, trk['state'], trk['contents'], trk['creation_date']) for trk in trackers]

        self.trackers = self.sort(trackers or [])

    def save(self):
        trackers = self.sort(self.get_not_deleted())
        saved_trackers = [SavedTracker(tracker) for tracker in trackers]

        self._save(saved_trackers, '.trck', 'wb', lambda obj, f: pickle.dump(obj, f))
        self._save(saved_trackers, '.json', 'w', lambda obj, f: json.dump(obj, f, default = json_encode_datetime, indent = 4))

    def _load(self, ext, mode, load):
        filename = self.filename + ext
        if os.path.exists(filename):
            with open(filename, mode) as f:
                obj = load(f)
            
            _log(f'trackers LOADED from "{filename}"')
            return obj

    def _save(self, obj, ext, mode, save):
        filename = self.filename + ext
        with open(filename, mode) as f:
            save(obj, f)
        _log(f'trackers SAVED to "{filename}"')

    def sort(self, objs, get_tracker = lambda obj : obj): 
        return sorted(objs, key = lambda obj : get_tracker(obj).creation_date, reverse = True)

    def new(self, idship, description, used_couriers):
        if idship is not None:
            tracker = Tracker(idship, description, used_couriers, self.couriers)
            self.trackers.append(tracker)
            return tracker

    def get_not_deleted(self):
        return [tracker for tracker in self.trackers if tracker.state != TrackerState.deleted]
    
    def count_state(self, state):
        return len([tracker for tracker in self.trackers if tracker.state == state])

    def close(self):
        self.couriers.close()
