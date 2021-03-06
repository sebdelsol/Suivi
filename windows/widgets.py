import math
import threading
import time
from ctypes import windll
from tkinter import font as tk_font

import PySimpleGUI as sg
from tools.img_tool import get_gif_durations, get_img64_size, resize_and_colorize_img

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080

if hasattr(windll.user32, "GetWindowLongPtrW"):
    _get_window_style = windll.user32.GetWindowLongPtrW
    _set_window_style = windll.user32.SetWindowLongPtrW
else:
    _get_window_style = windll.user32.GetWindowLongW
    _set_window_style = windll.user32.SetWindowLongW


# PySimpleGUI calls its widgets : elements
# base window class to handle custom element._finalize()
class Window(sg.Window):
    @staticmethod
    def _try_finalize(elt):
        if hasattr(elt, "finalize"):
            elt.finalize()

    def _finalize_layout(self, rows):
        for row in rows:
            for elt in row:
                if hasattr(elt, "Rows"):
                    self._finalize_layout(elt.Rows)
                else:
                    self._try_finalize(elt)

    def Finalize(self, *args, **kwargs):
        super().Finalize(*args, **kwargs)
        for elt in self.element_list():
            self._try_finalize(elt)

    def extend_layout(self, container, rows):
        super().extend_layout(container, rows)
        self._finalize_layout(rows)


class ShowInTaskbarWindow(Window):
    def __init__(self, *args, no_titlebar=False, **kwargs):
        self._no_titlebar = no_titlebar
        super().__init__(*args, **kwargs)

    def Finalize(self, *args, **kwargs):
        super().Finalize(*args, **kwargs)
        if self._no_titlebar:
            self.normal()

    def minimize(self):
        if self._no_titlebar:
            root = self.TKroot
            # clear override or Tcl will raise an error
            root.overrideredirect(False)
            # redraw the window to have something to show in the taskbar
            self.refresh()
            # catch the deinconify event
            root.bind("<Map>", lambda event: self.normal())

        super().minimize()

    def normal(self):
        if self._no_titlebar:
            root = self.TKroot
            # set override to remove the tittlebar
            root.overrideredirect(True)
            # set ex_style as WS_EX_APPWINDOW so that it shows in the taskbar
            hwnd = windll.user32.GetParent(root.winfo_id())
            style = _get_window_style(hwnd, GWL_EXSTYLE)
            style &= ~WS_EX_TOOLWINDOW
            style |= WS_EX_APPWINDOW
            _set_window_style(hwnd, GWL_EXSTYLE, style)
            # avoid infinite loop (withdraw + deiconify triggers a <Map>)
            root.unbind("<Map>")
            # re-assert window style
            root.withdraw()
            # enforce KeepOnTop=False
            if not self.KeepOnTop:
                root.lower()
                root.lift()

        super().normal()


