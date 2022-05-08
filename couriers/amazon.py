from config import AMAZON_ID, AMAZON_PASSWORD
from tools.date_parser import get_local_time
from tracking.courier import Courier
from windows.localization import TXT


class Amazon(Courier):
    domain = None
    idship_validation = r"^\d{3}\-\d{7}\-\d{7}$"
    idship_validation_msg = f"3 {TXT.digits}-7 {TXT.digits}-7 {TXT.digits}"

    def get_url_for_browser(self, idship):
        return True  # so that show button is displayed

    @Courier.driversToShow.get(wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    def login(self, idship, driver):
        self.log(f"driver LOGIN - {idship}")

        email_loc = '//input[@type="email"]'
        email = driver.wait_for_clickable(email_loc)
        driver.execute_script(f"arguments[0].value = '{AMAZON_ID}';", email)

        continue_loc = '//input[@id="continue"]'
        continue_button = driver.xpath(continue_loc)
        continue_button.click()

        password_loc = '//input[@id="ap_password"]'
        password = driver.wait_for_clickable(password_loc)
        driver.execute_script(f"arguments[0].value = '{AMAZON_PASSWORD}';", password)

        identify_loc = '//input[@id="signInSubmit"]'
        identify = driver.wait_for_clickable(identify_loc)
        identify.click()

    def find_shipment(self, idship, driver):
        self.log(f"driver get ORDER - {idship}")

        url = (
            f"https://www.amazon.{self.domain}/gp/your-account/order-history/"
            f"ref=ppx_yo_dt_b_search?opt=ab&search={idship}"
        )
        driver.get(url)

        # already logged in ?
        login_loc = '//*[@id="nav-link-accountList"]'
        if not driver.xpath(login_loc, safe=True):
            self.login(idship, driver)

        track_loc = '//*[contains(@class,"track-package-button")]'
        track = driver.wait_for_clickable(track_loc)
        track.click()

        self.log(f"driver get DETAILS - {idship}")
        details_loc = '//*[contains(@class,"tracker-seeDetailsLink")]'
        details = driver.wait_for_clickable(details_loc)
        details.click()

        self.log(f"driver get SHIPMENT - {idship}")
        events_loc = '//*[@id="tracking-events-container"]'
        driver.wait_for_visibility(events_loc)

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        self.find_shipment(idship, driver)
        return driver.page_source

    def parse_content(self, content):
        events = []

        product_loc = '//*[contains(@class,"tracking-event-carrier-header")]'
        by_day_loc = '//div[@id="tracking-events-container"]/div/div[@class="a-row"]'
        product = self.get_txt(content, product_loc)
        for by_day in content.xpath(by_day_loc):
            day_loc = './/div[contains(@class,"tracking-event-date-header")]'
            event_loc = './/div[contains(@class,"a-spacing-large")]'
            day = self.get_txt(by_day, day_loc)
            for evt in by_day.xpath(event_loc):
                hour_loc = './/*[@class="tracking-event-time"]'
                label_loc = './/*[@class="tracking-event-message"]'
                status_loc = './/*[@class="tracking-event-location"]'
                hour = self.get_txt(evt, hour_loc)
                events.append(
                    dict(
                        date=get_local_time(
                            f"{day} {hour}", locale_country=self.domain
                        ),
                        label=self.get_txt(evt, label_loc),
                        status=self.get_txt(evt, status_loc).title(),
                    )
                )

        return events, dict(product=product)


class AmazonFr(Amazon):
    name = "Amazon.fr"
    domain = "fr"


class AmazonIt(Amazon):
    name = "Amazon.it"
    domain = "it"
