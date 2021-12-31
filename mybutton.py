import PySimpleGUI as sg


class MyButton(sg.Button):
    default_colors = dict( enter = 'grey75', leave = 'grey95')
    binds = dict( enter = '<Enter>', leave = '<Leave>')

    @classmethod
    def catch_mouseover_event(cls, window, event):
        if isinstance(event, tuple):
            key, msg = event
            if msg in cls.binds.keys():
                window[key].mouseover(msg)
                return True
        
        elif isinstance(event, str):
            widget = window.find_element(event, silent_on_error = True)
            if widget and isinstance(widget, MyButton): # it's a clic
                widget.mouseover('leave')
                return False
            
            else:
                for msg in cls.binds.keys():
                    if msg in event:
                        key = event.replace(msg, '')
                        window[key].mouseover(msg)
                        return True
        
        return False

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

        self.colors = { 'leave' : button_color or MyButton.default_colors['leave'],
                        'enter' : mouseover_color or MyButton.default_colors['enter'] }

        kwargs['button_color' ] = (text_color, self.colors['leave'])
        kwargs['border_width'] = 0

        super().__init__(*args, **kwargs)

    def finalize(self):
        for event, bind in MyButton.binds.items():
            self.bind(bind, f'{event}')            
    
    def update(self, *args, **kwargs):
        if kwargs.get('disabled') is False:
            kwargs['button_color'] = self.colors.get('leave')
        super().update(*args, **kwargs)

    def mouseover(self, event):
        if self.Disabled:
            event = 'leave'
        color = self.colors.get(event)
        if color:
            self.update(button_color = color)