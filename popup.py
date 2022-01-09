import PySimpleGUI as sg
from mybutton import MyButton
import webbrowser

from couriers import Courier
from style import FixFont, FixFontBold, VarFont, VarFontBold, Get_window_args

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

        args, kwargs = Get_window_args(layout)
        super().__init__(*args, **kwargs)

    def loop(self, child_event_handler = None):
        self.child_event_handler = child_event_handler

        while True: 
            exit = self.main_window.event_handler()            
            if exit:
                return exit

    def event_handler(self, event, values):
        if event in (None, 'Cancel', 'Escape:27'):
            return 'cancel'

        elif event == 'OK':
            return 'ok'
        
        elif self.child_event_handler is not None:
            self.child_event_handler(self, event, values) 

    def close(self):
        self.main_window.do_greyed(False)
        super().close()

#------------------------------------------------------------------------------
def edit(title, idship, description, used_couriers, couriers, main_window):

    def update_idship_widgets(idship):
        for msg, button in idship_widgets:
            courier = button.Key
            disabled = not courier.get_url_for_browser(idship)
            button.update(disabled = disabled)
            msg.update(text_color = 'red' if disabled else 'green')

    couriers_names = couriers.get_names()
    couriers_names.sort()
    layout = [      [ sg.T('Description', font = (FixFont, 10)), sg.Input(description, font = (FixFont, 10), border_width = 0, key='description') ],
                    [ sg.T('Tracking n°', font = (FixFont, 10)), sg.Input(idship, font = (FixFont, 10), border_width = 0, enable_events = True, key='idship') ] ]

    idship_widgets = []
    for name in couriers_names:
        courier = couriers.get(name)

        is_checked = name in used_couriers
        cb = sg.CB(f' {name}', default = is_checked, text_color = 'black' if is_checked else 'grey60', font = (FixFont, 12), enable_events = True, k = name)
        msg = sg.T(f'({courier.idship_check_msg})', font = (FixFont, 7), expand_x = True, justification = 'r')
        button = MyButton('voir', font = (FixFont, 8), button_color ='grey90', k = courier)

        idship_widgets.append((msg, button))
        layout.append([cb, msg, button])

    window = MyPopup(title, layout, main_window)
    update_idship_widgets(idship)

    idship, description = None, None

    def event_handler(window, event, values):
        if event == 'idship':
            update_idship_widgets(values['idship'])
        
        elif isinstance(event, Courier):
            courier, idship = event, values['idship']
            url = courier.get_url_for_browser(idship)
            webbrowser.open(url)
        
        elif event in couriers_names:
            window[event].update(text_color = 'black' if values[event] else 'grey60')

    exit = window.loop(event_handler)
    if exit == 'ok':
        idship = window['idship'].get() 
        description = window['description'].get()
        used_couriers = [name for name in couriers_names if window[name].get()]

    window.close()
    return idship, description, used_couriers

#--------------------------------------
def choices(choices, title, main_window):
    max_lines = 15
    
    selected_font, unselected_font =  (FixFontBold, 9),  (FixFont, 9)
    text_key = 'choice_desc'
    chcks = []
    for i, (choice, color) in enumerate(choices):
        cb = sg.CB(' ', p = 0, default = False, enable_events = True, k = f'{i}')
        t = sg.T(f'{choice}', p = 0, font = unselected_font, text_color = color, enable_events = True, k = f'{text_key}{i}') 
        chcks.append( [cb, t] )

    rows = sg.Col(chcks, scrollable = len(chcks) > max_lines, vertical_scroll_only = True)
    layout = [ [ rows ] ]

    window = MyPopup(title, layout, main_window)
    
    for chck in chcks:
        chck[1].bind('<Button-1>', '')

    if rows.Scrollable:
        chck_height = chcks[0][0].get_size()[1]
        height = chck_height * min(max_lines, len(chcks))
        # https://github.com/PySimpleGUI/PySimpleGUI/issues/4407#issuecomment-860863915
        rows.Widget.canvas.configure(width = None, height = height)    

    chosen = []

    def event_handler(window, event, values):
        if event.isdigit() and int(event) in range(len(choices)):
            chck_widget = window[f'{text_key}{event}']
            is_checked = values[event]
            chck_widget.update(font = selected_font if is_checked else unselected_font)

        elif text_key in event:
            chck_widget = window[event.replace(text_key, '')]
            is_checked = not chck_widget.get()
            chck_widget.update(value = is_checked)
            window[event].update(font = selected_font if is_checked else unselected_font)

    exit = window.loop(event_handler)
    if exit == 'ok':
        chosen = [ choice for choice in range(len(choices)) if window[f'{choice}'].get() ]

    window.close()
    return chosen

#-----------------------------------------
def one_choice(choices, choice_colors, title, main_window, default = 0):
    layout = []
    for i, choice in enumerate(choices):
        color = choice_colors[choice if i==default else False]
        radio = sg.Radio(choice, group_id = 'choices', text_color = color, font = (VarFontBold, 20), enable_events = True, default= i==0, k = choice)
        layout.append([radio])

    window = MyPopup(title, layout, main_window)

    choice = None

    def event_handler(window, event, values):
        if event in choices:
            for choice in choices:
                color = choice_colors[choice if values[choice] else False]
                window[choice].update(text_color = color)

    exit = window.loop(event_handler)
    if exit == 'ok':
        # https://stackoverflow.com/questions/2361426/get-the-first-item-from-an-iterable-that-matches-a-condition
        choice = next(choice for choice in choices if window[choice].get()) 

    window.close()
    return choice

#------------------------
def warning(title, text, main_window):
    layout = [ [ sg.Image(filename = 'icon/warn.png'), sg.T(text, font = (VarFont, 15)) ] ]
    window = MyPopup(title, layout, main_window)

    ok = window.loop() == 'ok'

    window.close()
    return ok
