import traceback
import threading
import os
import copy
import json
import pickle as pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures.thread import _threads_queues

from jsondate import json_decode_datetime, json_encode_datetime
from couriers import Couriers, get_local_now
from log import log

json_ext = '.json'
pickle_ext = '.trck'


class TrackerState:
    deleted = 'deleted'
    archived = 'archived'
    shown = 'shown'


class SavedTracker(dict):
    def __init__(self, tracker):
        with tracker.critical:
            # tracker attribute to save
            for attr in ('idship', 'description', 'used_couriers', 'state', 'contents', 'creation_date'):
                self[attr] = tracker.__dict__[attr]


class Tracker:
    def __init__(self, idship, description, used_couriers, available_couriers, state=TrackerState.shown, contents=None, creation_date=None):
        self.set_id(idship, description, used_couriers)
        self.state = state
        self.contents = contents or {}
        self.creation_date = creation_date or get_local_now()

        self.available_couriers = available_couriers
        self.critical = threading.Lock()
        self.couriers_error = {}
        self.couriers_updating = {}

        self.executor_ops = threading.Lock()
        self.executors = []

        self.loaded_events = set()
        for content in self.contents.values():
            if events := content.get('events'):
                self.loaded_events |= {tuple(event.items()) for event in events}  # can't hash dict

    def set_id(self, idship, description, used_couriers):
        self.used_couriers = used_couriers or []
        self.description = (description or '').strip().title()
        self.idship = (idship.upper() or '').strip()

    def _get_and_prepare_idle_couriers_names(self):
        if self.idship:
            with self.critical:
                for courier_name in self.used_couriers:
                    # check it's not already updating
                    if not self.couriers_updating.get(courier_name):
                        # check it's a valid id_ship for this courier
                        if courier := self.available_couriers.get(courier_name):
                            if courier.check_idship(self.idship):
                                self.couriers_error[courier_name] = True
                                self.couriers_updating[courier_name] = True
                                yield courier_name

    def get_idle_couriers(self):
        return list(self._get_and_prepare_idle_couriers_names())

    def is_courier_still_updating(self):
        if self.idship:
            with self.critical:
                for courier_name in self.used_couriers:
                    if self.couriers_updating.get(courier_name):
                        return True
                else:
                    return False
        else:
            return True  # as if it's updating, to prevent enabling refresh button

    def update_idle_couriers(self, courier_names):
        if self.idship and courier_names:
            log(f'update START - {self.description} - {self.idship}, {" - ".join(courier_names)}')

            # create threads with executor
            with self.executor_ops:
                executor = ThreadPoolExecutor(max_workers=len(courier_names))
                futures = {executor.submit(self._update_courier, courier_name): courier_name for courier_name in courier_names}
                self.executors.append(executor)

            # handle threads
            for future in as_completed(futures):
                new_content = future.result()
                courier_name = futures[future]
                with self.critical:
                    if new_content is not None:
                        if new_content['ok'] or courier_name not in self.contents:
                            new_content['courier_name'] = courier_name
                            self.contents[courier_name] = new_content

                    error = not(new_content and new_content['ok'])
                    self.couriers_error[courier_name] = error
                    self.couriers_updating[courier_name] = False

                msg = 'FAILED' if error else 'DONE'
                log(f'update {msg} - {self.description} - {self.idship}, {courier_name}', error=error)

                yield self.get_consolidated_content()

            # dispose executor
            with self.executor_ops:
                executor.shutdown()
                self.executors.remove(executor)

    def _update_courier(self, courier_name):
        try:
            if courier := self.available_couriers.get(courier_name):
                return courier.update(self.idship)

        except:
            log(traceback.format_exc(), error=True)

    def get_consolidated_content(self):
        consolidated = {}

        with self.critical:
            contents_ok = []
            for courier_name, content in self.contents.items():
                if courier_name in self.used_couriers and content['ok'] and content.get('idship') == self.idship:
                    contents_ok.append(copy.deepcopy(content))

        if len(contents_ok) > 0:
            contents_ok.sort(key=lambda c: c['status']['date'], reverse=True)
            consolidated = contents_ok[0]

            events = sum((content['events'] for content in contents_ok), [])
            events.sort(key=lambda evt: evt['date'], reverse=True)

            for event in events:
                event['new'] = tuple(event.items()) not in self.loaded_events

            consolidated['events'] = events

            delivered = any(content['status'].get('delivered') for content in contents_ok)
            consolidated['status']['delivered'] = delivered
            consolidated['elapsed'] = events and (events[0]['date'] if delivered else get_local_now()) - events[-1]['date']
            consolidated['status']['date'] = self._no_future(consolidated['status']['date'])

        consolidated['couriers_update'] = self.get_couriers_update()

        return consolidated

    def get_couriers_update(self):
        with self.critical:
            couriers_update = {}
            for courier_name in self.used_couriers:
                content = self.contents.get(courier_name)
                ok_date = self._no_future(content and content.setdefault('status', {}).get('ok_date'))
                error = self.couriers_error.get(courier_name, True)
                updating = self.couriers_updating.get(courier_name, False)
                courier = self.available_couriers.get(courier_name)
                valid_idship = courier and self.idship and courier.check_idship(self.idship)
                couriers_update[courier_name] = (ok_date, error, updating, valid_idship)

        return couriers_update

    def _no_future(self, date):
        if date:  # not in future
            return min(date, get_local_now())

    def get_delivered(self):
        content = self.get_consolidated_content()
        return content.setdefault('status', {}).get('delivered')

    def close(self):
        with self.executor_ops:
            if self.executors:
                for executor in self.executors:
                    # kill the updating threads https://stackoverflow.com/questions/49992329/the-workers-in-threadpoolexecutor-is-not-really-daemon
                    for thread in executor._threads:
                        del _threads_queues[thread]


