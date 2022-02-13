import lxml.html
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time
from tracking.secrets import AMAZON_ID, AMAZON_PASSWORD
from windows.localization import TXT


class Amazon(Courier):
    name = "Amazon"
    idship_validation = r"^\d{3}\-\d{7}\-\d{7}$"
    idship_validation_msg = f"3 {TXT.digits}-7 {TXT.digits}-7 {TXT.digits}"

    def get_url_for_browser(self, idship):
        return True  # so that show button is displayed

    @Courier.driversToShow.get(page_load_timeout=10, wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    def login(self, idship, driver):
        self.log(f"driver LOGIN - {idship}")
        clickable = EC.element_to_be_clickable

        email_loc = '//input[@type="email"]'
        continue_loc = '//input[@id="continue"]'
        password_loc = '//input[@id="ap_password"]'
        identify_loc = '//input[@id="signInSubmit"]'

        email = driver.wait_for(email_loc, clickable)
        driver.execute_script(f"arguments[0].value = '{AMAZON_ID}';", email)

        continue_button = driver.find_element(By.XPATH, continue_loc)
        continue_button.click()

        password = driver.wait_for(password_loc, clickable)
        driver.execute_script(f"arguments[0].value = '{AMAZON_PASSWORD}';", password)

        identify = driver.wait_for(identify_loc, clickable)
        identify.click()

    def find_shipment(self, idship, driver):
        self.log(f"driver get ORDER - {idship}")

        url = f"https://www.amazon.fr/gp/your-account/order-history/ref=ppx_yo_dt_b_search?opt=ab&search={idship}"
        driver.get(url)

        login_loc = '//*[@id="nav-link-accountList"]'
        track_loc = '//*[contains(@class,"track-package-button")]'
        details_loc = '//*[contains(@class,"tracker-seeDetailsLink")]'
        events_loc = '//*[@id="tracking-events-container"]'

        # already logged in ?
        try:
            driver.find_element(By.XPATH, login_loc)

        except NoSuchElementException:
            self.login(idship, driver)

        track = driver.wait_for(track_loc, EC.element_to_be_clickable)
        track.click()

        self.log(f"driver get DETAILS - {idship}")
        details = driver.wait_for(details_loc, EC.element_to_be_clickable)
        details.click()

        self.log(f"driver get SHIPMENT - {idship}")
        driver.wait_for(events_loc, EC.visibility_of_element_located)

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        self.find_shipment(idship, driver)
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        product_loc = '//*[contains(@class,"tracking-event-carrier-header")]'
        by_day_loc = '//div[@id="tracking-events-container"]/div/div[@class="a-row"]'
        day_loc = './/div[contains(@class,"tracking-event-date-header")]'
        event_loc = './/div[contains(@class,"a-spacing-large")]'
        hour_loc = './/*[@class="tracking-event-time"]'
        label_loc = './/*[@class="tracking-event-message"]'
        status_loc = './/*[@class="tracking-event-location"]'

        product = self.get_txt(content, product_loc)
        for by_day in content.xpath(by_day_loc):
            day = self.get_txt(by_day, day_loc)
            for evt in by_day.xpath(event_loc):
                hour = self.get_txt(evt, hour_loc)
                events.append(
                    dict(
                        date=get_local_time(f"{day} {hour}", use_locale_parser=True),
                        label=self.get_txt(evt, label_loc),
                        status=self.get_txt(evt, status_loc).title(),
                    )
                )

        return events, dict(product=product)
