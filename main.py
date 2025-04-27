#
# Copyright 2024 by Steve Oualline
# Licensed under the GNU Public License (GPL)
#
"""
Main GUI for the trolley simulator

TODO:
        Add replay/playback mode
"""
import sys
import pprint   #pylint: disable=W0611
import platform
import time
import vlc
import enum
import subprocess
import math
import webbrowser
import os

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import ( QApplication, QDialog, QMainWindow, QMessageBox )
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
from PyQt5.QtCore import Qt, QUrl, QRect
from PyQt5.QtGui import QBrush, QPen, QFont, QPixmap, QPainter

import mode_window
import sim_ui4
import brake_ui
import state
import controller
import sound
import video_player

if '_PYI_APPLICATION_HOME_DIR' in os.environ:
    DIR=os.environ['_PYI_APPLICATION_HOME_DIR']
    os.chdir(DIR)
else:
    DIR=os.getcwd()

VideoFile = DIR + "/video/trolley.m4v"

class ModeEnum(enum.Enum):
    EASY = 0         # Mode is easy
    START_STOP = 1   # Mode is start/stop
    FULL = 2         # Mode is full checking

#----------------------------------------------------------------
# Physics section
#
# Speed is measured in playback rate.  1.0 is normal playback speed
# Run1 at full speed is 1.5
# Run2 at full speed is 2.0
# Run3 at full speed is 2.5
#
# These speeds are based on the speed of the video and have no scientific
# justification.
#
# Acceleration is defined A=VT. V is defined by MAX_SPEED.
# The time to reach full speed is set to SPEED_TIME or 6 seconds.
# (Again an estimation)
#----------------------------------------------------------------
MIN_SPEED=0.5   # Vlc won't move at lower speeds
#            0    1    2    3    4     5     6     7      8
MAX_SPEED = [0.5, 1.5, 2.0, 2.5, -1.0, -1.0, -1.0, -1.0, -1.0]
SPEED_TIME = 6  # Number of seconds it takes to get to full speed.

FRICTION=0.99995   # Friction is 0.005% of the current speed

MAX_RUN_TIME=10 # Longest we can run in anything but full series or full parallel
MAX_DOWN_TIME=1 # Longest we can stay in a run level going down

# Signal section
MAX_SIGNAL_START=10     # You must move within 10 seconds of issuing start signal
MAX_START_BETWEEN=2     # The ding ding that starts must occur within 2 seconds
STOP_TIME_CHECK=10      # Check stop signal 10 seconds after stop
STOP_SIGNAL_TIME=2      # Must have two seconds before stop to avoid confusion

STORE_POSITION=0.95     # Beginning of the store
END_OF_VIDEO=0.98       # After this there is no more video

CLICK_CLACK_NORMAL_INTERVAL = 3.0       # Click/clack 3 seconds at normal speed

CENTRAL_BELL_START = 0.36       # Location to start sounding central bell
CENTRAL_BELL_STOP = 0.45        # Location to stop sounding central bell

def ComputeAcceleration(Level):
    """
    Given a run level, compute the acceleration for that run level

    :param Level: The run level
    :returns: Acceleration
    """
    global MAX_SPEED
    global SPEED_TIME

    return((MAX_SPEED[Level] - MAX_SPEED[Level-1]) / SPEED_TIME)

class EasyMode:
    Name = "Easy Mode"
    """
    Class that defines the easy mode of operation.

    In this mode you can press Run0, Run1, Run2. 
    Run0 will brake the trolley until it stops.
    Run1 will accelerate to the Run1 speed.  If you are faster that that it brakes.
    Run2 will accelerate to the Run2 speed.  If you are faster that that we have an internal error
    """
    def __init__(self):                 # EasyMode
        # The deacceleration speed
        self.SlowDownAcceleration = -0.5
        self.CentralSounding = False

    """
    Mode where you move by setting Run-1 and Run-2.  
    Moving the controller back will slow you down.

    :param: MainWindow -- The main window
    """
    def ModeSetRun(self, MainWindow, RunLevel):         # Easymode
        """
        Set the run level

        :param MainWindow: The Top level window
        :param RunLevel: RunLevel to set
        """
        state.Log("Runlevel Old %d New %d" % (state.State.RunLevel, RunLevel))
        # First do nothing if the run level does not change
        if (RunLevel == state.State.RunLevel):
            return (True)

        # Find the maximum speed
        self.MaxSpeed = MAX_SPEED[RunLevel]

        # Run0 has special speed
        if (RunLevel == 0):
            self.MaxSpeed = 0

        # Don't let us fall below the minimum
        # VLC don't really move right with speeds from 0 to 0.5
        if (RunLevel > 0) and (state.State.Speed < MIN_SPEED):
            state.State.Speed = MIN_SPEED
            state.Log("Speed %f" % state.State.Speed)

        # Decide what type of acceleration we need
        if (state.State.Speed > self.MaxSpeed):
            state.State.Acceleration = self.SlowDownAcceleration
            state.Log("Acceleration %1.3f" % state.State.Acceleration)
        else:
            state.State.Acceleration = ComputeAcceleration(RunLevel)
            state.Log("Acceleration %1.3f" % state.State.Acceleration)
        return True

    def ModeReset(self):                    # EasyMode
        """
        Called to reset the mode

        """
        self.MaxSpeed = 0
        state.State.Reset()

    def ModeUpdate(self, MainWindow):                   # EasyMode
        """
        Return the updated speed

        :param MainWindow: The main window
        """

        # Increase speed based on acceleration 
        # The 10.0 is because we update 10 times a second
        state.State.Speed += (state.State.Acceleration/10.0)         
        state.Log("Speed %1.3f" % state.State.Speed)

        if (state.State.Acceleration > 0):
            if (state.State.Speed > self.MaxSpeed):
                state.State.Acceleration = 0
                state.State.Speed = self.MaxSpeed
                state.Log("Speed %1.3f" % state.State.Speed)
        else:
            if (state.State.Speed < 0):
                state.State.Acceleration = 0
                state.State.Speed = 0
                state.Log("Speed %1.3f" % state.State.Speed)

        ##@@ Make common code
        if ((MainWindow.MediaPlayer.get_position() >= CENTRAL_BELL_START) and 
            (not self.CentralSounding)):
            self.CentralSounding = True
            sound.PlaySound.Play(sound.SoundEnum.CENTRAL_BELL, True)

        if ((MainWindow.MediaPlayer.get_position() >= CENTRAL_BELL_STOP) and 
            (self.CentralSounding)):
            self.CentralSounding = False
            sound.PlaySound.Stop(sound.SoundEnum.CENTRAL_BELL)

    def RulesCheck(self, MainWindow):   # EasyMode
        """
        Check to see if we violated any of the rules

        :param MainWindow: Top level window

        :returns: True if it's safe to contine
        """
        if (not state.State.Deadman) and ((state.State.Speed != 0) or (state.State.RunLevel != 0)):
            state.Log("MediaPlayer.pause()")
            Result = MainWindow.MediaPlayer.pause()
            MainWindow.ErrorDeadman()
            MainWindow.MainReset()
            return False
        return True

