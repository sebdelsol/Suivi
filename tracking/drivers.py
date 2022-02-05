import atexit
import queue
import threading
import time
import traceback
from socket import error as SocketError

import psutil
from selenium.common.exceptions import (
    NoSuchWindowException,
    SessionNotCreatedException,
    WebDriverException,
)
from urllib3.exceptions import ProtocolError
from windows.localization import TXT
from windows.log import log

from tracking.config import CHROME_EXE_PATH

USE_UC_V2 = True
CREATE_DRIVER_AT_INIT = False

if USE_UC_V2:
    import undetected_chromedriver as webdriver

else:
    import undetected_chromedriver._compat as webdriver


class _DriversHandler:
    name = None

    def __init__(self):
        self._drivers = []
        self.max_drivers = None
        self._in_creation = 0
        self._creation_threads = []
        self._driver_count_ops = threading.Lock()
        atexit.register(self._close)

    def _log_creation(self, txt, n_drivers, error=False):
        msg = f"{self.name} {txt}"
        if self.max_drivers:
            msg += f" ({n_drivers + 1}/{self.max_drivers})"
        log(msg, error=error)

    def create(self, create_driver_func):
        with self._driver_count_ops:
            n_drivers = len(self._drivers) + self._in_creation
            can_create = not self.max_drivers or n_drivers < self.max_drivers
            if can_create:
                self._in_creation += 1
                thread = threading.current_thread()
                self._creation_threads.append(thread)

        if can_create:
            driver = None
            self._log_creation("start CREATION", n_drivers)
            try:
                driver = create_driver_func(n_drivers)
                self._log_creation("has been CREATED", n_drivers)

            except (SessionNotCreatedException, ProtocolError, SocketError) as e:
                self._log_creation(f"creation FAILED ({e})", n_drivers, error=True)

            finally:
                with self._driver_count_ops:
                    self._creation_threads.remove(thread)
                    self._in_creation -= 1
                    if driver:
                        self._drivers.append(driver)

            return driver
        return None

    def destroy(self, driver):
        with self._driver_count_ops:
            driver.quit()
            self._drivers.remove(driver)

    def _close(self):
        log(f"CLOSING {self.name}")
        with self._driver_count_ops:
            n_drivers = len(self._drivers)
            for i, driver in enumerate(self._drivers):
                log(f"QUIT {self.name} ({i + 1}/{n_drivers})")
                driver.quit()

            # if drivers are still being created terminate those
            current_proc = psutil.Process()
            if any(thread.is_alive() for thread in self._creation_threads):
                for child in current_proc.children(recursive=True):
                    if "chromedriver.exe" in child.name().lower():
                        log(f"TERMINATE {child.name()} {child.pid}")
                        child.terminate()


class DriversToScrape(_DriversHandler):
    max_drivers = 2
    name = "chromedriver to scrape"

    experimental_options = dict(
        prefs={
            "translate_whitelists": {
                "de": "fr",
                "es": "fr",
                "en": "fr",
                "und": "fr",
                "zh-CN": "fr",
                "zh-TW": "fr",
            },
            "translate": {"enabled": "true"},
            "profile.managed_default_content_settings.images": 2,  # remove image
            "profile.managed_default_content_settings.cookies": 2,  # remove cookies
        },
        excludeSwitches=["enable-logging"],
    )

    options = (
        "--no-first-run",
        "--no-service-autorun",
        "--password-store=basic",
        "--lang=fr",
    )

    options_V1 = ("--window-size=1024,768",)  # reach sliders
    options_V2 = (
        "--excludeSwitches --enable-logging",
        "--blink-settings=imagesEnabled=false",
    )

    def start(self, splash, max_drivers=None):
        self._drivers_available = queue.Queue()
        self._first_driver = threading.Lock()
        self.max_drivers = max_drivers or DriversToScrape.max_drivers

        if CREATE_DRIVER_AT_INIT:
            for i in range(self.max_drivers):
                if splash:
                    splash.update(f"{TXT.driver_creation} {i + 1}/{self.max_drivers}")
                self.create(self._create_driver)

    def _create_driver(self, n_drivers):
        options = webdriver.ChromeOptions()
        options.headless = True
        options.binary_location = CHROME_EXE_PATH

        for option in self.options + (
            self.options_V2 if USE_UC_V2 else self.options_V1
        ):
            options.add_argument(option)

        # prefs do not work with UC v2 at the moment
        if not USE_UC_V2:
            for k, v in self.experimental_options.items():
                options.add_experimental_option(k, v)

        if n_drivers == 0:
            with self._first_driver:
                driver = webdriver.Chrome(options=options)

        else:
            # block till the 1st driver has been created
            # to avoid permission error caused by the 1st driver being patched
            with self._first_driver:
                pass
            driver = webdriver.Chrome(options=options)

        self._drivers_available.put(driver)
        return driver

    def get(self):
        self.create(self._create_driver)  # done till max_drivers is reached
        return self._drivers_available.get()

    def dispose(self, driver):
        self._drivers_available.put(driver)


class DriversToShow(_DriversHandler):
    name = "chromedriver to show"

    @staticmethod
    def _create_driver(n_driver):
        options = webdriver.ChromeOptions()
        options.binary_location = CHROME_EXE_PATH
        options.add_argument("--start-maximized")
        return webdriver.Chrome(options=options)

    def defer(self, show, url):
        threading.Thread(target=self._defer, args=(show, url), daemon=True).start()

    @staticmethod
    def _wait_browser_closed(driver):
        disconnected_msg = (
            "disconnected: not connected to DevTools"
        )
        while True:
            if msg := driver.get_log("driver"):
                if disconnected_msg in msg[-1]["message"]:
                    log("Chrome window closed by user")
                    break

    def _defer(self, show, url):
        if driver := self.create(self._create_driver):
            log(f"SHOW in {self.name}")
            try:
                driver.get(url)
                show(driver)
                self._wait_browser_closed(driver)

            except (
                NoSuchWindowException,
                WebDriverException,
                SessionNotCreatedException,
            ) as e:
                log(f"{self.name} SHOW failed ({e})", error=True)

            except:
                log(traceback.format_exc(), error=True)

            finally:
                self.destroy(driver)
