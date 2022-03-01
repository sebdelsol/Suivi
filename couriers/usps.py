import lxml.html
from dateutil.parser import ParserError
from selenium.webdriver.support import expected_conditions as EC
from tools.date_parser import get_local_time
from tracking.courier import Courier


class USPS(Courier):
    name = "USPS"
    timeline_xpath = '//div[contains(@id, "trackingHistory")]'

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

        spans = content.xpath(self.timeline_xpath + "//span")
        for span in spans:
            if txt := span.xpath("normalize-space()"):
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