class StartStopMode:
    """
    Mode where you move by setting Run-1 and Run-2.  
    Moviing the controller back does nothing.

    Brakes work.
    """
    Name = "Start/Stop Mode"

    def __init__(self):
        self.CentralSounding = False

    def ModeSetRun(self, MainWindow, RunLevel):         # StartStopMode
        """
        Set the run level

        :param MainWindow: Main window
        :param RunLevel: Run level selected

        :returns: True if we should contine, false if should reset
        """
        # First we check to see if the RunLevel has changed
        if (state.State.RunLevel != RunLevel):
            self.LastRunLevel = state.State.RunLevel
            self.RunLevelTime = time.time()
            # Now we need to check if we've exceeded the limits on run level
            # If so, we will error out and stop the simulation
            if (MAX_SPEED[RunLevel] < 0):
                MainWindow.ErrorMessageRun4()
                return False

            # Run level is acceptable.
            # Now we need to decide if we need to accelerate.
            # If we are moving, then we compute the acceleration in (video speed/tick)
            # by checking how much it takes to go from one run speed to another in the
            # time needed to reach maximum speed
            if (RunLevel != 0):
                state.State.Acceleration = ComputeAcceleration(RunLevel)
                state.Log("Acceleration %1.3f" % state.State.Acceleration)

                # Save off the maximum speed for this run level
                self.MaxSpeed = MAX_SPEED[RunLevel]
            else:
                # We are run level 0.  So we coast (as far as the motor is concerned)
                # The brake will play with this number later
                state.State.Acceleration = 0
                state.Log("Acceleration %1.3f" % state.State.Acceleration)

        if (self.MaxSpeed < state.State.Speed):
            state.State.Acceleration = 0
            state.Log("Acceleration %1.3f" % state.State.Acceleration)
            state.State.Speed = self.MaxSpeed
            state.Log("Speed %1.3f" % state.State.Speed)
            
        state.Log("StartStopMode: SetRunLevel %d Acceleration %1.3f" % (RunLevel, state.State.Acceleration))
        return (True)

    def ModeReset(self):            # StartStopMode
        """
        Called to reset the mode

        """
        state.State.Reset()
        self.MaxSpeed = 0
        self.LastRunLevel = 0

    def ModeUpdate(self, MainWindow):           # StartStopMode
        """
        Return the updated speed

        :param MainWindow: Main window
        """

        # Increase speed based on acceleration 
        # The 10.0 is because we update 10 times a second
        state.State.Speed += ((state.State.Acceleration + state.State.BrakeAcceleration)/10.0)          
        state.Log("Speed %f No FRICTION" % state.State.Speed)
        state.State.Speed *= FRICTION
        state.Log("Speed %f FRICTION" % state.State.Speed)

        if (state.State.Speed < 0):
            state.State.Speed = 0
            state.Log("Speed %f" % state.State.Speed)

        state.Log("Acceleration {0} BrakeAcceleration: {1}".format( \
                state.State.Acceleration, state.State.BrakeAcceleration))

        if (state.State.Acceleration > 0):
            if (state.State.Speed > self.MaxSpeed):
                state.State.Speed = self.MaxSpeed
                state.Log("Speed %f" % state.State.Speed)
                state.State.Acceleration = 0
                state.Log("Acceleration %f" % state.State.Acceleration)
        else:
            if (state.State.Speed < 0):
                state.State.Speed = 0
                state.Log("Speed %f" % state.State.Speed)
                state.State.Acceleration = 0
                state.Log("Acceleration %f" % state.State.Acceleration)

        if ((MainWindow.MediaPlayer.get_position() >= CENTRAL_BELL_START) and (not self.CentralSounding)):
            self.CentralSounding = True
            sound.PlaySound.Play(sound.SoundEnum.CENTRAL_BELL, True)

        if ((MainWindow.MediaPlayer.get_position() >= CENTRAL_BELL_STOP) and (self.CentralSounding)):
            self.CentralSounding = False
            sound.PlaySound.Stop(sound.SoundEnum.CENTRAL_BELL)


    def RulesCheck(self, MainWindow):   # Start stop mode
        """
        Check to see if we violated any of the rules

        :param MainWindow: Top level window

        :returns: True if it's safe to contine
        """
        # The deadman must be pressed if we are moving or trying to run
        if (not state.State.Deadman) and \
            ((state.State.Speed != 0) or (state.State.RunLevel != 0)):
            state.Log("StartStop: Deadman %d %f %d" % \
                 (state.State.Deadman, state.State.Speed, state.State.RunLevel))
            MainWindow.ErrorDeadman()
            MainWindow.MainReset()
            return False

        # If we are moving or trying to the brake must be released
        if ((state.State.RunLevel != 0) and \
            (state.State.BrakeValvePosition != state.BrakeEnum.RELEASE)):
            MainWindow.ErrorMoveWithBrakesOn()
            MainWindow.MainReset()
            return False

        # We are only allowed to move in the forward direction
        if ((state.State.RunLevel != 0) and \
            (state.State.Direction != state.DirectionEnum.FORWARD)):
            MainWindow.ErrorNoForward()
            MainWindow.MainReset()
            return False

        if (state.State.RunLevel != 0):
            # Get the time of the last element of the run info file
            TimeDiff = time.time() - self.RunLevelTime

            if (state.State.RunLevel > self.LastRunLevel):
                if (TimeDiff > MAX_RUN_TIME):
                    MainWindow.ErrorRunTooLong()
                    MainWindow.MainReset()
                    return (False)
            else:
                if (TimeDiff > MAX_DOWN_TIME):
                    MainWindow.ErrorRunTooLongDown()
                    MainWindow.MainReset()
                    return (False)

        return True

