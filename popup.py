import PySimpleGUI as sg
from mybutton import MyButton
from couriers import Courier
import webbrowser

#-------------
VarFont = None
FixFont = None 

def set_font(var_font, fix_font):
    global VarFont, FixFont
    VarFont, FixFont = var_font, fix_font

#-------------
class MyPopup:
    def __init__(self, title, body_layout):
        layout =      [ [ sg.T(title, font = (FixFont, 20)) ],
                        [ sg.HorizontalSeparator() ] ]
        
        layout.extend(  body_layout )

        layout.append(  [ sg.HorizontalSeparator() ] )
        layout.append(  [ MyButton('OK', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95', bind_return_key=True), 
                          MyButton('Cancel', font = (VarFont, 12), button_color = 'grey80', mouseover_color = 'grey95')] )

        layout = [ [ sg.Frame('', [[sg.Col(layout, p = 10)]], p = 0, border_width = 3, relief = sg.RELIEF_SOLID) ] ]
        self.window = sg.Window('', layout, margins = (0, 0), modal = True, grab_anywhere = True, keep_on_top = True, no_titlebar = True, return_keyboard_events = True, finalize = True)
        
        MyButton.finalize_all(self.window)

    def loop(self, catch_event = None):
        while True:             
            event, values = self.window.read()
            # _log (event)
            if event in (None, 'Cancel', 'Escape:27'):
                return None
            
            elif MyButton.catch_mouseover_event(self.window, event):
                pass

            elif event == 'OK':
                return values
            
            elif catch_event is not None:
                catch_event(self.window, event, values) 

    def close(self):
        self.window.close()
        del self.window

#------------------------------------------------------------------------------
def edit(title, idship, description, used_couriers, couriers):

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

    edit_window = MyPopup(title, layout)
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
def choices(choices, title):
    max_lines = 15
    
    chcks =  [ [ sg.CB(f' {choice}', p = 0, font = (FixFont, 9), text_color = color, default = False, k = f'{i}') ] for i, (choice, color) in enumerate(choices) ]
    rows = sg.Col(chcks, scrollable = len(chcks) > max_lines, vertical_scroll_only = True)
    layout = [ [ rows ] ]

    choices_window = MyPopup(title, layout)

    if rows.Scrollable:
        chck_height = chcks[0][0].get_size()[1]
        height = chck_height * min(max_lines, len(chcks))
        # https://github.com/PySimpleGUI/PySimpleGUI/issues/4407#issuecomment-860863915
        rows.Widget.canvas.configure(width = None, height = height)    

    chosen = []

    values = choices_window.loop()
    if values:
        chosen = [ int(choice) for choice in values.keys() if values[choice] ]

    choices_window.close()
    return chosen

#-----------------------------------------
def one_choice(choices, title):
    layout = [ [ sg.Radio(choice, group_id = 'choices', font = (VarFont, 15), default= i==0, k = choice)] for i, choice in enumerate(choices) ]

    choices_window = MyPopup(title, layout)

    choice = None

    values = choices_window.loop()
    if values:
        # https://stackoverflow.com/questions/2361426/get-the-first-item-from-an-iterable-that-matches-a-condition
        choice = next(choice for choice in choices if values[choice]) 

    choices_window.close()
    return choice

#------------------------
def warning(title, text):
    layout = [ [ sg.Image(filename = 'icon/warn.png'), sg.T(text, font = (VarFont, 15)) ] ]
    warning_window = MyPopup(title, layout)

    ok = False

    values = warning_window.loop()
    if values is not None:
        ok = True

    warning_window.close()
    return ok