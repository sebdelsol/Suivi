from tracking.courier import (
    Courier,
    RequestsHandler,
    get_local_time,
    get_simple_validation,
)
from windows.localization import TXT


class RelaisColis(Courier):
    name = "Relais Colis"
    idship_validation, idship_validation_msg = get_simple_validation(10, 16)
    url = "https://www.relaiscolis.com/suivi-de-colis/index/tracking/"

    def get_url_for_browser(self, idship):
        return "https://www.relaiscolis.com/suivi-de-colis/"

    @Courier.driversToShow.get()
    def open_in_browser(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)
        driver.execute_script(
            f'document.getElementById("valeur").value="{idship}";validationForm();'
        )

    @RequestsHandler()
    def get_content(self, idship, request):
        r = request.request(
            "POST", self.url, data={"valeur": idship, "typeRecherche": "EXP"}
        )
        if r.status_code == 200:
            return r.json()
        return None

    def parse_content(self, content):
        events = []
        product = None
        delivered = False

        shipment = content.get("Colis", {}).get("Colis")
        if shipment:
            vendor = shipment.get("Enseigne")
            if vendor:
                product = f"{TXT.package_product} {vendor.capitalize()}"

            timeline = shipment.get("ListEvenements", {}).get("Evenement", ())
            for event in timeline:
                status = None
                label = event["Libelle"]
                date = get_local_time(event["Date"])

                event_delivered = False
                if event.get("CodeJUS") == "LIV":
                    delivered = True
                    event_delivered = True
                    relais = content.get("Relais", {}).get("Relais")
                    if relais:
                        status = label
                        label = ", ".join(
                            txt
                            for k in ("Nom", "Adresse", "CodePostal", "Commune")
                            if (txt := relais.get(k)) is not None
                        )

                events.append(
                    dict(
                        date=date, status=status, label=label, delivered=event_delivered
                    )
                )

        return events, dict(product=product, delivered=delivered)
