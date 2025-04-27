#
# Copyright 2024 by Steve Oualline
# Licensed under the GNU Public License (GPL)
#
import math
import enum
import subprocess
import os
import signal

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import ( QApplication, QDialog, QMainWindow, QMessageBox )
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
from PyQt5.QtCore import Qt, QUrl, QRect
from PyQt5.QtGui import QBrush, QPen, QFont, QPixmap, QPainter

import state
import sound

# Define the sizes needed to draw the gauge.
# The gauge canvas is twice the gauge size for text and other 
# info on the bottom
# Note: You will need to change the UI using designer if you adjust these
DEBUG=False             # Draw debug lines
DRAW_X_SIZE = 100       # Gauge area X
DRAW_Y_SIZE = 100       # Gauge graphics Y
GAUGE_SIZE=DRAW_X_SIZE  # Size of the item
TICK_SIZE = 10          # Length of a tick
TICK_MARGIN = 10        # Margin for the ticks
ARROW_MARGIN = 30       # Margin for ends of the arrow
ARROW_X_OFFSET=12       # Shift arrow right
ARROW_X_CENTER=39       # Distance between point of arrow and center
#
# Angles on the gauge
#
START_ANGLE=-30        # Angle of first tick
STOP_ANGLE=220         # Angle of the last tick
MAX_PRESSURE=120       # Max pressure

MAX_BRAKE_PRESSURE=60   # How much brake pipe pressure we can have
MAX_RED_PRESSURE=MAX_BRAKE_PRESSURE-5   # Cylinder brake pressure

TICK=10.0               # Number of ticks/second
# Brake release behavior
# From a video it takes 2 seconds to go from 60 to 0 (about)
# so 30 PSI / second is the release rate
RELEASE_RATE=30.0/TICK  # Release rate in PSI/Tick
APPLY_RATE=60.0/TICK    # Apply Rate in PSI/Tick
#
# Pump up stuff
#
PUMP_UP_RATE=20.0/TICK   # Pump up at the rate of 20LBS per second
PUMP_UP_START=MAX_BRAKE_PRESSURE-15      # After loosing 15 LBS, pump up
APPLY_DROP=5.0/TICK     # We drop at the rate of 5 LBS/second when APPLY 
# Apply tuning
MAX_EXTEND=1.0          # It takes one second to extend
EXTEND_RATE=MAX_EXTEND/TICK     # How much to move when extending
# We brake at the rate of 1.0 (video speed) per second per 10 pounds of pressure
# So with a pressure of 10 we go from 1.0 to 0 in 1 second
# So with a pressure of 20 we go from 1.0 to 0 in 2 seconds
def ComputeBrakeAcceleration(RedPressure):
    """ 
    Return the acceleration caused by brakes

    :param RedPressure: Brake pressure
    """
    # 20 LB set stops the trolley in 10 seconds
    # Trolley speed goes from 1.0 to 0.0 in 10 seconds
    # speed = acceleration * time
    # Speed change -1
    # time 10 seconds
    # -1 = acceleration * 10
    # -1/10 = acceleration with 20 LB set

    # 10 LB set, slows at the rate of 0.025 speed
    Acceleration = (-((0.025 * RedPressure) / TICK))
    state.Log("BrakeAcceleration %3.2f RedPressure %d" % (Acceleration, RedPressure))
    return(Acceleration)

def PressureToAngle(Pressure):
     """
     Given a pressure, return the angle of the arrow

     :param Pressure: Pressure to convert

     :returns: Angle on the gauge
     """
     return (Pressure*2 + START_ANGLE)


def CreateTick(Angle):
    """
    Create a tick line at the given angle.

    :param Angle: Angle in degrees for the tick

    :returns: The tick line object
    """
    XCenter = GAUGE_SIZE / 2
    YCenter = GAUGE_SIZE / 2

    x0 = TICK_MARGIN
    y0 = GAUGE_SIZE/2
    x1 = TICK_MARGIN + TICK_SIZE
    y1 = GAUGE_SIZE / 2
    (x0, y0) = rotate_point((x0,y0), Angle, (XCenter, YCenter))
    (x1, y1) = rotate_point((x1,y1), Angle, (XCenter, YCenter))

    TickLine = QGraphicsLineItem(x0, y0, x1, y1)
    return(TickLine)

