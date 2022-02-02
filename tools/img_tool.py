import base64
import io

from PIL import Image, ImageOps


def load_img64(image64):
    buffer = io.BytesIO(base64.b64decode(image64))
    return Image.open(buffer)


def save_img64(im, **kwargs):
    buffer = io.BytesIO()
    im.save(buffer, **kwargs)
    return base64.b64encode(buffer.getvalue())


def resize_and_colorize_gif(image64, height, color):
    im = load_img64(image64)

    resize_to = (im.size[0] * height / im.size[1], height)
    frames = []

    try:
        while True:
            frame = ImageOps.colorize(ImageOps.grayscale(im), white="white", black=color)
            frame = frame.convert("RGBA")
            frame.thumbnail(resize_to)
            frames.append(frame)
            im.seek(im.tell() + 1)

    except EOFError:
        pass

    return save_img64(
        frames[0],
        optimize=False,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        format="GIF",
        transparency=0,
    )


def get_gif_durations(image64):
    im = load_img64(image64)

    durations = []
    first_frame_duration = im.info["duration"]

    try:
        while True:
            durations.append(im.info.get("duration", first_frame_duration))
            im.seek(im.tell() + 1)

    except EOFError:
        pass

    return durations


def resize_and_colorize_img(image, height, color, canvas_size=None, margin=None):
    im = Image.open(image)

    alpha = im.split()[3]
    im = ImageOps.colorize(ImageOps.grayscale(im), white="white", black=color)
    im.putalpha(alpha)
    width = round(im.size[0] * height / im.size[1])
    im.thumbnail((width, height))

    w, h = im.size
    if margin:
        padw, padh = margin
        canvas_size = w + 2 * padw, h + 2 * padh

    elif canvas_size:
        W, H = canvas_size
        padw, padh = round((W - w) * 0.5), round((H - h) * 0.5)

    if canvas_size:
        new = Image.new("RGBA", canvas_size, 0)
        new.paste(im, (padw, padh))
        im = new

    return save_img64(im, format="PNG")


def get_img64_size(image64):
    im = load_img64(image64)
    return im.size
