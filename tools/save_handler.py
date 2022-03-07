import json
import os
import pickle

from windows.log import log

from .json_date import json_decode_datetime, json_encode_datetime

JSON_EXT = ".json"
PICKLE_EXT = ".pickle"


class SaveHandler:
    def __init__(self, filename, load_as_json=True):
        self.filename = filename
        self.load = self.load_as_json if load_as_json else self.load_as_binary

    @staticmethod
    def json_load(f):
        return json.load(f, object_hook=json_decode_datetime)

    @staticmethod
    def json_save(obj, f):
        json.dump(obj, f, default=json_encode_datetime, indent=4, ensure_ascii=False)

    def load_as_json(self):
        return self._load_from_file(JSON_EXT, "r", self.json_load, encoding="utf8")

    def load_as_binary(self):
        return self._load_from_file(PICKLE_EXT, "rb", pickle.load)

    def save_as_json(self, obj):
        self._save_to_file(obj, JSON_EXT, "w", self.json_save, encoding="utf8")

    def save_as_binary(self, obj):
        self._save_to_file(obj, PICKLE_EXT, "wb", pickle.dump)

    def _load_from_file(self, ext, mode, load, encoding=None):
        filename = self.filename + ext
        if os.path.exists(filename):
            with open(filename, mode, encoding=encoding) as f:
                obj = load(f)
            log(f'"{filename}" LOADED')
            return obj
        return None

    def _save_to_file(self, obj, ext, mode, save, encoding=None):
        filename = self.filename + ext
        with open(filename, mode, encoding=encoding) as f:
            save(obj, f)
        log(f'"{filename}" SAVED')
