# weird module name is ok since it's auto-imported with import_module
# pylint: disable=invalid-name

import lxml.html
from tools.date_parser import get_local_time
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler


class FourPX(Courier):
    name = "4PX"

    def get_url_for_browser(self, idship):
        return f"http://track.4px.com/query/{idship}?"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        r = request.request("GET", url)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)
        return None

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//div[@class="track-container"]//li')
        for event in timeline:
            date, hour, label = [
                stxt
                for txt in event.xpath(".//*")
                if (stxt := txt.xpath("normalize-space()")) != ""
            ]
            status, label = label.split("/", 1) if "/" in label else ("", label)

            events.append(
                dict(
                    date=get_local_time(f"{date} {hour}"),
                    status=status.strip(),
                    label=label.strip(),
                )
            )

        return events, {}
