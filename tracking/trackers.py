import copy
import json
import os
import pickle
import threading
import traceback
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures.thread import _threads_queues

from tools.json_date import json_decode_datetime, json_encode_datetime
from windows.log import log

from tracking.couriers import CouriersHandler, get_local_now

JSON_EXT = ".json"
PICKLE_EXT = ".trck"


class TrackerState:
    definitly_deleted = "definitly deleted"
    deleted = "deleted"
    archived = "archived"
    shown = "shown"


class EventsNew:
    """for keeping track of new events"""

    def __init__(self, contents):
        self.events = {}
        for content in contents:
            for event in content["events"]:
                self.events[self._get_key(event)] = event

    @staticmethod
    def _get_key(event):
        """get a key by removing 'new' from the event dict"""
        return tuple((k, v) for k, v in event.items() if k != "new")

    def update(self, new_content):
        """keep self.events and new_content["events"] in sync"""
        if new_content:
            for event in new_content["events"]:
                key = self._get_key(event)
                if key in self.events:
                    event["new"] = self.events[key].get("new", False)
                else:
                    event["new"] = True
                self.events[key] = event

    def remove_new_event(self, event):
        """change only self.events, they are in sync with new_content"""
        if event := self.events.get(self._get_key(event)):
            event["new"] = False

    @staticmethod
    def remove_all_new_event(contents):
        """change only contents events, they are in sync with self.events"""
        for content in contents:
            for event in content["events"]:
                event["new"] = False


class Contents:
    def __init__(self, contents):
        self.contents = contents or {}
        self.events = EventsNew(self.contents.values())
        self.critical = threading.Lock()

    def update(self, courier_name, new_content):
        with self.critical:
            if new_content is not None:
                if new_content["ok"] or courier_name not in self.contents:
                    new_content["courier_name"] = courier_name
                    self.contents[courier_name] = new_content
                    self.events.update(new_content)

            return new_content and new_content["ok"]

    def _get_ok(self, idship, courier_names):
        for courier_name, content in self.contents.items():
            if (
                content["ok"]
                and courier_name in courier_names
                and content.get("idship") == idship
                and content.get("courier_name") == courier_name
            ):
                yield content

    @staticmethod
    def _get_delivered(contents_ok):
        return any(content["status"].get("delivered") for content in contents_ok)

    @staticmethod
    def _no_future(date):
        if date:  # not in future
            return min(date, get_local_now())
        return None

    def get_consolidated(self, idship, courier_names):
        """
        gives a copy of contents that can't be tampered with
        where status is the most recent one
        and events are merged
        """
        with self.critical:
            get_ok = self._get_ok(idship, courier_names)
            contents_ok = [copy.deepcopy(content) for content in get_ok]

        consolidated = {}
        if len(contents_ok) > 0:
            # consolidated is the content with the most recent date status
            consolidated = max(contents_ok, key=lambda content: content["status"]["date"])

            # merge all events
            events = sum((content["events"] for content in contents_ok), [])
            events.sort(key=lambda evt: evt["date"], reverse=True)
            consolidated["events"] = events

            delivered = self._get_delivered(contents_ok)
            consolidated["status"]["delivered"] = delivered

            if events:
                last_date = events[0]["date"] if delivered else get_local_now()
                consolidated["elapsed"] = last_date - events[-1]["date"]

            else:
                consolidated["elapsed"] = None

            consolidated["status"]["date"] = self._no_future(consolidated["status"]["date"])

        return consolidated

    def get(self):
        with self.critical:
            return copy.deepcopy(self.contents)

    def get_delivered(self, idship, courier_names):
        with self.critical:
            get_ok = self._get_ok(idship, courier_names)
            return self._get_delivered(get_ok)

    def get_ok_date(self, courier_name):
        with self.critical:
            content = self.contents.get(courier_name)
            return self._no_future(content and content.get("status", {}).get("ok_date"))

    def remove_new_event(self, event):
        with self.critical:
            self.events.remove_new_event(event)

    def remove_all_new_event(self):
        with self.critical:
            self.events.remove_all_new_event(self.contents.values())

    def clean(self, all_courier_names):
        with self.critical:
            for courier_name in all_courier_names:
                if content := self.contents.get(courier_name):
                    if not content["ok"]:
                        del self.contents[courier_name]
                        yield courier_name


