import lxml.html
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

        self.log(f"driver get DETAILS - {idship}")
        details_locator = "//modal-shipment-view-details/button"
        details = driver.wait_for(details_locator, EC.element_to_be_clickable)
        driver.execute_script("arguments[0].click();", details)

        self.log(f"driver get TIMELINE - {idship}")
        timeline_locator = '//*[@class="ups-simplified_tracking_wrap-inner"]'
        driver.wait_for(timeline_locator, EC.element_to_be_clickable)
        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        product_locator = '//*[contains(@id,"txtAdditionalInfoShipmentCat")]'
        weight_locator = '//*[contains(@id,"InfoserviceWeight")]'
        timeline_locator = '//*[contains(@id,"activitydetails_row")]'

        product = self.get_txt(content, product_locator)
        if not product:
            product = TXT.default_product
        if weight := self.get_txt(content, weight_locator):
            product += f" {weight}"

        timeline = content.xpath(timeline_locator)
        for event in timeline:
            location_locator = './/*[contains(@id, "milestoneActivityLocation")]/text()'
            label_locator = './/*[contains(@id, "milestoneName")]'
            day_hour = './/*[contains(@id,"activitiesdateTime")]/text()'
            day, hour = event.xpath(day_hour)
            events.append(
                dict(
                    date=get_local_time(
                        f"{day} {hour}", locale_country=TXT.locale_country_code
                    ),
                    label=self.get_txt(event, label_locator),
                    status=self.clean_txt(event, location_locator),
                )
            )

        return events, dict(product=product)
