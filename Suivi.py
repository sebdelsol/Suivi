# the less, the better for startup time
import sys

import PySimpleGUI as sg
from packaging.specifiers import SpecifierSet

from tools.img_tool import resize_and_colorize_img
from tracking.chrome import check_chrome
from windows.localization import TXT
from windows.theme import TH

PYTHON_REQUIREMENTS = ">=3.8"
TRACKERS_FILENAME = "Trackers"
LOAD_AS_JSON = True


class Splash:
    def __init__(self):
        self.log = sg.T(
            "", font=(TH.var_font, TH.splash_font_size), text_color=TH.splash_color
        )
        img_data = resize_and_colorize_img(
            TH.mail_img, TH.splash_img_height, TH.splash_color
        )
        layout = [[sg.Image(data=img_data)], [self.log]]
        args, kwargs = TH.get_window_params(layout)
        self.window = sg.Window(*args, **kwargs)

    def update(self, txt):
        self.log.update(f"{txt.capitalize()} ...")
        self.window.refresh()  # needed since there's no window loop

    def __enter__(self):
        return self

    def __exit__(self, atype, value, traceback):
        self.window.close()


def check_python(requirements):
    current_version = ".".join(str(n) for n in sys.version_info[:3])
    print(f"Python {current_version} running")

    if current_version in SpecifierSet(requirements):
        return True

    require = " and ".join(req.strip() for req in requirements.split(","))
    print(f"this app requires Python {require}")
    return False


if __name__ == "__main__":
    if check_python(PYTHON_REQUIREMENTS) and check_chrome():
        sg.theme(TH.theme)

        # create splash before importing to reduce startup time
        with Splash() as splash:
            splash.update(TXT.init)

            from windows.log import logger
            from windows.main import MainWindow

            main_window = MainWindow(TRACKERS_FILENAME, LOAD_AS_JSON, splash)
            main_window.addlog(logger)

        main_window.loop()
        print("Exiting")
        main_window.close()
        logger.close()

    print("Exit")
