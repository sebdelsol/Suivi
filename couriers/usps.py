import re

import lxml.html
from dateutil.parser import ParserError
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time


class USPS(Courier):
    name = "USPS"
    timeline_xpath = '//div[contains(@id, "trackingHistory")]'

    @staticmethod
    def clean(txt):
        txt = txt.replace("\xa0", " ")
        return re.sub(r"[\n\t]+", " ", txt).strip()

    def get_url_for_browser(self, idship):
        return f"https://tools.usps.com/go/TrackConfirmAction?tLabels={idship}"

    @Courier.driversToScrape.get(wait_elt_timeout=10)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)
        self.log(f"driver WAIT timeline - {idship}")
        driver.wait_for(self.timeline_xpath, EC.presence_of_all_elements_located)

        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        txts = content.xpath(self.timeline_xpath + "//span//text()")
        for txt in txts:
            txt = self.clean(txt)
            if txt:
                try:
                    # is it a date ?
                    date = get_local_time(txt)
                    event = dict(date=date)
                    events.append(event)

                except ParserError:
                    # not a date, it's either a label then a status, skip everything after
                    if event:
                        if event.setdefault("label", txt) != txt:
                            event.setdefault("status", txt)

        return events, {}