class Tracker:
    def __init__(
        self,
        idship,
        description,
        used_couriers,
        couriers_handler,
        state=TrackerState.shown,
        contents=None,
        creation_date=None,
    ):
        self.modify(idship, description, used_couriers)
        self.state = state
        self.creation_date = creation_date or get_local_now()
        self.couriers_handler = couriers_handler
        self.couriers_error = {}
        self.couriers_updating = {}

        self.contents = Contents(contents)

        self.critical = threading.Lock()
        self.executor_ops = threading.Lock()
        self.executors = []
        self.closing = False

    def get_to_save(self):
        with self.critical:
            return dict(
                creation_date=self.creation_date,
                description=self.description,
                idship=self.idship,
                state=self.state,
                used_couriers=self.used_couriers,
                contents=self.contents.get(),
            )

    def modify(self, idship, description, used_couriers):
        self.used_couriers = used_couriers or []
        self.description = (description or "").strip().title()
        self.idship = (idship.upper() or "").strip()

    def prepare_idle_couriers(self):
        idle_couriers = []
        if self.idship:
            with self.critical:
                for courier_name in self.used_couriers:
                    if self.couriers_handler.exists(courier_name):
                        if not self.couriers_updating.get(courier_name):
                            if self.couriers_handler.validate_idship(courier_name, self.idship):
                                self.couriers_error[courier_name] = True
                                self.couriers_updating[courier_name] = True
                                idle_couriers.append(courier_name)
        return idle_couriers

    def is_still_updating(self):
        if self.idship:
            with self.critical:
                for courier_name in self.used_couriers:
                    if self.couriers_updating.get(courier_name):
                        return True
                return False
        else:
            return True  # as if it's updating, to prevent enabling refresh button

    def update_idle_couriers(self, courier_names):
        if self.idship and courier_names:
            log(f'update START - {self.description} - {self.idship}, {" - ".join(courier_names)}')

            # create threads with executor
            with self.executor_ops:
                if not self.closing:
                    executor = ThreadPoolExecutor(max_workers=len(courier_names))
                    futures = {
                        executor.submit(self._update_courier, courier_name): courier_name
                        for courier_name in courier_names
                    }
                    self.executors.append(executor)

            # handle threads
            if executor:
                for future in as_completed(futures):
                    new_content = future.result()
                    courier_name = futures[future]
                    ok = self.contents.update(courier_name, new_content)
                    with self.critical:
                        self.couriers_error[courier_name] = not ok
                        self.couriers_updating[courier_name] = False

                    msg = "DONE" if ok else "FAILED"
                    log(
                        f"update {msg} - {self.description} - {self.idship}, {courier_name}",
                        error=not ok,
                    )

                    yield self.get_consolidated_content()

                # dispose executor
                with self.executor_ops:
                    executor.shutdown()
                    self.executors.remove(executor)

    def _update_courier(self, courier_name):
        try:
            return self.couriers_handler.update(courier_name, self.idship)

        except:
            log(traceback.format_exc(), error=True)
            return None

    CouriersStatus = namedtuple("CouriersStatus", "name, ok_date, error, updating, valid_idship, exists")

    def get_couriers_status(self):
        with self.critical:
            couriers_status = []
            for courier_name in sorted(self.used_couriers):
                ok_date = self.contents.get_ok_date(courier_name)
                error = self.couriers_error.get(courier_name, True)
                updating = self.couriers_updating.get(courier_name, False)
                valid_idship = self.couriers_handler.validate_idship(courier_name, self.idship)
                exists = self.couriers_handler.exists(courier_name)

                status = self.CouriersStatus(courier_name, ok_date, error, updating, valid_idship, exists)
                couriers_status.append(status)

            return couriers_status

    def get_consolidated_content(self):
        consolidated = self.contents.get_consolidated(self.idship, self.used_couriers)
        consolidated["couriers_status"] = self.get_couriers_status()
        return consolidated

    def get_delivered(self):
        return self.contents.get_delivered(self.idship, self.used_couriers)

    def remove_new_event(self, event):
        self.contents.remove_new_event(event)

    def remove_all_new_event(self):
        self.contents.remove_all_new_event()

    def open_in_browser(self, courier_name):
        if courier_name in self.used_couriers:
            self.couriers_handler.open_in_browser(courier_name, self.idship)

    def clean(self):
        all_courier_names = self.couriers_handler.get_names()
        for courier_name in self.contents.clean(all_courier_names):
            log(f"CLEAN {self.description} - {self.idship}, {courier_name}")

    def close(self):
        # https://stackoverflow.com/questions/49992329/the-workers-in-threadpoolexecutor-is-not-really-daemon
        # doesn't work with Python >= 3.9 ?
        with self.executor_ops:
            self.closing = True
            if self.executors:
                for executor in self.executors:
                    for thread in executor._threads:
                        del _threads_queues[thread]


