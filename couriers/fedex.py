import json

from tools.date_parser import get_local_time
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


class Fedex(Courier):
    name = "Fedex"

    idship_validation = r"^\d{12}(-\d{1})?$"
    idship_validation_msg = f"12 {TXT.digits}[-{TXT.digit}]"

    url = "https://www.fedex.com/trackingCal/track"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/59.0.3071.115 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.fedex.com/apps/fedextrack/?tracknumbers=&locale=fr_FR",
    }

    def get_url_for_browser(self, idship):
        if "-" in idship:
            idship = idship.split("-")[0]
        return f"https://www.fedex.com/fedextrack/?trknbr={idship}"

    @RequestsHandler(request_timeout=20)
    def get_content(self, idship, request):

        if "-" in idship:
            idship, track_no = idship.split("-")

        else:
            track_no = 0

        json_data = {
            "TrackPackagesRequest": {
                "appType": "WTRK",
                "appDeviceType": "DESKTOP",
                "uniqueKey": "",
                "processingParameters": {},
                "trackingInfoList": [
                    {
                        "trackNumberInfo": {
                            "trackingNumber": idship,
                            "trackingQualifier": "",
                            "trackingCarrier": "",
                        }
                    }
                ],
            }
        }

        data = {
            "action": "trackpackages",
            "data": json.dumps(json_data),
            "format": "json",
            "locale": "fr_FR",
            "version": "1",
        }

        r_json = request.request_json("POST", self.url, headers=self.headers, data=data)
        return r_json, int(track_no)

    def parse_content(self, content):
        events = []

        json_content, track_no = content
        package = json_content["TrackPackagesResponse"]["packageList"][track_no]

        if product := package.get("trackingCarrierDesc"):
            if weight := package.get("displayPkgKgsWgt"):
                product += f" {weight}"

        from_ = package.get("shipperCntryCD", "")
        to_ = package.get("recipientCntryCD", "")
        if from_ or to_:
            fromto = f"{from_}{Courier.r_arrow}{to_}"

        else:
            fromto = None

        status_label = package.get("statusWithDetails")

        timeline = package["scanEventList"]
        for event in timeline:
            day = event["date"]
            hour = event["time"]
            offset = event["gmtOffset"]

            events.append(
                dict(
                    date=get_local_time(f"{day} {hour} {offset}"),
                    label=event["status"],
                    status=event["scanLocation"],
                    delivered=event["isDelivered"],
                    warn=event["isClearanceDelay"]
                    or event["isDelException"]
                    or event["isException"],
                )
            )

        return events, dict(product=product, fromto=fromto, status_label=status_label)
