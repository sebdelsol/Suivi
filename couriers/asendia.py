from datetime import datetime

import pytz
from tracking.courier import Courier, RequestsHandler


class Asendia(Courier):
    name = "Asendia"
    fromto = f"CN{Courier.r_arrow}FR"
    headers = {"Content-Type": "application/json", "Accept-Language": "fr"}
    url = "https://tracking.asendia.com/alliot/items/references"

    def get_url_for_browser(self, idship):
        return f"https://tracking.asendia.com/tracking/{idship}"

    @RequestsHandler(max_retry=1)
    def get_content(self, idship, request):
        r = request.request(
            "POST",
            self.url,
            json={"criteria": [idship], "shipped": False},
            headers=self.headers,
        )
        if r.status_code == 200:
            return r.json()
        return None

    def parse_content(self, content):
        events = []

        timeline = content[0]["events"]
        for event in timeline:
            label = event["translatedLabelBC"]
            location = event["location"]["name"]

            if label and location:
                # location = location.replace("Hong Kong", "HK")
                country = event["location"]["countryCode"]

                if country not in location:
                    location = ", ".join((location, country))

                date = datetime.utcfromtimestamp(event["date"] / 1000).replace(
                    tzinfo=pytz.utc
                )

                events.append(dict(date=date, status=location, label=label))

        return events, {}
