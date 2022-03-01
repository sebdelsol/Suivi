import re
import webbrowser

from windows.localization import TXT
from windows.log import log

from .drivers import DriversToScrape, DriversToShow

# auto register all Courier subclasses
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


class Courier:
    driversToShow = DriversToShow()
    driversToScrape = DriversToScrape()
    r_arrow = "→"
    fromto = None
    idship_validation, idship_validation_msg = get_simple_validation(8, 20)

    delivered_searchs = (
        r"(?<!be )delivered",
        r"final delivery",
        r"(?<!être )livré",
        r"(?<!être )distribué",
        r"mis à disposition",
        r"livraison effectuée",
        r"est disponible dans",
        r"consegnato",
    )

    error_words = ("error", "erreur")

    subs = (
        (r"[\(\[].*?[\)\]]", ""),  # remove () and []
        (r"[\.\,]$", ""),  # remove ending '.' or ','
        (r" +", " "),  # remove extra spaces
        (r"[\n\r]", ""),  # remove line return
        (r"^\W", ""),  # remove leading non alphanumeric char
        (r"(\w):(\w)", r"\1: \2"),  # add space after ':'
    )

    additional_subs = ()

    name = None

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
            re.compile(pattern).search for pattern in self.delivered_searchs
        ]

        self.subs = self.additional_subs + self.subs
        self.subs = [
            (re.compile(pattern).sub, replace) for (pattern, replace) in self.subs
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

    def get_url_for_browser(self, idship):
        raise NotImplementedError("get_url_for_browser method is missing")

    def parse_content(self, content):
        raise NotImplementedError("parse_content method is missing")

    def get_content(self, idship):
        raise NotImplementedError("parse_content method is missing")

    @staticmethod
    def get_txt(elt, xpath):
        try:
            return elt.xpath(xpath)[0].xpath("normalize-space()")

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

    def update(self, idship):
        if not self.name:
            log(f"courier {type(self).__name__} miss a name", error=True)
            return None

        if not self.validate_idship(idship):
            self.log(
                f"invalid tracking number {idship}, ({self.idship_validation_msg})",
                error=True,
            )
            return None

        self.log(f"LOAD - {idship}")

        events = []
        infos = {}
        content = self.get_content(idship)

        if ok := content is not None:
            self.log(f"PARSE - {idship}")
            if result := self.parse_content(content):
                events, infos = result

        # remove duplicate events while keeping insertion order, won't work with a set
        events = {tuple(evt.items()): evt for evt in events}.values()

        # sort by date
        events = sorted(events, key=lambda evt: evt["date"], reverse=True)

        # add couriers and check for delivery & errors events
        delivered = infos.get("delivered", False)
        for event in events:
            event["courier"] = self.name
            event["status"] = event.get("status") or ""

            # clean label
            for sub, replace in self.subs:
                event["label"] = sub(replace, event["label"].strip())
                event["status"] = sub(replace, event["status"].strip())

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

        if not (events or infos.get("status_label")):
            ok = False

        status_date = infos.get("status_date", events[0]["date"] if events else None)
        status_label = infos.get(
            "status_label", events[0]["label"] if events else TXT.status_error
        )
        status_warn = infos.get("status_warn", not events)

        status = dict(
            date=status_date,
            ok_date=status_date if ok else None,
            label=get_sentences(status_label),
            warn=status_warn,
            delivered=delivered,
        )

        return dict(
            ok=ok,
            product=infos.get("product"),
            idship=idship,
            fromto=infos.get("fromto", self.fromto),
            status=status,
            events=events,
        )
