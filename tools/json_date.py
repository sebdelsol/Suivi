import re
from datetime import datetime

from dateutil.parser import parse

# https://stackoverflow.com/a/48881514
ISOFORMAT_RE = (
    r"^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-"
    r"(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):"
    r"([0-5][0-9]):([0-5][0-9])(\.[0-9]+)"
    r"?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$"
)

match_isoformat = re.compile(ISOFORMAT_RE).match


def json_decode_datetime(obj):
    for k, v in obj.items():
        if isinstance(v, str) and match_isoformat(v):
            obj[k] = parse(v)
    return obj


def json_encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return None
