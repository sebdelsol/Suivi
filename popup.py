import PySimpleGUI as sg
from mybutton import MyButton
from couriers import Courier
import webbrowser

from fonts import FixFont, FixFontBold, VarFont

#-------------
class MyPopup:
    def __init__(self, title, body_layout, no_border, main_loop):
        self.main_loop = main_loop

        layout =      [ [ sg.T(title, font = (FixFont, 20)) ],
                        [ sg.HorizontalSeparator() ] ]
        
        layout.extend(  body_layout )

        layout.append(  [ sg.HorizontalSeparator() ] )
        layout.append(  [ MyButton('OK', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95', bind_return_key=True), 
                          MyButton('Cancel', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95')] )

        layout = [ [ sg.Frame('', [[sg.Col(layout, p = 10)]], p = 0, border_width = 3, relief = sg.RELIEF_SOLID) ] ]
        self.window = sg.Window('', layout, margins = (0, 0), modal = True, grab_anywhere = True, keep_on_top = no_border, no_titlebar = no_border, return_keyboard_events = True, finalize = True, debugger_enabled = False)
        
        MyButton.finalize_all(self.window)

    def loop(self, catch_event = None):
        while True: 
            exit, forward = self.main_loop.get_event()            
            
            if exit:
                break

            elif forward:
                window, event, values = forward
                if window == self.window:
                    if event in (None, 'Cancel', 'Escape:27'):
                        return None

                    elif event == 'OK':
                        return values
                    
                    elif catch_event is not None:
                        catch_event(self.window, event, values) 

    def close(self):
        self.window.close()
        del self.window

#------------------------------------------------------------------------------
def edit(title, idship, description, used_couriers, couriers, no_border, main_loop):

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

    edit_window = MyPopup(title, layout, no_border, main_loop)
    update_idship_widgets(idship)

    idship, description = None, None

    def catch_event(window, event, values):
        if event == 'idship':
            update_idship_widgets(values['idship'])
        
        elif isinstance(event, Courier):
            courier, idship = event, values['idship']
            url = courier.get_url_for_browser(idship)
            webbrowser.open(url)
        
        elif event in couriers_names:
            window[event].update(text_color = 'black' if values[event] else 'grey60')

    values = edit_window.loop(catch_event)
    if values:
        idship, description, used_couriers = values['idship'], values['description'], [name for name in couriers_names if values[name]]

    edit_window.close()
    return idship, description, used_couriers

#--------------------------------------
def choices(choices, title, no_border, main_loop):
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

    choices_window = MyPopup(title, layout, no_border, main_loop)
    
    for chck in chcks:
        chck[1].bind('<Button-1>', '')

    if rows.Scrollable:
        chck_height = chcks[0][0].get_size()[1]
        height = chck_height * min(max_lines, len(chcks))
        # https://github.com/PySimpleGUI/PySimpleGUI/issues/4407#issuecomment-860863915
        rows.Widget.canvas.configure(width = None, height = height)    

    chosen = []

    def catch_event(window, event, values):
        if event.isdigit() and int(event) in range(len(choices)):
            chck_widget = window[f'{text_key}{event}']
            is_checked = values[event]
            chck_widget.update(font = selected_font if is_checked else unselected_font)

        elif text_key in event:
            chck_widget = window[event.replace(text_key, '')]
            is_checked = not chck_widget.get()
            chck_widget.update(value = is_checked)
            window[event].update(font = selected_font if is_checked else unselected_font)

    values = choices_window.loop(catch_event)
    if values:
        chosen = [ int(choice) for choice in values.keys() if values[choice] ]

    choices_window.close()
    return chosen

#-----------------------------------------
def one_choice(choices, choice_colors, title, no_border, main_loop, default = 0):
    layout = []
    for i, choice in enumerate(choices):
        color = choice_colors[choice if i==default else False]
        radio = sg.Radio(choice, group_id = 'choices', text_color = color, font = (VarFont, 20), enable_events = True, default= i==0, k = choice)
        layout.append([radio])

    choices_window = MyPopup(title, layout, no_border, main_loop)

    choice = None

    def catch_event(window, event, values):
        if event in choices:
            for choice in choices:
                color = choice_colors[choice if values[choice] else False]
                window[choice].update(text_color = color)

    values = choices_window.loop(catch_event)
    if values:
        # https://stackoverflow.com/questions/2361426/get-the-first-item-from-an-iterable-that-matches-a-condition
        choice = next(choice for choice in choices if values[choice]) 

    choices_window.close()
    return choice

#------------------------
def warning(title, text, no_border, main_loop):
    layout = [ [ sg.Image(filename = 'icon/warn.png'), sg.T(text, font = (VarFont, 15)) ] ]
    warning_window = MyPopup(title, layout, no_border, main_loop)

    ok = False

    values = warning_window.loop()
    if values is not None:
        ok = True

    warning_window.close()
    return ok
