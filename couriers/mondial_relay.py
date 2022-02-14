import lxml.html
from tracking.courier import Courier, RequestsHandler, get_local_time
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
        r = request.request("GET", url)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)
        return None

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
                    f"{date_text} {hour_text}", use_locale_parser=True
                )
                events.append(dict(date=date, label=label))

        return events, {}