class FullMode(StartStopMode):
    """
    Make sure we follow all the rules.

    Rules:
        1. Two dings before each start
        2. One ding after stop.
        3. Stop at broadway
        4. Sound bell when crossing.
        5. Sound bell when crossing center.
        6. Stop at CB4
        7. No power at Zorch point / broadway spur
        8. Bell crossing broadway
        9. No power at Zorch point / main spur
        10. Stop at thomas
        11. Stop at store
    """

    ########
    ######## Stop information
    ########
    BROADWAY_STOP_BEGIN=0.09        # Position of the start of where can do a Broadway stop
    BROADWAY_STOP_END=0.12          # Position of the end of where can do a Broadway stop
    BROADWAY_STOP_CHECK=0.15        # Position of where we check to see if Broadway stop done
    ##@@ REmove above

    CB4_STOP_BEGIN=0.58             # Position of the start of where can do a CB4 stop
    CB4_STOP_END=0.61               # Position of the end of where can do a CB4 stop

    ##@@ Make real
    THOMAS_STOP_BEGIN=0.87           # Position of the start of the Thomas stop
    THOMAS_STOP_END=0.93             # Position of the end of the Thomas stop

    STOP_CHECKS_START = (BROADWAY_STOP_BEGIN, CB4_STOP_BEGIN, THOMAS_STOP_BEGIN)
    STOP_CHECKS_END =   (BROADWAY_STOP_END,   CB4_STOP_END,   THOMAS_STOP_BEGIN)
    STOP_MESSAGE    =   ("Broadway",          "Carbarn 2",    "Thomas")

    ########
    ######## Crossing information
    ########
    BROADWAY_NORTH_BEGIN=0.12       # Position where we start crossing Broadway
    BROADWAY_NORTH_END=0.15         # Position where we stop crossing Broadway
    
    CENTRAL_BEGIN=0.39              # Where we start crossing Central Ave.
    CENTRAL_END=0.42                # Where we start crossing Central Ave.

    BROADWAY_SOUTH_BEGIN=0.70       # Position where we start crossing Broadway (South)
    BROADWAY_SOUTH_END=0.75         # Position where we stop crossing Broadway (South)

    CROSSING_START   = (BROADWAY_NORTH_BEGIN, CENTRAL_BEGIN, BROADWAY_SOUTH_END)
    CROSSING_END     = (BROADWAY_NORTH_END,   CENTRAL_END,   BROADWAY_SOUTH_END)
    CROSSING_MESSAGE = ("Broadway north",     "Central",     "Broadway South")

    CROSSING_DING_COUNT=3           # Number of dings needed at each crossing

    ########
    ######## Zorch information
    ########
    ZORCH1_POS_START=0.70                 # Zorch position 1 start
    ZORCH2_POS_START=0.77                 # Zorch position 2 start
    ZORCH1_POS_END=0.73                   # Zorch position 1 ending
    ZORCH2_POS_END=0.79                   # Zorch position 2 ending

    ZORCH_START   = (ZORCH1_POS_START, ZORCH2_POS_START)
    ZORCH_END     = (ZORCH1_POS_END,   ZORCH2_POS_END)
    ZORCH_MESSAGE = ("Carbarn1 lead", "Main line spur")

    Name = "Full Mode"

    def __init__(self):
        self.CentralSounding = False

    def ModeSetRun(self, MainWindow, RunLevel):         # FullMode
        """
        Set the run level

        :param MainWindow: Main window
        :param RunLevel: Run level selected

        :returns: True if we should continue, false if should reset
        """
        Continue = super().ModeSetRun(MainWindow, RunLevel)
        state.Log("Continue %s" % Continue)
        return (Continue)

    def ModeReset(self):            # FullMode
        """
        Called to reset the mode

        """
        super().ModeReset()
        # These two variables are used to detect starts and stops
        self.LastSpeed = 0              # The speed before this one
        self.CurrentSpeed = 0           # The speed we have now

        self.StopTime = 0               # Time of last stop is old

        self.StopCheckDone = [False, False, False]      # Have we checked for a stop
        self.CrossingCheckDone = [False, False, False]  # Did we ring at a crossing
        self.ZorchDone = [False, False]                 # Did we do a zorch

    def ModeUpdate(self, MainWindow):           # FullMode
        """
        Return the updated speed

        :param MainWindow: Main window
        """
        super().ModeUpdate(MainWindow)
        self.LastSpeed = self.CurrentSpeed
        self.CurrentSpeed = state.State.Speed

    def DingCount(self, DingPosition, Start, End):
        """
        Return the number of dings in the interval

        :param DingPosition: List of ding positions
        :param Start: When to start counting
        :param End: When to stop counting

        :returns: Number of dings seen
        """
        Result = 0
        for ADing in DingPosition:
            if (ADing >= Start) and (ADing <= End):
                Result += 1
        return (Result)

    def CheckStartStopDing(self, MainWindow):
        """
        Checks to see if we started or stopped and did 
        the dings correctly

        :param MainWindow: The main window

        Notes:
            DingTime -- When we did each ding

        """
        # See if we went from stopped to moving
        if (self.LastSpeed == 0) and (self.CurrentSpeed != 0):
            # Now check to see if the operator did ding-ding before moving
            # There must be two dings in the last 10 seconds
            # and they must be less than 2 seconds apart

            # Do we have two dings
            if (len(MainWindow.DingTime) < 2):
                MainWindow.AddWarning("Started moving without sounding start signal")
            else:
                # Current time 1000 Ding time 999 Good=true
                # Current time 1000 Ding time 900 Good=false

                # Did we signal within the last 10 seconds
                if (time.time() - MainWindow.DingTime[-2] > MAX_SIGNAL_START):
                    MainWindow.AddWarning("Started moving without sounding start signal")
                # Are the ding ding more than 2 seconds apart
                elif ((MainWindow.DingTime[-1] - MainWindow.DingTime[-2]) > MAX_START_BETWEEN):
                    MainWindow.AddWarning("Start signal is ding-ding not ding-wait-ding")

        # Did we ding after stopping
        if (len(MainWindow.DingTime) > 0):
            if (MainWindow.DingTime[-1] >= self.StopTime):
                LastDing = MainWindow.DingTime[-1]
            else:
                LastDing = 0
        else:
            LastDing = 0

        if (self.StopTime != 0) and \
            ((time.time() - self.StopTime >= STOP_TIME_CHECK) or (LastDing > self.StopTime)):
            # There should be one ding in the last second

            DingLen = len(MainWindow.DingTime)
            # Check to see if signal missed
            if (DingLen == 0):
                MainWindow.AddWarning("No stop signal")
            else:
                # Check to see if single ding.  (Occurs when start signal missed)
                if ((time.time() - MainWindow.DingTime[-1]) > STOP_SIGNAL_TIME):
                    MainWindow.AddWarning("Stop Signal too slow or missing")
                elif (DingLen > 1):
                    if ((MainWindow.DingTime[-1] -  \
                                MainWindow.DingTime[-2]) < STOP_SIGNAL_TIME):
                        MainWindow.AddWarning("Stop Signal confused with other signals")

            self.StopTime = 0   # We've looked at this so clear it

        if (self.LastSpeed != 0) and (self.CurrentSpeed == 0):
            self.StopTime = time.time()

    def RulesCheck(self, MainWindow):   # Full mode
        """
        Check to see if we violated any of the rules

        :param MainWindow: Top level window

        :returns: True if it's safe to continue
        """
        Continue = super().RulesCheck(MainWindow)
        if (not Continue):
            return (Continue)

        self.CheckStartStopDing(MainWindow)

        # Check bell at crossing
        for Index in range(len(self.CROSSING_START)):
            if (self.CrossingCheckDone[Index]):
                continue

            if (MainWindow.MediaPlayer.get_position() >= self.CROSSING_END[Index]):
               # Get the number of times we dinged here
               DingDingDing = self.DingCount(MainWindow.DingPosition, 
                   self.CROSSING_START[Index], self.CROSSING_END[Index])

               if (DingDingDing < self.CROSSING_DING_COUNT):
                   MainWindow.AddWarning("Failed to sound bell crossing %s" % self.CROSSING_MESSAGE[Index])

               self.CrossingCheckDone[Index] = True

        # Check stops
        for Index in range(len(self.STOP_CHECKS_START)):
            if (self.StopCheckDone[Index]):
                continue
            if ((self.CurrentSpeed == 0) and 
                (MainWindow.MediaPlayer.get_position() >= self.STOP_CHECKS_START[Index]) and 
                (MainWindow.MediaPlayer.get_position() <= self.STOP_CHECKS_END[Index])):
                state.Log("Setting Stop for %s" % self.STOP_MESSAGE[Index])
                self.StopCheckDone[Index] = True
                continue

            if (MainWindow.MediaPlayer.get_position() > self.STOP_CHECKS_END[Index]):
                self.StopCheckDone[Index] = True
                MainWindow.AddWarning("Failed stop at %s" % self.STOP_MESSAGE[Index])

        # Check Zorching
        for Index in range(len(self.ZORCH_START)):
            if ((MainWindow.MediaPlayer.get_position() >= self.ZORCH_START[Index]) and
                (MainWindow.MediaPlayer.get_position() <= self.ZORCH_END[Index])):
                if (state.State.RunLevel != 0):
                    state.Log("Zorch at position %0.2f" % MainWindow.MediaPlayer.get_position())
                    sound.PlaySound.Play(sound.SoundEnum.ZORCH, False)
                    if (not self.ZorchDone[Index]):
                        MainWindow.AddWarning("Zorched %s" % ZORCH_MESSAGE[Index])
                        self.ZorchDone[Index] = True

        if (MainWindow.MediaPlayer.get_position() > STORE_POSITION) and \
            (state.State.Speed == 0):
            state.Log("Stopped correctly at store")
            MainWindow.DisplayWarnings()
            MainWindow.GoodStop();
            MainWindow.MainReset()
            return (False)

        return True

