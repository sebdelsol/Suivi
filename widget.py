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
        kwargs['border_width'] = 0

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
