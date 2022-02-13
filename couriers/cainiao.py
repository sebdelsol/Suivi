import lxml.html
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tracking.courier import Courier, get_utc_time


class Cainiao(Courier):
    name = "Cainiao"
    fromto = f"CN{Courier.r_arrow}FR"

    def get_url_for_browser(self, idship):
        return f"https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=zh"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=30)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)

        data_locator = (
            By.XPATH,
            f'//p[@class="waybill-num"][contains(text(),"{idship}")]',
        )
        try:
            is_data = driver.find_elements(*data_locator)

        except NoSuchElementException:
            is_data = None

        if not is_data:
            self.log(f"driver WAIT slider - {idship}")
            slider = driver.wait_for(
                '//span[@class="nc_iconfont btn_slide"]', EC.element_to_be_clickable
            )

            slide = driver.find_element(
                By.XPATH, '//div[@class="scale_text slidetounlock"]/span'
            )
            action = ActionChains(driver)
            action.drag_and_drop_by_offset(slider, slide.size["width"], 0).perform()

            self.log(f"driver WAIT datas - {idship}")
            driver.wait_for(
                f'//p[@class="waybill-num"][contains(text(),"{idship}")]',
                EC.visibility_of_element_located,
            )

        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        timeline = content.xpath('//ol[@class="waybill-path"]/li')
        for event in timeline:
            txts = event.xpath("./p/text()")
            label, date = txts[:2]
            events.append(dict(date=get_utc_time(date), label=label))

        return events, {}