class GraphRounded(sg.Graph):
    def draw_rounded_box(self, x, y, w, h, r, color, corner="all"):
        draw_arc = self.draw_arc
        draw_rectangle = self.draw_rectangle
        w, h, r2 = w * 0.5, h * 0.5, r * 2
        rec_colors = dict(fill_color=color, line_color=color)
        # cross
        draw_rectangle((x - w, y + h - r), (x + w, y - h + r), **rec_colors)
        draw_rectangle((x - w + r, y + h), (x + w - r, y - h), **rec_colors)
        # corners
        colors = dict(fill_color=color, arc_color=color)
        if corner == "all":
            draw_arc((x - w, y + h - r2), (x - w + r2, y + h), 90, 90, **colors)  # nw
            draw_arc((x + w - r2, y + h - r2), (x + w, y + h), 90, 0, **colors)  # ne
            draw_arc((x - w, y - h), (x - w + r2, y - h + r2), 90, 180, **colors)  # sw
            draw_arc((x + w - r2, y - h), (x + w, y - h + r2), 90, 270, **colors)  # se

        elif corner == "top":
            draw_arc((x - w, y + h - r2), (x - w + r2, y + h), 90, 90, **colors)  # nw
            draw_arc((x + w - r2, y + h - r2), (x + w, y + h), 90, 0, **colors)  # ne
            draw_rectangle((x - w, y - h + r), (x + w, y - h), **rec_colors)

        elif corner == "bottom":
            draw_arc((x - w, y - h), (x - w + r2, y - h + r2), 90, 180, **colors)  # sw
            draw_arc((x + w - r2, y - h), (x + w, y - h + r2), 90, 270, **colors)  # se
            draw_rectangle((x - w, y + h), (x + w, y + h - r), **rec_colors)

        elif corner == "left":
            draw_arc((x - w, y + h - r2), (x - w + r2, y + h), 90, 90, **colors)  # nw
            draw_arc((x - w, y - h), (x - w + r2, y - h + r2), 90, 180, **colors)  # sw
            draw_rectangle((x + w, y - h), (x + w - r, y + h), **rec_colors)

        elif corner == "right":
            draw_arc((x + w - r2, y + h - r2), (x + w, y + h), 90, 0, **colors)  # ne
            draw_arc((x + w - r2, y - h), (x + w, y - h + r2), 90, 270, **colors)  # se
            draw_rectangle((x - w + r, y - h), (x - w, y + h), **rec_colors)


class ButtonMouseOver(sg.Button):
    default_colors = dict(Enter="grey75", Leave="grey95")
    binds = ("<Enter>", "<Leave>")

    def __init__(self, *args, mouse_over_color=None, **kwargs):
        colors = kwargs.get("button_color")
        if isinstance(colors, tuple):
            text_color, button_color = colors
        else:
            text_color, button_color = None, colors

        self.colors = {
            "Leave": button_color or ButtonMouseOver.default_colors["Leave"],
            "Enter": mouse_over_color or ButtonMouseOver.default_colors["Enter"],
        }

        kwargs["button_color"] = (text_color, self.colors["Leave"])

        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in ButtonMouseOver.binds:
            self.Widget.bind(bind, self._on_mouse_over)

    def _on_mouse_over(self, event):
        self.update(button_color=self.colors.get(event.type.name))


class ButtonTxtAndImg(ButtonMouseOver):
    def __init__(
        self,
        *args,
        im_margin=0,
        image_filename=None,
        image_justify="left",
        im_height=20,
        **kwargs,
    ):
        self.im_margin = im_margin
        self.im_height = im_height
        self.image_filename = image_filename
        self.image_justify = image_justify
        kwargs["image_data"] = self._get_image_data(kwargs)
        kwargs["auto_size_button"] = False
        super().__init__(*args, **kwargs)

    def _get_image_data(self, kwargs):
        self._height = self.im_height + self.im_margin[1] * 2
        if self.image_filename:
            # colorize the img with the text color
            txt_color = kwargs.get("button_color")[0]
            self.im_data = resize_and_colorize_img(
                self.image_filename, self.im_height, txt_color, margin=self.im_margin
            )
            self._width = get_img64_size(self.im_data)[0] + self.im_margin[0] * 2
            return self.im_data

        self._width = self.im_margin[0]
        return None

    def _update_size(self, txt):
        wfont = tk_font.Font(self.ParentForm.TKroot, self.Font)
        size = wfont.measure(txt) + self._width, self._height
        self.set_size(size)

    def finalize(self):
        self.Widget.config(compound=self.image_justify, justify=self.image_justify)
        self._update_size(self.get_text())
        super().finalize()

    def update(self, *args, **kwargs):
        if color := kwargs.get("button_color"):
            if isinstance(color, tuple):
                if color[0] != self.ButtonColor[0]:
                    kwargs["image_data"] = self._get_image_data(kwargs)

        super().update(*args, **kwargs)

        if txt := kwargs.get("text") or (len(args) > 0 and args[0]):
            self._update_size(txt)


