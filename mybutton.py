import PySimpleGUI as sg
from tkinter import font

from imgtool import expand_right_img64, get_img64_size, resize_and_colorize_img

#-------------------------
class MyButton(sg.Button):
    default_colors = dict( Enter = 'grey75', Leave = 'grey95')
    binds = ('<Enter>', '<Leave>')

    @classmethod
    def finalize_all(cls, window):
        for button in filter(lambda elt: isinstance(elt, cls), window.element_list()):
            button.finalize()

    def __init__(self, *args, mouseover_color = None, **kwargs):
        colors = kwargs.get('button_color')
        if isinstance(colors, tuple):
            text_color, button_color = colors
        else:
            text_color, button_color = None, colors

        self.colors = { 'Leave' : button_color or MyButton.default_colors['Leave'],
                        'Enter' : mouseover_color or MyButton.default_colors['Enter'] }

        kwargs['button_color'] = (text_color, self.colors['Leave'])
        kwargs['border_width'] = 0

        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in MyButton.binds:
            self.Widget.bind(bind, self.mouseover)            

    def mouseover(self, event):
        self.update(button_color = self.colors.get(event.type.name))

#-------------------------------------------------
class MyButtonImg(MyButton):
    def __init__(self, *args, im_margin = 0, im_height = 20, **kwargs):
        kwargs['image_data'] = resize_and_colorize_img(kwargs['image_filename'], im_height, kwargs['button_color'][0])
        kwargs['image_filename'] = None
        kwargs['auto_size_button'] = False
        self.im_margin = im_margin
        self.im_data = kwargs['image_data']
        self.im_size = get_img64_size(kwargs['image_data'])[0], im_height

        super().__init__(*args, **kwargs)

    def update_layout(self, txt):
        # add spaces to fit text after the img
        wfont = font.Font(self.ParentForm.TKroot, self.Font)
        new_txt = ' ' *  round((self.im_size[0] + self.im_margin * 2) / wfont.measure(' ')) + txt
        new_size = (wfont.measure(new_txt) + self.im_margin, self.im_size[1] + self.im_margin * 2)

        # expand the img to the right to fill the whole button
        self.set_size(new_size)
        self.Widget.configure(wraplength = new_size[0])
        new_image_data = expand_right_img64(self.im_data, new_size)
        self.update(new_txt, image_data = new_image_data, update_layout = False)

    def finalize(self):
        self.update_layout(self.get_text())        
        super().finalize()

    def update(self, *args, update_layout = True, **kwargs):
        super().update(*args, **kwargs)
        if update_layout:
            txt = kwargs.get('text') or (len(args) > 0 and args[0])
            if txt:
                self.update_layout(txt)        
