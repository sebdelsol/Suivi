import io
from PIL import Image, ImageOps
import base64

#---------------------------------------------------
def resize_and_colorize_gif(image64, height, color):
    buffer = io.BytesIO(base64.b64decode(image64))
    im = Image.open(buffer)

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

    buffer = io.BytesIO()
    frames[0].save(buffer, optimize = False, save_all = True, append_images = frames[1:], loop = 0, format = 'GIF', transparency = 0)
    return base64.b64encode(buffer.getvalue())

#-------------------------------------------------
def resize_and_colorize_img(image, height, color):
    im = Image.open(image)

    alpha = im.split()[3]
    im = ImageOps.colorize(ImageOps.grayscale(im), white = 'white', black = color) 
    im.putalpha(alpha)
    width = int(im.size[0] * height / im.size[1])
    im.thumbnail((width, height))

    buffer = io.BytesIO()
    im.save(buffer, format = 'PNG')
    return base64.b64encode(buffer.getvalue())

#-----------------------------------------
def expand_right_img64(image64, new_size):
    buffer = io.BytesIO(base64.b64decode(image64))
    im = Image.open(buffer)

    new = Image.new('RGBA', new_size, 0)
    pad = int((new_size[1] - im.size[1]) * .5)
    new.paste(im, (pad, pad))
    
    buffer = io.BytesIO()
    new.save(buffer, format = 'PNG')
    return base64.b64encode(buffer.getvalue())

#---------------------------
def get_img64_size(image64): 
    buffer = io.BytesIO(base64.b64decode(image64))
    im = Image.open(buffer)
    return im.size