class Trackers:
    def __init__(self, filename, load_as_json, splash):
        self.filename = filename
        self.couriers = Couriers(splash)

        if load_as_json:
            trackers = self.load_from_file(json_ext, 'r', lambda f: json.load(f, object_hook=json_decode_datetime))

        else:
            trackers = self.load_from_file(pickle_ext, 'rb', lambda f: pickle.load(f))

        if trackers:
            trackers = [Tracker(trk['idship'], trk['description'], trk['used_couriers'], self.couriers, trk['state'], trk['contents'], trk['creation_date']) for trk in trackers]

        self.trackers = self.sort(trackers or [])

    def save(self):
        trackers = self.sort(self.get_not_deleted())
        saved_trackers = [SavedTracker(tracker) for tracker in trackers]

        self.save_to_file(saved_trackers, pickle_ext, 'wb', lambda obj, f: pickle.dump(obj, f))
        self.save_to_file(saved_trackers, json_ext, 'w', lambda obj, f: json.dump(obj, f, default=json_encode_datetime, indent=4))

    def load_from_file(self, ext, mode, load):
        filename = self.filename + ext
        if os.path.exists(filename):
            with open(filename, mode) as f:
                obj = load(f)
            log(f'trackers LOADED from "{filename}"')
            return obj

    def save_to_file(self, obj, ext, mode, save):
        filename = self.filename + ext
        with open(filename, mode) as f:
            save(obj, f)
        log(f'trackers SAVED to "{filename}"')

    def sort(self, objs, get_tracker=lambda obj: obj):
        return sorted(objs, key=lambda obj: get_tracker(obj).creation_date, reverse=True)

    def new(self, idship, description, used_couriers):
        tracker = Tracker(idship, description, used_couriers, self.couriers)
        self.trackers.append(tracker)
        return tracker

    def get_not_deleted(self):
        return [tracker for tracker in self.trackers if tracker.state != TrackerState.deleted]

    def count_state(self, state):
        return len([tracker for tracker in self.trackers if tracker.state == state])

    def close(self):
        self.save()
        self.couriers.close()
        for tracker in self.trackers:
            tracker.close()
