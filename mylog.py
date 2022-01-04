
import re
import queue
import PySimpleGUI as sg
from mybutton import MyButton

def trigger_event(window, *events):
    if window and window.TKroot:
        window.write_event_value(*events)

class MyLog:
    
    link_txt = '\n'.join('❱❱❱❱❱')
    unlink_txt = '\n'.join('❰❰❰❰❰')
    close_txt = '\n'.join('CLOSE')

    log_event = '-UPDATE LOG-'
    listen_step = 20
   
    def __init__(self):
        self.prints = queue.Queue()
        self.linked = True
        self.resizing = False
        self.visible = False

    def create_window(self, log_font, button_font, no_border, main_window):
        self.main_window = main_window

        self.output = sg.MLine('', p = 0, font = log_font, s = (80, 50), auto_refresh = True, autoscroll  = True, disabled = True, border_width = 0, expand_x = True, expand_y = True, background_color = None)
                               
        self.link_button = MyButton(self.link_txt, p = 0, font = button_font, button_color = ('grey60', 'grey75'), mouseover_color = 'grey80', expand_x = True, expand_y = True, k = 'Link')
        layout = [ [ self.output, sg.Col( [ [self.link_button], [ sg.Sizegrip() ] ], p = 0, expand_x = True, expand_y = True) ] ]
        frame =  [ [ sg.Frame('', layout, p = 0, border_width = 1, relief = sg.RELIEF_SOLID, expand_x = True, expand_y = True) ] ]
        self.window = sg.Window('', frame, margins = (0, 0), resizable = True, keep_on_top = no_border, no_titlebar = no_border, return_keyboard_events = True, debugger_enabled = False)
        self.window.finalize().disappear()

        self.default_bindtags = self.output.Widget.bindtags()

        self.window.TKroot.resizable(width=False, height=True)
        self.window.set_min_size((self.window.size[0], 300))
        self.height = self.window.size[0]
        
        self.window.TKroot.bind('<Configure>', self.resize)
        self.window.TKroot.after(self.listen_step, self.listen)

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
        if self.linked and event.height != self.height:
            self.height = event.height
            self.stick_to_main()

    def catch_event(self, window, event):
        if window == self.window:
            if event in (None, 'l'): 
                self.toggle()

            elif event == 'Link':
                self.linked =  not self.linked
                if self.linked :
                    # enable selection 
                    self.output.Widget.bindtags(self.default_bindtags)
                    
                    self.window.grab_any_where_off()
                    self.output.grab_anywhere_exclude()
                    self.link_button.update(self.link_txt)
                    self.stick_to_main()
                
                else:
                    # remove & prevent selection 
                    self.output.Widget.bindtags((str(self.output.Widget), str(self.window.TKroot), 'all'))
                    self.output.Widget.tag_remove('sel', '1.0', 'end')

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
            self.window.move(int(x - w - gap) + 1, int(y + (H - h) *.5))
    
    def toggle(self):
        self.visible = not self.visible
        if self.visible: 
            self.window.reappear()
            self.window.BringToFront()
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