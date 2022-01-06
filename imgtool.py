import io
from PIL import Image, ImageOps
import base64

#-----------------------
def load_img64(image64):
    buffer = io.BytesIO(base64.b64decode(image64))
    return Image.open(buffer)

def save_img64(im, **kwargs):
    buffer = io.BytesIO()
    im.save(buffer, **kwargs)
    return base64.b64encode(buffer.getvalue())

#---------------------------------------------------
def resize_and_colorize_gif(image64, height, color):
    im = load_img64(image64)

    resize_to = (im.size[0] * height / im.size[1], height)
    frames = []

    try:
        while True:
            frame = ImageOps.colorize(ImageOps.grayscale(im), white = 'white', black = color)
            frame = frame.convert('RGBA')
            frame.thumbnail(resize_to)
            frames.append(frame)
            im.seek(im.tell() + 1)
    
    except EOFError:
        pass

    return save_img64(frames[0], optimize = False, save_all = True, append_images = frames[1:], loop = 0, format = 'GIF', transparency = 0)

#-------------------------------------------------
def resize_and_colorize_img(image, height, color):
    im = Image.open(image)

    alpha = im.split()[3]
    im = ImageOps.colorize(ImageOps.grayscale(im), white = 'white', black = color) 
    im.putalpha(alpha)
    width = int(im.size[0] * height / im.size[1])
    im.thumbnail((width, height))

    return save_img64(im, format = 'PNG')

#-----------------------------------------
def expand_right_img64(image64, new_size):
    im = load_img64(image64)

    new = Image.new('RGBA', new_size, 0)
    pad = int((new_size[1] - im.size[1]) * .5)
    new.paste(im, (pad, pad))
    
    return save_img64(new, format = 'PNG')

#---------------------------
def get_img64_size(image64): 
    im = load_img64(image64)
    return im.size
