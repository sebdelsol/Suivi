import atexit
import json
import os
import queue
import stat
import tempfile
import threading
import time
from functools import reduce
from socket import error as SocketError

import psutil
import undetected_chromedriver as webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    NoSuchWindowException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError
from windows.localization import TXT
from windows.log import log

from .chrome import get_chrome_main_version


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
    log("chromedriver PATCHED")


class ChromeWithPrefsAndTools(webdriver.Chrome):
    def __init__(self, *args, options=None, **kwargs):
        if options:
            self._handle_prefs(options)

        super().__init__(*args, options=options, **kwargs)

        # remove the user_data_dir when quitting
        self.keep_user_data_dir = False
        self._wait_elt_timeout = 0

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

    # wait tools
    def set_timeouts(self, page_load_timeout, wait_elt_timeout):
        self.set_page_load_timeout(page_load_timeout)
        self._wait_elt_timeout = wait_elt_timeout

    def wait_until(self, until, timeout=None):
        return WebDriverWait(self, timeout or self._wait_elt_timeout).until(until)

    def wait_for(self, xpath, expected_condition, timeout=None):
        locator = (By.XPATH, xpath)
        return self.wait_until(expected_condition(locator), timeout)

    def wait_for_translation(self):
        """detect if it's needed to wait for an automatic translation"""
        try:
            translation_loc = '//*[@class="goog-te-spinner-pos"]'
            if self.find_elements(By.XPATH, translation_loc):
                lang_loc = '/html[contains(@class,"translated")]'
                self.wait_for(lang_loc, EC.presence_of_element_located)

        except NoSuchElementException:
            pass


class Options(webdriver.ChromeOptions):
    default_options = (
        "--no-service-autorun",
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


class DriversHandler:
    name = None
    headless = False
    auto_translate = True
    options = ()
    prefs = {}

    _terminate_lock = threading.Lock()
    _patching_lock = threading.Lock()
    _patching_done = False

    def __init__(self, max_drivers=None):
        self.max_drivers = max_drivers or float("inf")
        self._n_in_creation = 0
        self._drivers = []
        self._drivers_available = queue.Queue()
        self._driver_count_ops = threading.Lock()
        atexit.register(self._close)

    def _log_creation(self, txt, n_drivers, error=False):
        msg = f"{self.name} {txt}"
        n_max = "∞" if repr(self.max_drivers) == "inf" else self.max_drivers
        msg += f" ({n_drivers + 1}/{n_max})"
        log(msg, error=error)

    @classmethod
    def _patch_driver(cls):
        """patch chromedriver only once, thread safe"""
        with cls._patching_lock:
            if not cls._patching_done:
                patch_driver(get_chrome_main_version())
                cls._patching_done = True

    def _create_driver(self):
        with self._driver_count_ops:
            n_drivers = len(self._drivers) + self._n_in_creation
            if can_create := n_drivers < self.max_drivers:
                self._n_in_creation += 1

        if can_create:
            driver = None
            self._log_creation("CREATION", n_drivers)
            try:
                DriversHandler._patch_driver()
                options = Options(
                    headless=self.headless,
                    auto_translate=self.auto_translate,
                )
                driver = ChromeWithPrefsAndTools(options=options)
                self._log_creation("CREATED", n_drivers)

            except (SessionNotCreatedException, ProtocolError, SocketError) as e:
                self._log_creation(f"creation FAILED ({e})", n_drivers, error=True)

            finally:
                with self._driver_count_ops:
                    self._n_in_creation -= 1
                    if driver:
                        self._drivers.append(driver)
                        self._drivers_available.put(driver)

            return driver
        return None

    def _get(self, always_create=False):
        """
        try to get an available driver.
        if not try to create a driver & wait for an available one
        """
        if not always_create:
            try:
                if driver := self._drivers_available.get(block=False):
                    return driver
            except queue.Empty:
                pass

        self._create_driver()
        # wait for an available driver since the creation might have failed
        # or the created driver might have be stolen by another thread
        return self._drivers_available.get()

    def _dispose(self, driver):
        self._drivers_available.put(driver)

    def _destroy(self, driver):
        with self._driver_count_ops:
            log(f"QUIT {self.name}")
            driver.quit()
            self._drivers.remove(driver)

    def _close(self):
        log(f"CLOSING {self.name}")

        with self._driver_count_ops:
            n_drivers = len(self._drivers)
            for i, driver in enumerate(self._drivers):
                log(f"QUIT {self.name} ({i + 1}/{n_drivers})")
                driver.quit()

            DriversHandler._terminate()

    @classmethod
    def _terminate(cls):
        """if drivers are still being created terminate those"""
        with cls._terminate_lock:
            terminated = []
            current_proc = psutil.Process()
            for child in current_proc.children(recursive=True):
                if "chromedriver.exe" in child.name().lower():
                    log(f"TERMINATE {child.name()} {child.pid}")
                    child.terminate()
                    terminated.append(child)
            # wait for actual termination to avoid collisions
            # from _terminate in different threads
            for proc in terminated:
                proc.wait(2)


class DriversToScrape(DriversHandler):
    name = "Chromedriver (scrapper)"
    headless = True
    auto_translate = False

    def set_max_drivers(self, max_drivers):
        self.max_drivers = max_drivers

    def get(self, page_load_timeout=100, wait_elt_timeout=30):
        """
        decorator to give the decorated function a driver
        and handle get_content with timeouts
        """

        def inner(get_content):
            def wrapper(courier, idship):
                if driver := self._get():
                    try:
                        driver.set_timeouts(page_load_timeout, wait_elt_timeout)
                        return get_content(courier, idship, driver)

                    except (
                        WebDriverException,
                        TimeoutException,
                        ProtocolError,
                        NewConnectionError,
                        MaxRetryError,
                    ) as e:
                        error = type(e).__name__

                    finally:
                        self._dispose(driver)

                else:
                    error = "no driver available"

                courier.log(f"driver FAILURE - {error} for {idship}", error=True)
                return None

            return wrapper

        return inner


class DriversToShow(DriversHandler):
    name = "Chromedriver (browser)"
    headless = False
    auto_translate = True

    def get(self, page_load_timeout=30, wait_elt_timeout=15):
        """
        decorator to give the decorated function a driver
        and handle the deferred show with timeouts
        """

        def inner(show):
            def wrapper(courier, idship):
                args = (courier, idship, show, page_load_timeout, wait_elt_timeout)
                threading.Thread(target=self._defer, args=args, daemon=True).start()

            return wrapper

        return inner

    def _defer(self, courier, idship, show, page_load_timeout, wait_elt_timeout):
        if driver := self._get(always_create=True):
            log(f"SHOW in {self.name}")
            try:
                driver.set_timeouts(page_load_timeout, wait_elt_timeout)
                show(courier, idship, driver)
                self._wait_browser_closed(driver)

            except (
                NoSuchWindowException,
                WebDriverException,
                SessionNotCreatedException,
                TimeoutException,
            ) as e:
                log(f"{self.name} SHOW failed ({e})", error=True)

            finally:
                self._destroy(driver)

    @staticmethod
    def _wait_browser_closed(driver):
        disconnected_msg = "disconnected: not connected to DevTools"
        while True:
            time.sleep(0.5)
            if msg := driver.get_log("driver"):
                if disconnected_msg in msg[-1]["message"]:
                    log("Chrome window closed by user")
                    break
