from tools.date_parser import get_local_time
from tracking.courier import Courier
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
        details = driver.wait_for_clickable(details_locator)
        driver.execute_script("arguments[0].click();", details)

        self.log(f"driver get TIMELINE - {idship}")
        timeline_locator = '//*[@class="ups-simplified_tracking_wrap-inner"]'
        driver.wait_for_clickable(timeline_locator)
        return driver.page_source

    def parse_content(self, content):
        events = []

        status_locator = "//track-details-estimation"
        product_locator = '//*[contains(@id,"txtAdditionalInfoShipmentCat")]'
        weight_locator = '//*[contains(@id,"InfoserviceWeight")]'
        timeline_locator = '//*[contains(@id,"activitydetails_row")]'

        status_label = self.get_txt(content, status_locator)

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

        return events, dict(product=product, status_label=status_label)
