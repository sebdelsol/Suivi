from tracking.courier import Courier, RequestsHandler, get_local_time


class GLS(Courier):
    name = "GLS"

    def get_url_for_browser(self, idship):
        return f"https://gls-group.eu/FR/fr/suivi-colis.html?match={idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = f"https://gls-group.eu/app/service/open/rest/FR/fr/rstt001?match={idship}"
        r = request.request("GET", url)
        if r.status_code == 200:
            return r.json()
        return None

    def parse_content(self, content):
        events = []
        product = None
        fromto = None

        if shipments := content.get("tuStatus"):
            if len(shipments) > 0:
                shipment = shipments[0]
                if infos := shipment.get("infos"):
                    infos = dict((info["type"], info) for info in infos)
                    if product := infos.get("PRODUCT"):
                        product = product.get("value")

                        if weight := infos.get("WEIGHT"):
                            product += f" {weight.get('value')}"

                if timeline := shipment.get("history"):
                    countries = []

                    for event in timeline:
                        label = event["evtDscr"]
                        address = event["address"]

                        countries.append(address["countryCode"])
                        date = get_local_time(f"{event['date']} {event['time']}")
                        events.append(
                            dict(
                                date=date,
                                status=f"{address['city']}, {address['countryName']}",
                                label=label,
                            )
                        )

                    if len(countries) > 0:
                        fromto = f"{countries[-1]} {Courier.r_arrow}"
                        if len(countries) > 1:
                            fromto += countries[0]

        return events, dict(product=product, fromto=fromto)
