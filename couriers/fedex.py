import random
import time

from selenium.webdriver.common.action_chains import ActionChains
from tools.date_parser import get_local_time
from tracking.courier import Courier
from windows.localization import TXT


class Fedex(Courier):
    name = "Fedex"

    idship_validation = r"^\d{12}(-\d{1})?$"
    idship_validation_msg = f"12 {TXT.digits}[-{TXT.digit}]"

    def get_url_for_browser(self, idship):
        return True  # so that show button is displayed

    @Courier.driversToShow.get(wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    @staticmethod
    def get_idship_track_no(idship):
        track_no = 0
        if "-" in idship:
            idship, track_no = idship.split("-")
        return idship, int(track_no)

    def send_keys_one_by_one(self, driver, elt_loc, txt):
        elt = driver.wait_for_clickable(elt_loc)
        for t in txt:
            elt.send_keys(t)
            self.rnd_wait(0.2)

    @staticmethod
    def rnd_wait(wait):
        time.sleep(random.uniform(wait * 0.5, wait))

    def find_shipment(self, idship, driver):
        idship, track_no = self.get_idship_track_no(idship)

        for _ in range(2):
            action = ActionChains(driver)
            url = "https://www.fedex.com/fr-fr/home.html"
            driver.get(url)

            self.log(f"driver check RGPD - {idship}")
            rgpd_loc = '//button[contains(@class,"cookie-consent__accept")]'
            if rgpd := driver.wait_for_clickable(rgpd_loc, timeout=1, safe=True):
                self.rnd_wait(1)
                action.move_to_element(rgpd).click().perform()

            form = '//div[@class="fxg-app__single-tracking"]'

            self.log(f"driver fill FORM - {idship}")
            input_loc = f"{form}//input"
            input_ = driver.wait_for_clickable(input_loc)
            self.rnd_wait(1)
            action.reset_actions()
            action.move_to_element(input_).click().perform()
            self.rnd_wait(3)
            self.send_keys_one_by_one(driver, input_loc, idship)

            self.log(f"driver submit FORM - {idship}")
            submit_locator = f'{form}//button[@type="submit"]'
            submit = driver.xpath(submit_locator)
            action.reset_actions()
            self.rnd_wait(1)
            action.move_to_element(submit).click().perform()

            self.log(f"driver TRK - {idship}")
            tracking_loc = '//div[@class="wtrk-wrapper"]'
            driver.wait_for_presence_of_all(tracking_loc)

            print(driver.current_url)
            if "system-error" in driver.current_url:
                driver.reconnect(5)

            else:
                break
        else:
            return False

        if "duplicate-results" in driver.current_url:
            self.log(f"driver handle DUPS - {idship}")
            duplicate_locator = '//div[@role="alert"]/following-sibling::ul//a'
            dup_link = driver.xpath(duplicate_locator)
            dup_link.click()

            dups_loc = '//app-duplicate-results//button[@class="button-link"]'
            dups = driver.wait_for_presence_of_all(dups_loc)
            dups[track_no].click()

        return True

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=40)
    def get_content(self, idship, driver):
        self.log(f"driver wait TIMELINE - {idship}")
        if self.find_shipment(idship, driver):
            history_loc = "//trk-shared-travel-history"
            driver.wait_for_presence(history_loc)
            return driver.page_source
        return None

    def parse_content(self, content):
        events = []

        details_loc = "//trk-shared-key-value-list//li/div"
        if product := self.get_txt(content, details_loc, 1):
            if weight := self.get_txt(content, details_loc, 3):
                product = f"{product} { weight}"

        day = ""
        time_loc = './/td[@headers="time_header"]'
        status_loc = './/td[@headers="location_header"]'
        label_loc = './/td[@headers="status_header"]'

        timeline_loc = '//table[@class="travel-history-table full-width"]//tr'
        for tr in content.xpath(timeline_loc):
            if cls := tr.attrib.get("class"):
                if "scan-event-date-row" in cls:
                    day = self.get_txt(tr, time_loc)

                elif "scan-event-details-row" in cls:
                    hour = self.get_txt(tr, time_loc)
                    date = f"{day} {hour}"
                    date = get_local_time(date, locale_country=TXT.locale_country_code)
                    events.append(
                        dict(
                            date=date,
                            status=self.get_txt(tr, status_loc),
                            label=self.get_txt(tr, label_loc),
                        )
                    )

        return events, dict(product=product)