class SelectWindow(QMainWindow, mode_window.Ui_SelectWindow):
    """
    This class controls the select mode window
    """
    def __init__(self, parent=None):
        """
        Create the select window

        :param self: This class
        :param parent: Parent of this class
        """
        super().__init__(parent)
        self.setupUi(self)
        self.Mode = ModeEnum.EASY

    def show(self):
        """
        We need to show the window

        Save the mode in case we need to cancel a change
        """
        super().show()
        self.OldMode = self.Mode

    def SelectHelpButtonClicked(self):
        """
        Help button pressed
        """
        webbrowser.open("help.pdf")

    def SelectCancelButtonClicked(self):
        """
        Cancel button pressed
        """
        self.SetMode(self.OldMode)
        self.hide()

    def SelectApplyButtonClicked(self):
        """
        Apply button pressed
        """
        self.hide()

    def closeEvent(self, event):
        """
        Window closed so restore old mode
        """
        self.setMode(self.OldMode)

    def GetMode(self):
        """
        Return the mode we currently have selected

        :returns: Mode
        """
        if (self.EasyModeRadioButton.isChecked()):
            return (ModeEnum.EASY)
        elif (self.StartStopModeRadioButton.isChecked()):
            return (ModeEnum.START_STOP)
        elif (self.FullModeRadioButton.isChecked()):
            return (ModeEnum.FULL)
        else:
            print("INTERNAL ERROR: No mode checked")
            sys.exit(8)

    def SetMode(self, Mode):
        """
        Set the mode to the given mode

        :param Mode: Mode to set
        """
        self.Mode = Mode
        self.EasyModeRadioButton.setChecked(Mode == ModeEnum.EASY)
        self.StartStopModeRadioButton.setChecked(Mode == ModeEnum.START_STOP)
        self.FullModeRadioButton.setChecked(Mode == ModeEnum.FULL)

