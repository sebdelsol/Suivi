from mylog import _log

chrome_exe = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
USE_UC_V2 = True
CREATE_DRIVER_AT_INIT = False

if USE_UC_V2:
    import undetected_chromedriver as webdriver
else:
    import undetected_chromedriver._compat as webdriver

import psutil
import threading
import queue

class Drivers:
    driver_timeout = 100 # s
    lock = threading.Lock()
    n_drivers = 1

    experimental_options = dict(
        prefs = {'translate_whitelists': {'de':'fr', 'es':'fr', 'en':'fr', 'und':'fr', 'zh-CN':'fr', 'zh-TW':'fr'},
                 'translate': {'enabled':'true'},
                 'profile.managed_default_content_settings.images': 2,  # remove image
                 'profile.managed_default_content_settings.cookies': 2, # remove cookies
        },
        excludeSwitches = ['enable-logging']
    )

    options = ( '--no-first-run', 
                '--no-service-autorun', 
                '--password-store=basic', 
                '--lang=fr', 
    )

    options_V1 = ('--window-size=1024,768', ) # reach sliders
    options_V2 = ('--excludeSwitches --enable-logging', 
                  '--blink-settings=imagesEnabled=false')

    def __init__(self, splash):
        self.drivers = queue.Queue() if self.n_drivers > 0 else None
        self.n_created_drivers = 0

        if CREATE_DRIVER_AT_INIT:
            for i in range(self.n_drivers):
                splash.update(f'création pilote {i + 1}/{self.n_drivers}')
                self.create_driver_if_needed()

    def create_driver_if_needed(self):
        with self.lock: # prevents driver creation when it's already being created in another thread
            if self.n_created_drivers < self.n_drivers:

                _log ('DRIVER creation')
                options = webdriver.ChromeOptions()
                options.headless = True
                options.binary_location = chrome_exe
                
                for option in self.options + (self.options_V2 if USE_UC_V2 else self.options_V1):
                    options.add_argument(option)
                
                if not USE_UC_V2: # prefs do not work on UC v2
                    for k, v in self.experimental_options.items():
                        options.add_experimental_option(k, v)

                driver = webdriver.Chrome(options = options) 
                driver.set_page_load_timeout(self.driver_timeout)

                self.drivers.put(driver)
                self.n_created_drivers += 1
                _log (f'DRIVER #{self.n_created_drivers} created')

    def get(self):
        self.create_driver_if_needed()
        return self.drivers.get()

    def dispose(self, driver):
        self.drivers.put(driver)

    def close(self):
        for proc in psutil.process_iter():
            if 'chromedriver.exe' in proc.name().lower():
                _log (f'kill {proc.name()} {proc.pid}')
                proc.kill()