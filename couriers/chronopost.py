import lxml.html
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time


class Chronopost(Courier):
    name = "Chronopost"
    timeline_xpath = '//tr[@class="toggleElmt show"]'

    # use La Poste API to find out the url
    def get_url_for_browser(self, idship):
        return f"https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT={idship}"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=10)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)
        self.log(f"driver WAIT timeline - {idship}")
        timeline_locator = (By.XPATH, self.timeline_xpath)
        driver.wait_until(EC.presence_of_all_elements_located(timeline_locator))
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        for tr in content.xpath(self.timeline_xpath):
            tds = tr.xpath("./td")
            day, hour = tds[0].xpath("./text()")
            location, label = tds[1].xpath("./text()")
            day = day.split(" ", 1)[1]  # remove full day name
            date = get_local_time(f"{day} {hour}")
            location = location.replace("...", "").strip()
            events.append(dict(date=date, status=location, label=label))

        return events, {}
