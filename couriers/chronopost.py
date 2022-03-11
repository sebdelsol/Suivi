from tools.date_parser import get_local_time
from tracking.courier import Courier
from windows.localization import TXT


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
        driver.wait_for_presence_of_all(self.timeline_xpath)

        return driver.page_source

    def parse_content(self, content):
        events = []

        for tr in content.xpath(self.timeline_xpath):
            tds = tr.xpath("./td")
            day, hour = tds[0].xpath("./text()")
            location, label = tds[1].xpath("./text()")
            date = get_local_time(
                f"{day} {hour}", locale_country=TXT.locale_country_code
            )
            location = location.replace("...", "").strip()
            events.append(dict(date=date, status=location, label=label))

        return events, {}
