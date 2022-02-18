import lxml.html
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time
from windows.localization import TXT


class UPS(Courier):
    name = "UPS"

    def get_url_for_browser(self, idship):
        return f"https://www.ups.com/track?loc=fr_FR&tracknum={idship}&requester=ST/trackdetails"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=10)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)

        rgpd_locator = '//div[@class="privacy_prompt_content"]'
        if driver.find_element(By.XPATH, rgpd_locator):
            radio_locator = rgpd_locator + '//div[@class="option_explicit"]/label'
            radio = driver.wait_for(radio_locator, EC.element_to_be_clickable)
            radio.click()

            button_locator = (
                rgpd_locator + '//div[@class="privacy_prompt_buttons_explicit"]/button'
            )
            button = driver.wait_for(button_locator, EC.element_to_be_clickable)
            button.click()

        details_locator = "//modal-shipment-view-details"
        details = driver.wait_for(details_locator, EC.element_to_be_clickable)
        details.click()

        timeline_locator = '//div[@class="ups-simplified_tracking_wrap-inner"]'
        driver.wait_for(timeline_locator, EC.element_to_be_clickable)
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        product = self.get_txt(
            content, '//*[contains(@id,"txtAdditionalInfoShipmentCat")]'
        )
        if not product:
            product = TXT.default_product
        if weight := self.get_txt(content, '//*[contains(@id,"InfoserviceWeight")]'):
            product += f" {weight}"

        timeline = content.xpath('//*[contains(@id,"activitydetails_row")]')
        for event in timeline:
            day, hour = event.xpath('.//*[contains(@id,"activitiesdateTime")]/text()')
            label = self.get_txt(event, './/*[contains(@id, "milestoneName")]')
            location = self.get_clean_txt(
                event, './/*[contains(@id, "milestoneActivityLocation")]'
            )
            events.append(
                dict(
                    date=get_local_time(f"{day} {hour}", use_locale_parser=True),
                    label=label,
                    status=location,
                )
            )

        return events, {}