class TextFit(sg.Text):
    def font_fit_to_txt(self, txt, max_width, font_wanted_size, min_font_size):
        name, size = self.Font[0], font_wanted_size
        while True:
            font = name, size
            wfont = tk_font.Font(self.ParentForm.TKroot, font)
            extend = wfont.measure(txt)
            if size > min_font_size and extend > max_width:
                size -= 1
            else:
                self.update(font=font)
                break
        return size


class HLine(sg.Col):
    def __init__(self, p=0, color="black", thickness=1):
        super().__init__(
            [[]], p=p, s=(None, thickness), background_color=color, expand_x=True
        )

    def set_width(self, width):
        self.Widget.canvas.config(width=width)


class AnimatedGif(sg.Image):
    def __init__(self, *args, speed=1, **kwargs):
        self.speed = speed
        super().__init__(*args, **kwargs)

        self.durations = get_gif_durations(self.Data)
        self._animate(reset=True)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if kwargs.get("visible"):
            self._animate(reset=True)

    def _animate(self, reset=False):
        if self.visible:
            now = time.perf_counter()
            if reset:
                self.last_time = now
                self.frame_index = 0
                self.precise_index = 0
            dt = now - self.last_time
            self.last_time = now

            duration = self.durations[self.frame_index % len(self.durations)]
            self.precise_index += self.speed * dt * 1000 / duration
            frame_step = round(self.precise_index - self.frame_index)
            self.frame_index += frame_step
            for _ in range(frame_step):
                self.update_animation(self.Data, time_between_frames=0)

            time_step = max(20, round(duration / self.speed))
            window = self.ParentForm
            window.TKroot.after(time_step, self._animate)


# basic components
class Component:
    _for = None

    def __init__(self, element):
        if type(element).__name__ == self._for.__name__:
            self._element = element


class MlineButtonsComponent(Component):
    _for = sg.MLine

    def init(self, on_click=None, mouse_over_color=None, button_color=None):
        element = self._element
        self.mouse_enter_color = mouse_over_color or element.BackgroundColor
        self.mouse_leave_color = button_color or element.BackgroundColor
        self.tag = f"button{id(self)}"
        self.tags = {}
        self.on_click_callback = on_click
        self.pointed_button_key = None

        widget = element.Widget
        widget.bind("<Any-Motion>", self._on_mouse_move, add="+")
        widget.bind("<Leave>", self._on_mouse_leave, add="+")
        widget.bind("<Button-1>", self._on_click, add="+")

    def _on_mouse_leave(self, event):
        if event.type.name == "Leave":
            self.pointed_button_key = None
            for tag in self.tags:
                self._element.Widget.tag_configure(
                    tag, background=self.mouse_leave_color
                )

    def _on_click(self, event):
        if self.pointed_button_key and self.on_click_callback:
            self.on_click_callback(self.pointed_button_key)

    @staticmethod
    def _is_in_between(widget, index, start, end):
        return widget.compare(start, "<=", index) and widget.compare(index, "<=", end)

    def _on_mouse_move(self, event):
        widget = self._element.Widget
        index = widget.index(f"@{event.x},{event.y}")

        self.pointed_button_key = None
        tags = widget.tag_names(index)
        for tag, (button_key, start, end) in self.tags.items():
            if tag in tags and self._is_in_between(widget, index, start, end):
                self.pointed_button_key = button_key
                widget.tag_configure(tag, background=self.mouse_enter_color)
            else:
                widget.tag_configure(tag, background=self.mouse_leave_color)

    def add_tag(self, button_key, start, end):
        tag = f"{self.tag}{button_key}"
        self.tags[tag] = (button_key, start, end)
        self._element.Widget.tag_add(tag, start, end)

    def remove_tags(self):
        for tag in self.tags:
            self._element.Widget.tag_delete(tag)


