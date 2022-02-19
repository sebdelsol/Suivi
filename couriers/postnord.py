import lxml.html
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_local_time, get_sentences
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

        # wait for the parent of a shadow-root where the tracking is hidden
        self.log(f"driver WAIT for timeline - {idship}")
        tracking_loc = "//postnord-widget-tracking"
        tracking = driver.wait_for(tracking_loc, EC.visibility_of_element_located)

        # wait for the timeline hidden in the shadow-root
        def timeline_present(driver):  # pylint: disable=unused-argument
            shadow_root = tracking.shadow_root
            timeline_loc = (By.CSS_SELECTOR, "app-delivery-route")
            return shadow_root.find_element(*timeline_loc)

        driver.wait_until(timeline_present)

        # click all <p> in the shadow-root to expand infos
        self.log(f"driver EXPAND timeline - {idship}")
        click_all_p = (
            '[...arguments[0].shadowRoot.querySelectorAll("p")].forEach(p => p.click())'
        )
        driver.execute_script(click_all_p, tracking)

        # get innerHTML in the shadow-root
        self.log(f"driver COLLECT timeline - {idship}")
        get_shadow_html = "return arguments[0].shadowRoot.innerHTML"
        tracking_html = driver.execute_script(get_shadow_html, tracking)
        return lxml.html.fromstring(tracking_html)

    def parse_content(self, content):
        events = []

        product = self.get_txt(content, '//*[@id="itemType"]')
        if weight := self.get_txt(content, '//*[@id="itemWeight"]'):
            product = product or TXT.package_product
            product += f" {weight}"

        timeline = content.xpath("///app-delivery-route//li")
        for event in timeline:
            date = self.get_txt(event, ".//div/p")
            label = self.get_txt(event, ".//div/following-sibling::p")
            events.append(
                dict(
                    date=get_local_time(date),
                    status=self.get_txt(event, ".//h3"),
                    label=get_sentences(label),
                )
            )

        return events, dict(product=product)
