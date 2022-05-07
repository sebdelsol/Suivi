import undetected_chromedriver as webdriver
from win32api import HIWORD, GetFileVersionInfo

# needed for being compliant with W3C webdriver shadow-root specs
CHROME_MIN_VERSION = 96


def get_chrome_main_version():
    """get installed Chrome main version number"""
    filename = webdriver.find_chrome_executable()
    # https://stackoverflow.com/a/1237635
    info = GetFileVersionInfo(filename, "\\")
    return HIWORD(info["FileVersionMS"])


def check_chrome():
    """check chrome exists and is a good enough version"""
    if webdriver.find_chrome_executable():
        if (version := get_chrome_main_version()) >= CHROME_MIN_VERSION:
            print(f"found chrome {version}")
            return True

    print(f"this app needs chrome >={CHROME_MIN_VERSION}")
    return False


Chrome_Version = get_chrome_main_version()
