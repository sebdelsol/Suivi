import re
import queue
import PySimpleGUI as sg
import sys

from myWidget import MyButton
import theme as TH
import local_txts as TXT

is_debugger = sys.gettrace()


class MyLog(sg.Window):
    link_txt = '\n'.join('❱❱❱❱❱')
    unlink_txt = '\n'.join('❰❰❰❰❰')
    close_txt = '\n'.join(TXT.close.upper())

    log_event = '-UPDATE LOG-'
    listen_step = 20  # ms
    select_bg_color = '#C0C0C0'

    def __init__(self, no_border):
        self.prints = queue.Queue()
        self.linked = True
        self.resizing = False
        self.visible = False

        log_f_size = 8
        log_font, self.log_font_bold, button_font = (TH.fix_font, log_f_size), (TH.fix_font_bold, log_f_size), (TH.var_font, 12)
        self.output = sg.MLine('', p=0, font=log_font, s=(80, 40), auto_refresh=True, autoscroll=True, disabled=True, border_width=0, expand_x=True, expand_y=True, background_color='grey90')
        self.link_button = MyButton(self.link_txt, p=0, font=button_font, button_color=('grey60', 'grey90'), mouseover_color='grey80', expand_x=True, expand_y=True, k='Link')

        layout = [[self.output, sg.Col([[self.link_button], [sg.Sizegrip()]], p=0, expand_x=True, expand_y=True)]]

        args, kwargs = TH.get_window_params(layout, alpha_channel=0, resizable=True)
        super().__init__(*args, **kwargs)

        self.TKroot.resizable(width=False, height=True)
        self.set_min_size(self.size)
        self.wanted_pos = None
        self.output.Widget.configure(selectbackground=self.select_bg_color)
        self.link_button.finalize()

    def link_to(self, main_window):
        self.main_window = main_window

        self.TKroot.bind('<Configure>', self.resize)
        self.main_window.TKroot.bind('<Configure>', lambda evt: self.stick_to_main(), add='+')

        self.listen()

    def listen(self, exiting=False):
        try:
            while True:
                args, error, kwargs = self.prints.get_nowait()
                print(*args, **kwargs)
                self.output.print(*args, **kwargs, t='red' if error else 'green', font=self.log_font_bold if error else None)

        except queue.Empty:
            if not exiting:
                self.TKroot.after(self.listen_step, self.listen)

    def resize(self, event):
        if self.linked and ((event.x == 0 and event.y == 0) or self.current_location() != self.wanted_pos):
            self.stick_to_main()

    def event_handler(self, event):
        if event in (None, 'l'):
            self.toggle()

        elif event == 'Link':
            self.linked = not self.linked
            if self.linked:
                self.output.Widget.tag_remove('sel', '1.0', 'end')
                self.output.Widget.configure(selectbackground=self.select_bg_color)

                self.grab_any_where_off()
                self.output.grab_anywhere_exclude()
                self.link_button.update(self.link_txt)
                self.stick_to_main()

            else:
                # invisible selection
                self.output.Widget.configure(selectbackground=self.output.Widget.cget('bg'))

                self.grab_any_where_on()
                self.output.grab_anywhere_include()
                self.link_button.update(self.unlink_txt)
                self.stick_to_main(gap=10, force=True)

    def stick_to_main(self, gap=0, force=False):
        if (self.visible and self.linked) or force:
            w, h = self.size
            W, H = self.main_window.size
            x, y = self.main_window.current_location()
            self.wanted_pos = int(x - w - gap) + 1, int(y + (H - h) * .5)
            self.move(*self.wanted_pos)

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.reappear()
            self.enable()
            self.stick_to_main()

        else:
            self.disappear()
            self.disable()

    def log(self, *args, error=False, **kwargs):
        self.prints.put((args, error, kwargs))

    def close(self):
        if self.visible:
            self.log('<< HIT a key to CLOSE >>', error=True)
            self.link_button.update(self.close_txt, button_color=('red', 'grey85'))
            self.force_focus()
            self.TKroot.unbind('<Configure>')

            while True:
                event = self.read()[0]

                if event in (None, 'Link') or len(event) == 1 or re.match(r'\w+\:\d+', event):
                    break

        self.listen(exiting=True)

        super().close()


mylog = MyLog(not is_debugger)
_log = mylog.log
