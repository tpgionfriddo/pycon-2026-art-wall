"""Text and shapes. Static PIL, returning the Image."""
# draw() can also hand back a PIL Image, which is the shortest way in if you
# would rather place shapes than compute pixels.
#
# "RGBA" and a fully transparent fill start the image empty rather than
# white, so only what you draw appears on the wall.

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
NAVY, ORANGE, PINK = "#020763", "#FC801D", "#FF318C"


def draw():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(img)

    # Boxes are given as [left, top, right, bottom] in pixels, measured from
    # the top left corner.
    pen.ellipse([46, 46, SIZE - 46, SIZE - 46], fill=NAVY)
    pen.rectangle([46, 232, SIZE - 46, 280], fill=ORANGE)

    for i in range(6):
        left = 104 + i * 50
        pen.rectangle([left, 330, left + 28, 330 + 12 * (i + 1)], fill=PINK)

    font = ImageFont.load_default(size=44)
    pen.text((SIZE / 2, 150), "hello", font=font, fill="white", anchor="mm")
    return img