class BrakeGraphics():
    """
    Handle the drawing and clicking of the brake controller.
    """
    def __init__(self, MainWindow):
        """
        Setup controller window

        :param MainWindow: Top level window

        """
        global ShowButtons              # If set, show the buttons

        # Show or hide the buttons
        MainWindow.ButtonLayoutW1.setVisible(ShowButtons)
        MainWindow.ButtonLayoutW2.setVisible(ShowButtons)

        # 
        # These numbers came from trial and error with the gui app
        #
        MARGIN = 5                      # Margin for top/bottom of brake
        BRAKE_X_OFFSET = 80             # Move the brake controller over this amount
        BRAKE_HANDLE_X_OFFSET=129       # Move brake handle over this much
        BRAKE_HANDLE_Y_OFFSET=47        # Move handle up this much
        self.BRAKE_ANGLES=[152, 121, 57, 20]    # Angles for each brake position
        # Information about each brake position
        self.BRAKE_STATE = [state.BrakeEnum.RELEASE, state.BrakeEnum.LAP, state.BrakeEnum.APPLY, state.BrakeEnum.EMERGENCY]
        self.BRAKE_MAP = {}
        for Index in range(len(self.BRAKE_ANGLES)):
            self.BRAKE_MAP[self.BRAKE_STATE[Index]] = self.BRAKE_ANGLES[Index]

        Height = MainWindow.BrakeGraphicsView.height()
        Width = MainWindow.BrakeGraphicsView.width()
        self.BrakeControlScene = QGraphicsScene(0, 0, Width-MARGIN, Height-MARGIN)
        BrakeBackgroundImage = QPixmap(os.path.join("image", "brake-controller.png"))
        BrakeBackgroundImageScaled = BrakeBackgroundImage.scaledToHeight(Height - 2 * MARGIN)
        BrakeBackgroundItem = self.BrakeControlScene.addPixmap(BrakeBackgroundImageScaled)
        BrakeBackgroundItem.setPos(BRAKE_X_OFFSET, 0)

        BrakeHandle = QPixmap(os.path.join("image", "brake-handle.png"))
        self.BrakeHandleItem = self.BrakeControlScene.addPixmap(BrakeHandle)

        # Because end of hande is rounded, we need to move it a little based on height alone
        self.BrakeHandleItem.setPos(BRAKE_HANDLE_X_OFFSET, BRAKE_HANDLE_Y_OFFSET)
        self.BrakeHandleItem.setTransformOriginPoint(2, 6)
        self.BrakeHandleRotation = 0
        self.BrakeHandleItem.setRotation(0)
        self.MoveBrakeLever(state.BrakeEnum.LAP)

        self.MainWindow = MainWindow
        MainWindow.BrakeGraphicsView.mousePressEvent = self.MouseClick
        MainWindow.BrakeGraphicsView.setScene(self.BrakeControlScene)
        MainWindow.BrakeGraphicsView.show()

    def MouseClick(self, Event):
        """
        Handle a mouse click in the brake controller graphics box

        :param Event: Mouse click event
        """
        CENTER_X = 129  # Center of the image
        CENTER_Y = 53   # Center of the Y image
        x = Event.x()
        y = Event.y()
        ClosestDelta = 9999

        for Index in range(len(self.BRAKE_STATE)):
            Angle = math.degrees(math.atan2(y-CENTER_Y, x-CENTER_X))
            if (abs(Angle-self.BRAKE_ANGLES[Index]) < ClosestDelta):
                BrakeLever = self.BRAKE_STATE[Index]
                ClosestDelta = abs(Angle-self.BRAKE_ANGLES[Index])

        self.MoveBrakeLever(BrakeLever)
        self.MainWindow.BrakeUi.SetBrake(BrakeLever)

    def MoveBrakeLever(self, State):
        """ Move the brake lever to the given location

        :param State: State of the brake lever
        """
        self.BrakeHandleItem.setRotation(self.BRAKE_MAP[State])


