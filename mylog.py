
import re
import PySimpleGUI as sg
from mybutton import MyButton

class MyLog:
    
    def vertical(txt): return '\n'.join(c for c in txt)
    link_txt = vertical('❱❱❱❱❱')
    unlink_txt = vertical('❰❰❰❰❰')
    close_txt = 'CLOSE'
   
    def __init__(self):
        self.window = None

    def set_window(self, log_font, button_font, no_border = True):
        self.linked = True
        self.resizing = False
        self.visible = False

        self.output = sg.MLine('', p = 0, font = log_font, s = (80, 50), auto_refresh = True, autoscroll  = True, disabled = True, border_width = 0, expand_x = True, expand_y = True, background_color = None)
        self.link_button = MyButton(self.link_txt, p = 0, font = button_font, button_color = ('grey60', 'grey75'), mouseover_color = 'grey80', expand_y = True, expand_x = False, k = 'Link')
        sizegrip = sg.Sizegrip()
        layout = [ [ self.output, sg.Col( [ [self.link_button], [ sizegrip ] ], p = 0, expand_y = True, expand_x = False) ] ]

        self.window = sg.Window('', layout, margins = (0, 0), modal = False, resizable = True, keep_on_top = no_border, no_titlebar = no_border, return_keyboard_events = True, finalize = True)
        self.window.disappear()

        self.default_bindtags = self.output.Widget.bindtags()

        self.window.TKroot.resizable(width=False, height=True)
        sizegrip.bind('<ButtonPress-1>', '')
        sizegrip.bind('<ButtonRelease-1>', '')
        self.window.set_min_size((self.window.size[0], 300))

        self.link_button.finalize()

    def catch_event(self, window, event, values, button_log, main_window):
        if window == self.window:
            if event in (None, 'l'): 
                self.toggle(main_window)
                return True

            elif event == '-UPDATE LOG-':
                self.update_log(event, values)

            elif event == '<ButtonPress-1>':
                self.resizing = True
                return True

            elif event == '<ButtonRelease-1>':
                self.resizing = False
                if self.linked:
                    self.move_left_to(main_window)
                    return True
        
            elif event == 'Link':
                self.linked =  not self.linked
                if self.linked :
                    # enable selection 
                    self.output.Widget.bindtags(self.default_bindtags)
                    
                    self.window.grab_any_where_off()
                    self.output.grab_anywhere_exclude()
                    self.link_button.update(self.link_txt)
                    self.move_left_to(main_window)
                
                else:
                    # remove & prevent selection 
                    self.output.Widget.bindtags((str(self.output.Widget), str(self.window.TKroot), 'all'))
                    self.output.Widget.tag_remove('sel', '1.0', 'end')

                    self.window.grab_any_where_on()
                    self.output.grab_anywhere_include()
                    self.link_button.update(self.unlink_txt)
                    self.move_left_to(main_window, gap = 10, force = True)

                return True
            
        elif event in (button_log, 'l'):
            self.toggle(main_window)
            return True

    def move_left_to(self, main_window, gap = 0, force = False):
        if not self.resizing and (self.visible and self.linked) or force:
            w, h = self.window.size
            W, H = main_window.size
            x, y = main_window.current_location()
            self.window.move(int(x - w - gap), int(y + (H - h) *.5))
            self.window.refresh()
    
    def toggle(self, main_window):
        self.visible = not self.visible
        if self.visible: 
            self.window.reappear()
            self.window.BringToFront()
            self.window.enable()
            self.move_left_to(main_window)

        else:
            self.window.disappear()
            self.window.disable()

    def log(self, *args, error = False, **kwargs):
        print(*args, **kwargs)
        if self.window:
            self.window.write_event_value('-UPDATE LOG-', (args, error, kwargs))
    
    def update_log(self, event, values):
        args, error, kwargs = values[event]
        self.output.print(*args, **kwargs, t = 'red' if error else 'black')

    def close(self):
        if self.visible: 
            self.log ('<< HIT a key to CLOSE >>', error = True)

            self.link_button.update(self.close_txt, button_color = ('red', 'grey85'))
            self.window.force_focus()

            while True:
                event, values = self.window.read() 

                if event == '-UPDATE LOG-':
                    self.update_log(event, values)

                elif event in (None,'Link') or len(event) == 1 or re.match(r'\w+\:\d+', event):
                    break
                
                elif MyButton.catch_mouseover_event(self.window, event):
                    pass

        self.window.close()

mylog = MyLog()
_log = mylog.log