def TickNumber(Angle, Pressure, XAdjust, YAdjust):
    """
    Create text with a tick number in it

    :param Angle: Angle at which to place the number
    :param Pressure: Pressure to display
    :param XAdjust: Adjust X direction
    :param YAdjust: Adjust Y direction

    :returns: Text object
    """
    Font = QFont()
    Font.setPointSize(6)

    Text = QGraphicsTextItem("%d" % Pressure)
    Text.setFont(Font)

    RotatePoint = rotate_point((TICK_MARGIN + TICK_SIZE, GAUGE_SIZE/2), Angle, (GAUGE_SIZE/2, GAUGE_SIZE/2))

    Text.setPos(RotatePoint[0] - XAdjust, RotatePoint[1] - Text.boundingRect().height()/2 - YAdjust)
    return(Text)

#https://stackoverflow.com/questions/20023209/function-for-rotating-2d-objects
def rotate_point(point, angle, center_point=(0, 0)):
    """Rotates a point around center_point(origin by default)
    Angle is in degrees.
    Rotation is counter-clockwise

    :param point: Point we are rotating
    :param angle: Angle of rotation in degrees
    :param center_point: Point around which we rotate

    :returns: Rotated point
    """
    angle_rad = math.radians(angle % 360)
    # Shift the point so that center_point becomes the origin
    new_point = (point[0] - center_point[0], point[1] - center_point[1])
    new_point = (new_point[0] * math.cos(angle_rad) - new_point[1] * math.sin(angle_rad),
                 new_point[0] * math.sin(angle_rad) + new_point[1] * math.cos(angle_rad))
    # Reverse the shifting we have done
    new_point = (new_point[0] + center_point[0], new_point[1] + center_point[1])
    return new_point

