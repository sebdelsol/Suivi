import re

from tools.date_parser import get_local_time
from tracking.courier import Courier
from windows.localization import TXT


class CanadaPost(Courier):
    name = "Canada Post"

    idship_validation = r"^\d{16}$|^\w{2}\d{9}\w{2}$"
    idship_validation_msg = (
        f"16 {TXT.digits} {TXT.or_} 2 {TXT.letters} 9 {TXT.digits} 2 {TXT.letters}"
    )

    def get_url_for_browser(self, idship):
        return (
            f"https://www.canadapost-postescanada.ca/track-reperage/"
            f"{TXT.locale_country_code}#/details/{idship}"
        )

    @Courier.driversToShow.get(wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        driver.get(self.get_url_for_browser(idship))

    # do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=60)
    def get_content(self, idship, driver):
        driver.get(self.get_url_for_browser(idship))
        history_loc = "//app-track-delivery-results"
        driver.wait_for_presence(history_loc)
        return driver.page_source

    def parse_content(self, content):
        events = []

        product = self.get_txt(content, "//track-service-type").split(":")[-1].strip()

        day = ""
        timeline_loc = '//tr[@id="progressRow"]'

        for tr in content.xpath(timeline_loc):
            day = self.get_txt(tr, ".//td", 0) or day
            hour = self.get_txt(tr, ".//td", 1)
            label = self.get_txt(tr, ".//td", 2)

            hour = re.sub(r"\s?h\s?", "h", hour)
            date = f"{day} {hour}"
            date = get_local_time(date, locale_country=TXT.locale_country_code)
            label = label.split("Plus de renseignements")[0].strip()

            events.append(dict(date=date, label=label))

        return events, dict(product=product)
