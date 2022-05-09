from tools.date_parser import get_local_time
from tracking.courier import Courier, get_simple_validation
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


class EMS(Courier):
    name = "EMS"
    idship_validation, idship_validation_msg = get_simple_validation(13)

    def get_url_for_browser(self, idship):
        return (
            f"https://items.ems.post/api/publicTracking/track?"
            f"language={TXT.locale_country_code.upper()}&itemId={idship}"
        )

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        return request.request_tree("GET", url)

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//tr[@class="result-table-row"]')
        for event in timeline:
            infos = event.xpath("./td/text()")

            events.append(
                dict(
                    date=get_local_time(
                        infos[0], locale_country=TXT.locale_country_code
                    ),
                    status=infos[2] if len(infos) == 3 else None,
                    label=infos[1],
                )
            )

        return events, {}
