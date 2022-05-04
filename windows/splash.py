import PySimpleGUI as sg
from tools.img_tool import resize_and_colorize_img

from windows.localization import TXT
from windows.theme import TH


class Splash:
    log_kw = dict(font=(TH.var_font, TH.splash_font_size), text_color=TH.splash_color)
    img_args = TH.splash_img, TH.splash_img_height, TH.splash_color

    def __init__(self):
        img = sg.Image(data=resize_and_colorize_img(*self.img_args))
        self.log = sg.T("", **self.log_kw)
        layout = [[img], [self.log]]
        args, kwargs = TH.get_window_params(layout)
        self.window = sg.Window(*args, **kwargs)
        self.update(TXT.init)

    def update(self, txt):
        self.log.update(f"{txt.capitalize()} ...")
        self.window.refresh()  # needed since there's no window loop

    def __enter__(self):
        return self

    def __exit__(self, atype, value, traceback):
        self.window.close()