class Window(QMainWindow, sim_ui4.Ui_MainWindow):
    """
    Main window in which everything happens
    """
    def __init__(self, parent=None):
        """
        Create the main window

        :param self: This class
        :param parent: Parent of this class
        """
        super().__init__(parent)
        self.setupUi(self)
        state.State.Reset()

        self.BrakeApply.clicked.connect(self.BrakeApplyClicked)
        self.BrakeRelease.clicked.connect(self.BrakeReleaseClicked)
        self.BrakeLap.clicked.connect(self.BrakeLapClicked)
        self.BrakeEmergency.clicked.connect(self.BrakeEmergencyClicked)

        ##++self.DingProc = None

        #-----------------------------------------------------------
        # Setup video player
        #-----------------------------------------------------------
        self.instance = vlc.Instance()  # Create an instance of the player
        self.MediaPlayer = self.instance.media_player_new()
        self.MediaPlayer.audio_output_device_set("adummy", "/dev/null")
        self.MediaPlayer.audio_set_mute(True)

        if platform.system() == "Linux": # for Linux using the X Server
            self.MediaPlayer.set_xwindow(int(self.VideoFrame.winId()))
        elif platform.system() == "Windows": # for Windows
            self.MediaPlayer.set_hwnd(int(self.VideoFrame.winId()))
        elif platform.system() == "Darwin": # for MacOS
            self.MediaPlayer.set_nsobject(int(self.VideoFrame.winId()))

        self.VideoFrame.setStyleSheet("""
            background-image: url(%s/background.png) 0 0 0 0 stretch stretch;
            background-repeat: no-repeat;
            background-position: center;
            """ % os.path.join(DIR, "image"))

        self.BrakeUi = brake_ui.BrakeUi(self)

        self.BrakeView.setScene(self.BrakeUi.Scene)
        self.BrakeView.show()

        self.BrakeGUI = BrakeGraphics(self)
        self.ControllerGraphics = controller.ControllerGraphics(self)
        self.ControllerButtons = controller.ControllerButtons(self)

        self.SelectWindow = SelectWindow()
        self.SelectWindow.SelectApplyButton.clicked.connect(self.SelectApplyButtonClicked)
        self.SelectWindow.SelectCancelButton.clicked.connect(self.SelectCancelButtonClicked)
        self.Timer = QtCore.QTimer(self)
        self.Timer.setInterval(100)
        self.Timer.timeout.connect(self.Tick)
        self.Timer.start()
        self.MainReset()
        self.setWindowTitle("SCRM Trolley")

    def PlayVideo(self):
        """
        We were asked to play a video
        """
        print("### Video %s" % self.SelectWindow.GetMode())
        ModeType = self.SelectWindow.GetMode()
        if (ModeType == ModeEnum.EASY):
            video_player.play_video("video/easy.mp4")
        elif (ModeType == ModeEnum.START_STOP):
            video_player.play_video("video/start_stop.mp4")
        elif (ModeType == ModeEnum.FULL):
            video_player.play_video("video/full.mp4")

    def HelpClicked(self):
        """
        Help button pressed
        """
        webbrowser.open("help.pdf")

    def DeadmanClicked(self, Checked):
        """
        Deadman clicked

        :param Checked: Is it checked
        """
        state.State.Deadman = Checked
        self.DeadmanButton.setChecked(Checked)
        self.DeadmanGraphic.setChecked(Checked)

    def SelectApplyButtonClicked(self):
        """
        Apply button in select mode window clicked
        """
        self.SelectWindow.SelectApplyButtonClicked()
        self.MainReset()

    def SelectCancelButtonClicked(self):
        """
        Cancel button in select mode window clicked
        """
        self.SelectWindow.SelectCancelButtonClicked()
        self.MainReset()

    def Tick(self):
        """ 
        The clock has ticked.  Take action
        """
        # Update the speed and acceleration
        self.BrakeUi.UpdateBrake(self)
        self.Mode.ModeUpdate(self)
        Continue = self.Mode.RulesCheck(self)
        if (not Continue):
            return

        # Tell the video to change the state
        self.MediaPlayer.set_rate(state.State.Speed)

        state.Log("ClickClackTime %f" % self.ClickClackTime)
        if (self.ClickClackTime == 0):
            if (state.State.Speed > 0.0):
                state.Log("ClickClackPlay")
                sound.PlaySound.Play(sound.SoundEnum.CLICK_CLACK, False)
                self.ClickClackTime = time.monotonic() + CLICK_CLACK_NORMAL_INTERVAL / state.State.Speed
                state.Log("ClickClackTime %f" % self.ClickClackTime)
        else:
            if (time.monotonic() > self.ClickClackTime):
                if (state.State.Speed > 0):
                    state.Log("ClickClackPlay")
                    sound.PlaySound.Play(sound.SoundEnum.CLICK_CLACK, False)
                    self.ClickClackTime = time.monotonic() + CLICK_CLACK_NORMAL_INTERVAL / state.State.Speed
                else:   # Not moving, shutdown click/clack
                    self.ClickClackTime = 0.0
                state.Log("ClickClackTime %f" % self.ClickClackTime)

        # Are we too close to the end to do anything
        if (self.MediaPlayer.get_position() < END_OF_VIDEO):
            # Check to see if we are not playing and moving
            if ((self.MediaPlayer.get_state() != vlc.State.Playing) and \
                        (state.State.Speed > 0.0)):
                state.Log("MediaPlayer.play()")
                Result = self.MediaPlayer.play()

            elif ((self.MediaPlayer.get_state() == vlc.State.Playing) and \
                        (state.State.Speed <= 0.0)):
                state.Log("MediaPlayer.pause()")
                Result = self.MediaPlayer.pause()

        StatusMsg = "Run %d Position %.2f Speed %.2f Acceleration %.3f Brake Acc. %.3f Brake:%2.2f Res:%2.2f Extend: %f" % \
             (state.State.RunLevel, self.MediaPlayer.get_position(), state.State.Speed, 
             state.State.Acceleration, state.State.BrakeAcceleration, self.BrakeUi.RedPressure, self.BrakeUi.BlackPressure, self.BrakeUi.Extend)
        state.Log(StatusMsg)
        self.StatusLabel.setText(StatusMsg)

        if (self.MediaPlayer.get_position() > END_OF_VIDEO):
            state.Log("MediaPlayer.pause()")
            Result = self.MediaPlayer.pause()
            self.AddWarning("Failed to stop at store")
            self.DisplayWarnings()
            self.NoticeDone()
            self.MainReset()

    def Ding(self):
        """ 
        Ring the bell
        """
        if (not sound.PlaySound.Running[sound.SoundEnum.BELL1.value]):
            sound.PlaySound.Play(sound.SoundEnum.BELL1, False)
        elif (not sound.PlaySound.Running[sound.SoundEnum.BELL2.value]):
            sound.PlaySound.Play(sound.SoundEnum.BELL2, False)
        else:
            sound.PlaySound.Play(sound.SoundEnum.BELL3, False)

        ThisDingTime = time.time()
        DingPosition = self.MediaPlayer.get_position()
        self.DingTime.append(ThisDingTime)
        self.DingPosition.append(DingPosition)
        state.Log("DING Time: %f Pos: %f" % (ThisDingTime, DingPosition))

    def ChangeModeClicked(self):
        """
        Mode change button clicked
        """
        self.MainReset()
        self.SelectWindow.show()

    def SetSimulatorMode(self):
        """
        We are starting out.  Setup the mode
        """
        ModeType = self.SelectWindow.GetMode()
        if (ModeType == ModeEnum.EASY):
            self.Mode = EasyMode()
        elif (ModeType == ModeEnum.START_STOP):
            self.Mode = StartStopMode()
        elif (ModeType == ModeEnum.FULL):
            self.Mode = FullMode()

        self.ModeLabel.setText(self.Mode.Name)

    def MainReset(self):
        """ 
        Reset to the starting position
        """
        self.MediaPlayer.set_position(0.0)
        self.SetSimulatorMode()
        state.State.Reset()
        self.Mode.ModeReset()
        self.WarningList = []
        self.WarningLabel.setText("")

        self.DeadmanButton.setChecked(False)
        self.DeadmanGraphic.setChecked(False)

        self.SetRun(0)
        self.SetDirection(state.DirectionEnum.NEUTRAL)

        self.Media = self.instance.media_new(VideoFile)
        self.MediaPlayer.set_media(self.Media)
        self.Media.parse()

        self.MediaPlayer.set_rate(1.0)

        self.MediaPlayer.audio_set_volume(0)
        state.Log("Reset: Pause")
        self.MediaPlayer.pause()
        self.BrakeGUI.MoveBrakeLever(state.BrakeEnum.APPLY)
        self.BrakeUi.SetBrake(state.BrakeEnum.APPLY)
        self.BrakeUi.BrakeReset()

        self.DingTime = []
        self.DingPosition = []
        self.ClickClackTime = 0.0

    def BrakeApplyClicked(self): 
        """
        The Brake:Apply button clicked
        """
        self.BrakeUi.BrakeApplyClicked()

    def BrakeReleaseClicked(self):
        """
        The Brake:Release button clicked
        """
        self.BrakeUi.BrakeReleaseClicked()

    def BrakeLapClicked(self):
        """
        The Brake:Lap button clicked
        """
        self.BrakeUi.BrakeLapClicked()

    def BrakeEmergencyClicked(self):
        """
        The Brake:Emergency button clicked
        """
        self.BrakeUi.BrakeEmergencyClicked()

    def closeEvent(self, event):
        sys.exit(0)

    ## Not used @@
    def OverspeedMessage(self):
        """
        You tried to do run4 or above.  You can't do this.
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Too Fast")
        msg.setInformativeText("The track you are on is limited to 15MPH.\nDo not advance the controller past Run-3\n\nStart over.")
        msg.setWindowTitle("Error")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.buttonClicked.connect(lambda i: print(f"Button pressed is: {i.text()}"))
        msg.exec_()
        self.MainReset()

    def AddWarning(self, Message):
        """
        Something went wrong, but we are just going to tell the user about it.

        :param Message: Message to add to the warnings
        """
        state.Log("Warning %s" % Message)
        self.WarningList.append(Message)

        if (len(self.WarningList) < 5):
            WarningMessage = '\n\n'.join(self.WarningList)
        else:
            WarningMessage = '\n\n'.join(self.WarningList[-5:])
        self.WarningLabel.setText(WarningMessage)

    def DisplayWarnings(self):
        """
        Display a message indicating what warning occurred
        """
        if (len(self.WarningList) == 0):
            return
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>You made some mistakes</B></H1>")
        MessageBox.setWindowTitle("Warnings")
        Message = "Warning:\n"
        for Index in range(len(self.WarningList)):
            Message += "%2d: %s\n" % (Index+1, self.WarningList[Index])
        MessageBox.setInformativeText(Message)
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("Continue")
        ReturnValue = MessageBox.exec()

    def ErrorDeadman(self):
        """
        You tried to run without setting the deadman
        """
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Deadman not engaged</B></H1>")
        MessageBox.setWindowTitle("Deadman not engaged")
        MessageBox.setInformativeText("""The deadman must be pressed (or clicked) 
