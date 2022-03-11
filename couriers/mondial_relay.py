from tools.date_parser import get_local_time
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


class MondialRelay(Courier):
    name = "Mondial Relay"
    idship_validation = r"^\d{8}(\d{2})?(\d{2})?\-\d{5}$"
    idship_validation_msg = f"8, 10 {TXT.or_} 12 {TXT.digits}-{TXT.zipcode}"

    def get_url_for_browser(self, idship):
        number, zip_code = idship.split("-")
        return f"https://www.mondialrelay.fr/suivi-de-colis?numeroExpedition={number}&codePostal={zip_code}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        return request.request_tree("GET", url)

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//div[@class="infos-account"]')
        for events_by_days in timeline:
            elts = events_by_days.xpath("./div")
            date_text = elts[0].xpath(".//p//text()")[0]
            events_by_hours = elts[1].xpath("./div")

            for event in events_by_hours:
                elts = event.xpath("./div/p//text()")
                hour_text, label = elts[:2]
                date = get_local_time(
                    f"{date_text} {hour_text}", locale_country=TXT.locale_country_code
                )
                events.append(dict(date=date, label=label))

        return events, {}