class _PulsingBaseComponent(Component):
    colors = {}
    color_array_size = 32  # size of colors array
    time_step = 50  # ms

    def init(self, color_start, color_end, percent_to_end_color=0.75, frequency=1.5):
        self._is_pulsing = False
        self.frequency = frequency
        self._index_and_time = {}
        self._lock = threading.Lock()

        color_start = self._color_to_rgb(color_start)
        color_end = self._color_to_rgb(color_end)
        color_end = self._blend_rgb_colors(color_start, color_end, percent_to_end_color)
        self.colors_key = (color_start, color_end)

        # initialized as a class attribute
        if self.colors_key not in self.colors:
            self.colors[self.colors_key] = self._get_color_array(color_start, color_end)

    @staticmethod
    def _blend_rgb_colors(color1, color2, t):
        return tuple(
            map(lambda color: color[0] * (1 - t) + color[1] * t, zip(color1, color2))
        )

    @staticmethod
    def _get_color_array(color_start, color_end):
        array_size = _PulsingBaseComponent.color_array_size
        colors = []
        for x in range(array_size):
            t = 0.5 * (1 + math.cos((2 * math.pi * (x % array_size)) / array_size))
            r, g, b = _PulsingBaseComponent._blend_rgb_colors(
                color_start, color_end, 1 - t
            )
            colors.append(f"#{round(r):02x}{round(g):02x}{round(b):02x}")
        return colors

    def _color_to_rgb(self, color):
        # winfo_rgb works with any tkinter defined color like "red"
        rgb = self._element.Widget.winfo_rgb(color)
        return tuple(map(lambda color: int(color / 256), rgb))

    def _add_key(self, key):
        with self._lock:
            self._index_and_time[key] = (0, None)

    def _remove_key(self, key):
        pass

    def start(self):
        if not self._is_pulsing:
            self._is_pulsing = True
            self._pulse()

    def stop(self):
        self._is_pulsing = False
        with self._lock:
            for key in self._index_and_time:
                self._remove_key(key)
            self._index_and_time = {}

    def _pulse(self):
        if self._is_pulsing:
            now = time.perf_counter()
            colors = self.colors[self.colors_key]
            array_size = _PulsingBaseComponent.color_array_size
            with self._lock:
                for key, (index, t) in self._index_and_time.items():
                    color = colors[round(index) % array_size]
                    if t:
                        index += self.frequency * array_size * (now - t)
                    self._index_and_time[key] = index, now
                    self._update_color(key, color)

            window = self._element.ParentForm
            window.TKroot.after(self.time_step, self._pulse)


class MlinePulsingComponent(_PulsingBaseComponent):
    _for = sg.MLine

    def init(self, *args, **kwargs):
        super().init(*args, **kwargs)
        self.tag = f"pulsing{id(self)}"

    def add_tag(self, key, start, end):
        key = f"{self.tag}{key}"
        self._element.Widget.tag_add(key, start, end)
        super()._add_key(key)

    def _remove_key(self, key):
        self._element.Widget.tag_delete(key)

    def _update_color(self, key, color):
        self._element.Widget.tag_configure(key, foreground=color)


class TextPulsingComponent(_PulsingBaseComponent):
    _for = sg.Text

    def start(self):
        self._add_key("")
        super().start()

    def _update_color(self, key, color):
        self._element.update(text_color=color)


class BindToFunction:
    def __init__(self, sequence, bind_func):
        self.bind_ids = {}
        self.bind_func = bind_func
        self.sequence = sequence

    def bind(self, *elements):
        for element in elements:
            if not self.bind_ids.get(element):
                bind_id = element.Widget.bind(self.sequence, self.bind_func, add="+")
                self.bind_ids[element] = bind_id

    def unbind(self, element):
        if bind_id := self.bind_ids.get(element):
            # should use unbind but it removes all existing bind
            binds = element.Widget.bind(self.sequence).split("\n")
            new_binds = [l for l in binds if l[6 : 6 + len(bind_id)] != bind_id]
            element.Widget.bind(self.sequence, "\n".join(new_binds))
            del self.bind_ids[element]
