import os

from win32api import HIWORD, GetFileVersionInfo

# needed for being compliant with W3C webdriver shadow-root specs
CHROME_MIN_VERSION = 96


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


def get_chrome_main_version():
    """get installed Chrome main version number"""
    filename = find_chrome_executable()
    # https://stackoverflow.com/a/1237635
    info = GetFileVersionInfo(filename, "\\")
    return HIWORD(info["FileVersionMS"])


def check_chrome():
    if find_chrome_executable():
        if (version := get_chrome_main_version()) >= CHROME_MIN_VERSION:
            print(f"found chrome {version}")
            return True

    print(f"this app needs chrome >={CHROME_MIN_VERSION}")
    return False
