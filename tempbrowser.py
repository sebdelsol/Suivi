import atexit
import threading
import time
import traceback
from socket import error as SocketError

import undetected_chromedriver as webdriver
from selenium.common.exceptions import NoSuchWindowException, SessionNotCreatedException, WebDriverException
from urllib3.exceptions import ProtocolError

from config import chrome_exe
from log import log


class TempBrowser:
    @staticmethod
    def create_browser():
        try:
            options = webdriver.ChromeOptions()
            options.binary_location = chrome_exe
            options.add_argument("--start-maximized")
            return webdriver.Chrome(options=options)

        except (SessionNotCreatedException, ProtocolError, SocketError):
            pass

    def __init__(self):
        self.browsers = []
        self.browsers_ops = threading.Lock()
        atexit.register(self.close)

    def defer(self, show_func, url):
        threading.Thread(target=self._defer, args=(show_func, url), daemon=True).start()

    def _defer(self, show_func, url):
        log("CREATE a temp browser")
        browser = self.create_browser()

        if browser:
            with self.browsers_ops:
                self.browsers.append(browser)

            log("SHOW in temp browser")

            try:
                browser.get(url)
                show_func(browser)

                # keep alive till the browser is closed
                while True:
                    _ = browser.window_handles
                    time.sleep(0.5)

            except (NoSuchWindowException, WebDriverException, SessionNotCreatedException) as e:
                log(f"QUIT temp browser ({e})")

            except:
                log(traceback.format_exc(), error=True)

            finally:
                with self.browsers_ops:
                    browser.quit()
                    self.browsers.remove(browser)

    def close(self):
        print("CLOSE temp browsers")
        with self.browsers_ops:
            for browser in self.browsers:
                print("QUIT temp browser")
                browser.quit()


TempBrowser = TempBrowser()
