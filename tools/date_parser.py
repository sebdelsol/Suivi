import calendar
import locale
from datetime import datetime, timedelta

import pytz
from dateutil import parser
from tzlocal import get_localzone

LOCALE_SETTINGS = dict(
    fr=dict(lc_time="French_France.1252", day_first=True),
    it=dict(lc_time="Italian_Italy.1252", day_first=True),
)
_locale_parsers = {}

for country, settings in LOCALE_SETTINGS.items():
    locale.setlocale(locale.LC_TIME, settings["lc_time"])  # date in correct language

    class _LocaleParserInfo(parser.parserinfo):
        WEEKDAYS = list(zip(calendar.day_abbr, calendar.day_name))
        MONTHS = list(zip(calendar.month_abbr, calendar.month_name))[1:]

    _locale_parsers[country] = _LocaleParserInfo(dayfirst=settings["day_first"])


def _round_minute(dt):
    return dt.replace(second=0, microsecond=0) + timedelta(
        minutes=(dt.second + dt.microsecond * 0.001) // 30
    )


def _get_time(date, locale_country=None):
    # today at noon
    default = datetime.now().replace(hour=12, minute=00, second=0, microsecond=0)
    parserinfo = _locale_parsers.get(locale_country) if locale_country else None
    return _round_minute(parser.parse(date, parserinfo=parserinfo, default=default))


def get_local_time(date, locale_country=None):
    return _get_time(date, locale_country).astimezone(get_localzone())


def get_utc_time(date, locale_country=None):
    return (
        _get_time(date, locale_country)
        .replace(tzinfo=pytz.utc)
        .astimezone(get_localzone())
    )


def get_local_now():
    return datetime.now().astimezone(get_localzone())
