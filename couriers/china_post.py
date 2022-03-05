import lxml.html
from PIL import ImageFilter
from retry import retry
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from tools.actions_chain import EnhancedActionChains
from tools.date_parser import get_utc_time
from tools.img_tool import load_img64
from tracking.courier import Courier


def _get_missing_piece_x_pos(image, luma_threshold):
    return (
        image.convert("L")  # grayscale
        .point(lambda l: l >= luma_threshold)  # higlight
        .filter(ImageFilter.MinFilter(5))  # remove noise using a big kernel
        .getbbox()[0]  # bbox is (left, upper, right, lower)
    )


class ChinaPost(Courier):
    name = "China Post"
    fromto = f"CN{Courier.r_arrow}"

    url = "http://yjcx.ems.com.cn/qps/english/yjcx"

    def get_url_for_browser(self, idship):
        return True

    @Courier.driversToShow.get(wait_elt_timeout=15)
    def open_in_browser(self, idship, driver):
        self._get_timeline(idship, driver)

    @retry(TimeoutException, tries=3, delay=2)
    def _solve_captcha(self, slider, idship, driver, elt_to_wait):
        self.log(f"driver RESOLVE captcha - {idship}")

        img_loc = '//*[@class="yz-bg-img"]//img'
        img = driver.wait_for(img_loc, EC.visibility_of_element_located)
        # src = "data:image/[format];base64,[base64 encoded data]"
        # where format is intentionally wrong !
        data64 = img.get_attribute("src").split(",")[1]
        image = load_img64(data64)
        x = _get_missing_piece_x_pos(image, luma_threshold=255)

        action = EnhancedActionChains(driver)
        action.click_and_hold(slider).smooth_move_mouse(x - 5, 0).release().perform()

        return driver.wait_for(elt_to_wait, EC.visibility_of_element_located, 4)

    def _get_timeline(self, idship, driver):
        self.log(f"driver get SHIPMENT - {idship}")

        driver.get(self.url)

        input_loc = '//div[@class="mailquery_container"]//textarea'
        input_ = driver.wait_for(input_loc, EC.element_to_be_clickable)
        input_.send_keys(idship)

        submit_loc = '//button[@id="buttonSub"]'
        submit = driver.wait_for(submit_loc, EC.element_to_be_clickable)
        submit.click()

        slider_loc = '//div[@class="yz-control-btn"]'
        slider = driver.wait_for(slider_loc, EC.element_to_be_clickable)

        timeline_loc = '//div[@class="package_container"]'
        return self._solve_captcha(slider, idship, driver, timeline_loc)

    @Courier.driversToScrape.get(wait_elt_timeout=15)
    def get_content(self, idship, driver):
        if timeline := self._get_timeline(idship, driver):
            # driver.wait_for_translation()
            return lxml.html.fromstring(timeline.get_attribute("innerHTML"))
        return None

    def parse_content(self, content):
        events = []
        day = ""
        timeline = content.xpath('//ul[@class="package_list"]/li')
        for event in timeline:
            day = self.get_txt(event, './/span[@class="data"]') or day
            hour = self.get_txt(event, './/span[@class="time"]')
            events.append(
                dict(
                    date=get_utc_time(f"{day} {hour}"),
                    label=self.get_txt(event, './/span[@class="text"]'),
                    status=self.get_txt(event, './/span[@class="opOrgCity"]'),
                )
            )

        return events, {}
