import re
import webbrowser
from abc import ABC, abstractmethod

from windows.localization import TXT
from windows.log import log

from .drivers_handler import DriversToScrape, DriversToShow

# auto register all Courier subclasses, check Courier.__init_subclass__
Couriers_classes = []


def get_sentences(txt, n=1):
    return "".join(re.split(r"[.!]", txt)[:n])


def get_simple_validation(_min, _max=None):
    if _max is None:
        return rf"^\w{{{_min}}}$", f"{_min} {TXT.letters} {TXT.or_} {TXT.digits}"

    return (
        rf"^\w{{{_min},{_max}}}$",
        f"{TXT.from_} {_min} {TXT.to_} {_max} {TXT.letters} {TXT.or_} {TXT.digits}",
    )


class Courier(ABC):
    driversToShow = DriversToShow()
    driversToScrape = DriversToScrape()
    r_arrow = "→"
    fromto = None
    idship_validation, idship_validation_msg = get_simple_validation(8, 20)
    name = None

    error_words = ("error", "erreur")

    delivered_searchs = (
        r"(?<!be )delivered",
        r"final delivery",
        r"(?<!être )livré",
        r"(?<!être )distribué",
        r"mis à disposition",
        r"livraison effectuée",
        r"est disponible dans",
        r"consegnato",
        r"Arrival at the Destination",
    )
    additional_delivered_searchs = ()

    subs = (
        (r"[\(\[].*?[\)\]]", ""),  # remove () and []
        (r"[\.\,]$", ""),  # remove ending '.' or ','
        (r"\xa0", " "),  # non breaking space
        (r" +", " "),  # remove extra spaces
        (r"[\n\r]", ""),  # remove line return
        (r"^\W", ""),  # remove leading non alphanumeric char
        (r"(\w):(\w)", r"\1: \2"),  # add space after ':'
    )
    additional_subs = ()

    def __init_subclass__(cls):
        """register subclasses"""
        if cls.name:
            Couriers_classes.append(cls)

    @classmethod
    def set_max_scrape_drivers(cls, max_drivers):
        cls.driversToScrape.set_max_drivers(max_drivers)

    def __init__(self):
        # compile re
        self.idship_validation = re.compile(self.idship_validation).match
        self.delivered_searchs = [
            re.compile(pattern.lower()).search
            for pattern in self.additional_delivered_searchs + self.delivered_searchs
        ]
        self.subs = [
            (re.compile(pattern).sub, replace)
            for (pattern, replace) in self.additional_subs + self.subs
        ]

    def log(self, *args, **kwargs):
        args = list(args)
        args[0] = f"{args[0]}, {self.name}"
        log(*args, **kwargs)

    def validate_idship(self, idship):
        return self.idship_validation(idship)

    def open_in_browser(self, idship):
        if url := self.get_url_for_browser(idship):
            webbrowser.open(url)

    @abstractmethod
    def get_url_for_browser(self, idship):
        pass

    @abstractmethod
    def parse_content(self, content):
        pass

    @abstractmethod
    def get_content(self, idship):
        pass

    @staticmethod
    def get_txt(elt, xpath, index=0):
        try:
            return elt.xpath(xpath)[index].xpath("normalize-space()")

        except IndexError:
            return None

    @staticmethod
    def clean_txt(elt, xpath):
        try:
            return " ".join(
                txt_clean
                for txt in elt.xpath(xpath)
                if (txt_clean := txt.replace("\n", "").strip())
            )

        except IndexError:
            return None

    def _apply_subs(self, txt):
        for sub, replace in self.subs:
            txt = sub(replace, txt.strip())
        return txt

    def _update_events(self, events):
        delivered = False

        # remove duplicate events while keeping insertion order, won't work with a set
        events = {tuple(evt.items()): evt for evt in events}.values()

        # sort by date
        events = sorted(events, key=lambda evt: evt["date"], reverse=True)

        for event in events:
            event["courier"] = self.name
            event["status"] = event.get("status") or ""

            # clean label
            event["label"] = self._apply_subs(event["label"])
            event["status"] = self._apply_subs(event["status"])

            # delivered ?
            whole_txt = " ".join((event["status"], event["label"]))
            event["delivered"] = event.get("delivered", False) or any(
                search(whole_txt.lower()) for search in self.delivered_searchs
            )

            if event["delivered"]:
                delivered = True

            # warn ?
            event["warn"] = event.get("warn", False) or any(
                error_word in whole_txt.lower() for error_word in self.error_words
            )
        return events, delivered

    def _update_status(self, infos, ok, events, delivered):
        delivered = infos.get("delivered", False) or delivered

        if not (events or infos.get("status_label")):
            ok = False

        if events:
            last_event = events[0]
            default_status_date = last_event["date"]
            default_status_label = last_event["label"]
            default_status_warn = last_event.get("warn", False)

        else:
            default_status_date = None
            default_status_label = TXT.status_error
            default_status_warn = True

        status_date = infos.get("status_date", default_status_date)
        status_label = infos.get("status_label", default_status_label)
        status_warn = infos.get("status_warn", default_status_warn)

        return ok, dict(
            date=status_date,
            ok_date=status_date if ok else None,
            label=get_sentences(self._apply_subs(status_label)),
            warn=status_warn,
            delivered=delivered,
        )

    def update(self, idship):
        if not self.validate_idship(idship):
            self.log(
                f"invalid tracking number {idship}, ({self.idship_validation_msg})",
                error=True,
            )
            return None

        events = []
        infos = {}
        self.log(f"GET - {idship}")
        content = self.get_content(idship)

        if ok := content is not None:
            self.log(f"PARSE - {idship}")
            if result := self.parse_content(content):
                events, infos = result

        events, delivered = self._update_events(events)
        ok, status = self._update_status(infos, ok, events, delivered)

        return dict(
            ok=ok,
            product=infos.get("product"),
            idship=idship,
            fromto=infos.get("fromto", self.fromto),
            status=status,
            events=events,
        )
