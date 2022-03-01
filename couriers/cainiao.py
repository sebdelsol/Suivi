import lxml.html
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tools.date_parser import get_utc_time
from tracking.courier import Courier, smooth_move_mouse


class Cainiao(Courier):
    name = "Cainiao"
    fromto = f"CN{Courier.r_arrow}FR"

    def get_url_for_browser(self, idship):
        return f"https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=zh"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=15)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)

        data_locator = f'//p[@class="waybill-num"][contains(text(),"{idship}")]'
        try:
            is_data = driver.find_elements(By.XPATH, data_locator)

        except NoSuchElementException:
            is_data = None

        if not is_data:
            self.log(f"driver WAIT slider - {idship}")
            slider = driver.wait_for(
                '//span[@class="nc_iconfont btn_slide"]', EC.element_to_be_clickable
            )
            slide = driver.wait_for(
                '//div[@class="scale_text slidetounlock"]/span[contains(text(),"slide")]',
                EC.element_to_be_clickable,
            )
            action = ActionChains(driver)
            action.click_and_hold(slider)
            smooth_move_mouse(action, slide.size["width"], 0)
            action.release().perform()

            self.log(f"driver WAIT datas - {idship}")
            driver.wait_for(data_locator, EC.visibility_of_element_located)

        return lxml.html.fromstring(driver.page_source)

    def parse_content(self, content):
        events = []

        status_label = self.get_txt(content, '//*[@id="waybill_title"]/h3')
        timeline = content.xpath('//ol[@class="waybill-path"]/li')
        for event in timeline:
            txts = event.xpath("./p/text()")
            label, date = txts[:2]
            events.append(dict(date=get_utc_time(date), label=label))

        return events, dict(status_label=status_label)
