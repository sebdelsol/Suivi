import atexit
import os
import queue
import stat
import threading
import time
from socket import error as SocketError

import psutil
import undetected_chromedriver as webdriver
from selenium.common.exceptions import (
    NoSuchWindowException,
    SessionNotCreatedException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import ProtocolError
from win32api import HIWORD, GetFileVersionInfo
from windows.localization import TXT
from windows.log import log

CREATE_DRIVER_AT_INIT = False


def find_chrome_executable():
    """fix find_chrome_executable for x86 Windows"""
    candidates = set()
    for item in map(
        os.environ.get, ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
    ):
        if item:  # it happens to be None
            for subitem in (
                "Google/Chrome/Application",
                "Google/Chrome Beta/Application",
                "Google/Chrome Canary/Application",
            ):
                candidates.add(os.sep.join((item, subitem, "chrome.exe")))
    for candidate in candidates:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return os.path.normpath(candidate)
    return None


# monkey patch it
webdriver.find_chrome_executable = find_chrome_executable


def get_chrome_main_version():
    """get installed Chrome main version number"""
    filename = find_chrome_executable()
    # https://stackoverflow.com/a/1237635
    info = GetFileVersionInfo(filename, "\\")
    return HIWORD(info["FileVersionMS"])


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


class DriversHandler:
    name = None
    _terminate_lock = threading.Lock()
    _patching_lock = threading.Lock()
    _patching_done = False

    def __init__(self):
        self.max_drivers = float("inf")
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

    def get_driver_options(self):
        raise NotImplementedError("a driver needs options")

    def create_driver(self):
        with self._driver_count_ops:
            n_drivers = len(self._drivers) + self._n_in_creation
            if can_create := n_drivers < self.max_drivers:
                self._n_in_creation += 1

        if can_create:
            driver = None
            self._log_creation("CREATION", n_drivers)
            try:
                DriversHandler._patch_driver()
                options = self.get_driver_options()
                driver = webdriver.Chrome(options=options)
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

    def get(self):
        """
        try to get an available driver.
        if not try to create a driver & wait for an available one
        """
        try:
            if driver := self._drivers_available.get(block=False):
                return driver
        except queue.Empty:
            pass

        self.create_driver()
        # wait for an available driver since the creation might have failed
        # or the created driver might have be stolen by another thread
        return self._drivers_available.get()

    def dispose(self, driver):
        self._drivers_available.put(driver)

    def destroy(self, driver):
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
    max_drivers = 2
    name = "Chromedriver (scrapper)"

    options = (
        "--no-first-run",
        "--no-service-autorun",
        "--password-store=basic",
        "--lang=fr",
        "--excludeSwitches --enable-logging",
        "--blink-settings=imagesEnabled=false",
    )

    def start(self, splash, max_drivers=None):
        self.max_drivers = max_drivers or DriversToScrape.max_drivers

        if CREATE_DRIVER_AT_INIT:
            for i in range(self.max_drivers):
                if splash:
                    splash.update(f"{TXT.driver_creation} {i + 1}/{self.max_drivers}")
                self.create_driver()

    def get_driver_options(self):
        options = webdriver.ChromeOptions()
        options.headless = True
        for option in self.options:
            options.add_argument(option)

        return options


class DriversToShow(DriversHandler):
    name = "Chromedriver (browser)"

    def get_driver_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        return options

    def get_and_defer_show(self, page_load_timeout=10, wait_elt_timeout=15):
        """decorator to give the decorated function a driver
        and handle the deferred show with timeouts"""

        def inner(show):
            def wrapper(*args):
                args = (show, page_load_timeout, wait_elt_timeout) + args
                threading.Thread(target=self._defer, args=args, daemon=True).start()

            return wrapper

        return inner

    def _defer(self, show, page_load_timeout, wait_elt_timeout, *args):
        if driver := self.get():
            log(f"SHOW in {self.name}")
            try:

                def wait_until(until):
                    return WebDriverWait(driver, wait_elt_timeout).until(until)

                driver.wait_until = wait_until
                driver.set_page_load_timeout(page_load_timeout)
                show(*args, driver)
                self._wait_browser_closed(driver)

            except (
                NoSuchWindowException,
                WebDriverException,
                SessionNotCreatedException,
            ) as e:
                log(f"{self.name} SHOW failed ({e})", error=True)

            finally:
                self.destroy(driver)

    @staticmethod
    def _wait_browser_closed(driver):
        disconnected_msg = "disconnected: not connected to DevTools"
        while True:
            time.sleep(0.5)
            if msg := driver.get_log("driver"):
                if disconnected_msg in msg[-1]["message"]:
                    log("Chrome window closed by user")
                    break
