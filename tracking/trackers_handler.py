from tools.save_handler import SaveHandler
from translation.translate import TranslationHandler
from windows.localization import TXT

from .couriers_handler import CouriersHandler
from .tracker import Tracker, TrackerState


class TrackersHandler:
    def __init__(self, filename=None, translation_module="deepl", load_as_json=True):
        self.couriers_handler = CouriersHandler()
        self.translation_handler = TranslationHandler(
            TXT.locale_country_code, translation_module
        )

        trackers = []
        self.save_handler = SaveHandler(filename, "trackers", load_as_json)
        if loaded_trackers := self.save_handler.load():
            for kwargs in loaded_trackers:
                trackers.append(
                    Tracker(self.couriers_handler, self.translation_handler, **kwargs)
                )

        self.trackers = self.sort(trackers)

    def save(self):
        trackers = self.sort(self.get_not_definitly_deleted())
        to_save_trackers = [tracker.get_to_save() for tracker in trackers]
        self.save_handler.save_as_json(to_save_trackers)
        self.save_handler.save_as_binary(to_save_trackers)

    @staticmethod
    def sort(objs, get_tracker=lambda obj: obj):
        return sorted(
            objs, key=lambda obj: get_tracker(obj).creation_date, reverse=True
        )

    def new(self, idship, description, used_couriers):
        tracker = Tracker(
            self.couriers_handler,
            self.translation_handler,
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
        self.translation_handler.save()
        for tracker in self.trackers:
            tracker.close()
