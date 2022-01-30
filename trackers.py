import copy
import json
import os
import pickle
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures.thread import _threads_queues

from couriers import Couriers, get_local_now
from jsondate import json_decode_datetime, json_encode_datetime
from log import log

JSON_EXT = ".json"
PICKLE_EXT = ".trck"


class TrackerState:
    definitly_deleted = "definitly deleted"
    deleted = "deleted"
    archived = "archived"
    shown = "shown"


class SavedTracker(dict):
    def __init__(self, tracker):
        with tracker.critical:
            # tracker attribute to save
            for attr in (
                "idship",
                "description",
                "used_couriers",
                "state",
                "contents",
                "creation_date",
            ):
                self[attr] = tracker.__dict__[attr]


class Tracker:
    def __init__(
        self,
        idship,
        description,
        used_couriers,
        couriers,
        state=TrackerState.shown,
        contents=None,
        creation_date=None,
    ):
        self.set_id(idship, description, used_couriers)
        self.state = state
        self.contents = contents or {}
        self.creation_date = creation_date or get_local_now()

        self.couriers = couriers
        self.critical = threading.Lock()
        self.couriers_error = {}
        self.couriers_updating = {}

        self.executor_ops = threading.Lock()
        self.executors = []
        self.closing = False

        self.loaded_events = set()
        for content in self.contents.values():
            if events := content.get("events"):
                self.loaded_events |= {tuple(event.items()) for event in events}  # can't hash dict

    def set_id(self, idship, description, used_couriers):
        self.used_couriers = used_couriers or []
        self.description = (description or "").strip().title()
        self.idship = (idship.upper() or "").strip()

    def _get_and_prepare_idle_couriers_names(self):
        if self.idship:
            with self.critical:
                for name in self.used_couriers:
                    if self.couriers.exists(name):
                        if not self.couriers_updating.get(name):
                            if self.couriers.validate_idship(name, self.idship):
                                self.couriers_error[name] = True
                                self.couriers_updating[name] = True
                                yield name

    def get_idle_couriers(self):
        return list(self._get_and_prepare_idle_couriers_names())

    def is_courier_still_updating(self):
        if self.idship:
            with self.critical:
                for name in self.used_couriers:
                    if self.couriers_updating.get(name):
                        return True
                return False
        else:
            return True  # as if it's updating, to prevent enabling refresh button

    def update_idle_couriers(self, names):
        if self.idship and names:
            log(f'update START - {self.description} - {self.idship}, {" - ".join(names)}')

            # create threads with executor
            with self.executor_ops:
                if not self.closing:
                    executor = ThreadPoolExecutor(max_workers=len(names))
                    futures = {executor.submit(self._update_courier, name): name for name in names}
                    self.executors.append(executor)

            # handle threads
            if executor:
                for future in as_completed(futures):
                    new_content = future.result()
                    name = futures[future]
                    with self.critical:
                        if new_content is not None:
                            if new_content["ok"] or name not in self.contents:
                                new_content["courier_name"] = name
                                self.contents[name] = new_content

                        error = not (new_content and new_content["ok"])
                        self.couriers_error[name] = error
                        self.couriers_updating[name] = False

                    msg = "FAILED" if error else "DONE"
                    log(
                        f"update {msg} - {self.description} - {self.idship}, {name}",
                        error=error,
                    )

                    yield self.get_consolidated_content()

                # dispose executor
                with self.executor_ops:
                    executor.shutdown()
                    self.executors.remove(executor)

    def _update_courier(self, name):
        try:
            return self.couriers.update(name, self.idship)

        except:
            log(traceback.format_exc(), error=True)
            return None

    def get_consolidated_content(self):
        consolidated = {}

        with self.critical:
            contents_ok = []
            for name, content in self.contents.items():
                if name in self.used_couriers and content["ok"] and content.get("idship") == self.idship:
                    contents_ok.append(copy.deepcopy(content))

        if len(contents_ok) > 0:
            contents_ok.sort(key=lambda c: c["status"]["date"], reverse=True)
            consolidated = contents_ok[0]

            events = sum((content["events"] for content in contents_ok), [])
            events.sort(key=lambda evt: evt["date"], reverse=True)

            for event in events:
                event["new"] = tuple(event.items()) not in self.loaded_events

            consolidated["events"] = events

            delivered = any(content["status"].get("delivered") for content in contents_ok)
            consolidated["status"]["delivered"] = delivered
            consolidated["elapsed"] = (
                events and (events[0]["date"] if delivered else get_local_now()) - events[-1]["date"]
            )
            consolidated["status"]["date"] = self._no_future(consolidated["status"]["date"])

        consolidated["couriers_update"] = self.get_couriers_update()

        return consolidated

    def get_couriers_update(self):
        with self.critical:
            couriers_update = {}
            for name in self.used_couriers:
                content = self.contents.get(name)
                ok_date = self._no_future(content and content.setdefault("status", {}).get("ok_date"))
                error = self.couriers_error.get(name, True)
                updating = self.couriers_updating.get(name, False)
                valid_idship = self.couriers.validate_idship(name, self.idship)
                exists = self.couriers.exists(name)
                couriers_update[name] = (ok_date, error, updating, valid_idship, exists)

            return couriers_update

    @staticmethod
    def _no_future(date):
        if date:  # not in future
            return min(date, get_local_now())
        return None

    def get_delivered(self):
        content = self.get_consolidated_content()
        return content.setdefault("status", {}).get("delivered")

    def open_in_browser(self, name):
        if name in self.used_couriers:
            self.couriers.open_in_browser(name, self.idship)

    def clean(self):
        for name in self.couriers.get_names():
            content = self.contents.get(name)
            if content:
                if not content["ok"]:
                    log(f"CLEAN {self.description} - {self.idship}, {name}")
                    del self.contents[name]

    def close(self):
        with self.executor_ops:
            self.closing = True
            if self.executors:
                for executor in self.executors:
                    # https://stackoverflow.com/questions/49992329/the-workers-in-threadpoolexecutor-is-not-really-daemon
                    # doesn't work with Python >= 3.9 ?
                    for thread in executor._threads:
                        del _threads_queues[thread]


class Trackers:
    def __init__(self, filename, load_as_json, splash):
        self.filename = filename
        self.couriers = Couriers(splash)

        if load_as_json:

            def json_load(f):
                return json.load(f, object_hook=json_decode_datetime)

            trackers = self.load_from_file(JSON_EXT, "r", json_load)

        else:
            trackers = self.load_from_file(PICKLE_EXT, "rb", pickle.load)

        if trackers:
            trackers = [
                Tracker(
                    trk["idship"],
                    trk["description"],
                    trk["used_couriers"],
                    self.couriers,
                    trk["state"],
                    trk["contents"],
                    trk["creation_date"],
                )
                for trk in trackers
            ]

        self.trackers = self.sort(trackers or [])

    def save(self):
        trackers = self.sort(self.get_not_definitly_deleted())
        for tracker in trackers:
            print(tracker.description)
        saved_trackers = [SavedTracker(tracker) for tracker in trackers]

        self.save_to_file(saved_trackers, PICKLE_EXT, "wb", pickle.dump)

        def json_save(obj, f):
            json.dump(obj, f, default=json_encode_datetime, indent=4)

        self.save_to_file(saved_trackers, JSON_EXT, "w", json_save)

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
