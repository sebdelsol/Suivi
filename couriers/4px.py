# module name is ok since it's auto-imported with import_module
# pylint: disable=invalid-name
import re

import lxml.html
from tracking.courier import Courier, RequestsHandler, get_local_time


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
                for txt in event.xpath(".//text()")
                if (stxt := re.sub(r"[\n\t]", "", txt).strip().replace("\xa0", ""))
                != ""
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
