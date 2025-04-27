#
# Copyright 2024 by Steve Oualline
# Licensed under the GNU Public License (GPL)
#
"""
Provides the controller and controller GUI class
"""
import sys
import pprint   #pylint: disable=W0611
import platform
import time
import vlc
import enum
import subprocess
import math
import os


from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import ( QApplication, QDialog, QMainWindow, QMessageBox )
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
from PyQt5.QtCore import Qt, QUrl, QRect
from PyQt5.QtGui import QBrush, QPen, QFont, QPixmap, QPainter

import state

class ControllerGraphics():
    """
    Handle the drawing and clicking of the controller controller.

    Fuctions:
        ControllerReset -- Reset the controller
        SetControllerRun(RunLevel) -- Set the run level of the controller
        SetReverse(Direction) -- Set the direction on the controller

    Callbacks
        MainWindow.SetRun -- Called to set run level
        MainWindow.SetDirection -- Called to set the direction

    """
    def __init__(self, MainWindow):
        """
        Setup controller window

        :param MainWindow: Top level window


        """

        MARGIN = 15                     # Margin for top/bottom of controller
        CONTROLLER_X_OFFSET = 80        # Move the controller over this amount

        Height = MainWindow.ControllerGraphicsView.height()
        Width = MainWindow.ControllerGraphicsView.width()

        self.ControllerScene = QGraphicsScene(0, 0, Width-MARGIN, Height-MARGIN)

        # Create the crontroller
        ControllerBackgroundImage = QPixmap(os.path.join("image", "controller-bg.png"))
        ControllerBackgroundImageScaled = ControllerBackgroundImage.scaledToHeight(Height - 2 * MARGIN)
        ControllerBackgroundItem = self.ControllerScene.addPixmap(ControllerBackgroundImageScaled)

        # Figure out the height of the controller and it's middle
        ControllerHeight = ControllerBackgroundImageScaled.height()
        Offset = (Height - ControllerHeight)/2 - MARGIN/2

        # Center the controller
        ControllerBackgroundItem.setPos(CONTROLLER_X_OFFSET, Offset)

        # Now put the controller on the controller
        ControllerHandle = QPixmap(os.path.join("image", "controller-arm.png"))
        ControllerScale = float(ControllerBackgroundImageScaled.width()) / \
            float(ControllerBackgroundImage.width()) 
        NewHeight = int(float(ControllerHandle.height()) * ControllerScale)

        # Scale the arm
        ControllerHandleScaled = ControllerHandle.scaledToHeight(NewHeight)

        self.ControllerHandleItem = self.ControllerScene.addPixmap(ControllerHandleScaled)

        # Try and adjust the center of the handle to the correct location
        CONTROLLER_HANDLE_X_OFFSET = 156
        CONTROLLER_HANDLE_Y_OFFSET = 40
        #                      0  1   2   3   4    5    6    7     8
        self.RUN_TO_ANGLE = (-30, 0, 30, 60, 90, 120, 150, 180, -150)

        # Because end of hand is rounded, we need to move it a little based on height alone
        self.ControllerHandleItem.setPos(CONTROLLER_HANDLE_X_OFFSET, CONTROLLER_HANDLE_Y_OFFSET)
        CONTROLLER_X_CENTER = 22   # The rotation point of the controller in X
        self.ControllerHandleItem.setTransformOriginPoint(ControllerHandleScaled.height()/2, ControllerHandleScaled.height()/2)
        self.ControllerHandleRotation = 0
        state.Log("Controller run level %d Angle %d" % (state.State.RunLevel, self.RUN_TO_ANGLE[state.State.RunLevel]))
        self.ControllerHandleItem.setRotation(self.RUN_TO_ANGLE[state.State.RunLevel])

        ReverseHandle = QPixmap(os.path.join("image", "reverser.png"))
        NewHeight = int(float(ReverseHandle.height()) * ControllerScale)

        # Scale the reverser
        ReverseHandleScaled = ReverseHandle.scaledToHeight(NewHeight)

        self.ReverseHandleItem = self.ControllerScene.addPixmap(ReverseHandleScaled)
        REVERSE_HANDLE_X_POS = 64      # Position of the handle in X
        REVERSE_HANDLE_X_OFFSET = 38    # Offset to rotation point
        self.ReverseHandleItem.setPos(REVERSE_HANDLE_X_POS, ControllerHeight/2+2)
        self.ReverseHandleItem.setTransformOriginPoint(REVERSE_HANDLE_X_OFFSET, ReverseHandleScaled.height()/2)
        self.ReverseHandleItem.setRotation(0)  

        self.MainWindow = MainWindow
        MainWindow.ControllerGraphicsView.mousePressEvent = self.MouseClick
        MainWindow.ControllerGraphicsView.setScene(self.ControllerScene)
        MainWindow.ControllerGraphicsView.show()

    def ControllerReset(self):
        """
        Reset the controller and the reverser
        """
        state.Log("Controller run level %d Angle %d" % (state.State.RunLevel, self.RUN_TO_ANGLE[RunLevel]))
        self.ControllerHandleItem.setRotation(self.RUN_TO_ANGLE[state.State.RunLevel])
        self.ReverseHandleItem.setRotation(0)  

    def SetControllerRun(self, RunLevel):
        """
        Set the run level for the controller

        :param RunLevel: The run level to use
        """
        state.Log("Controller run level %d Angle %d" % (RunLevel, self.RUN_TO_ANGLE[RunLevel]))
        self.ControllerHandleItem.setRotation(self.RUN_TO_ANGLE[RunLevel])

    def SetReverse(self, Direction):
        """
        Set the reverser position

        :param Reverse: The reverse position
        """
        if (Direction == state.DirectionEnum.FORWARD):
            self.ReverseHandleItem.setRotation(30)
        elif (Direction == state.DirectionEnum.NEUTRAL):
            self.ReverseHandleItem.setRotation(0)
        elif (Direction == state.DirectionEnum.REVERSE):
            self.ReverseHandleItem.setRotation(-30)
        else:
            print("INTERNAL ERROR: Illegal direction")

    def MouseClick(self, Event):
        """
        Handle a mouse click in the brake controller graphics box

        :param Event: Mouse click event
        """
        x = Event.x()
        y = Event.y()

        CONTROLLER_CLICK_X = 171   # Center of the controller
        CONTROLLER_CLICK_Y = 56

        REVERSER_X = 90         # Dividing line between reverser and controller
        REVERSER_Y_CENTER = 55  # Center of the controller in Y
        REVERSER_Y_WIDTH = 8    # Width of the reverser

        if (x <= REVERSER_X):
            if (y > (REVERSER_Y_CENTER + REVERSER_Y_WIDTH)): 
                self.MainWindow.SetDirection(state.DirectionEnum.REVERSE)
            elif (y < (REVERSER_Y_CENTER - REVERSER_Y_WIDTH)): 
                self.MainWindow.SetDirection(state.DirectionEnum.FORWARD)
            else:
                self.MainWindow.SetDirection(state.DirectionEnum.NEUTRAL)
            return

        Angle = math.degrees(math.atan2(y-CONTROLLER_CLICK_Y, x-CONTROLLER_CLICK_X))

        ClosestDelta = 9999
        # Loop through each runlevel to find nearest angle
        for Index in range(len(self.RUN_TO_ANGLE)):
            if (abs(Angle-self.RUN_TO_ANGLE[Index]) < ClosestDelta):
                RunLevel = Index
                ClosestDelta = abs(Angle-self.RUN_TO_ANGLE[Index])

        self.MainWindow.SetRun(RunLevel)

