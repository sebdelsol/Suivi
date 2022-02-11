import lxml.html
from tracking.courier import Courier, RequestsHandler, get_local_time


class ColisPrive(Courier):
    name = "Colis Privé"

    def get_url_for_browser(self, idship):
        return f"https://www.colisprive.com/moncolis/pages/detailColis.aspx?numColis={idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        r = request.request("GET", url)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)
        return None

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//tr[@class="bandeauText"]')
        for event in timeline:
            date, label = event.xpath("./td/text()")
            events.append(dict(date=get_local_time(date), label=label.strip()))

        return events, {}
