from dateutil.parser import parse
from datetime import datetime
import re

# https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
isoformat_re = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'
match_isoformat = re.compile(isoformat_re).match

def json_decode_datetime(obj):
    for k, v in obj.items():
        if isinstance(v, str) and match_isoformat(v):
            obj[k] = parse(v)
    return obj

def json_encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
