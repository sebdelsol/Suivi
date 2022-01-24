import threading
import queue
from log import log
from config import chrome_exe
import theme as TH

USE_UC_V2 = True
CREATE_DRIVER_AT_INIT = False

if USE_UC_V2:
    import undetected_chromedriver as webdriver
else:
    import undetected_chromedriver._compat as webdriver


class DriverHandler:
    driver_timeout = 100  # s
    driver_creation = threading.Lock()
    n_drivers = 1

    experimental_options = dict(
        prefs={'translate_whitelists': {'de': 'fr', 'es': 'fr', 'en': 'fr', 'und': 'fr', 'zh-CN': 'fr', 'zh-TW': 'fr'},
               'translate': {'enabled': 'true'},
               'profile.managed_default_content_settings.images': 2,  # remove image
               'profile.managed_default_content_settings.cookies': 2,  # remove cookies
               },
        excludeSwitches=['enable-logging']
    )

    options = ('--no-first-run',
               '--no-service-autorun',
               '--password-store=basic',
               '--lang=fr',
               )

    options_V1 = ('--window-size=1024,768', )  # reach sliders
    options_V2 = ('--excludeSwitches --enable-logging',
                  '--blink-settings=imagesEnabled=false')

    def __init__(self, splash):
        self.drivers_available = queue.Queue() if self.n_drivers > 0 else None
        self.drivers = []

        if CREATE_DRIVER_AT_INIT:
            for i in range(self.n_drivers):
                if splash:
                    splash.update(f'{TH.driver_creation} {i + 1}/{self.n_drivers}')
                self.create_driver_if_needed()

    def create_driver_if_needed(self):
        # prevents driver creation when it's already being created in another thread
        with self.driver_creation:
            if len(self.drivers) < self.n_drivers:

                log(f'driver ({len(self.drivers) + 1}/{self.n_drivers}) CREATION')
                options = webdriver.ChromeOptions()
                options.headless = True
                options.binary_location = chrome_exe

                for option in self.options + (self.options_V2 if USE_UC_V2 else self.options_V1):
                    options.add_argument(option)

                if not USE_UC_V2:  # prefs do not work on UC v2
                    for k, v in self.experimental_options.items():
                        options.add_experimental_option(k, v)

                driver = webdriver.Chrome(options=options)
                driver.set_page_load_timeout(self.driver_timeout)

                self.drivers_available.put(driver)
                self.drivers.append(driver)
                log(f'driver ({len(self.drivers)}/{self.n_drivers}) CREATED')

    def get(self):
        self.create_driver_if_needed()
        return self.drivers_available.get()

    def dispose(self, driver):
        self.drivers_available.put(driver)

    def close(self):
        # remaining driver in creation is handled by undetected_chromedriver @ exit
        for i, driver in enumerate(self.drivers):
            log(f'QUIT driver {i + 1}/{len(self.drivers)}')
            driver.quit()
