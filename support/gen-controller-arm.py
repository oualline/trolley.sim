from PIL import Image, ImageDraw

# Define constants
BROWN_COLOR = (0x8b, 0x45, 0x13)  # RGB values for tan color
CIRCLE_RADIUS = 40
RECT_LENGTH = 130
END_CIRCLE_RADIUS = 20
BORDER_WIDTH = 3
HOLE_RADIUS = 3

# Calculate minimum image size
Width = (CIRCLE_RADIUS + BORDER_WIDTH) + RECT_LENGTH + END_CIRCLE_RADIUS + BORDER_WIDTH
Height = 2 * (CIRCLE_RADIUS + BORDER_WIDTH)

# Create a new image with transparent background (RGBA mode)
Img = Image.new('RGBA', (Width, Height), (0, 0, 0, 0))
Draw = ImageDraw.Draw(Img)

# Starting position for the circle (left side)
CircleCenterX = CIRCLE_RADIUS + BORDER_WIDTH
CircleCenterY = Height // 2

# Draw the rectangle extending to the right (draw first, behind circles)
RectWidth = 20
RectLeft = CircleCenterX
RectTop = CircleCenterY - RectWidth // 2
RectRight = RectLeft + RECT_LENGTH
RectBottom = RectTop + RectWidth

Draw.rectangle(
    [RectLeft, RectTop, RectRight, RectBottom],
    fill=BROWN_COLOR,
    outline='black',
    width=BORDER_WIDTH
)

# Draw the main circle (radius 40, tan fill, 3px black border)
Draw.ellipse(
    [CircleCenterX - CIRCLE_RADIUS, CircleCenterY - CIRCLE_RADIUS,
     CircleCenterX + CIRCLE_RADIUS, CircleCenterY + CIRCLE_RADIUS],
    fill=BROWN_COLOR,
    outline='black',
    width=BORDER_WIDTH
)

# Draw the hole in the center (3 pixel radius)
Draw.ellipse(
    [CircleCenterX - HOLE_RADIUS, CircleCenterY - HOLE_RADIUS,
     CircleCenterX + HOLE_RADIUS, CircleCenterY + HOLE_RADIUS],
    fill=(0, 0, 0, 0),  # Transparent fill
    outline='black',
    width=1
)

# Draw the black circle at the right end of the rectangle
EndCircleCenterX = RectRight
EndCircleCenterY = CircleCenterY

Draw.ellipse(
    [EndCircleCenterX - END_CIRCLE_RADIUS, EndCircleCenterY - END_CIRCLE_RADIUS,
     EndCircleCenterX + END_CIRCLE_RADIUS, EndCircleCenterY + END_CIRCLE_RADIUS],
    fill='black',
    outline='black'
)

# Save and display the image
IMAGE="controller-arm.png"
Img.save(IMAGE)
Img.show()
print(f"Image generated and saved as {IMAGE}")
