from tracking.courier import (
    Courier,
    RequestsHandler,
    get_local_time,
    get_sentence,
    get_simple_validation,
)
from tracking.secrets import LAPOSTE_KEY
from windows.localization import TXT


class LaPoste(Courier):
    name = "La Poste"
    idship_validation, idship_validation_msg = get_simple_validation(11, 15)
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
        r = request.request("GET", url, headers=self.headers)
        if r.status_code == 200:
            return r.json()
        return None

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

            timeline = list(filter(lambda t: t["shortLabel"], shipment.get("timeline")))
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
                label = f"{get_sentence(event['label'], 1)}"

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
        status_label = get_sentence(error, 1)
        return events, dict(
            status_warn=True, status_label=status_label.replace(".", "")
        )
