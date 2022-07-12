import calendar
import locale
from datetime import datetime, timedelta

import pytz
from dateutil import parser
from tzlocal import get_localzone

# https://docs.moodle.org/dev/Table_of_locales
LOCALE_SETTINGS = dict(
    fr=dict(lc_time="French_France.1252", day_first=True),
    it=dict(lc_time="Italian_Italy.1252", day_first=True),
    de=dict(lc_time="English_Australia.1252", day_first=True),
    es=dict(lc_time="Spanish_Spain.1252", day_first=True),
)
_locale_parsers = {}

for country, settings in LOCALE_SETTINGS.items():
    locale.setlocale(locale.LC_TIME, settings["lc_time"])  # date in correct language

    class _LocaleParserInfo(parser.parserinfo):
        day_abbr = calendar.day_abbr
        day_abbr2 = (d.replace(".", "") for d in day_abbr)
        WEEKDAYS = list(zip(day_abbr, day_abbr2, calendar.day_name))

        month_abbr = calendar.month_abbr
        month_abbr2 = (m.replace(".", "") for m in month_abbr)
        MONTHS = list(zip(month_abbr, month_abbr2, calendar.month_name))[1:]

    _locale_parsers[country] = _LocaleParserInfo(dayfirst=settings["day_first"])


def _round_minute(dt):
    minutes = (dt.second + dt.microsecond * 0.001) // 30
    return dt.replace(second=0, microsecond=0) + timedelta(minutes=minutes)


def _get_time(date, locale_country=None):
    # today at noon
    default = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
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


def get_utc_from_timestamp(time_stamp):
    return _round_minute(
        datetime.utcfromtimestamp(time_stamp)
        .replace(tzinfo=pytz.utc)
        .astimezone(get_localzone())
    )


def get_local_now():
    return datetime.now().astimezone(get_localzone())