class ControllerButtons():
    """
    The controller using buttons only

    Functions
        ControllerReset -- Reset the controller
        SetControllerRun(RunLevel) -- Set the run level
        SetReverse(Direction) -- Set direction
    Callbacks
        MainWindow.SetRun -- Called to set run level
        MainWindow.SetDirection -- Called to set the direction
    """
    def __init__(self, MainWindow):
        """
        Setup controller window

        :param MainWindow: Top level window

        """
        self.MainWindow = MainWindow
        #-----------------------------------------------------------
        # Setup the buttons
        #-----------------------------------------------------------
        MainWindow.Run0.clicked.connect(lambda: MainWindow.SetRun(0))
        MainWindow.Run1.clicked.connect(lambda: MainWindow.SetRun(1))
        MainWindow.Run2.clicked.connect(lambda: MainWindow.SetRun(2))
        MainWindow.Run3.clicked.connect(lambda: MainWindow.SetRun(3))
        MainWindow.Run4.clicked.connect(lambda: MainWindow.SetRun(4))
        MainWindow.Run5.clicked.connect(lambda: MainWindow.SetRun(5))
        MainWindow.Run6.clicked.connect(lambda: MainWindow.SetRun(6))
        MainWindow.Run7.clicked.connect(lambda: MainWindow.SetRun(7))
        MainWindow.Run8.clicked.connect(lambda: MainWindow.SetRun(8))

        # A list of all the buttons
        self.RunList = [MainWindow.Run0, MainWindow.Run1, MainWindow.Run2, MainWindow.Run3, 
               MainWindow.Run4, MainWindow.Run5, MainWindow.Run6, MainWindow.Run7, MainWindow.Run8]

        MainWindow.ForwardButton.clicked.connect(lambda: MainWindow.SetDirection(state.DirectionEnum.FORWARD))
        MainWindow.NeutralButton.clicked.connect(lambda: MainWindow.SetDirection(state.DirectionEnum.NEUTRAL))
        MainWindow.ReverseButton.clicked.connect(lambda: MainWindow.SetDirection(state.DirectionEnum.REVERSE))
        self.DirectionList = [MainWindow.ForwardButton, MainWindow.NeutralButton, MainWindow.ReverseButton]

    def SetControllerRun(self, RunLevel):
        """
        Set the run level for the controller

        :param RunLevel: The run level to use
        """
        for Button in range(len(self.RunList)):
            self.RunList[Button].setChecked(Button == RunLevel)

    def ControllerReset(self):
        """
        Reset the controller and the reverser
        """
        SetControllerRun(0)
        SetReverse(state.DirectionList.NEUTRAL)

    def SetReverse(self, Direction):
        """
        Set the reverser position

        :param Reverse: The reverse position
        """
        for Button in range(len(self.DirectionList)):
            self.DirectionList[Button].setChecked(Button == Direction.value)

