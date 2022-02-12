import json
import os
import pickle

from tools.json_date import json_decode_datetime, json_encode_datetime
from windows.log import log

from tracking.couriers_handler import CouriersHandler
from tracking.tracker import Tracker, TrackerState

JSON_EXT = ".json"
PICKLE_EXT = ".trck"


class TrackersHandler:
    def __init__(self, filename, load_as_json):
        self.filename = filename
        self.couriers_handler = CouriersHandler()

        if load_as_json:

            def json_load(f):
                return json.load(f, object_hook=json_decode_datetime)

            loaded_trackers = self._load_from_file(
                JSON_EXT, "r", json_load, encoding="utf8"
            )

        else:
            loaded_trackers = self._load_from_file(PICKLE_EXT, "rb", pickle.load)

        if loaded_trackers:
            trackers = [
                Tracker(self.couriers_handler, **kwargs) for kwargs in loaded_trackers
            ]

        else:
            trackers = []

        self.trackers = self.sort(trackers)

    def save(self):
        trackers = self.sort(self.get_not_definitly_deleted())
        to_save_trackers = [tracker.get_to_save() for tracker in trackers]

        self._save_to_file(to_save_trackers, PICKLE_EXT, "wb", pickle.dump)

        def json_save(obj, f):
            json.dump(
                obj, f, default=json_encode_datetime, indent=4, ensure_ascii=False
            )

        self._save_to_file(to_save_trackers, JSON_EXT, "w", json_save, encoding="utf8")

    def _load_from_file(self, ext, mode, load, encoding=None):
        filename = self.filename + ext
        if os.path.exists(filename):
            with open(filename, mode, encoding=encoding) as f:
                obj = load(f)
            log(f'trackers LOADED from "{filename}"')
            return obj
        return None

    def _save_to_file(self, obj, ext, mode, save, encoding=None):
        filename = self.filename + ext
        with open(filename, mode, encoding=encoding) as f:
            save(obj, f)
        log(f'trackers SAVED to "{filename}"')

    @staticmethod
    def sort(objs, get_tracker=lambda obj: obj):
        return sorted(
            objs, key=lambda obj: get_tracker(obj).creation_date, reverse=True
        )

    def new(self, idship, description, used_couriers):
        tracker = Tracker(
            self.couriers_handler,
            idship=idship,
            description=description,
            used_couriers=used_couriers,
        )
        self.trackers.append(tracker)
        return tracker

    def get_not_definitly_deleted(self):
        return [
            tracker
            for tracker in self.trackers
            if tracker.state != TrackerState.definitly_deleted
        ]

    def count_state(self, state):
        return len([tracker for tracker in self.trackers if tracker.state == state])

    def close(self):
        self.save()
        for tracker in self.trackers:
            tracker.close()
