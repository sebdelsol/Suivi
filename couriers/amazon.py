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
        return True

    @Courier.driversToShow.get(page_load_timeout=10, wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    def login(self, idship, driver):
        self.log(f"driver LOGIN - {idship}")
        email = driver.wait_for('//input[@type="email"]', EC.element_to_be_clickable)
        driver.execute_script(f"arguments[0].value = '{AMAZON_ID}';", email)

        continue_loc = (By.XPATH, '//input[@id="continue"]')
        continue_button = driver.find_element(*continue_loc)
        continue_button.click()

        password = driver.wait_for(
            '//input[@id="ap_password"]', EC.element_to_be_clickable
        )
        driver.execute_script(f"arguments[0].value = '{AMAZON_PASSWORD}';", password)

        identify_button = driver.wait_for(
            '//input[@id="signInSubmit"]', EC.element_to_be_clickable
        )
        identify_button.click()

    def find_shipment(self, idship, driver):
        self.log(f"driver get ORDER - {idship}")
        driver.get(
            f"https://www.amazon.fr/gp/your-account/order-history/ref=ppx_yo_dt_b_search?opt=ab&search={idship}"
        )

        # already logged in ?
        try:
            driver.find_element(By.XPATH, '//*[@id="nav-link-accountList"]')

        except NoSuchElementException:
            self.login(idship, driver)

        track_button = driver.wait_for(
            '//*[contains(@class,"track-package-button")]', EC.element_to_be_clickable
        )
        track_button.click()

        self.log(f"driver get DETAILS - {idship}")
        details_button = driver.wait_for(
            '//*[contains(@class,"tracker-seeDetailsLink")]', EC.element_to_be_clickable
        )
        details_button.click()

        self.log(f"driver get SHIPMENT - {idship}")
        driver.wait_for(
            '//*[@id="tracking-events-container"]', EC.visibility_of_element_located
        )

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        self.find_shipment(idship, driver)
        return lxml.html.fromstring(driver.page_source)

    @staticmethod
    def get_txt(elt, xpath):
        return elt.xpath(xpath)[0].xpath("normalize-space()")

    def parse_content(self, content):
        events = []

        product = self.get_txt(
            content, '//*[contains(@class,"tracking-event-carrier-header")]'
        )

        timeline = content.xpath(
            '//div[@id="tracking-events-container"]/div/div[@class="a-row"]'
        )
        for div in timeline:
            day = self.get_txt(
                div, './/div[contains(@class,"tracking-event-date-header")]'
            )
            for evt_div in div.xpath('.//div[contains(@class,"a-spacing-large")]'):
                hour = self.get_txt(evt_div, './/*[@class="tracking-event-time"]')
                date = get_local_time(f"{day} {hour}", use_locale_parser=True)
                label = self.get_txt(evt_div, './/*[@class="tracking-event-message"]')
                try:
                    status = self.get_txt(
                        evt_div, './/*[@class="tracking-event-location"]'
                    ).title()
                except IndexError:
                    status = None

                events.append(dict(date=date, label=label, status=status))

        return events, dict(product=product)
