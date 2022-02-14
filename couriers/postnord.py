import lxml.html
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time
from windows.localization import TXT


class PostNord(Courier):
    name = "Postnord"

    def get_url_for_browser(self, idship):
        return (
            f"https://www.postnord.se/en/our-tools/track-and-trace?shipmentId={idship}"
        )

    @Courier.driversToScrape.get(wait_elt_timeout=20)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)

        # rgpd ?
        try:
            rgpd_loc = '//*[@id="onetrust-accept-btn-handler"]'
            rgpd = driver.wait_for(rgpd_loc, EC.element_to_be_clickable, timeout=2)
            rgpd.click()
            self.log(f"driver PASS rgpd - {idship}")

        except TimeoutException:
            pass

        # wait for tracking (hidden in a shadow-root)
        self.log(f"driver WAIT for timeline - {idship}")
        tracking_loc = "//postnord-widget-tracking"
        tracking = driver.wait_for(tracking_loc, EC.element_to_be_clickable)

        # click all <p> in the shadow-root to expand infos
        self.log(f"driver EXPAND timeline - {idship}")
        click_all_p = (
            '[...arguments[0].shadowRoot.querySelectorAll("p")].forEach(a => a.click())'
        )
        driver.execute_script(click_all_p, tracking)

        # get innerHTML in the shadow-root
        self.log(f"driver COLLECT timeline - {idship}")
        get_shadow_html = "return arguments[0].shadowRoot.innerHTML"
        tracking_html = driver.execute_script(get_shadow_html, tracking)
        return lxml.html.fromstring(tracking_html)

    def parse_content(self, content):
        events = []

        product = TXT.package_product
        if weight := self.get_txt(content, '//*[@id="itemWeight"]'):
            product += f" {weight}"

        timeline = content.xpath("///app-delivery-route//li")
        for event in timeline:
            location = self.get_txt(event, ".//h3")
            date = self.get_txt(event, ".//div/p")
            label = self.get_txt(event, ".//div/following-sibling::p")

            events.append(dict(date=get_local_time(date), status=location, label=label))

        return events, dict(product=product)
