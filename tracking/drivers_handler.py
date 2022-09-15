import atexit
import os
import queue
import threading
from socket import error as SocketError
from subprocess import CREATE_NO_WINDOW

import lxml.html
import psutil
from selenium.common.exceptions import (
    NoSuchElementException,
    NoSuchWindowException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError
from windows.log import log

from .driver import EnhancedChrome, EnhancedOptions


class DriversHandler:
    name = None
    headless = False
    auto_translate = True

    _terminate_lock = threading.Lock()

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

    def _create_driver(self):
        with self._driver_count_ops:
            n_drivers = len(self._drivers) + self._n_in_creation
            if can_create := n_drivers < self.max_drivers:
                self._n_in_creation += 1

        if can_create:
            driver = None
            self._log_creation("CREATION", n_drivers)
            try:
                options = EnhancedOptions(
                    headless=self.headless,
                    auto_translate=self.auto_translate,
                )
                driver = EnhancedChrome(
                    options=options, service_creationflags=CREATE_NO_WINDOW
                )
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
                    terminated.append((child, child.exe()))

            # wait for actual termination to avoid collisions
            # from _terminate in different threads
            for proc, exe_path in terminated:
                proc.wait(2)
                if os.path.exists(exe_path):
                    print(f"remove {exe_path}")
                    os.remove(exe_path)


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
                    driver.set_timeouts(page_load_timeout, wait_elt_timeout)
                    try:
                        if content := get_content(courier, idship, driver):
                            return lxml.html.fromstring(content)
                        error = "No Content"

                    except (
                        NoSuchElementException,
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
                driver.wait_for_browser_closed()

            except (
                NoSuchElementException,
                NoSuchWindowException,
                WebDriverException,
                SessionNotCreatedException,
                TimeoutException,
            ) as e:
                log(f"{self.name} SHOW failed ({type(e).__name__})", error=True)

            finally:
                self._destroy(driver)
