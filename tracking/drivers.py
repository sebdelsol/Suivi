import atexit
import queue
import threading
import time
import traceback
from socket import error as SocketError

import psutil
from selenium.common.exceptions import NoSuchWindowException, SessionNotCreatedException, WebDriverException
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


class _BaseHandler:
    @staticmethod
    def driver_to_kill(n_to_kill):
        n_killed = 0
        current_proc = psutil.Process()
        while n_killed < n_to_kill:
            for child in current_proc.children(recursive=True):
                if "chromedriver.exe" in child.name().lower():
                    print(f"KILL ({n_killed + 1}/{n_to_kill}) {child.name()} {child.pid}")
                    child.terminate()
                    n_killed += 1
                    break
            else:
                time.sleep(0.5)

    def __init__(self, type_txt):
        self.type_txt = type_txt
        self._drivers = []
        self._n_drivers = 0
        self._driver_count_ops = threading.Lock()
        atexit.register(self._close)

    def _close(self):
        print(f"CLOSE {self.type_txt}s")
        with self._driver_count_ops:
            for i, driver in enumerate(self._drivers):
                print(f"QUIT {self.type_txt} {i + 1}/{self._n_drivers}")
                driver.quit()

            # check if there are drivers in creation, kill those
            if (n_to_kill := self._n_drivers - len(self._drivers)) > 0:
                print(f"{n_to_kill} {self.type_txt}(s) to KILL")
                self.driver_to_kill(n_to_kill)
        print(f"DONE CLOSE {self.type_txt}s")


class DriverHandler(_BaseHandler):
    _max_drivers = 2

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

    def __init__(self):
        self._drivers_available = queue.Queue()
        self._first_driver = threading.Lock()
        super().__init__("driver")

    def start(self, splash, max_drivers=None):
        if max_drivers:
            self._max_drivers = max_drivers

        if CREATE_DRIVER_AT_INIT:
            for i in range(self._max_drivers):
                if splash:
                    splash.update(f"{TXT.driver_creation} {i + 1}/{self._max_drivers}")
                self._create_driver_if_needed()

    def _create_driver(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        options.binary_location = CHROME_EXE_PATH

        for option in self.options + (self.options_V2 if USE_UC_V2 else self.options_V1):
            options.add_argument(option)

        if not USE_UC_V2:  # prefs do not work on UC v2
            for k, v in self.experimental_options.items():
                options.add_experimental_option(k, v)

        return webdriver.Chrome(options=options)

    def _create_driver_if_needed(self):
        # prevent not needed creation from another thread
        with self._driver_count_ops:
            needed = self._n_drivers < self._max_drivers
            if needed:
                is_first = self._n_drivers == 0
                self._n_drivers += 1
                n_driver = self._n_drivers

        if needed:
            log(f"CREATING driver ({n_driver}/{self._max_drivers})")
            if is_first:
                with self._first_driver:
                    driver = self._create_driver()
            else:
                # block till the 1st driver has been created
                # to avoid permission error due to the 1st driver patching the chromedriver.exe
                with self._first_driver:
                    pass
                driver = self._create_driver()

            log(f"driver ({n_driver}/{self._max_drivers}) has been CREATED")

            self._drivers_available.put(driver)

            with self._driver_count_ops:
                self._drivers.append(driver)

    def get(self):
        self._create_driver_if_needed()
        return self._drivers_available.get()

    def dispose(self, driver):
        self._drivers_available.put(driver)


class TempBrowser(_BaseHandler):
    @staticmethod
    def _create_driver():
        try:
            options = webdriver.ChromeOptions()
            options.binary_location = CHROME_EXE_PATH
            options.add_argument("--start-maximized")
            return webdriver.Chrome(options=options)

        except (SessionNotCreatedException, ProtocolError, SocketError):
            return None

    def __init__(self):
        super().__init__("browser")

    def defer(self, show_func, url):
        threading.Thread(target=self._defer, args=(show_func, url), daemon=True).start()

    def _defer(self, show_func, url):
        with self._driver_count_ops:
            self._n_drivers += 1

        log("temp browser CREATION")
        driver = self._create_driver()
        log("temp browser CREATED")

        if driver:
            with self._driver_count_ops:
                self._drivers.append(driver)

            log("SHOW in temp browser")

            try:
                driver.get(url)
                show_func(driver)

                # keep alive till the browser is closed
                while True:
                    _ = driver.window_handles
                    time.sleep(0.5)

            except (NoSuchWindowException, WebDriverException, SessionNotCreatedException) as e:
                log(f"QUIT temp browser ({e})")

            except:
                log(traceback.format_exc(), error=True)

            finally:
                with self._driver_count_ops:
                    driver.quit()
                    self._drivers.remove(driver)
                    self._n_drivers -= 1
        else:
            with self._driver_count_ops:
                self._n_drivers -= 1
