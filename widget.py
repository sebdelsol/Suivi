import math
import time
from ctypes import windll
from tkinter import font as tk_font

import PySimpleGUI as sg

from imgtool import expand_right_img64, get_gif_durations, get_img64_size, resize_and_colorize_img

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080


class Window(sg.Window):
    def __init__(self, *args, no_titlebar=False, **kwargs):
        self._no_titlebar = no_titlebar
        self.is_iconified = False
        super().__init__(*args, **kwargs)

    def Finalize(self, *args, **kwargs):
        super().Finalize(*args, **kwargs)
        if self._no_titlebar:
            root = self.TKroot
            root.overrideredirect(True)
            hwnd = windll.user32.GetParent(root.winfo_id())

            if hasattr(windll.user32, "GetWindowLongPtrW"):
                get_window_style = windll.user32.GetWindowLongPtrW
                set_window_style = windll.user32.SetWindowLongPtrW
            else:
                get_window_style = windll.user32.GetWindowLongW
                set_window_style = windll.user32.SetWindowLongW

            style = get_window_style(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            set_window_style(hwnd, GWL_EXSTYLE, style)
            root.withdraw()
            root.deiconify()

            root.bind("<Map>", self.notify)
            root.bind("<Unmap>", self.notify)

    def minimize(self):
        if self._no_titlebar:
            self.TKroot.overrideredirect(False)
        super().minimize()

    def notify(self, event):
        if self.TKroot == event.widget:
            # print("!!!!!!!", event.type.name, "icon:", self.is_iconified)
            if event.type.name == "Map":
                if self.is_iconified:
                    self.is_iconified = False
                    self.TKroot.overrideredirect(True)
                    # print("   UN minimize")

            elif event.type.name == "Unmap":
                if not self.is_iconified:
                    self.is_iconified = True
                    self.TKroot.overrideredirect(False)
                    # print("    minimize")


class GraphRounded(sg.Graph):
    def draw_rounded_box(self, x, y, w, h, r, color):
        w2, h2, r2 = w * 0.5, h * 0.5, r * 2
        # cross
        self.draw_rectangle((x - w2, y + h2 - r), (x + w2, y - h2 + r), fill_color=color, line_color=color)
        self.draw_rectangle((x - w2 + r, y + h2), (x + w2 - r, y - h2), fill_color=color, line_color=color)
        # corners
        self.draw_arc((x - w2, y + h2 - r2), (x - w2 + r2, y + h2), 90, 90, fill_color=color, arc_color=color)
        self.draw_arc((x + w2 - r2, y + h2 - r2), (x + w2, y + h2), 90, 0, fill_color=color, arc_color=color)
        self.draw_arc((x - w2, y - h2), (x - w2 + r2, y - h2 + r2), 90, 180, fill_color=color, arc_color=color)
        self.draw_arc((x + w2 - r2, y - h2), (x + w2, y - h2 + r2), 90, 270, fill_color=color, arc_color=color)


class ButtonMouseOver(sg.Button):
    default_colors = dict(Enter="grey75", Leave="grey95")
    binds = ("<Enter>", "<Leave>")

    @classmethod
    def finalize_all(cls, window):
        for button in filter(lambda elt: isinstance(elt, cls), window.element_list()):
            button.finalize()

    def __init__(self, *args, mouse_over_color=None, **kwargs):
        colors = kwargs.get("button_color")
        if isinstance(colors, tuple):
            text_color, button_color = colors
        else:
            text_color, button_color = None, colors

        self.colors = {
            "Leave": button_color or ButtonMouseOver.default_colors["Leave"],
            "Enter": mouse_over_color or ButtonMouseOver.default_colors["Enter"],
        }

        kwargs["button_color"] = (text_color, self.colors["Leave"])

        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in ButtonMouseOver.binds:
            self.Widget.bind(bind, self.on_mouse_over)

    def on_mouse_over(self, event):
        self.update(button_color=self.colors.get(event.type.name))


class ButtonTxtAndImg(ButtonMouseOver):
    def __init__(self, *args, im_margin=0, im_height=20, **kwargs):
        self.im_margin = im_margin
        self.im_height = im_height
        self.image_filename = kwargs["image_filename"]

        del kwargs["image_filename"]
        kwargs["image_data"] = self.get_image_data(kwargs)

        kwargs["auto_size_button"] = False
        super().__init__(*args, **kwargs)

    def get_image_data(self, kwargs):
        # colorize the img with the text color
        txt_color = kwargs.get("button_color")[0]
        self.im_data = resize_and_colorize_img(self.image_filename, self.im_height, txt_color)
        self.im_width = get_img64_size(self.im_data)[0]
        return self.im_data

    def update_layout(self, txt):
        # add spaces to fit text after the img
        wfont = tk_font.Font(self.ParentForm.TKroot, self.Font)
        new_txt = " " * round((self.im_width + self.im_margin * 2) / wfont.measure(" ")) + txt
        new_size = (wfont.measure(new_txt) + self.im_margin, self.im_height + self.im_margin * 2)

        # expand the img to the right to fill the whole button
        self.set_size(new_size)
        self.Widget.configure(wraplength=new_size[0])
        new_image_data = expand_right_img64(self.im_data, new_size)
        self.update(new_txt, image_data=new_image_data, update_layout=False)

    def finalize(self):
        self.update_layout(self.get_text())
        super().finalize()

    def update(self, *args, update_layout=True, **kwargs):
        if color := kwargs.get("button_color"):
            if isinstance(color, tuple):
                if color[0] != self.ButtonColor[0]:
                    kwargs["image_data"] = self.get_image_data(kwargs)

        super().update(*args, **kwargs)
        if update_layout:
            txt = kwargs.get("text") or (len(args) > 0 and args[0])
            if txt:
                self.update_layout(txt)


class TextFit(sg.Text):
    def font_fit_to_txt(self, txt, max_width, font_wanted_size, min_font_size):
        name, size = self.Font[0], font_wanted_size
        while True:
            font = name, size
            wfont = tk_font.Font(self.ParentForm.TKroot, font)
            extend = wfont.measure(txt)
            if size > min_font_size and extend > max_width:
                size -= 1
            else:
                self.update(font=font)
                break
        return size


class MlinePulsing(sg.MLine):
    colors = {}

    @staticmethod
    def blend_rgb_colors(color1, color2, t):
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        return r1 * (1 - t) + r2 * t, g1 * (1 - t) + g2 * t, b1 * (1 - t) + b2 * t

    @staticmethod
    def get_one_period_colors(color_start, color_end, array_size):
        colors = []
        for x in range(array_size):
            t = (math.cos((2 * math.pi * (x % array_size)) / array_size) + 1) * 0.5
            r, g, b = MlinePulsing.blend_rgb_colors(color_start, color_end, 1 - t)
            color = f"#{round(r):02x}{round(g):02x}{round(b):02x}"
            colors.append(color)
        return colors

    def color_to_rgb(self, color):
        r, g, b = self.Widget.winfo_rgb(color)  # works even with any tkinter defined color like 'red'
        return int(r / 256), int(g / 256), int(b / 256)

    def init_pulsing(self, color_start, color_end, percent_to_end_color=0.75, frequency=1.5):
        self.is_pulsing = False
        self.pulsing_tag = f"pulsing{id(self)}"
        self.pulsing_array_size = 32  # size of colors array
        self.pulsing_time_step = 50  # ms
        self.pulsing_frequency = frequency
        self.pulsing_tags = {}

        color_start = self.color_to_rgb(color_start)
        color_end = self.color_to_rgb(color_end)
        color_end = self.blend_rgb_colors(color_start, color_end, percent_to_end_color)
        self.colors_key = (color_start, color_end)

        # initialized after startup as a class attribute
        if self.colors_key not in MlinePulsing.colors:
            MlinePulsing.colors[self.colors_key] = self.get_one_period_colors(
                color_start, color_end, self.pulsing_array_size
            )

    def add_pulsing_tag(self, key, start, end):
        self.Widget.tag_add(f"{self.pulsing_tag}{key}", start, end)

    def start_pulsing(self, keys=None):
        for key in keys or [""]:
            self.pulsing_tags[f"{self.pulsing_tag}{key}"] = (0, time.time())

        if not self.is_pulsing:
            self.is_pulsing = True
            self.pulse()

    def stop_pulsing(self):
        for tag in self.pulsing_tags.keys():
            self.Widget.tag_delete(tag)
        self.pulsing_tags = {}
        self.is_pulsing = False

    def pulse(self):
        if self.is_pulsing:
            now = time.time()
            colors = MlinePulsing.colors[self.colors_key]
            for tag, (index, t) in self.pulsing_tags.items():
                color = colors[round(index) % self.pulsing_array_size]
                self.Widget.tag_configure(tag, foreground=color)

                index += self.pulsing_frequency * self.pulsing_array_size * (now - t)
                self.pulsing_tags[tag] = index, now

            window = self.ParentForm
            window.TKroot.after(self.pulsing_time_step, self.pulse)


class MLinePulsingButton(MlinePulsing):
    def as_a_button(self, on_click=None, mouse_over_color=None, button_color=None):
        self.mouse_enter_color = mouse_over_color or self.BackgroundColor
        self.mouse_leave_color = button_color or self.BackgroundColor
        self.button_tag = f"button{id(self)}"
        self.button_tags = {}
        self.on_click_callback = on_click
        self.pointed_key = None
        
        widget = self.Widget
        widget.bind("<Any-Motion>", self.on_mouse_move)
        widget.bind("<Leave>", self.on_mouse_leave)
        widget.bind("<Button-1>", self.on_click)

    def on_mouse_leave(self, event):
        if event.type.name == "Leave":
            self.pointed_key = None
            for tag in self.button_tags.keys():
                self.Widget.tag_configure(tag, background=self.mouse_leave_color)

    def on_click(self, event):
        if self.pointed_key and self.on_click_callback:
            self.on_click_callback(self.pointed_key)

    def on_mouse_move(self, event):
        widget = self.Widget
        index = widget.index("@%s,%s" % (event.x, event.y))

        self.pointed_key = None
        tags = widget.tag_names(index)
        for tag, (key, start, end) in self.button_tags.items():
            if tag in tags and widget.compare(start, "<=", index) and widget.compare(index, "<=", end):
                self.pointed_key = key
                widget.tag_configure(tag, background=self.mouse_enter_color)
            else:
                widget.tag_configure(tag, background=self.mouse_leave_color)

    def add_button_tag(self, key, start, end):
        tag = f"{self.button_tag}{key}"
        self.button_tags[tag] = (key, start, end)
        self.Widget.tag_add(tag, start, end)


class HLine(sg.Col):
    def __init__(self, p=0, color="black", thickness=1):
        super().__init__([[]], p=p, s=(None, thickness), background_color=color, expand_x=True)

    def set_width(self, width):
        self.Widget.canvas.config(width=width)


class AnimatedGif(sg.Image):
    def __init__(self, *args, speed=1, **kwargs):
        self.speed = speed
        super().__init__(*args, **kwargs)

        self.durations = get_gif_durations(self.Data)
        self.animate(reset=True)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if kwargs.get("visible"):
            self.animate(reset=True)

    def animate(self, reset=False):
        if self.visible:
            now = time.time()
            if reset:
                self.last_time = now
                self.frame_index = 0
                self.precise_index = 0
            dt = now - self.last_time
            self.last_time = now

            duration = self.durations[self.frame_index % len(self.durations)]
            self.precise_index += self.speed * dt * 1000 / duration
            frame_step = round(self.precise_index - self.frame_index)
            self.frame_index += frame_step
            for _ in range(frame_step):
                self.update_animation(self.Data, time_between_frames=0)

            time_step = max(20, round(duration / self.speed))
            window = self.ParentForm
            window.TKroot.after(time_step, self.animate)
