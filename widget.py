import math
import time
import PySimpleGUI as sg
from tkinter import font as tk_font

from imgtool import expand_right_img64, get_img64_size, resize_and_colorize_img


class GraphRounded(sg.Graph):
    def draw_rounded_box(self, x, y, w, h, r, color):
        w2, h2, r2 = w * .5, h * .5, r * 2
        # cross
        self.draw_rectangle((x - w2, y + h2 - r), (x + w2, y - h2 + r), fill_color=color, line_color=color)
        self.draw_rectangle((x - w2 + r, y + h2), (x + w2 - r, y - h2), fill_color=color, line_color=color)
        # corners
        self.draw_arc((x - w2, y + h2 - r2), (x - w2 + r2, y + h2), 90, 90, fill_color=color, arc_color=color)
        self.draw_arc((x + w2 - r2, y + h2 - r2), (x + w2, y + h2), 90, 0, fill_color=color, arc_color=color)
        self.draw_arc((x - w2, y - h2), (x - w2 + r2, y - h2 + r2), 90, 180, fill_color=color, arc_color=color)
        self.draw_arc((x + w2 - r2, y - h2), (x + w2, y - h2 + r2), 90, 270, fill_color=color, arc_color=color)


class ButtonMouseOver(sg.Button):
    default_colors = dict(Enter='grey75', Leave='grey95')
    binds = ('<Enter>', '<Leave>')

    @classmethod
    def finalize_all(cls, window):
        for button in filter(lambda elt: isinstance(elt, cls), window.element_list()):
            button.finalize()

    def __init__(self, *args, mouseover_color=None, **kwargs):
        colors = kwargs.get('button_color')
        if isinstance(colors, tuple):
            text_color, button_color = colors
        else:
            text_color, button_color = None, colors

        self.colors = {'Leave': button_color or ButtonMouseOver.default_colors['Leave'],
                       'Enter': mouseover_color or ButtonMouseOver.default_colors['Enter']}

        kwargs['button_color'] = (text_color, self.colors['Leave'])

        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in ButtonMouseOver.binds:
            self.Widget.bind(bind, self.mouseover)

    def mouseover(self, event):
        self.update(button_color=self.colors.get(event.type.name))


class ButtonTxtAndImg(ButtonMouseOver):
    def __init__(self, *args, im_margin=0, im_height=20, **kwargs):
        self.im_margin = im_margin
        self.im_height = im_height
        self.image_filename = kwargs['image_filename']

        del kwargs['image_filename']
        kwargs['image_data'] = self.get_image_data(kwargs)

        kwargs['auto_size_button'] = False
        super().__init__(*args, **kwargs)

    def get_image_data(self, kwargs):
        # colorize the img with the text color
        txt_color = kwargs.get('button_color')[0]
        self.im_data = resize_and_colorize_img(self.image_filename, self.im_height, txt_color)
        self.im_width = get_img64_size(self.im_data)[0]
        return self.im_data

    def update_layout(self, txt):
        # add spaces to fit text after the img
        wfont = tk_font.Font(self.ParentForm.TKroot, self.Font)
        new_txt = ' ' * round((self.im_width + self.im_margin * 2) / wfont.measure(' ')) + txt
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
        if color := kwargs.get('button_color'):
            if isinstance(color, tuple):
                if color[0] != self.ButtonColor[0]:
                    kwargs['image_data'] = self.get_image_data(kwargs)

        super().update(*args, **kwargs)
        if update_layout:
            txt = kwargs.get('text') or (len(args) > 0 and args[0])
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
    @staticmethod
    def blend_rgb_colors(color1, color2, t):
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        return r1 * (1 - t) + r2 * t, g1 * (1 - t) + g2 * t, b1 * (1 - t) + b2 * t

    @staticmethod
    def get_one_period_colors(color_start, color_end, array_size):
        colors = []
        for x in range(array_size):
            t = math.sin((2 * math.pi * (x % array_size)) / array_size)
            r, g, b = MlinePulsing.blend_rgb_colors(color_start, color_end, (t + 1) * .5)
            color = f'#{round(r):02x}{round(g):02x}{round(b):02x}'
            colors.append(color)
        return colors

    def color_to_rgb(self, color):
        r, g, b = self.Widget.winfo_rgb(color)  # works even with any tkinter defined color like 'red'
        return r / 256, g / 256, b / 256

    def init_pulsing(self, color_start, color_end, percent_to_end_color, frequency=1.5):
        self.is_pulsing = False
        self.pulsing_tag = f'pulsing{id(self)}'
        self.pulsing_array_size = 32  # size of colors array
        self.pulsing_time_step = 50  # ms
        self.pulsing_frequency = frequency
        self.pulsing_tags = {}

        # class attribute, initialized after startup
        if not hasattr(self, 'pulsing_colors'):
            color_start = self.color_to_rgb(color_start)
            color_end = self.color_to_rgb(color_end)
            color_end = self.blend_rgb_colors(color_start, color_end, percent_to_end_color)
            MlinePulsing.pulsing_colors = self.get_one_period_colors(color_start, color_end, self.pulsing_array_size)

    def add_tag(self, key, start, end):
        self.Widget.tag_add(f'{self.pulsing_tag}{key}', start, end)

    def start_pulsing(self, keys):
        for key in keys:
            self.pulsing_tags[f'{self.pulsing_tag}{key}'] = (0, time.time())

        if not self.is_pulsing:
            self.is_pulsing = True
            self.pulse()

    def stop_pulsing(self):
        self.pulsing_tags = {}
        self.is_pulsing = False

    def pulse(self):
        if self.is_pulsing:
            new_t = time.time()
            for tag, (index, t) in self.pulsing_tags.items():
                color = self.pulsing_colors[round(index) % self.pulsing_array_size]
                self.Widget.tag_configure(tag, foreground=color)

                index += self.pulsing_frequency * self.pulsing_array_size * (new_t - t)
                self.pulsing_tags[tag] = index, new_t

            window = self.ParentForm
            window.TKroot.after(self.pulsing_time_step, self.pulse)
