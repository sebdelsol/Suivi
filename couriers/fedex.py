from retry import retry
from tools.actions_chain import EnhancedActionChains
from tools.date_parser import get_local_time
from tracking.courier import Courier, CourierRetryError
from windows.localization import TXT


class Fedex(Courier):
    name = "Fedex"

    idship_validation = r"^\d{12}(-\d{1})?$"
    idship_validation_msg = f"12 {TXT.digits}[-{TXT.digit}]"
    url = "https://www.fedex.com/fr-fr/home.html"

    def get_url_for_browser(self, idship):
        return True  # so that show button is displayed

    @Courier.driversToShow.get(wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    @retry(CourierRetryError, tries=2, delay=5, jitter=(0, 1))
    def find_shipment(self, idship, driver):
        if "-" in idship:
            idship, track_n = idship.split("-")
        else:
            track_n = 0

        driver.get(self.url)
        action = EnhancedActionChains(driver)

        self.log(f"driver check RGPD - {idship}")
        rgpd_loc = '//button[contains(@class,"cookie-consent__accept")]'
        if rgpd := driver.wait_for_clickable(rgpd_loc, timeout=1, safe=True):
            action.rnd_pause(1).move_to_element(rgpd).click().perform()

        form = '//div[@class="fxg-app__single-tracking"]'

        self.log(f"driver fill FORM - {idship}")
        form_input_loc = f"{form}//input"
        form_input = driver.wait_for_clickable(form_input_loc)
        action.reset_actions()
        action.rnd_pause(1).move_to_element(form_input).click()
        action.rnd_pause(3).send_keys_1by1(idship).perform()

        self.log(f"driver submit FORM - {idship}")
        submit_locator = f'{form}//button[@type="submit"]'
        submit = driver.xpath(submit_locator)
        action.reset_actions()
        action.rnd_pause(3).move_to_element(submit).click().perform()

        self.log(f"driver TRK - {idship}")
        tracking_dups = '//div[@class="wtrk-wrapper"]'
        tracking_regular = "//trk-shared-shipment-identifier"
        driver.wait_for_visibility((tracking_dups, tracking_regular))

        if "system-error" in driver.current_url:
            self.log(f"driver ERROR - {driver.current_url}", error=True)
            raise CourierRetryError

        if "duplicate-results" in driver.current_url:
            self.log(f"driver get DUPS #{track_n} - {idship}")
            duplicate_locator = '//div[@role="alert"]/following-sibling::ul//a'
            dup_link = driver.xpath(duplicate_locator)
            action.reset_actions()
            action.rnd_pause(2).move_to_element(dup_link).click().perform()

            dups_loc = '//app-duplicate-results//button[@class="button-link"]'
            dup_n_loc = f"({dups_loc})[{int(track_n) + 1}]"
            dup_n = driver.wait_for_clickable(dup_n_loc)
            dup_n.click()

        else:
            details_loc = '//a[@id="seeFullDetails"]'
            details = driver.wait_for_clickable(details_loc)
            details.click()

    # do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=60)
    def get_content(self, idship, driver):
        self.find_shipment(idship, driver)
        history_loc = "//trk-shared-travel-history"
        driver.wait_for_presence(history_loc)
        return driver.page_source

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
            if attrib_class := tr.attrib.get("class"):
                if "scan-event-date-row" in attrib_class:
                    day = self.get_txt(tr, time_loc)

                elif "scan-event-details-row" in attrib_class:
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
