import re

from tools.actions_chain import EnhancedActionChains
from tools.date_parser import get_local_time
from tracking.courier import Courier


class Cainiao(Courier):
    name = "Cainiao"
    fromto = f"CN{Courier.r_arrow}FR"

    def get_url_for_browser(self, idship):
        return f"https://global.cainiao.com/detail.htm?mailNoList={idship}&lang=en"

    #  do not return any selenium objects, the driver is disposed after
    @Courier.driversToScrape.get(wait_elt_timeout=15)
    def get_content(self, idship, driver):
        url = self.get_url_for_browser(idship)
        driver.get(url)

        data_locator = f'//p[@class="waybill-num"][contains(text(),"{idship}")]'
        if not driver.xpaths(data_locator, safe=True):
            self.log(f"driver WAIT slider - {idship}")

            slider_loc = '//span[@class="nc_iconfont btn_slide"]'
            slider = driver.wait_for_clickable(slider_loc)
            slide_loc = (
                '//div[@class="scale_text slidetounlock"]'
                '/span[contains(text(),"slide")]'
            )
            slide = driver.wait_for_clickable(slide_loc)

            action = EnhancedActionChains(driver)
            action.click_and_hold(slider)
            action.smooth_move_mouse(slide.size["width"] + 10, 0)
            action.release().perform()

            self.log(f"driver WAIT datas - {idship}")
            driver.wait_for_visibility(data_locator, 5)

        return driver.page_source

    def parse_content(self, content):
        events = []

        status_label = self.get_txt(content, '//*[@id="waybill_title"]/h3')
        timeline = content.xpath('//ol[@class="waybill-path"]/li')
        for event in timeline:
            txts = event.xpath("./p/text()")
            label, date = txts[:2]
            label = re.sub(r"[\[\]]", " ", label)
            events.append(dict(date=get_local_time(date), label=label))

        return events, dict(status_label=status_label)
