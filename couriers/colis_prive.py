from tools.date_parser import get_local_time
from tracking.courier import Courier, get_sentences
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


class ColisPrive(Courier):
    name = "Colis Privé"

    def get_url_for_browser(self, idship):
        return f"https://www.colisprive.com/moncolis/pages/detailColis.aspx?numColis={idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        return request.request_tree("GET", url)

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//tr[@class="bandeauText"]')
        for event in timeline:
            date, label = event.xpath("./td/text()")
            label = get_sentences(label)
            events.append(
                dict(
                    date=get_local_time(date, locale_country=TXT.locale_country_code),
                    label=label.strip(),
                )
            )

        return events, {}