class Trackers:
    def __init__(self, filename, load_as_json, splash):
        self.filename = filename
        self.couriers_handler = CouriersHandler(splash)

        if load_as_json:

            def json_load(f):
                return json.load(f, object_hook=json_decode_datetime)

            loaded_trackers = self._load_from_file(JSON_EXT, "r", json_load)

        else:
            loaded_trackers = self._load_from_file(PICKLE_EXT, "rb", pickle.load)

        if loaded_trackers:
            trackers = [
                Tracker(
                    trk["idship"],
                    trk["description"],
                    trk["used_couriers"],
                    self.couriers_handler,
                    trk["state"],
                    trk["contents"],
                    trk["creation_date"],
                )
                for trk in loaded_trackers
            ]

        else:
            trackers = []

        self.trackers = self.sort(trackers)

    def save(self):
        trackers = self.sort(self.get_not_definitly_deleted())
        to_save_trackers = [tracker.get_to_save() for tracker in trackers]

        self._save_to_file(to_save_trackers, PICKLE_EXT, "wb", pickle.dump)

        def json_save(obj, f):
            json.dump(obj, f, default=json_encode_datetime, indent=4)

        self._save_to_file(to_save_trackers, JSON_EXT, "w", json_save)

    def _load_from_file(self, ext, mode, load):
        filename = self.filename + ext
        if os.path.exists(filename):
            with open(filename, mode) as f:
                obj = load(f)
            log(f'trackers LOADED from "{filename}"')
            return obj
        return None

    def _save_to_file(self, obj, ext, mode, save):
        filename = self.filename + ext
        with open(filename, mode) as f:
            save(obj, f)
        log(f'trackers SAVED to "{filename}"')

    @staticmethod
    def sort(objs, get_tracker=lambda obj: obj):
        return sorted(objs, key=lambda obj: get_tracker(obj).creation_date, reverse=True)

    def new(self, idship, description, used_couriers):
        tracker = Tracker(idship, description, used_couriers, self.couriers_handler)
        self.trackers.append(tracker)
        return tracker

    def get_not_definitly_deleted(self):
        return [tracker for tracker in self.trackers if tracker.state != TrackerState.definitly_deleted]

    def count_state(self, state):
        return len([tracker for tracker in self.trackers if tracker.state == state])

    def close(self):
        for tracker in self.trackers:
            tracker.clean()
        self.save()
        for tracker in self.trackers:
            tracker.close()