class BrakeUi():
    def __init__(self, MainWindow):
        """
        Setup brake gauge

        :param MainWindow: Top level window

        """
        #-----------------------------------------------------------
        # Setup the brake gauge
        #-----------------------------------------------------------
        self.Scene = QGraphicsScene(0, 0, DRAW_X_SIZE, DRAW_Y_SIZE)
        # Not a typo.  We want the circle centered at the top of the Scene
        Ellipse = QGraphicsEllipseItem(0, 0, GAUGE_SIZE, GAUGE_SIZE)

        Pen = QPen(Qt.black)
        Pen.setWidth(3)
        Ellipse.setPen(Pen)
        self.Scene.addItem(Ellipse)

        if DEBUG:
            DebugRect = QGraphicsRectItem(0,0,DRAW_X_SIZE, DRAW_Y_SIZE)
            DebugPen = QPen(Qt.red)
            DebugPen.setWidth(3)
            DebugRect.setPen(DebugPen)

            # Add the items to the scene. Items are stacked in the order they are added.
            self.Scene.addItem(DebugRect)
            DebugLine = QGraphicsLineItem(0, GAUGE_SIZE/2, DRAW_X_SIZE, GAUGE_SIZE/2)
            DebugLine.setPen(DebugPen)
            self.Scene.addItem(DebugLine)

            # Line up/down
            DebugLine = QGraphicsLineItem(GAUGE_SIZE/2, 0, GAUGE_SIZE/2, DRAW_Y_SIZE)
            DebugLine.setPen(DebugPen)
            self.Scene.addItem(DebugLine)

        TickPen = QPen(Qt.black)
        TickPen.setWidth(2)

        DebugPressure = 0
        for Angle in range(-30, 220, 20):
            DebugPressure += 10
            TickLine = CreateTick(Angle)
            TickLine.setPen(TickPen)
            self.Scene.addItem(TickLine)

        Text = TickNumber(-10, 10, 0, 0)
        self.Scene.addItem(Text)
        Text = TickNumber( 30, 30, 3, -2)
        self.Scene.addItem(Text)
        Text = TickNumber( 70, 50, 8, -5)
        self.Scene.addItem(Text)
        Text = TickNumber( 110, 70, 10, -5) 
        self.Scene.addItem(Text)
        Text = TickNumber( 150, 90, 15, -5) 
        self.Scene.addItem(Text)
        Text = TickNumber( 190, 110, 20, 0) 
        self.Scene.addItem(Text)

        RawRedArrow = QPixmap(os.path.join("image", "arrow-ed.png"))
        RedArrow = RawRedArrow.scaledToWidth(DRAW_X_SIZE - ARROW_MARGIN)
        self.RedItem = self.Scene.addPixmap(RedArrow)
        self.RedItem.setPos(ARROW_X_OFFSET, DRAW_Y_SIZE/2 - RedArrow.height()/2)
        self.RedItem.setTransformOriginPoint(ARROW_X_CENTER, RedArrow.height()/2)
        self.RedItem.setRotation(0)

        RawBlackArrow = QPixmap(os.path.join("image", "arrow-black.png"))
        BlackArrow = RawBlackArrow.scaledToWidth(DRAW_X_SIZE - ARROW_MARGIN)
        self.BlackItem = self.Scene.addPixmap(BlackArrow)
        self.BlackItem.setPos(ARROW_X_OFFSET, DRAW_Y_SIZE/2 - BlackArrow.height()/2)
        self.BlackItem.setTransformOriginPoint(ARROW_X_CENTER, BlackArrow.height()/2)
        self.BlackItem.setRotation(0)
        self.BrakeList = [MainWindow.BrakeApply, MainWindow.BrakeRelease, MainWindow.BrakeLap, MainWindow.BrakeEmergency]
        self.BrakeReset()

    def PumpStop(self):
        """ 
        Called to stop the pump because of emergency
        """
        self.PumpAllowed = False
        self.SetPumping(False)
        
    def SetPumping(self,NewPumping):
        """
        Set the pumping state

        :param NewPumping: The new state

        Turns on and off the pumping sound
        """
        self.Pumping = NewPumping
        if (self.Pumping):
            sound.PlaySound.Play(sound.SoundEnum.PUMP_UP, True)
            state.Log("Pump sound on")
        else:
            sound.PlaySound.Stop(sound.SoundEnum.PUMP_UP)
            state.Log("Pump sound off")

    def PumpCheck(self):
        """
        Check to see if we need to pump up
        """
        if (not self.PumpAllowed):
            return

        if (self.BlackPressure <= PUMP_UP_START):
            self.SetPumping(True)

        if (self.BlackPressure <= MAX_BRAKE_PRESSURE):
            self.BlackPressure += PUMP_UP_RATE

        if (self.BlackPressure >= MAX_BRAKE_PRESSURE):
            self.BlackPressure = MAX_BRAKE_PRESSURE
            self.PumpStop()

    def SetGauge(self):
        """
        Set the brake pressure
        """
        RedRotation = PressureToAngle(self.RedPressure)
        BlackRotation = PressureToAngle(self.BlackPressure)
        if (RedRotation == BlackRotation):
            BlackRotation += 3
        self.RedItem.setRotation(RedRotation)
        self.BlackItem.setRotation(BlackRotation)

    def BrakeApplyClicked(self): 
        """
        The Brake:Apply button clicked
        """
        self.SetBrake(state.BrakeEnum.APPLY)

    def BrakeReleaseClicked(self):
        """
        The Brake:Release button clicked
        """
        self.SetBrake(state.BrakeEnum.RELEASE)

    def BrakeLapClicked(self):
        """
        The Brake:Lap button clicked
        """
        self.SetBrake(state.BrakeEnum.LAP)

    def BrakeEmergencyClicked(self):
        """
        The Brake:Emergency button clicked
        """
        self.BlackPressure = 0
        self.RedPressure = 0
        self.SetGauge()
        self.SetBrake(state.BrakeEnum.EMERGENCY)

    def BrakeReset(self):
        """
        Called when the brakes go into release
        """
        self.SetBrake(state.BrakeEnum.APPLY)
        self.BlackPressure = MAX_BRAKE_PRESSURE
        self.RedPressure = MAX_RED_PRESSURE
        self.PumpAllowed = True
        self.SetPumping(False)
        self.Extend = 0
        state.State.BrakeAcceleration = 0
        state.Log("BrakeAcceleration %f" % state.State.BrakeAcceleration)
        self.SetGauge()

    def SetBrake(self, What):
        """
        Set the correct brake button

        :param What: Valve position
        """
        state.State.BrakeValvePosition = What
        # Emergency sound here.  All others in the update function
        if (What == state.BrakeEnum.EMERGENCY):
            sound.PlaySound.Play(sound.SoundEnum.EMERGENCY, False)
        BrakeIndex = state.State.BrakeValvePosition.value
        state.Log("SetBrake(%s[%d])" % (What, BrakeIndex))

        for Button in range(len(self.BrakeList)):
            self.BrakeList[Button].setChecked(Button == BrakeIndex)

    def UpdateBrake(self, MainWindow):
        """
        Called every 1/10 seconds to update things

        :param MainWindow: The top level window
        """
        if (state.State.BrakeValvePosition == state.BrakeEnum.APPLY):
            self.RedPressure += APPLY_RATE

            if (self.RedPressure >= MAX_RED_PRESSURE):
                self.RedPressure = MAX_RED_PRESSURE
                sound.PlaySound.Stop(sound.SoundEnum.APPLY)
            else:
                sound.PlaySound.Play(sound.SoundEnum.APPLY, True)
                # We used some air from the reservoir so drop the pressure
                self.BlackPressure -= APPLY_DROP

            # Pressure can never go below 0
            if (self.BlackPressure < 0):
                self.BlackPressure = 0

            self.SetGauge()
            self.PumpAllowed = True

            state.Log("Extend: %f MAX_EXTEND %f" % (self.Extend, MAX_EXTEND))
            # Are we extending the brake 
            if (self.Extend < MAX_EXTEND):
                self.Extend += EXTEND_RATE
                state.Log("Extending")
                if (self.Extend > MAX_EXTEND):
                    self.Extend = MAX_EXTEND
                state.State.BrakeAcceleration = 0
            else:
                state.State.BrakeAcceleration = ComputeBrakeAcceleration(self.RedPressure)
                state.Log("Braking %f" % state.State.BrakeAcceleration)

        elif (state.State.BrakeValvePosition  == state.BrakeEnum.RELEASE):
            sound.PlaySound.Play(sound.SoundEnum.RELEASE, True)
            # We are releasing, so drop brake pressure
            self.RedPressure -= RELEASE_RATE
            self.PumpAllowed = True
            state.State.BrakeAcceleration = 0
            state.Log("BrakeAcceleration {0}".format(state.State.BrakeAcceleration))
            if (self.Extend > 0):
                self.Extend -= EXTEND_RATE
                if (self.Extend < 0):
                    self.Extend = 0

            if (self.RedPressure <= 0):
                self.RedPressure = 0
                sound.PlaySound.Stop(sound.SoundEnum.RELEASE)

        elif (state.State.BrakeValvePosition  == state.BrakeEnum.LAP):
            self.PumpAllowed = True
            # Are we extending the brake 
            if (self.Extend < MAX_EXTEND):
                self.Extend += EXTEND_RATE
                if (self.Extend > MAX_EXTEND):
                    self.Extend = MAX_EXTEND
                state.State.BrakeAcceleration = 0
                state.Log("BrakeAcceleration {0} Extend {1}".format(
                        state.State.BrakeAcceleration, self.Extend))
            else:
                state.State.BrakeAcceleration = ComputeBrakeAcceleration(self.RedPressure)
                state.Log("BrakeAcceleration %f" % state.State.BrakeAcceleration)
        elif (state.State.BrakeValvePosition  == state.BrakeEnum.EMERGENCY):
            self.PumpStop()
            state.State.BrakeAcceleration = ComputeBrakeAcceleration(MAX_BRAKE_PRESSURE)
            state.Log("BrakeAcceleration %f" % state.State.BrakeAcceleration)
        else:
            printf("Internal error: Impossible brake mode %s" % state.State.BrakeValvePosition )
            sys.exit(8)

        self.SetGauge()
        self.PumpCheck()

