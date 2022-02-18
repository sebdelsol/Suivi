import lxml.html
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time
from windows.localization import TXT


class SwissPost(Courier):
    name = "Swiss Post"
    idship_validation = r"^\d{2}\.\d{2}\.\d{6}\.\d{8}"
    idship_validation_msg = (
        f"2 {TXT.digits}.2 {TXT.digits}.6 {TXT.digits}.8 {TXT.digits}"
    )

    def get_url_for_browser(self, idship):
        return True  # so that show button is displayed

    @Courier.driversToShow.get(page_load_timeout=10, wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.find_shipment(idship, driver)

    def find_shipment(self, idship, driver):
        self.log(f"driver get SHIPMENT - {idship}")

        url = "https://service.post.ch/ekp-web/ui/list"
        driver.get(url)

        self.log(f"driver get SHIPMENT - {idship}")
        input_locator = '//input[@aria-label="searchValue"]'
        input_idship = driver.wait_for(input_locator, EC.element_to_be_clickable)
        input_idship.send_keys(idship)

        search_locator = '//button[@aria-label="searchButton"]'
        search = driver.wait_for(search_locator, EC.element_to_be_clickable)
        search.click()

        show_details_locator = "//ekp-shipment-item//button"
        show_details = driver.wait_for(show_details_locator, EC.element_to_be_clickable)
        show_details.click()

        self.log(f"driver get DETAILS - {idship}")
        details_locator = "//ekp-shipment-detail"
        details = driver.wait_for(details_locator, EC.element_to_be_clickable)

        try:
            more_locator = details_locator + '//*[contains(@class, "moreEvents")]'
            more = driver.find_element(By.XPATH, more_locator)
            more.click()
        except NoSuchElementException:
            pass

        return details

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        details = self.find_shipment(idship, driver)
        return lxml.html.fromstring(details.get_attribute("innerHTML"))

    def parse_content(self, content):
        events = []

        weight_locator = "//ekp-shipment-info//span"
        product_locator = '//ekp-detail-header//div[@class="row"]//span'
        timeline_locator = "//ekp-event-timeline//ekp-event-day"

        product = self.get_txt(content, product_locator)
        if not product:
            product = TXT.default_product
        if weight := self.get_txt(content, weight_locator):
            product += f" {weight}"

        timeline = content.xpath(timeline_locator)
        for days in timeline:
            day_locator = './/*[@class="sub-menu-item"]'
            day = self.get_txt(days, day_locator)

            event_locator = ".//ekp-event-item"
            by_days = days.xpath(event_locator)
            for event in by_days:
                hour_locator = './/*[contains(@class, "time")]'
                label_locator = './/*[@class="row"][1]//text()'
                hour = self.get_txt(event, hour_locator)
                events.append(
                    dict(
                        date=get_local_time(f"{day} {hour}", use_locale_parser=True),
                        label=self.clean_txt(event, label_locator),
                    )
                )

        return events, dict(product=product)
