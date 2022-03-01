import lxml.html
from PIL import ImageFilter
from retry import retry
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from tools.actions_chain import EnhancedActionChains
from tools.date_parser import get_utc_time
from tools.img_tool import load_img64
from tracking.courier import Courier


class ChinaPost(Courier):
    name = "China Post"
    fromto = f"CN{Courier.r_arrow}FR"

    def get_url_for_browser(self, idship):
        return True

    @Courier.driversToShow.get(page_load_timeout=10, wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self.get_timeline(idship, driver)

    @staticmethod
    def find_hole_x_pos(image, luma_threshold):
        # the hole is what's above threshold
        image = image.convert("L").point(lambda l: l >= luma_threshold)
        # remove noise
        image = image.filter(ImageFilter.MinFilter(5))
        # crop to get x pos of hole
        return image.getbbox()[0]

    @retry(TimeoutException, tries=3, delay=2)
    def solve_captcha(self, slider, idship, driver):
        self.log(f"driver RESOLVE captcha - {idship}")
        img_locator = '//*[@class="yz-bg-img"]//img'
        img = driver.wait_for(img_locator, EC.visibility_of_element_located)
        data = img.get_attribute("src").split(",")[1]
        image = load_img64(data)
        x = self.find_hole_x_pos(image, luma_threshold=255) or 0
        action = EnhancedActionChains(driver)
        action.click_and_hold(slider)
        action.smooth_move_mouse(x - 5, 0)
        action.release().perform()

        timeline_locator = '//div[@class="package_container"]'
        timeline = driver.wait_for(
            timeline_locator, EC.visibility_of_element_located, 3
        )
        return timeline

    def get_timeline(self, idship, driver):
        url = "http://yjcx.ems.com.cn/qps/english/yjcx"
        driver.get(url)

        self.log(f"driver get SHIPMENT - {idship}")
        input_locator = '//div[@class="mailquery_container"]//textarea'
        input_ = driver.wait_for(input_locator, EC.element_to_be_clickable)
        input_.send_keys(idship)

        submit_locator = '//button[@id="buttonSub"]'
        submit = driver.wait_for(submit_locator, EC.element_to_be_clickable)
        submit.click()

        slider_locator = '//div[@class="yz-control-btn"]'
        slider = driver.wait_for(slider_locator, EC.element_to_be_clickable)

        return self.solve_captcha(slider, idship, driver)

    @Courier.driversToScrape.get(wait_elt_timeout=15)
    def get_content(self, idship, driver):
        if timeline := self.get_timeline(idship, driver):
            return lxml.html.fromstring(timeline.get_attribute("innerHTML"))
        return None

    def parse_content(self, content):
        events = []
        timeline = content.xpath('//ul[@class="package_list"]/li')
        last_day = ""
        for event in timeline:
            day = self.get_txt(event, './/span[@class="data"]') or last_day
            hour = self.get_txt(event, './/span[@class="time"]')
            last_day = day
            events.append(
                dict(
                    date=get_utc_time(f"{day} {hour}"),
                    label=self.get_txt(event, './/span[@class="text"]'),
                    status=self.get_txt(event, './/span[@class="opOrgCity"]'),
                )
            )

        return events, {}
