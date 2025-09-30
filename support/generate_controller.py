"""
Generate the controller for the trolley

The image has the throttle centered at
@@@, @@@ with 9 positions numbered from 
0 to 8.   Optionally there are cyan dots
indicating the run positions.

The angle of the controller is -30 to 210 at 30 degrees each.


There is a reverser centered at @@,@@ with forward
and reveres angles of 135 (R) and 225 (F).
Neutral is 180.

Documentation References:
- Pillow (PIL) Documentation: https://pillow.readthedocs.io/
- Pillow ImageDraw Module: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html
- Python Math Module: https://docs.python.org/3/library/math.html

"""

from PIL import Image, ImageDraw
import math

# Size of the image
IMAGE_X=650
IMAGE_Y=300

CONTROLLER_LEFT=50      # Controller is 50 pixels to the right
CONTROLLER_X=650
CONTROLLER_Y=300
CONTROLLER_CORNER=27    # Rounding factor

RUN_TICK_START=50       # Where the run tick starts
RUN_TICK_END=100        # Where the run tick ends
RUN_TICK_LABEL=130      # Where the label for the run tick goes
TICK_COLOR = (0, 0, 0)  # RGB for ticks

REVERSER_OFFSET=80      # Space reverser is from left side
REVERSER_SIZE=15        # Size of the reverser dot

REVERSER_TICK_START=40  # Where to start the tick
REVERSER_TICK_END=80    # Where to end the tick
REVERSER_TICK_WIDTH=15  # Width of the tick
REVERSER_DOT_POS=110    # Where to put the dot

REVERSER_COLOR = (0, 0, 0)  # RGB for black
DOT_COLOR = (0, 255, 255)  # RGB for the helper dots
MIDDLE_DOT_COLOR = (255, 0, 0)  # RGB for the dot in the middle

DOT_RADUIS = 10  # 20 pixel diameter for all cyan dots

# WARNING: Edit ../controller.py if these change
CONTROLLER_CENTER_X, CONTROLLER_CENTER_Y = 350, 150   # Location of the center of the controller
circle_radius = 3               # Radius of red dot in the middle of the controller

def ReverserDot(Reverser_x, Reverser_y, Angle, Label):
    """
    Draw a reverser label

    Args:
        Reverser_x: Center of the reverser in X
        Reverser_y: Center of the reverser in Y
        Angle: The angle of the line
        Label: The label 
    """
    LineAngle = math.radians(Angle)  # Convert degrees to radians for trig functions
    # Draw a cyan dot with label at the end of the line
    dot_f_x = Reverser_x + REVERSER_DOT_POS * math.cos(LineAngle)
    dot_f_y = Reverser_y + REVERSER_DOT_POS * math.sin(LineAngle)
    ControllerDraw.ellipse([dot_f_x - DOT_RADUIS, dot_f_y - DOT_RADUIS,
                  dot_f_x + DOT_RADUIS, dot_f_y + DOT_RADUIS], fill=DOT_COLOR)
    ControllerDraw.text((dot_f_x, dot_f_y), Label, fill=(0, 0, 0), anchor="mm")
    
def ReverserLine(Reverser_x, Reverser_y, Angle, Label):
    """
    Draw a reverser line

    Args:
        Reverser_x: Center of the reverser in X
        Reverser_y: Center of the reverser in Y
        Angle: The angle of the line
        Label: The label to put at the end
    """
    LineAngle = math.radians(Angle)  # Convert degrees to radians for trig functions
    LineStart_x = Reverser_x + REVERSER_TICK_START * math.cos(LineAngle)  
    LineStart_y = Reverser_y + REVERSER_TICK_START * math.sin(LineAngle)
    LineEnd_x = Reverser_x + REVERSER_TICK_END * math.cos(LineAngle)  
    LineEnd_y = Reverser_y + REVERSER_TICK_END * math.sin(LineAngle)

    # Draw the black portion (second half of the line)
    ControllerDraw.line([LineStart_x, LineStart_y, LineEnd_x, LineEnd_y], 
              fill=REVERSER_COLOR, width=REVERSER_TICK_WIDTH)
    ReverserDot(Reverser_x, Reverser_y, Angle, Label)


