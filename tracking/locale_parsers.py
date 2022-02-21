import calendar
import locale

from dateutil import parser

LOCALE_SETTINGS = dict(
    fr=dict(lc_time="French_France.1252", day_first=True),
    it=dict(lc_time="Italian_Italy.1252", day_first=True),
)
locale_parsers = {}

for country, settings in LOCALE_SETTINGS.items():
    locale.setlocale(locale.LC_TIME, settings["lc_time"])  # date in correct language

    class _LocaleParserInfo(parser.parserinfo):
        WEEKDAYS = list(zip(calendar.day_abbr, calendar.day_name))
        MONTHS = list(zip(calendar.month_abbr, calendar.month_name))[1:]

    locale_parsers[country] = _LocaleParserInfo(dayfirst=settings["day_first"])
