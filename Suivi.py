# the less, the better for startup time
import sys

import PySimpleGUI as sg
from packaging.specifiers import SpecifierSet

import localization as TXT
import theme as TH
from imgtool import resize_and_colorize_img

Python_version = ">=3.8, <3.9"
Trackers_filename = "Trackers"
Load_as_json = True


class Splash:
    def __init__(self):
        self.log = sg.T("", font=(TH.var_font, TH.splash_font_size), text_color=TH.splash_color)
        img_data = resize_and_colorize_img(TH.mail_img, TH.splash_img_height, TH.splash_color)
        layout = [[sg.Image(data=img_data)], [self.log]]
        args, kwargs = TH.get_window_params(layout, grab_anywhere=False)
        self.window = sg.Window(*args, **kwargs)

    def update(self, txt):
        self.log.update(f"{txt.capitalize()} ...")
        self.window.refresh()  # needed since there's no window loop

    def close(self):
        self.window.close()


if __name__ == "__main__":
    version = ".".join(str(v) for v in sys.version_info[:3])
    print(f"Python {version} running")

    needed_version = SpecifierSet(Python_version)
    if version not in needed_version:
        needs = " and ".join(need for need in str(needed_version).split(","))
        print(f"Unfortunatly this app needs Python {needs}")

    else:
        sg.theme(TH.theme)

        # create splash before importing to reduce startup time
        splash = Splash()
        splash.update(TXT.init)

        from log import logger
        from mainWindow import MainWindow

        main_window = MainWindow(Trackers_filename, Load_as_json, splash)
        main_window.addlog(logger)
        splash.close()

        main_window.loop()

        main_window.close()
        logger.close()

    print("exiting")
