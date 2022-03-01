import lxml.html
from tools.date_parser import get_local_time
from tracking.courier import Courier
from tracking.requests_handler import RequestsHandler
from windows.localization import TXT


class DPD(Courier):
    name = "DPD"
    additional_subs = ((r"Predict vous informe : \n", ""), (r"Instruction :", ""))

    def get_url_for_browser(self, idship):
        return f"https://trace.dpd.fr/fr/trace/{idship}"

    @RequestsHandler()
    def get_content(self, idship, request):
        url = self.get_url_for_browser(idship)
        r = request.request("GET", url)
        if r.status_code == 200:
            return lxml.html.fromstring(r.content)
        return None

    def parse_content(self, content):
        events = []

        infos = content.xpath('//ul[@class="tableInfosAR"]//text()')
        infos = [info for info in infos if info.replace("\n", "").strip() != ""]
        infos = dict((k, v) for k, v in zip(infos[::2], infos[1::2]))
        product = TXT.package_product
        if weight := infos.get("Poids du colis"):
            product += f" {weight}"

        timeline = content.xpath('//tr[contains(@id, "ligneTableTrace")]')
        for evt in timeline:
            txts = [
                stxt for txt in evt.xpath("./td//text()") if (stxt := txt.strip()) != ""
            ]
            date, hour, label = txts[:3]
            location = txts[3] if len(txts) == 4 else None

            events.append(
                dict(
                    date=get_local_time(f"{date} {hour}"),
                    status=location,
                    label=label,
                )
            )

        return events, dict(product=product)