def DrawReverser():
    # ============================================================================
    # Reverser center
    # ============================================================================
    Reverser_x = CONTROLLER_LEFT + REVERSER_OFFSET  # Left edge of rectangle (50) + 80 pixels offset
    Reverser_y = CONTROLLER_Y/2      # Vertical center of the image
    Reverser_radius = REVERSER_SIZE  # Half of 30 pixel diameter
    ControllerDraw.ellipse([Reverser_x - Reverser_radius, Reverser_y - Reverser_radius,
                  Reverser_x + Reverser_radius, Reverser_y + Reverser_radius], 
                  fill=REVERSER_COLOR)

    # ============================================================================
    # LINES The reverser
    # ============================================================================
    ReverserLine(Reverser_x, Reverser_y, 210, "F")
    ReverserLine(Reverser_x, Reverser_y, 150, "R")
    ReverserDot (Reverser_x, Reverser_y, 180, "N")

# Create a new RGB image with dimensions 650x300 pixels
# Background color is white
ControllerImage = Image.new('RGB', (IMAGE_X, IMAGE_Y), color='white')

# Create a drawing context for adding shapes and text to the image
ControllerDraw = ImageDraw.Draw(ControllerImage)

# ============================================================================
# MAIN RECTANGLE
# ============================================================================
# Draw a tan rectangle with rounded corners on the right side of the image
# Rectangle dimensions: 600 pixels wide x 300 pixels tall
# Position: starts at x=50 (to leave 50 pixels on left) and extends to x=650
# The rectangle fills the entire height (y=0 to y=300)
BROWN_COLOR = (0xda, 0xa5, 0x20)  # RGB values for tan color
ControllerDraw.rounded_rectangle([CONTROLLER_LEFT, 0, CONTROLLER_X, CONTROLLER_Y], radius=CONTROLLER_CORNER, fill=BROWN_COLOR)

DrawReverser()

def DrawRun(Center_X, Center_Y, Angle, Label, Width):
    """
    Draw the run tick

    Args:
        Center_X: Center of the controller in X
        Center_Y: Center of the controller in Y
        Angle: Angle of the tick
        Lable: Tick label
        Width: Width of the tick
    """

    LineAngle = math.radians(Angle)
    Line_Start_X = Center_X + RUN_TICK_START * math.cos(LineAngle)   # Midpoint for color transition
    Line_Start_Y = Center_Y + RUN_TICK_START * math.sin(LineAngle)
    Line_End_X = Center_X + RUN_TICK_END * math.cos(LineAngle)  # Endpoint
    Line_End_Y = Center_Y + RUN_TICK_END * math.sin(LineAngle)

    ControllerDraw.line([Line_Start_X, Line_Start_Y, Line_End_X, Line_End_Y], fill=TICK_COLOR, width=Width)

    # Dot for -30 degree line (label "0")
    Dot_X = Center_X + RUN_TICK_LABEL * math.cos(LineAngle)
    Dot_Y = Center_Y + RUN_TICK_LABEL * math.sin(LineAngle)
    ControllerDraw.ellipse([Dot_X - DOT_RADUIS, Dot_Y - DOT_RADUIS,
                  Dot_X + DOT_RADUIS, Dot_Y + DOT_RADUIS], fill=DOT_COLOR)
    ControllerDraw.text((Dot_X, Dot_Y), Label, fill=(0, 0, 0), anchor="mm")

# Draw the 9 ticks
for Tick in range(9):
    Angle = -30 + 30*Tick
    Label = str(Tick)
    Width = 5
    if (Tick in (0, 4, 8)):
       Width = 10
    DrawRun(CONTROLLER_CENTER_X, CONTROLLER_CENTER_Y, Angle, Label, Width)

# Red dot in the middle
ControllerDraw.ellipse([CONTROLLER_CENTER_X - circle_radius, CONTROLLER_CENTER_Y - circle_radius,
              CONTROLLER_CENTER_X + circle_radius, CONTROLLER_CENTER_Y + circle_radius], 
              fill=MIDDLE_DOT_COLOR)

# ============================================================================
# SAVE IMAGE
# ============================================================================
# Save the completed image as a PNG file
IMAGE_NAME="controller-bg.png"
ControllerImage.save(IMAGE_NAME)
print(f"Image created successfully: {IMAGE_NAME}")

# Optionally display the image (uncomment if running in an environment that supports it)
ControllerImage.show()
