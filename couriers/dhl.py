from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.api_keys import DHL_KEY
from tracking.courier import (
    Courier,
    RequestsHandler,
    get_local_time,
    get_simple_validation,
)


class DHL(Courier):
    name = "DHL"
    idship_validation, idship_validation_msg = get_simple_validation(10, 39)
    headers = {"Accept": "application/json", "DHL-API-Key": DHL_KEY}

    def get_url_for_browser(self, idship):
        return f"https://www.dhl.com/fr-en/home/our-divisions/parcel/private-customers/tracking-parcel.html?tracking-id={idship}"

    # force submit button
    @Courier.driversToShow.get(page_load_timeout=10, wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)
        rgpd_locator = (
            By.XPATH,
            '//button[contains(@class, "save-preference-btn")]',
        )
        btn_rgpd = driver.wait_until(EC.element_to_be_clickable(rgpd_locator))
        btn_rgpd.click()

        submit_locator = (By.XPATH, '//button[contains(@class, "tracking-input")]')
        submit = driver.wait_until(EC.element_to_be_clickable(submit_locator))
        submit.click()

    @RequestsHandler()
    def get_content(self, idship, request):
        url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={idship}&language=FR"
        r = request.request("GET", url, headers=self.headers)
        return r.status_code == 200, r.json()

    def parse_content(self, content):
        events = []

        shipments = content[1].get("shipments")
        if shipments:
            shipment = shipments[0]
            product = f"DHL {shipment['service']}"

            for event in shipment["events"]:
                label = event.get("description") or event.get("status")
                if label:
                    label = label.capitalize()

                warn = False
                if code := event.get("statusCode"):
                    warn = code == "failure"

                # round dates to minute to better find duplicate
                date = get_local_time(event["timestamp"])

                status = None
                location = event.get("location")
                if location:
                    status = location.get("address", {}).get("addressLocality").title()
                if status:
                    status = status.title()

                events.append(dict(date=date, status=status, label=label, warn=warn))

            return events, dict(product=product)
        return None
