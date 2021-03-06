from tools.date_parser import get_utc_from_timestamp
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler


class Asendia(Courier):
    name = "Asendia"
    fromto = f"CN{Courier.r_arrow}FR"
    headers = {"Content-Type": "application/json", "Accept-Language": "fr"}
    url = "https://tracking.asendia.com/alliot/items/references"

    def get_url_for_browser(self, idship):
        return f"https://tracking.asendia.com/tracking/{idship}"

    @RequestsHandler(max_retry=1)
    def get_content(self, idship, request):
        return request.request_json(
            "POST",
            self.url,
            json={"criteria": [idship], "shipped": False},
            headers=self.headers,
        )

    def parse_content(self, content):
        events = []

        timeline = content[0]["events"]
        for event in timeline:
            label = event["translatedLabelBC"]
            location = event["location"]["name"]

            if label and location:
                country = event["location"]["countryCode"]
                if country not in location:
                    location = ", ".join((location, country))

                date = get_utc_from_timestamp(event["date"] / 1000)

                events.append(dict(date=date, status=location, label=label))

        return events, {}