at all times while the trolley is moving.   

If it is released the trolley performs an emergency stop
""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("Restart")
        ReturnValue = MessageBox.exec()

    def SetDirection(self, Direction):
        """
        Change the direction we are going
        """
        if ((state.State.RunLevel != 0) and (Direction != state.DirectionEnum.FORWARD)):
            state.Log("MediaPlayer: Pause")
            self.MediaPlayer.pause()
            self.ErrorReverserMoved()
            Direction = state.DirectionEnum.FORWARD
            state.Log("MediaPlayer: Play")
            self.MediaPlayer.play()
            
        self.ControllerGraphics.SetReverse(Direction)
        self.ControllerButtons.SetReverse(Direction)

        state.State.Direction = Direction

    def NoticeDone(self):
        """
        Display the information message that you completed the course
        """
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Information)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Congratulations: The run is complete</B></H1>")
        MessageBox.setWindowTitle("Finished")
        MessageBox.setInformativeText("""You've made it around the loop.

Press "Restart" to start another run""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("Restart")
        ReturnValue = MessageBox.exec()

    def GoodStop(self):
        """
        The player stopped at the correct position at the store
        """
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Information)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Congratulations: The run is complete</B></H1>")
        MessageBox.setWindowTitle("Finished")
        MessageBox.setInformativeText("""You've made it around the loop.

And you stopped back at the store
Press "Restart" to start another run""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("Restart")
        ReturnValue = MessageBox.exec()

    def ErrorStart(self):
        """ 
        Handle all the stuff you need at the beginning of an error message
        """
        state.Log("MediaPlayer.pause()")
        Result = self.MediaPlayer.pause()
        state.State.Acceleration = 0
        state.State.Speed = 0
        state.Log("Speed %f" % state.State.Speed)

    def ErrorMessageRun4(self):
        """
        Display the error message indicating that we exceeded the run limit
        """
        self.ErrorStart()
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Speed limit exceeded</B></H1>")
        MessageBox.setWindowTitle("Speed Limit Exceeded")
        MessageBox.setInformativeText("""This is not a high speed trolley.
The loop line speed limit is 15mph.
It is not possible to use the controller at settings "Run-4" or above

Please try again, only slower""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("Restart")
        ReturnValue = MessageBox.exec()

    def ErrorRunTooLong(self):
        """
        Display the error message when we stay in a run_x too long
        """
        self.ErrorStart()
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Overheated Resisters</B></H1>")
        MessageBox.setWindowTitle("Overheated Resisters")
        MessageBox.setInformativeText("""You stayed in Run-%d too long.

The resister pack overheated.  

You can only stay in Run-%d for %d seconds.
""" % (state.State.RunLevel, state.State.RunLevel, MAX_RUN_TIME))
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("OK")
        ReturnValue = MessageBox.exec()

    def ErrorRunTooLongDown(self):
        """
        Display the error message when we stay in a run_x too long on the way down
        """
        self.ErrorStart()
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Electrical Overload</B></H1>")
        MessageBox.setWindowTitle("Electrical Overload")
        MessageBox.setInformativeText("""Going from Run-x to idle should be done
as quickly as possible.   Failure to do so causes the motors to act as
generators and create feedback which can damage the trolley.

So slam that controller back to idle and avoid this problem.
""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("OK")
        ReturnValue = MessageBox.exec()

    def ErrorNoForward(self):
        """
        Display the error message we should be in forward before starting
        """
        self.ErrorStart()
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Reverser not set</B></H1>")
        MessageBox.setWindowTitle("Reverser not set")
        MessageBox.setInformativeText("""You must select "Forward" on the reverser
before moving.

Controller has been reset to Run-0

Please set direction and try again.""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("OK")
        ReturnValue = MessageBox.exec()

    def ErrorMoveWithBrakesOn(self):
        """
        Display the error message indicating that you can't run with the brakes on
        """
        self.ErrorStart()

        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Attempt to move with brakes set</B></H1>")
        MessageBox.setWindowTitle("Move with brakes on")
        MessageBox.setInformativeText("""The brakes and the motor should never be on at the same time.

Set the controller to "Run-0" before applying the brakes.
Release the brakes before entering "Run-1".

Simulation will now reset.
""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("OK")
        ReturnValue = MessageBox.exec()

    def ErrorReverserMoved(self):
        """
        Display the error message indicating the reverser moved while car in motion
        """
        self.ErrorStart()

        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Reverser moved while car in motion</B></H1>")
        MessageBox.setWindowTitle("Reverser move while car in motion")
        MessageBox.setInformativeText("""You cannot change the reverser while the trolley is in motion.

Reverser has been returned to "Forward"

Press OK to continue""")
        MessageBox.setStandardButtons(QMessageBox.Ok)
        ButtonOk = MessageBox.button(QMessageBox.Ok)
        ButtonOk.setText("OK")
        ReturnValue = MessageBox.exec()

    def SetRun(self, Level):
        """
        Used to change the run level.

        :param: Level the level to use

        :returns: True if we should continue our journey
        """
        state.Log("SetRun %d" % Level)
        self.ControllerGraphics.SetControllerRun(Level)
        self.ControllerButtons.SetControllerRun(Level)

        if (state.State.RunLevel != Level):
            if (MAX_SPEED[Level] < 0):
                self.ErrorMessageRun4()
                self.MainReset()
                return False

        KeepGoing = self.Mode.ModeSetRun(self, Level)
        
        if (not KeepGoing):
            state.Log("MediaPlayer: Pause")
            Result = self.MediaPlayer.pause()
            state.State.Acceleration = 0
            state.State.Speed = 0
            state.Log("Speed %f" % state.State.Speed)
            return False

        if (self.MediaPlayer.get_state() != vlc.State.Playing):
            state.Log("MediaPlayer: Play")
            Result = self.MediaPlayer.play()

        state.State.RunLevel = Level
        return (True)

    def keyPressEvent(self, event):
        """
        Handle key presses.

        Keys:
            X -- Move brake to lap position -- make a 10 pound set
            M -- Mark position
            0-8 -- Move the controller to position indicate by the run level.
                (Do not actually set the run level)
        """
        if (event.key() == ord('X')):
            self.BrakeUi.BrakeLapClicked()
            self.BrakeUi.RedPressure += 10.0
            if (self.BrakeUi.RedPressure > brake_ui.MAX_RED_PRESSURE):
                self.BrakeUi.RedPressure = brake_ui.MAX_RED_PRESSURE
            print("DEBUG: 10 pound set %f" % self.BrakeUi.RedPressure)
            state.Log("DEBUG: 10 pound set %f" % self.BrakeUi.RedPressure)
        elif (event.key() == ord('M')):
            print("Mark Position %.2f" % self.MediaPlayer.get_position())
            state.Log("Mark Position: %.2f" % self.MediaPlayer.get_position())
        elif ((event.key() >= ord('0')) and (event.key() <= ord('8'))):
            RunLevel = event.key() - ord('0')
            print("DEBUG: Run level %d" % RunLevel)
            self.ControllerGraphics.SetControllerRun(RunLevel)

if __name__ == "__main__":
    sound.Init()

    if (len(sys.argv) != 1):
        ShowButtons = True
    else:
        ShowButtons = False

    app = QtWidgets.QApplication(sys.argv)  #pylint: disable=I1101

    state.Init()
    mainWindow = Window()
    mainWindow.showMaximized()
    state.Log("New run----------------------------------------------------------------")

    app.exec()
