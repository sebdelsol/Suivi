import re
import queue
import PySimpleGUI as sg
from mybutton import MyButton

class MyLog:
    link_txt = '\n'.join('❱❱❱❱❱')
    unlink_txt = '\n'.join('❰❰❰❰❰')
    close_txt = '\n'.join('CLOSE')

    log_event = '-UPDATE LOG-'
    listen_step = 20
    select_bg_color = '#C0C0C0'
   
    def __init__(self):
        self.prints = queue.Queue()
        self.linked = True
        self.resizing = False
        self.visible = False

    def create_window(self, log_font, button_font, no_border, main_window):
        self.main_window = main_window

        self.output = sg.MLine('', p = 0, font = log_font, s = (80, 40), auto_refresh = True, autoscroll  = True, disabled = True, border_width = 0, expand_x = True, expand_y = True, background_color = None)
                               
        self.link_button = MyButton(self.link_txt, p = 0, font = button_font, button_color = ('grey60', 'grey95'), mouseover_color = 'grey80', expand_x = True, expand_y = True, k = 'Link')
        layout = [ [ self.output, sg.Col( [ [self.link_button], [ sg.Sizegrip() ] ], p = 0, expand_x = True, expand_y = True) ] ]
        frame =  [ [ sg.Frame('', layout, p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True) ] ]
        self.window = sg.Window('', frame, margins = (0, 0), resizable = True, keep_on_top = no_border, no_titlebar = no_border, return_keyboard_events = True, debugger_enabled = False, alpha_channel = 0, finalize = True)

        self.window.TKroot.resizable(width = False, height = True)
        self.window.set_min_size(self.window.size)
        self.wanted_pos = None
        
        self.window.TKroot.bind('<Configure>', self.resize)
        self.window.TKroot.after(self.listen_step, self.listen)

        self.output.Widget.configure(selectbackground = self.select_bg_color)

        self.link_button.finalize()

    def listen(self):
        try:
            while True:
                args, error, kwargs = self.prints.get_nowait()
                print(*args, **kwargs)
                self.output.print(*args, **kwargs, t = 'red' if error else 'green')

        except queue.Empty:
            self.window.TKroot.after(self.listen_step, self.listen)

    def resize(self, event):
        if self.linked and ((event.x == 0 and event.y == 0) or self.window.current_location()!=self.wanted_pos):
            self.stick_to_main()

    def catch_event(self, window, event):
        if window == self.window:
            if event in (None, 'l'): 
                self.toggle()

            elif event == 'Link':
                self.linked =  not self.linked
                if self.linked :
                    self.output.Widget.tag_remove('sel', '1.0', 'end')
                    self.output.Widget.configure(selectbackground = self.select_bg_color)

                    self.window.grab_any_where_off()
                    self.output.grab_anywhere_exclude()
                    self.link_button.update(self.link_txt)
                    self.stick_to_main()
                
                else:
                    # invisible selection
                    self.output.Widget.configure(selectbackground = self.output.Widget.cget('bg'))

                    self.window.grab_any_where_on()
                    self.output.grab_anywhere_include()
                    self.link_button.update(self.unlink_txt)
                    self.stick_to_main(gap = 10, force = True)

            return True

    def stick_to_main(self, gap = 0, force = False):
        if (self.visible and self.linked) or force:
            w, h = self.window.size
            W, H = self.main_window.size
            x, y = self.main_window.current_location()
            self.wanted_pos = int(x - w - gap) + 1, int(y + (H - h) *.5) 
            self.window.move(*self.wanted_pos)
    
    def toggle(self):
        self.visible = not self.visible
        if self.visible: 
            self.window.reappear()
            self.window.enable()
            self.stick_to_main()

        else:
            self.window.disappear()
            self.window.disable()

    def log(self, *args, error = False, **kwargs):
        self.prints.put((args, error, kwargs))

    def close(self):
        if self.visible: 
            self.log ('<< HIT a key to CLOSE >>', error = True)

            self.link_button.update(self.close_txt, button_color = ('red', 'grey85'))
            self.window.force_focus()
            self.window.TKroot.unbind('<Configure>')

            while True:
                event = self.window.read()[0]

                if event in (None, 'Link') or len(event) == 1 or re.match(r'\w+\:\d+', event):
                    break

        self.window.close()
        del self.window

mylog = MyLog()
_log = mylog.log