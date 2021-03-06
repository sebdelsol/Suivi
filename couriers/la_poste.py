from config import LAPOSTE_KEY
from tools.date_parser import get_local_time
from tracking.courier import Courier, get_sentences
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


def get_validation(_min, _max, _max2):
    return (
        rf"^(\w{{{_min},{_max}}})|(\d{{{_max2}}}\^)$",
        f"{TXT.from_} {_min} {TXT.to_} {_max} {TXT.letters} {TXT.or_} {TXT.digits}"
        f", {TXT.or_} {_max2} {TXT.digits} {TXT.and_} '^'",
    )


class LaPoste(Courier):
    name = "La Poste"
    idship_validation, idship_validation_msg = get_validation(11, 15, 18)

    headers = {"X-Okapi-Key": LAPOSTE_KEY, "Accept": "application/json"}

    codes = dict(
        DR1=("Déclaratif réceptionné", False),
        PC1=("Pris en charge", False),
        PC2=("Pris en charge dans le pays d’expédition", False),
        ET1=("En cours de traitement", False),
        ET2=("En cours de traitement dans le pays d’expédition", False),
        ET3=("En cours de traitement dans le pays de destination", False),
        ET4=("En cours de traitement dans un pays de transit", False),
        EP1=("En attente de présentation", False),
        DO1=("Entrée en Douane", False),
        DO2=("Sortie  de Douane", False),
        DO3=("Retenu en Douane", True),
        PB1=("Problème en cours", True),
        PB2=("Problème résolu", False),
        MD2=("Mis en distribution", False),
        ND1=("Non distribuable", True),
        AG1=("En attente d'être retiré au guichet", True),
        RE1=("Retourné à l'expéditeur", True),
        DI1=("Distribué", False),
        DI2=("Distribué à l'expéditeur", True),
    )

    def get_url_for_browser(self, idship):
        return f"https://www.laposte.fr/outils/suivre-vos-envois?code={idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = f"https://api.laposte.fr/suivi/v2/idships/{idship}?lang=fr_FR"
        return request.request_json("GET", url, headers=self.headers)

    def parse_content(self, content):
        events = []

        shipment = content.get("shipment")
        if shipment:
            product = shipment.get("product").capitalize()

            ctx = shipment.get("contextData")
            if ctx:
                fromto = (
                    f"{ctx['originCountry']}{Courier.r_arrow}{ctx['arrivalCountry']}"
                )
            else:
                fromto = None

            timeline = list(filter(lambda t: t["status"], shipment.get("timeline")))
            status_label = timeline[-1]["shortLabel"]
            if date := timeline[-1].get("date"):
                date = get_local_time(date)
                status_label += f" {date:{TXT.long_day_format}}"
            delivered = False

            for event in shipment.get("event", ()):
                code = event["code"]
                event_delivered = code in ("DI1", "DI2")
                delivered |= event_delivered

                status, warn = self.codes.get(code, "?")
                label = f"{get_sentences(event['label'])}"

                events.append(
                    dict(
                        date=get_local_time(event["date"]),
                        status=status,
                        warn=warn,
                        label=label,
                        delivered=event_delivered,
                    )
                )

            status_warn = events[-1]["warn"] if events else False
            return events, dict(
                product=product,
                fromto=fromto,
                delivered=delivered,
                status_warn=status_warn,
                status_label=status_label.replace(".", ""),
            )

        error = content.get("returnMessage", "Erreur")
        status_label = get_sentences(error)
        return events, dict(
            status_warn=True, status_label=status_label.replace(".", "")
        )
