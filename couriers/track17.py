import lxml.html
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time, get_sentences
from windows.localization import TXT


class Track17(Courier):
    name = "Track17"
    idship_validation = r".+"
    idship_validation_msg = TXT.no_validation

    timeline_loc = '//*[@class="ori-block"]/dd'

    def get_url_for_browser(self, idship):
        return f"https://t.17track.net/fr#nums={idship}"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)
        self.log(f"driver WAIT timeline - {idship}")
        driver.wait_for(self.timeline_loc, EC.visibility_of_element_located)
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        timeline = content.xpath(self.timeline_loc)
        for event in timeline:
            date = self.get_txt(event, ".//time")
            label = self.get_txt(event, ".//p")
            events.append(dict(date=get_local_time(date), label=get_sentences(label)))

        return events, {}
