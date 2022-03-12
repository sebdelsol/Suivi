import json
import os
import stat
import tempfile
import threading
from functools import reduce

import undetected_chromedriver as webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from windows.localization import TXT
from windows.log import log

from .chrome import get_chrome_main_version


class EnhancedOptions(webdriver.ChromeOptions):
    default_options = (
        "--no-service-autorun",
        "--no-first-run",
        "--password-store=basic",
        "--start-maximized",
        # "--excludeSwitches --enable-logging",
        # "--excludeSwitches --enable-automation",
        # "--disable-gpu",
        f"--lang={TXT.locale_driver_country_code}",
    )

    default_prefs = {  # no password popup
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }

    translate_prefs = {  # auto translation
        # "useAutomationExtension": True,
        # "translate.enabled": True,
        # "intl.accept_languages": f"{TXT.locale_country_code},{TXT.locale_driver_country_code}",
        "translate_language_blacklist": [],
        "translate_blocked_languages": [],
        "translate_site_blacklist": [],
        "translate_allowlists": {
            lang: TXT.locale_country_code
            for lang in ("en", "de", "es", "it", "it-it", "und", "zh", "zh-CN")
        },
    }

    def __init__(
        self,
        headless=False,
        auto_translate=False,
    ):
        super().__init__()
        self.headless = headless

        for option in self.default_options:
            self.add_argument(option)

        if auto_translate:
            self.default_prefs.update(self.translate_prefs)
        self.add_experimental_option("prefs", self.default_prefs)


def patch_driver(version):
    """
    patch chromedriver then prevent any further patching,
    driver patching is not thread safe
    """
    log(f"PATCHING chromedriver {version=}")
    patcher = webdriver.Patcher(version_main=version)
    # unlock chromedriver.exe and patch it
    if os.path.exists(patcher.executable_path):
        os.chmod(patcher.executable_path, stat.S_IWRITE)
    patcher.auto()
    # lock chromedriver.exe & monkey patch Patcher
    # to prevent the patcher from reading or writing on the driver
    os.chmod(patcher.executable_path, stat.S_IREAD)
    webdriver.Patcher.is_binary_patched = lambda self: True
    log(f"chromedriver PATCHED {version=}")


class SafeThreadPatcherChrome(webdriver.Chrome):
    _patching_lock = threading.Lock()
    _patching_done = False

    @classmethod
    def _patch_driver(cls):
        """patch chromedriver only once with the current chrome version, thread safe"""
        with cls._patching_lock:
            if not cls._patching_done:
                patch_driver(get_chrome_main_version())
                cls._patching_done = True

    def __init__(self, *args, **kwargs):
        self._patch_driver()
        super().__init__(*args, **kwargs)


class ChromeWithPrefs(webdriver.Chrome):
    def __init__(self, *args, options=None, **kwargs):
        if options:
            self._handle_prefs(options)

        super().__init__(*args, options=options, **kwargs)

        # remove the user_data_dir when quitting
        self.keep_user_data_dir = False
        self._wait_elt_timeout = 0
        self._driver_wait = None

    @staticmethod
    def _handle_prefs(options):
        if prefs := options.experimental_options.get("prefs"):
            # turn a (dotted key, value) into a proper nested dict
            def undot_key(key, value):
                if "." in key:
                    key, rest = key.split(".", 1)
                    value = undot_key(rest, value)
                return {key: value}

            # undot prefs dict keys
            undot_prefs = reduce(
                lambda d1, d2: {**d1, **d2},  # merge dicts
                (undot_key(key, value) for key, value in prefs.items()),
            )

            # create an user_data_dir and add its path to the options
            user_data_dir = os.path.normpath(tempfile.mkdtemp())
            options.add_argument(f"--user-data-dir={user_data_dir}")

            # create the preferences json file in its default directory
            default_dir = os.path.join(user_data_dir, "Default")
            os.mkdir(default_dir)

            prefs_file = os.path.join(default_dir, "Preferences")
            with open(prefs_file, encoding="latin1", mode="w") as f:
                json.dump(undot_prefs, f)

            # pylint: disable=protected-access
            # remove the experimental_options to avoid an error
            del options._experimental_options["prefs"]


class ChromeWithTools(webdriver.Chrome):
    """find & wait tools"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
            locator = (By.XPATH, xpath)
            return self.wait_until(expected_condition(locator), timeout)

        except TimeoutException as e:
            if not safe:
                raise e
            return None

    def wait_for_visibility(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.visibility_of_element_located, timeout, safe)

    def wait_for_clickable(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.element_to_be_clickable, timeout, safe)

    def wait_for_presence_of_all(self, xpath, timeout=None, safe=False):
        return self.wait_for(xpath, EC.presence_of_all_elements_located, timeout, safe)

    def wait_for_css_in_shadow_root(self, shadow_root, css, timeout=None):
        shadow_root = shadow_root.shadow_root

        # wait for the element in the shadow-root
        def css_present(_):
            timeline_loc = (By.CSS_SELECTOR, css)
            return shadow_root.find_element(*timeline_loc)

        return self.wait_until(css_present, timeout)

    def wait_for_translation(self):
        """detect if it's needed to wait for an automatic translation"""
        try:
            translation_loc = '//*[@class="goog-te-spinner-pos"]'
            if self.find_elements(By.XPATH, translation_loc):
                lang_loc = '/html[contains(@class,"translated")]'
                self.wait_for(lang_loc, EC.presence_of_element_located)

        except NoSuchElementException:
            pass

    def xpath(self, xpath, safe=False):
        try:
            return self.find_element(By.XPATH, xpath)

        except NoSuchElementException as e:
            if not safe:
                raise e
            return None

    def xpaths(self, xpath, safe=False):
        try:
            return self.find_elements(By.XPATH, xpath)

        except NoSuchElementException as e:
            if not safe:
                raise e
            return None


# pylint: disable=too-many-ancestors
class EnhancedChrome(SafeThreadPatcherChrome, ChromeWithPrefs, ChromeWithTools):
    pass
