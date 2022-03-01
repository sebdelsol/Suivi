import lxml.html
from tools.date_parser import get_local_time
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler


class NLPost(Courier):
    name = "NL Post"

    def get_url_for_browser(self, idship):
        return f"https://postnl.post/Details?barcode={idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        r = request.request("GET", url)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)
        return None

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//tr[@class="first detail"]') + content.xpath(
            '//tr[@class="detail"]'
        )
        for event in timeline:
            date, label = event.xpath("./td/text()")[:2]

            events.append(
                dict(
                    date=get_local_time(date.strip()),
                    label=label,
                )
            )

        return events, {}
