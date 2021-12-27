import PySimpleGUI as sg
from mybutton import MyButton

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

    def loop(self):
        while True:             
            event, values = self.window.read()
            # _log (event)
            if event in (None, 'Cancel', 'Escape:27'):
                return None
            
            elif MyButton.catch_mouseover_event(self.window, event):
                pass

            elif event == 'OK':
                return values

    def close(self):
        self.window.close()
        del self.window

#------------------------------------------------------------------------------
def edit(title, idship, description, used_couriers, couriers_names):
    layout = [      [ sg.T('Description', font = (FixFont, 10)), sg.Input(description, font = (FixFont, 10), border_width = 0, key='description') ],
                    [ sg.T('Tracking n°', font = (FixFont, 10)), sg.Input(idship, font = (FixFont, 10), border_width = 0, key='idship') ] ]
    layout.extend(  [ sg.CB(f' {name}', default=name in used_couriers, font = (FixFont, 12), k = name) ] for i, name in enumerate(couriers_names) )

    edit_window = MyPopup(title, layout)

    idship, description = None, None

    values = edit_window.loop()
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
def one_choice(choices, txt, title):
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