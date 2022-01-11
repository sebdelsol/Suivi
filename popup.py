import PySimpleGUI as sg
from collections import namedtuple
import webbrowser

from myWidget import MyButton
from couriers import Courier
from style import FixFont, FixFontBold, VarFont, VarFontBold, Get_window_params

#-------------
class MyPopup(sg.Window):
    def __init__(self, title, body_layout, main_window):
        self.main_window = main_window
        self.main_window.do_greyed(True)

        layout =      [ [ sg.T(title, font = (FixFontBold, 20), justification = 'center', expand_x = True) ],
                        [ sg.HorizontalSeparator() ] ]
        layout.extend( body_layout )
        layout.append( [ sg.HorizontalSeparator() ] )
        layout.append( [ MyButton('OK', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95', bind_return_key=True), 
                         MyButton('Cancel', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95')] )
        layout = [ [ sg.Col(layout, p = 10) ] ]

        args, kwargs = Get_window_params(layout)
        super().__init__(*args, **kwargs)
        MyButton.finalize_all(self)

    def loop(self):
        while True: 
            exit = self.main_window.event_handler()            
            if exit:
                return exit

    def event_handler(self, event):
        if event in (None, 'Cancel', 'Escape:27'):
            return 'cancel'

        elif event == 'OK':
            return 'ok'

    def close(self):
        self.main_window.do_greyed(False)
        super().close()

#------------------------------------------------------------------------------
class edit(MyPopup):
    def __init__(self, title, idship, description, used_couriers, couriers, main_window):
        self.couriers_names = couriers.get_names()
        self.couriers_names.sort()
        layout = [      [ sg.T('Description', font = (FixFont, 10)), sg.Input(description, font = (FixFont, 10), border_width = 0, key='description') ],
                        [ sg.T('Tracking n°', font = (FixFont, 10)), sg.Input(idship, font = (FixFont, 10), border_width = 0, enable_events = True, key='idship') ] ]

        self.idship_widgets = []
        for name in self.couriers_names:
            courier = couriers.get(name)

            is_checked = name in used_couriers
            cb = sg.CB(f' {name}', default = is_checked, text_color = 'black' if is_checked else 'grey60', font = (FixFont, 12), enable_events = True, k = name)
            msg = sg.T(f'({courier.idship_check_msg})', font = (FixFont, 8), expand_x = True, justification = 'r')
            button = MyButton('voir', font = (FixFont, 8), button_color ='grey90', k = courier)

            self.idship_widgets.append((msg, button))
            layout.append([ cb, msg, sg.vcenter(button) ])

        super().__init__(title, layout, main_window)
        
        self.idship_updated(idship)

    def idship_updated(self, idship):
        for msg, button in self.idship_widgets:
            courier = button.Key
            disabled = not courier.get_url_for_browser(idship)
            button.update(disabled = disabled, visible = not disabled)
            msg.update(text_color = 'red' if disabled else 'green')

    def event_handler(self, event):
        if event == 'idship':
            self.idship_updated(self['idship'].get())
        
        elif isinstance(event, Courier):
            courier, idship = event, self['idship'].get()
            url = courier.get_url_for_browser(idship)
            webbrowser.open(url)
        
        elif event in self.couriers_names:
            self[event].update(text_color = 'black' if self[event].get() else 'grey60')

        else:
            return super().event_handler(event)

    def loop(self):
        idship, description, used_couriers = None, None, None

        if super().loop() == 'ok':
            idship = self['idship'].get() 
            description = self['description'].get()
            used_couriers = [name for name in self.couriers_names if self[name].get()]

        self.close()
        return idship, description, used_couriers

#--------------------------------------
class choices(MyPopup):
    max_lines = 15
    selected_font, unselected_font = (FixFontBold, 9),  (FixFont, 9)

    def __init__(self, choices, title, main_window):
        row = namedtuple('row', 'cb txt')
        rows = []
        for i, (choice, color) in enumerate(choices):
            cb = sg.CB('', p = 0, default = False, enable_events = True, k = f'cb_choice{i}')
            t = sg.T(choice, p = 0, font = self.unselected_font, text_color = color, enable_events = True, k = f'txt_choice{i}') 
            rows.append( row(cb, t) )

        if rows:
            col = sg.Col(rows, scrollable = len(rows) > self.max_lines, vertical_scroll_only = True)
            layout = [[ col ]]
        
        else:
            layout = [[ sg.T('Vide', expand_x = True, font = self.selected_font, text_color = 'red', justification = 'center') ]]

        self.choices = choices
        super().__init__(title, layout, main_window)

        if rows: 
            for row in rows:
                row.txt.bind('<Button-1>', '')

            if col.Scrollable:
                cb_height = rows[0].cb.get_size()[1]
                height = cb_height * min(self.max_lines, len(rows))
                # https://github.com/PySimpleGUI/PySimpleGUI/issues/4407#issuecomment-860863915
                rows.Widget.canvas.configure(width = None, height = height)    

    def event_handler(self, event):
        if 'cb_choice' in event:
            cb_widget, txt_widget = self[event], self[event.replace('cb', 'txt')]
            txt_widget.update(font = self.selected_font if cb_widget.get() else self.unselected_font)

        elif 'txt_choice' in event:
            cb_widget, txt_widget = self[event.replace('txt', 'cb')], self[event]
            toggle_check = not cb_widget.get()
            cb_widget.update(value = toggle_check)
            txt_widget.update(font = self.selected_font if toggle_check else self.unselected_font)

        else:
            return super().event_handler(event)

    def loop(self):
        chosen = []
    
        if super().loop() == 'ok':
            chosen = [ i for i in range(len(self.choices)) if self[f'cb_choice{i}'].get() ]

        self.close()
        return chosen

#-----------------------------------------
class one_choice(MyPopup):
    def __init__(self, choices, choice_colors, title, main_window, default = 0):
        layout = []
        for i, choice in enumerate(choices):
            color = choice_colors[choice if i==default else False]
            radio = sg.Radio(choice, group_id = 'choices', text_color = color, font = (VarFontBold, 20), enable_events = True, default= i==0, k = choice)
            layout.append([radio])

        self.choice_colors = choice_colors
        self.choices = choices
        super().__init__(title, layout, main_window)

    def event_handler(self, event):
        if event in self.choices:
            for choice in self.choices:
                color = self.choice_colors[choice if self[choice].get() else False]
                self[choice].update(text_color = color)

        else:
            return super().event_handler(event)

    def loop(self):
        choice = None

        if super().loop() == 'ok':
            # https://stackoverflow.com/questions/2361426/get-the-first-item-from-an-iterable-that-matches-a-condition
            choice = next(choice for choice in self.choices if self[choice].get()) 

        self.close()
        return choice

#------------------------
class warning(MyPopup):
    def __init__(self, title, text, main_window):
        layout = [ [ sg.Image(filename = 'icon/warn.png'), sg.T(text, font = (VarFont, 15)) ] ]
        super().__init__(title, layout, main_window)

    def loop(self):
        ok = super().loop() == 'ok'

        self.close()
        return ok
