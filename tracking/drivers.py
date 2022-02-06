import atexit
import os
import queue
import stat
import threading
import traceback
from socket import error as SocketError

import psutil
import undetected_chromedriver as webdriver
from selenium.common.exceptions import (
    NoSuchWindowException,
    SessionNotCreatedException,
    WebDriverException,
)
from urllib3.exceptions import ProtocolError
from win32com.client import Dispatch
from windows.localization import TXT
from windows.log import log

CREATE_DRIVER_AT_INIT = False


def find_chrome_executable():
    """fix find_chrome_executable for x86 Windows"""

    candidates = set()
    for item in map(
        os.environ.get, ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
    ):
        if item:
            for subitem in (
                "Google/Chrome/Application",
                "Google/Chrome Beta/Application",
                "Google/Chrome Canary/Application",
            ):
                candidates.add(os.sep.join((item, subitem, "chrome.exe")))
    for candidate in candidates:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return os.path.normpath(candidate)


# monkey patch it
webdriver.find_chrome_executable = find_chrome_executable


def get_chrome_main_version():
    """get installed Chrome main version number"""

    filename = find_chrome_executable()
    parser = Dispatch("Scripting.FileSystemObject")
    version = parser.GetFileVersion(filename)
    return version.split(".")[0]


def patch_driver(version):
    """patch chromedriver then lock it to avoid further patching and permission errors"""

    log(f"PATCHING chromedriver {version=}")
    patcher = webdriver.Patcher(version_main=version)
    # unlock chromdriver.exe and patch it
    if os.path.exists(patcher.executable_path):
        os.chmod(patcher.executable_path, stat.S_IWRITE)
    patcher.auto()
    # lock chromedriver.exe to prevent any further patch
    os.chmod(patcher.executable_path, stat.S_IREAD)
    # prevent further file op on chromedriver.exe by the patcher
    webdriver.Patcher.is_binary_patched = lambda self: True
    log("chromedriver PATCHED")


class _DriversHandler:
    name = None
    _patching_lock = threading.Lock()
    _patching_done = False
    _chrome_main_version = get_chrome_main_version()

    def __init__(self):
        self.max_drivers = float("inf")
        self._n_in_creation = 0
        self._drivers = []
        self._drivers_available = queue.Queue()
        self._creation_threads = []
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
                patch_driver(cls._chrome_main_version)
                cls._patching_done = True

    def get_driver_options(self):
        raise NotImplementedError("a driver needs options")

    def create_driver(self):
        with self._driver_count_ops:
            n_drivers = len(self._drivers) + self._n_in_creation
            if can_create := n_drivers < self.max_drivers:
                self._n_in_creation += 1
                thread = threading.current_thread()
                self._creation_threads.append(thread)

        if can_create:
            driver = None
            self._log_creation("CREATION", n_drivers)
            try:
                _DriversHandler._patch_driver()
                options = self.get_driver_options()
                driver = webdriver.Chrome(options=options)
                self._log_creation("CREATED", n_drivers)

            except (SessionNotCreatedException, ProtocolError, SocketError) as e:
                self._log_creation(f"creation FAILED ({e})", n_drivers, error=True)

            finally:
                with self._driver_count_ops:
                    self._creation_threads.remove(thread)
                    self._n_in_creation -= 1
                    if driver:
                        self._drivers.append(driver)
                        self._drivers_available.put(driver)

            return driver
        return None

    def get(self):
        """try to get an available driver. if not try to create a driver then wait for an available one"""
        try:
            if driver := self._drivers_available.get(block=False):
                return driver
        except queue.Empty:
            pass

        # create a driver till max_drivers is reached
        self.create_driver()
        # wait for an available driver
        # since the creation might fail or the driver could be stolen by another thread
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

            # if drivers are still being created terminate those
            current_proc = psutil.Process()
            if any(thread.is_alive() for thread in self._creation_threads):
                for child in current_proc.children(recursive=True):
                    if "chromedriver.exe" in child.name().lower():
                        log(f"TERMINATE {child.name()} {child.pid}")
                        child.terminate()


class DriversToScrape(_DriversHandler):
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


class DriversToShow(_DriversHandler):
    name = "Chromedriver (browser)"

    def __init__(self):
        self._drivers_available = queue.Queue()
        super().__init__()

    def get_driver_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        return options

    def defer(self, show, url):
        threading.Thread(target=self._defer, args=(show, url), daemon=True).start()

    @staticmethod
    def _wait_browser_closed(driver):
        disconnected_msg = "disconnected: not connected to DevTools"
        while True:
            if msg := driver.get_log("driver"):
                if disconnected_msg in msg[-1]["message"]:
                    log("Chrome window closed by user")
                    break

    def _defer(self, show, url):
        if driver := self.get():
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
