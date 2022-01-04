import PySimpleGUI as sg

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

        kwargs['button_color' ] = (text_color, self.colors['Leave'])
        kwargs['border_width'] = 0

        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in MyButton.binds:
            self.Widget.bind(bind, self.mouseover)            
    
    def update(self, *args, **kwargs):
        if kwargs.get('disabled') is False:
            kwargs['button_color'] = self.colors.get('Leave')
        super().update(*args, **kwargs)

    def mouseover(self, event):
        color = self.colors.get('Leave' if self.Disabled else event.type.name)
        if color:
            self.update(button_color = color)