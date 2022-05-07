import time

import undetected_chromedriver as webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from windows.localization import TXT
from windows.log import log

from .chrome import Chrome_Version


class EnhancedOptions(webdriver.ChromeOptions):
    default_options = (
        "--disable-features=ChromeWhatsNewUI",  # prevent WhatsNew when Chrome has been updated
        "--no-service-autorun",
        "--no-first-run",
        "--password-store=basic",
        "--start-maximized",
        f"--lang={TXT.locale_driver_country_code}",
    )

    # no password popup
    default_prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }

    # auto translation
    translate_prefs = {
        "translate_language_blacklist": [],
        "translate_blocked_languages": [],
        "translate_site_blacklist": [],
        "translate_allowlists": {
            lang: TXT.locale_country_code
            for lang in ("en", "de", "es", "it", "it-it", "und", "zh", "zh-CN")
        },
    }

    def __init__(self, headless=False, auto_translate=False):
        super().__init__()
        self.headless = headless

        for option in self.default_options:
            self.add_argument(option)

        prefs = self.default_prefs.copy()
        if auto_translate:
            prefs.update(self.translate_prefs)
        self.add_experimental_option("prefs", prefs)


class EnhancedChrome(webdriver.Chrome):
    """find & wait tools"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, version_main=Chrome_Version, **kwargs)
        self._wait_elt_timeout = 0
        self._driver_wait = None

    def set_timeouts(self, page_load_timeout, wait_elt_timeout):
        self.set_page_load_timeout(page_load_timeout)
        self._wait_elt_timeout = wait_elt_timeout
        self._driver_wait = WebDriverWait(self, wait_elt_timeout)

    def wait_until(self, until, timeout=None):
        if timeout and timeout != self._wait_elt_timeout:
            return WebDriverWait(self, timeout).until(until)

        return self._driver_wait.until(until)

    def wait_for(self, xpath, expected_condition, timeout=None, safe=False):
        try:
            locator = self._get_xpath_loc(xpath)
            return self.wait_until(expected_condition(locator), timeout)

        except TimeoutException as e:
            log(f"Error waiting for {xpath}", error=True)
            if not safe:
                raise e
            return None

    def wait_for_visibility(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.visibility_of_element_located, timeout, safe)

    def wait_for_clickable(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.element_to_be_clickable, timeout, safe)

    def wait_for_presence(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.presence_of_element_located, timeout, safe)

    def wait_for_presence_of_all(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.presence_of_all_elements_located, timeout, safe)

    def wait_for_css_in_shadow_root(self, shadow_root, css, timeout=None):
        shadow_root = shadow_root.shadow_root

        # wait for the element in the shadow-root
        def css_present(_):
            locator = (By.CSS_SELECTOR, css)
            return shadow_root.find_element(*locator)

        return self.wait_until(css_present, timeout)

    def wait_for_translation(self):
        """wait for an automatic browser translation"""
        translation_loc = '//*[@class="goog-te-spinner-pos"]'
        if self.xpaths(translation_loc, safe=True):
            lang_loc = '/html[contains(@class,"translated")]'
            self.wait_for_presence(lang_loc, safe=True)

    def wait_for_browser_closed(self):
        disconnected_msg = "disconnected: not connected to DevTools"
        while True:
            time.sleep(0.25)
            if msg := self.get_log("driver"):
                if disconnected_msg in msg[-1]["message"]:
                    log("Chrome closed by the user")
                    break

    @staticmethod
    def _get_xpath_loc(xpath):
        if type(xpath) in (tuple, list):
            xpath = " | ".join(xpath)
        return By.XPATH, xpath

    @staticmethod
    def _find(find_func, xpath, safe=False):
        try:
            locator = EnhancedChrome._get_xpath_loc(xpath)
            return find_func(*locator)

        except NoSuchElementException as e:
            log(f"Did not find {xpath}", error=True)
            if not safe:
                raise e
            return None

    def xpath(self, xpath, safe=False):
        return self._find(self.find_element, xpath, safe)

    def xpaths(self, xpath, safe=False):
        return self._find(self.find_elements, xpath, safe)
