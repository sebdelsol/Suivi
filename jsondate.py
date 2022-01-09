
from dateutil.parser import parse
from datetime import datetime
import re

# https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
date_iso8601 = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'
match_iso8601 = re.compile(date_iso8601).match

def json_decode_datetime(_dict):
    for k, v in _dict.items():
        if isinstance(v, str) and match_iso8601(v):
            _dict[k] = parse(v)
    return _dict

def json_encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
