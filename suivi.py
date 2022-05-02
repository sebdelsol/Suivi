"""
   .d8888b.           d8b          d8b
  d88P  Y88b          Y8P          Y8P
  Y88b.
   "Y888b.   888  888 888 888  888 888
      "Y88b. 888  888 888 888  888 888
        "888 888  888 888 Y88  88P 888
  Y88b  d88P Y88b 888 888  Y8bd8P  888
   "Y8888P"   "Y88888 888   Y88P   888
"""

# the less import, the better for startup time
import sys
from contextlib import contextmanager

import PySimpleGUI as sg

from tools.img_tool import resize_and_colorize_img
from tracking.chrome import check_chrome
from windows.localization import TXT
from windows.theme import TH

PYTHON_MIN_VERSION = "3.8"
TRACKERS_FILENAME = "Trackers"
LOAD_AS_JSON = True
TRANSLATION_MODULE = "deepl"  # a module in the translation package (except translate)


@contextmanager
def get_splash():
    log_font = TH.var_font, TH.splash_font_size
    log_txt = sg.T("", font=log_font, text_color=TH.splash_color)
    splash_args = TH.splash_img, TH.splash_img_height, TH.splash_color
    img_data = resize_and_colorize_img(*splash_args)
    args, kwargs = TH.get_window_params([[sg.Image(data=img_data)], [log_txt]])
    window = sg.Window(*args, **kwargs)

    def update(txt):
        log_txt.update(f"{txt.capitalize()} ...")
        window.refresh()  # needed since there's no window loop

    update(TXT.init)
    yield update
    window.close()


def check_python(min_version):
    print(f"Python {'.'.join(str(v) for v in sys.version_info[:3])} running")
    if sys.version_info >= tuple(int(r) for r in min_version.split(".")):
        return True

    print(f"Python {min_version} at least required")
    return False


if __name__ == "__main__":
    if check_python(PYTHON_MIN_VERSION) and check_chrome():
        sg.theme(TH.theme)

        # create splash before importing to reduce startup time
        with get_splash() as splash:
            from windows.log import logger
            from windows.main import MainWindow

            window_args = TRACKERS_FILENAME, TRANSLATION_MODULE, LOAD_AS_JSON, splash
            main_window = MainWindow(*window_args)
            main_window.addlog(logger)

        main_window.loop()
        main_window.close()
        logger.close()
