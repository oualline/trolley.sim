#
# Copyright 2024 by Steve Oualline
# Licensed under the GNU Public License (GPL)
#
"""
Main GUI for the trolley simulator

TODO:
        Add replay/playback mode
"""
import contextlib
import enum
import getopt
import math
import os
import platform
import select
import pprint   #pylint: disable=W0611
import signal
import sys
import webbrowser
import pynput
import inspect
import pathlib

from PyQt6 import QtWidgets, QtCore, uic
from PyQt6.QtWidgets import ( QApplication, QDialog, QMainWindow, QMessageBox )
from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QEvent
from PyQt6.QtGui import QPixmap

import mode_window
import sim_ui4
import brake_ui
import state
import controller
import sound
import video

###########
# Gloabsl #
###########
# MainWindow, Mode, ModeId


ShowButtons = False     # If true, turn on the buttons
FullScreen = False      # Start in full screen mode

TopMargin = None        # Margins
BottomMargin = None
LeftMargin = None
RightMargin = None
AttractEnable = False   # Enable attract mode
SkipCount=1             # How many frames to skip to speed video

ATTRACT_TIMEOUT = 300000 # 5 minutes = 300,000 milliseconds
ERROR_TIMEOUT = 60*1000 # Number of seconds for timeout

VideoFile = os.path.join("video", "trolley.m4v")

if '_PYI_APPLICATION_HOME_DIR' in os.environ:
    DIR=os.environ['_PYI_APPLICATION_HOME_DIR']
    os.chdir(DIR)
else:
    # Detect the operating system
    operating_system = platform.system()
    if operating_system != "Windows":
        DIR=os.getcwd()
    else:
        DIR="."

VideoFile = os.path.join(DIR, VideoFile)
AttractVideoFile = os.path.join(DIR, "video", "attract.mp4")
if 'TEMP' in os.environ:
    IMAGE_DIR = os.path.join(os.environ['TEMP'], "trolley.sim.temp.frames")
else:
    if 'HOME' in os.environ:
        IMAGE_DIR = os.path.join(os.environ['HOME'], "trolley.sim.temp.frames")
    else:
        IMAGE_DIR = os.path.join(DIR, "trolley.sim.temp.frames")

class PointerEnum(enum.Enum):
    MOUSE = 1,
    TRACKPAD = 2,
    TOUCHSCREEN = 3

PointerType = PointerEnum.MOUSE

class ModeEnum(enum.Enum):
    EASY = 0                  # Mode is easy
    EASY_TUTORIAL = 1         # Tutorial for easy
    START_STOP = 2            # Mode is start/stop
    START_STOP_TUTORIAL = 3   # Tutorial for start/stop
    FULL = 4                  # Mode is full checking
    FULL_TUTORIAL = 5         # Tutorial is full checking

# Check if we're running on Linux
IS_LINUX = platform.system().lower() == 'linux'

# Check if we're running on macOS
IS_MAC = platform.system().lower() == 'darwin'

if IS_LINUX:
    class NamedPipeReader(QThread):
        """
        Thread class that reads coordinates from a named pipe.
        
        This thread continuously monitors a named pipe for commands
        and emits a signal when valid coordinates are received.
        """
        
        # Signal emitted when a command is read from the pipe
        CommandReceived = pyqtSignal(str)

        POLL_SECONDS = 0.2      # How often run() re-checks self.running
        
        def __init__(self, pipe_path="/tmp/command_pipe"):
            """
            Initialize the named pipe reader.
            
            Args:
                pipe_path (str): Path to the named pipe (FIFO)
            """
            super().__init__()
            self.pipe_path = pipe_path
            self.running = True
            
        def run(self):
            """
            Main thread execution method.

            Creates the named pipe and reads newline-separated commands from
            it, emitting CommandReceived for each one.

            The FIFO is opened non-blocking and polled with select() on a
            short timeout, so the loop re-checks self.running at least every
            POLL_SECONDS.  The old version sat in a blocking open() (no
            writer yet) or readline() (writer connected but idle) and never
            looked at self.running again, so stop() -> wait() hung forever.
            """
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
                state.Log(f"Cleaned up named pipe: {self.pipe_path}")
            try:
                os.mkfifo(self.pipe_path)
            except OSError as e:
                state.Log(f"Named pipe error: cannot create {self.pipe_path}: {e}")
                return
            state.Log(f"Listening on named pipe: {self.pipe_path}")
            state.Log(f"Send commands with: echo 'Command' > {self.pipe_path}")

            Fd = None
            Buffer = b""
            try:
                while self.running:
                    if Fd is None:
                        # Non-blocking open of a FIFO's read end succeeds
                        # immediately, even with no writer.
                        Fd = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)

                    Ready, _, _ = select.select([Fd], [], [], self.POLL_SECONDS)
                    if not Ready:
                        continue

                    Data = os.read(Fd, 4096)
                    if Data:
                        Buffer += Data
                        while b"\n" in Buffer:
                            Line, Buffer = Buffer.split(b"\n", 1)
                            self._emit(Line)
                        continue

                    # EOF: the last writer closed.  Deliver any final line
                    # that had no newline (as readline() used to), then
                    # reopen -- a FIFO whose writers have all gone away
                    # stays "readable" (EOF) forever and would spin select().
                    if Buffer:
                        self._emit(Buffer)
                        Buffer = b""
                    os.close(Fd)
                    Fd = None
            except OSError as e:
                state.Log(f"Named pipe error: {e}")
            finally:
                if Fd is not None:
                    os.close(Fd)

        def _emit(self, RawLine):
            """Decode one line and emit it if it isn't blank."""
            Line = RawLine.decode("utf-8", errors="replace").strip()
            if Line:
                self.CommandReceived.emit(Line)

        def stop(self):
            """
            Stop the thread and wait for it to finish.

            run() notices self.running within POLL_SECONDS.  The wait is
            bounded anyway, so a surprise can never hang shutdown.
            """
            self.running = False
            if not self.wait(int(self.POLL_SECONDS * 1000) + 2000):
                state.Log("Named pipe reader did not stop in time")

    class CommandPipe():
        def __init__(self):
            """ Initialize the pipe reader and start the listener thread"""

            # Initialize and start the named pipe reader thread
            self.pipe_reader = NamedPipeReader()
            # Emitted on the reader thread; handled on the GUI thread.
            self.pipe_reader.CommandReceived.connect(
                self.HandlePipeCommand, Qt.ConnectionType.QueuedConnection)
            self.pipe_reader.start()

        def HandlePipeCommand(self, Command):
            """
            Handle coordinates received from the named pipe.
            
            This method is called when the pipe reader thread receives valid commands.
            
            Args:
                Command: command received
            """
            global MainWindow

            state.Log(f"Processing pipe command: {Command}")

            # The hardware panel is a person at the controls too: restart
            # the attract-mode idle timer, or end the attract video.
            MainWindow.NoteUserActivity()

            if (Command == "Run0"):
                MainWindow.SetRun(0)
            elif (Command == "Run1"):
                MainWindow.SetRun(1)
            elif (Command == "Run2"):
                MainWindow.SetRun(2)
            elif (Command == "Run3"):
                MainWindow.SetRun(3)
            elif (Command == "Run4"):
                MainWindow.SetRun(4)
            elif (Command == "Run5"):
                MainWindow.SetRun(5)
            elif (Command == "Run6"):
                MainWindow.SetRun(6)
            elif (Command == "Run7"):
                MainWindow.SetRun(7)
            elif (Command == "Run8"):
                MainWindow.SetRun(8)
            elif (Command == "Forward"):
                MainWindow.SetDirection(state.DirectionEnum.FORWARD)
            elif (Command == "Reverse"):
                MainWindow.SetDirection(state.DirectionEnum.REVERSE)
            elif (Command == "Neutral"):
                MainWindow.SetDirection(state.DirectionEnum.NEUTRAL)
            elif (Command == "Deadman"):
                MainWindow.DeadmanClicked(not state.State.Deadman)
            elif (Command == "Apply"):
                self.SetBrake(state.BrakeEnum.APPLY)
            elif (Command == "Lap"):
                self.SetBrake(state.BrakeEnum.LAP)
            elif (Command == "Release"):
                self.SetBrake(state.BrakeEnum.RELEASE)
            elif (Command == "Emergency"):
                self.SetBrake(state.BrakeEnum.EMERGENCY)
            elif (Command == "Bell"):
                MainWindow.Ding()
            else:
                print("Unknown pipe command %s" % Command)

        def SetBrake(self, Position):
            """
            Brake valve command from the panel.  Does the same as clicking
            the on-screen brake handle (BrakeGraphics.MouseClick): move the
            drawn handle to match, then set the valve.

            :param Position: state.BrakeEnum valve position
            """
            MainWindow.BrakeGraphics.MoveBrakeLever(Position)
            MainWindow.BrakeUi.SetBrake(Position)

        def shutDown(self):
            """
            Shutdown the input handler
            
            Ensures the named pipe reader thread is properly stopped when the window closes.
            
            Args:
                event: QCloseEvent
            """
            
            # Stop the pipe reader thread
            self.pipe_reader.stop()
            
            # Clean up the named pipe file
            try:
                if os.path.exists(self.pipe_reader.pipe_path):
                    os.unlink(self.pipe_reader.pipe_path)
            except OSError as e:
                print(f"Warning: Could not remove pipe file: {e}")
            
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
MAX_LEVEL = 8   # Maximum run level

FRICTION=0.99995   # Friction is 0.005% of the current speed

MAX_RUN_TIME=10 # Longest we can run in anything but full series or full parallel
MAX_DOWN_TIME=1 # Longest we can stay in a run level going down

# Signal section
MAX_SIGNAL_START=10     # You must move within 10 seconds of issuing start signal
MAX_START_BETWEEN=2     # The ding ding that starts must occur within 2 seconds
STOP_TIME_CHECK=10      # Stop bell must come within 10 seconds of stopping
STOP_SIGNAL_TIME=2      # Stop bell must be 2+ seconds from any other bell

STORE_POSITION=0.95     # Beginning of the store
STORE_HELP=0.92         # Position at which we display help for the easy mode store
END_OF_VIDEO=0.98       # After this there is no more video

CLICK_CLACK_DISTANCE = 0.03             # Distance between click/clack

CENTRAL_BELL_START = 0.36       # Location to start sounding central bell
CENTRAL_BELL_STOP = 0.41        # Location to stop sounding central bell

class TrackEvent():
    """
    Holds information about an event that will occur on the track
    """
    def __init__(self, Where, Action):
        """
        When the car passes "Where" perform "Action"

        Args:
            Where -- Where the event occurs
            Action -- What to do when it occurs
        """
        self.Where = Where
        self.Action = Action
        self.Done = False

    def Check(self, Where):
        """ 
        Check to see if we need to perform an action

        Args:
            Where -- Where we are
        """
        if (self.Done):
            return
        if (Where >= self.Where):
            if (self.Action is None):
                print("Internal error -- Abort", Where)
                sys.exit(8)
            self.Action()
            self.Done = True

GLOBAL_EVENTS = [
    TrackEvent(CENTRAL_BELL_START, lambda: sound.GlobalSound.Play(sound.SoundEnum.CENTRAL_BELL, True)),
    TrackEvent(CENTRAL_BELL_STOP,  lambda: sound.GlobalSound.Stop(sound.SoundEnum.CENTRAL_BELL, False)),
]

def ComputeAcceleration(Level):
    """
    Given a run level, compute the acceleration for that run level

    :param Level: The run level
    :returns: Acceleration
    """
    global MAX_SPEED
    global SPEED_TIME

    if (Level == 0):
        return (MAX_SPEED[Level] / SPEED_TIME)
    return((MAX_SPEED[Level] - MAX_SPEED[Level-1]) / SPEED_TIME)

def CenterOnMainWindow(Widget):
    """
    Position a not-yet-shown top-level widget over MainWindow: centered
    left-to-right, top-aligned vertically.

    The .ui files for these popups carry whatever x/y position was last
    saved by Designer, which is why they were popping up in the wrong
    place -- that saved position has nothing to do with where MainWindow
    actually ends up on screen at runtime.  This throws that position away
    and repositions the widget relative to MainWindow instead (or the
    primary screen, if MainWindow doesn't exist yet): horizontally
    centered over it, but flush with its top edge rather than vertically
    centered.

    :param Widget: The top-level widget to position (not yet shown)
    """
    global MainWindow

    if MainWindow is not None:
        Geometry = MainWindow.frameGeometry()
    else:
        Geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()

    WidgetGeometry = Widget.frameGeometry()
    NewX = Geometry.center().x() - WidgetGeometry.width() // 2
    NewY = Geometry.top()
    Widget.move(NewX, NewY)

def ShowModalTutorial(File, Window=None):
    """
    Display a modeal tutorial popup, loaded directly from
    File via uic.loadUi() (no compiled/generated .py needed).

    The popup's windowModality is ApplicationModal (set in the .ui file
    itself), so clicks outside the popup are ignored -- it stays up until
    the user clicks the "Click Here" button (or Cancel, if present).

    QMainWindow has no exec(), so this blocks the caller on a local
    QEventLoop instead, the same technique used by ShowErrorMessage()
    above.  The "Click Here" button's clicked() signal is already wired to
    TutorialWindow.close() by the .ui file itself; it's also connected to
    loop.quit() here so our wait ends the moment the button is clicked.

    If the .ui file has a "cancelButton" and a Window (the Mode object
    that's asking for this tutorial step -- NOT the stale module-global
    Mode, which during __init__ still points at whatever mode was active
    *before* this one) is supplied, Cancel is wired to close this window,
    unblock the wait, and notify Window.TutorialCancel() so it can update
    its own state. destroyed->loop.quit() is a safety net so we can never
    get stuck forever if the window goes away some other way.

    :param File: The file containing the tutorial
    :param Window: The Mode object requesting this tutorial (for Cancel);
                    omit for tutorials that don't need Cancel handling.
    """
    state.Log(f"ShowModalTutorial({File})")
    global MainWindow

    TutorialWindow = QMainWindow(MainWindow)
    uic.loadUi(os.path.join(DIR, File), TutorialWindow)

    CenterOnMainWindow(TutorialWindow)

    loop = QtCore.QEventLoop()
    TutorialWindow.ClickHere.clicked.connect(loop.quit)
    TutorialWindow.destroyed.connect(loop.quit)

    if (Window is not None) and hasattr(TutorialWindow, "cancelButton"):
        TutorialWindow.cancelButton.clicked.connect(TutorialWindow.close)
        TutorialWindow.cancelButton.clicked.connect(loop.quit)
        TutorialWindow.cancelButton.clicked.connect(Window.TutorialCancel)

    TutorialWindow.show()
    TutorialWindow.raise_()
    TutorialWindow.activateWindow()
    # Freeze the simulation while this modal tutorial blocks.  See
    # Window.SimSuspended() -- otherwise Tick() keeps running inside our
    # nested loop and can resume the video PauseTutorial() just paused.
    if MainWindow is not None:
        Suspend = MainWindow.SimSuspended()
    else:
        Suspend = contextlib.nullcontext()
    with Suspend:
        loop.exec()

    return TutorialWindow

def PauseTutorial(File, Window=None):
    """
    Display a tutorial that pauses the video to display it.

    :param File: File contining the ui
    :param Window: The Mode object requesting this tutorial (for Cancel);
                    omit for tutorials that don't need Cancel handling.

    Uses the module-global MainWindow (set in Window.__init__) rather than
    taking it as a parameter.
    """
    global MainWindow

    MainWindow.Video.Pause()
    ShowModalTutorial(File, Window)
    MainWindow.Video.Resume()



# Event list / easy mode
#       Central bell start
#       Central bell stop

# Event list / full mode
#       Stop at broadway
#       Broadway crossing
#       Central crossing
#       Zorch1
#       Broadway south
#       Zorch2
#       Thomas stop
#       Store stop

# class EventCheck:   __init__(List)
#       EventReset
#       CheckEvent(MainWindow)
def ShowTutorial(File, Window):
    """
    Show a non-modal tutorial

    Args:
        File -- The file to show
        Window -- Window which is creating us

    Returns
       Tutorial dialog we created
    """
    state.Log(f"ShowTutorial({File})")
    Tutorial = uic.loadUi(os.path.join(DIR, File))
    Tutorial.setWindowFlags(
        Tutorial.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
    )

    CenterOnMainWindow(Tutorial)

    Tutorial.cancelButton.clicked.connect(Window.TutorialCancel)
    Tutorial.show()
    Tutorial.raise_()

    return (Tutorial)

class EasyMode:
    Name = "Easy"
    """
    Class that defines the easy mode of operation.

    In this mode you can press Run0, Run1, Run2. 
    Run0 will brake the trolley until it stops.
    Run1 will accelerate to the Run1 speed.  If you are faster that that it brakes.
    Run2 will accelerate to the Run2 speed.  If you are faster that that we have an internal error
    """
    class TutorialEnum(enum.Enum):
        EASY_NONE = 0
        EASY_1 = 1
        EASY_2 = 2
        EASY_3 = 3
        EASY_STORE = 4  # Remind user to stop at store

    def __init__(self, Tutorial=False):                 # EasyMode
        """
        Create the mode

        """
        global MainWindow

        # The deacceleration speed
        self.SlowDownAcceleration = -0.5
        self.Events = GLOBAL_EVENTS
        self.MaxSpeed = 0
        self.Tutorial = Tutorial
        if (Tutorial):
            self.TutorialStep = self.TutorialEnum.EASY_1
            match (PointerType):
                case PointerEnum.MOUSE:
                    File= "easy.1.mouse.ui"
                case PointerEnum.TRACKPAD:
                    File= "easy.1.trackpad.ui"
                case PointerEnum.TOUCHSCREEN:
                    File= "easy.1.touchscreen.ui"
                case _:
                    print("ERROR: Impossible pointer type ", PointerType)
                    sys.exit(8)
            ShowModalTutorial(File, self)
            if self.TutorialStep != self.TutorialEnum.EASY_NONE:
                self.Tutorial = ShowTutorial('easy.2.ui', self)
                self.TutorialStep = self.TutorialEnum.EASY_2
        else:
            self.TutorialStep = self.TutorialEnum.EASY_NONE

    def SetBrake(self, Position):    # Easy mode
        """
        Set the brake mode

        Parameters
            :arg Position: Position of the brake handle
        """
        pass

    def ModeSetDirection(self, Direction):  # Easy Mode
        """
        Set the direction of the reverser

        Parameters
            :arg Direction: The direction of the reverser
        """
        pass

    def TutorialCancel(self):
        """
        Called when tutorial's cancel button is clicked

        Closes out the tutorial
        """
        self.TutorialStep = self.TutorialEnum.EASY_NONE
        if hasattr(getattr(self, "Tutorial", None), "close"):
            self.Tutorial.close()
        self.Tutorial = None

    def DeadmanClicked(self, Checked):
        """
        Called when the deadman is changed

        :param Checked: Is it checked
        """
        if (self.TutorialStep == self.TutorialEnum.EASY_2):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('easy.3.ui', self)
            self.TutorialStep = self.TutorialEnum.EASY_3

    """
    Mode where you move by setting Run-1 and Run-2.  
    Moving the controller back will slow you down.
    """
    def ModeSetRun(self, RunLevel):         # Easymode
        """
        Set the run level

        :param RunLevel: RunLevel to set
        """
        if (self.TutorialStep == self.TutorialEnum.EASY_3):
            self.Tutorial.close()
            del self.Tutorial
            self.TutorialStep = self.TutorialEnum.EASY_STORE

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

    def ModeTick(self):                   # EasyMode
        """
        Return the updated speed
        """
        global MainWindow

        if (MainWindow.Video.GetPosition() > STORE_HELP) and (self.TutorialStep == self.TutorialEnum.EASY_STORE):
            PauseTutorial('easy.store.ui', self)
            self.TutorialStep = self.TutorialEnum.EASY_NONE

        if (not state.State.Deadman) and ((state.State.Speed != 0) or (state.State.RunLevel != 0)):
            state.Log("Deadman is not set")
            state.State.Speed = 0.0
            MainWindow.Video.SetRate(0.0)
            MainWindow.ErrorDeadman()
            MainWindow.MainReset()
            return

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
            # Are we decellerating
            elif (state.State.Speed < self.MaxSpeed):
                state.State.Acceleration = 0

    def RulesCheck(self):   # EasyMode
        """
        Check to see if we violated any of the rules

        :returns: True if it's safe to contine
        """
        if (not state.State.Deadman) and ((state.State.Speed != 0) or (state.State.RunLevel != 0)):
            state.State.Speed = 0.0
            MainWindow.Video.SetRate(0.0)
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
    TUTORIAL_RUN_TIME = 5   # Run it for 5 seconds before turn off

    class TutorialEnum(enum.Enum):
        START_NONE = 0
        START_1 = 1
        START_2 = 2
        START_2b = 20
        START_3 = 3
        START_4 = 4
        START_5 = 5
        START_5B = 50
        START_5C = 51
        START_6 = 6
        START_6W = 61
        START_7 = 7
        START_8 = 8

    def __init__(self, Tutorial=False):     # Start/stop mode
        """
        Create the mode
        """
        self.Events = GLOBAL_EVENTS
        self.MaxSpeed = 0
        self.Tutorial = None

        if (Tutorial):
            self.TutorialStep = StartStopMode.TutorialEnum.START_1
            ShowModalTutorial('start.1.ui', self)

            if self.TutorialStep != StartStopMode.TutorialEnum.START_NONE:
                self.TutorialStep = StartStopMode.TutorialEnum.START_2
                ShowModalTutorial('start.2.ui', self)

            if self.TutorialStep != StartStopMode.TutorialEnum.START_NONE:
                self.TutorialStep = StartStopMode.TutorialEnum.START_2b
                self.Tutorial = ShowTutorial('start.2b.ui', self)
        else:
            self.TutorialStep = StartStopMode.TutorialEnum.START_NONE


    def SetBrake(self, Position):    # Start/Stop mode
        """
        Set the brake mode
        """
        if ((self.TutorialStep == StartStopMode.TutorialEnum.START_2b) and (Position == state.BrakeEnum.EMERGENCY)):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('start.3.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_3

        if ((self.TutorialStep == StartStopMode.TutorialEnum.START_3) and (Position == state.BrakeEnum.RELEASE)):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('start.4.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_4

        if ((self.TutorialStep == StartStopMode.TutorialEnum.START_5C) and (Position == state.BrakeEnum.RELEASE)):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('start.6.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_6

        if ((self.TutorialStep == StartStopMode.TutorialEnum.START_4) and (Position == state.BrakeEnum.LAP)):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('start.5.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_5

    def ModeSetDirection(self, Direction):  # Start/Stop Mode
        """
        Set the direction of the reverser

        Parameters
            :arg Direction: The direction of the reverser
        """
        if ((self.TutorialStep == StartStopMode.TutorialEnum.START_5) and
            (Direction == state.DirectionEnum.FORWARD)):
            self.Tutorial.close()
            self.Tutorial = None

            self.Tutorial = ShowTutorial('start.5b.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_5B

    def TutorialCancel(self):   # Start/Stop mode
        """
        Called when tutorial's cancel button is clicked

        Closes out the tutorial
        """
        self.TutorialStep = StartStopMode.TutorialEnum.START_NONE
        if hasattr(getattr(self, "Tutorial", None), "close"):
            self.Tutorial.close()
        self.Tutorial = None

    def DeadmanClicked(self, Checked):
        """
        Called when the deadman is changed

        :param Checked: Is it checked
        """
        if (self.TutorialStep == StartStopMode.TutorialEnum.START_5B):
            self.Tutorial.close()
            del self.Tutorial

            self.Tutorial = ShowTutorial('start.5c.ui', self)
            self.TutorialStep = StartStopMode.TutorialEnum.START_5C

    def ModeSetRun(self, RunLevel):         # StartStopMode
        """
        Set the run level

        :param RunLevel: Run level selected

        :returns: True if we should contine, false if should reset
        """
        if (self.TutorialStep == StartStopMode.TutorialEnum.START_6) and (RunLevel > 0):
            self.Tutorial.close()
            self.Tutorial = None

            self.TutorialStep = StartStopMode.TutorialEnum.START_6W  # Waiting after to turn off resistors

        if (self.TutorialStep == StartStopMode.TutorialEnum.START_7) and (RunLevel <= 0):
            self.Tutorial.close()
            self.Tutorial = None

            # Defer this instead of calling it directly: ShowModalTutorial()
            # blocks on its own nested event loop, and we're still in the
            # middle of ModeSetRun() here -- state.State.RunLevel hasn't
            # been committed to 0 yet (that happens back in SetRun(), once
            # ModeSetRun() returns), and neither has self.RunLevelTime/
            # self.LastRunLevel below.  Tick() keeps firing while the modal
            # is up, so RulesCheck() would keep seeing "RunLevel is still 1,
            # unchanged since the original + press" the whole time start.8.ui
            # is on screen, and just keep accumulating run time against the
            # resistor-overheat check -- which is exactly why it fired even
            # though "-" had already been pressed.  QTimer.singleShot(0, ...)
            # waits until this call (and SetRun()'s commit of RunLevel) has
            # fully unwound before showing the popup.
            QtCore.QTimer.singleShot(0, lambda: ShowModalTutorial("start.8.ui", self))
            self.TutorialStep = StartStopMode.TutorialEnum.START_NONE
        
        # First we check to see if the RunLevel has changed
        if (state.State.RunLevel != RunLevel):
            self.LastRunLevel = state.State.RunLevel
            self.RunLevelTime = state.SimTime()
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

    def ModeTick(self):           # StartStopMode
        """
        Return the updated speed
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

    def RulesCheck(self):   # Start stop mode
        """
        Check to see if we violated any of the rules

        :returns: True if it's safe to contine
        """
        global MainWindow

        # The deadman must be pressed if we are moving or trying to run
        if (not state.State.Deadman) and \
            ((state.State.Speed != 0) or (state.State.RunLevel != 0)):
            state.Log("StartStop: Deadman %d %f %d" % \
                 (state.State.Deadman, state.State.Speed, state.State.RunLevel))
            state.State.Speed = 0.0
            MainWindow.Video.SetRate(0.0)
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
            TimeDiff = state.SimTime() - self.RunLevelTime

            if (state.State.RunLevel > 0):
                if (TimeDiff > self.TUTORIAL_RUN_TIME):
                    if (self.TutorialStep == StartStopMode.TutorialEnum.START_6W) and (state.State.RunLevel > 0):
                        self.Tutorial = ShowTutorial("start.7.ui", self)
                        self.TutorialStep = StartStopMode.TutorialEnum.START_7

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
        6. Stop at CB2
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
    TUTORIAL_BROADWAY = 0.085       # Position of where we display the Broadway tutorial

    CB2_HELP=0.52                   # Position of the CB2 help display
    CB2_STOP_BEGIN=0.58             # Position of the start of where can do a CB2 stop
    CB2_STOP_END=0.61               # Position of the end of where can do a CB2 stop

    THOMAS_HELP=0.85                # Display Thomas help here
    THOMAS_STOP_BEGIN=0.87          # Position of the start of the Thomas stop
    THOMAS_STOP_END=0.93            # Position of the end of the Thomas stop

    ########
    ######## Crossing information
    ########
    BROADWAY_NORTH_BEGIN=0.12       # Position where we start crossing Broadway
    BROADWAY_NORTH_END=0.15         # Position where we stop crossing Broadway
    
    CENTRAL_HELP=0.37               # Where to display help for central
    CENTRAL_BEGIN=0.39              # Where we start crossing Central Ave.
    CENTRAL_END=0.42                # Where we start crossing Central Ave.

    BROADWAY_SOUTH_HELP=0.65        # Where we popup help for Broadway (South)
    BROADWAY_SOUTH_BEGIN=0.70       # Position where we start crossing Broadway (South)
    BROADWAY_SOUTH_END=0.75         # Position where we stop crossing Broadway (South)

    CROSSING_DING_COUNT=3           # Number of dings needed at each crossing

    ########
    ######## Zorch information
    ########
    ZORCH_HELP=0.66                       # Display Zorch help here

    ZORCH1_POS_START=0.70                 # Zorch position 1 start
    ZORCH1_POS_END=0.73                   # Zorch position 1 ending

    ZORCH2_POS_START=0.77                 # Zorch position 2 start
    ZORCH2_POS_END=0.79                   # Zorch position 2 ending

    Name = "Full Mode"

    class TutorialEnum(enum.Enum):
        FULL_NONE = 0
        FULL_1 = 1
        FULL_2 = 2
        FULL_3 = 3
        FULL_4 = 4
        FULL_5 = 5
        FULL_6 = 6
        FULL_7 = 7
        FULL_8 = 8
        FULL_9 = 9
        FULL_10 = 10
        FULL_11 = 11
        FULL_12 = 12

    N_TUTORIAL = TutorialEnum.FULL_12.value+1     # Number of tutorials

    def __init__(self, Tutorial = False):
        """
        Args:
            Main Window -- The main window
        """
        super().__init__(False)
        self.DoTutorial = Tutorial

        self.LOCAL_EVENTS = [
            TrackEvent(self.BROADWAY_NORTH_END, lambda: self.DingCheck(self.BROADWAY_NORTH_BEGIN, self.BROADWAY_NORTH_END, "Broadway North")),
            TrackEvent(self.CENTRAL_END,        lambda: self.DingCheck(self.CENTRAL_BEGIN,        self.CENTRAL_END,        "Central")),
            TrackEvent(self.BROADWAY_SOUTH_END, lambda: self.DingCheck(self.BROADWAY_SOUTH_BEGIN, self.BROADWAY_SOUTH_END, "Broadway South")),

            TrackEvent(self.BROADWAY_STOP_END,  lambda: self.StopCheck(self.BROADWAY_STOP_BEGIN, self.BROADWAY_STOP_END, "Broadway")),
            TrackEvent(self.CB2_STOP_END,       lambda: self.StopCheck(self.CB2_STOP_BEGIN,      self.CB2_STOP_END,      "Carbarn 2")),
            TrackEvent(self.THOMAS_STOP_END,    lambda: self.StopCheck(self.THOMAS_STOP_BEGIN,   self.THOMAS_STOP_END,   "Thomas")),

            TrackEvent(self.ZORCH1_POS_START, lambda: self.ZorchStart("Carbarn 1 Lead")),
            TrackEvent(self.ZORCH1_POS_END,   lambda: self.ZorchStop()),

            TrackEvent(self.ZORCH2_POS_START, lambda: self.ZorchStart("Main Line spur")),
            TrackEvent(self.ZORCH2_POS_END,   lambda: self.ZorchStop())

        ]
        self.TUTORIAL_EVENTS = []
        if (self.DoTutorial):
            self.TUTORIAL_EVENTS = [
                    TrackEvent(self.TUTORIAL_BROADWAY, lambda: self.FullTutorial('full.2.ui', self.TutorialEnum.FULL_2)),
                    TrackEvent(self.CENTRAL_HELP,      lambda: self.FullTutorial('full.4.ui', self.TutorialEnum.FULL_4)),
                    TrackEvent(self.CB2_HELP,          lambda: self.FullTutorial('full.5.ui', self.TutorialEnum.FULL_5)),
                    TrackEvent(self.ZORCH_HELP,        lambda: self.FullTutorial('full.7.ui', self.TutorialEnum.FULL_8)),
                    TrackEvent(self.BROADWAY_SOUTH_HELP,lambda: self.FullTutorial('full.9.ui', self.TutorialEnum.FULL_9)),
                    TrackEvent(self.THOMAS_HELP,       lambda: self.FullTutorial('full.10.ui', self.TutorialEnum.FULL_10)),
                    TrackEvent(STORE_HELP,             lambda: self.FullTutorial('full.12.ui', self.TutorialEnum.FULL_12)),
            ]

        self.Events = GLOBAL_EVENTS + self.LOCAL_EVENTS + self.TUTORIAL_EVENTS
        self.LastStop = -1
        self.ZorchEnable = False
        self.MaxSpeed = 0

        # Which tutorial popups have already been shown.  Must exist in
        # every Full mode, not just the tutorial: ModeTick() consults it on
        # every tick.  Without the tutorial, everything counts as "done", so
        # no popups appear.  Created before full.1.ui is shown so that
        # pressing Cancel on that very first popup (TutorialCancel()) sticks.
        self.TutorialDone = [not Tutorial] * self.N_TUTORIAL

        if (Tutorial):
            self.TutorialStep = self.TutorialEnum.FULL_1
            self.TutorialDone[self.TutorialEnum.FULL_1.value] = True
            ShowModalTutorial('full.1.ui', self)

    def TutorialCancel(self):   # Full mode
        """
        Called when a tutorial's Cancel button is clicked (and by
        MainReset()).

        The Full mode popups are driven by TutorialDone, not TutorialStep,
        so marking every step done is what actually stops them for the rest
        of the run.
        """
        super().TutorialCancel()
        self.TutorialDone = [True] * self.N_TUTORIAL

    def FullTutorial(self, FileName, StepName):
        """
        Display a full mode tutorial

        :arg FileName: File to display
        :arg StepName: The name of the step
        """
        if (not self.TutorialDone[StepName.value]):
            PauseTutorial(FileName, self)
            self.TutorialDone[StepName.value] = True

    def SetBrake(self, Position):    # Full mode
        """
        Set the brake mode
        """
        pass

    def ModeSetDirection(self, Direction):  # Full Mode
        """
        Set the direction of the reverser

        Parameters
            :arg Direction: The direction of the reverser
        """
        pass

    def DeadmanClicked(self, Checked):      # Full mode
        """
        Called when the deadman is changed

        :param Checked: Is it checked
        """

    def ZorchStart(self, What):     # Full mode
        """
        Start zorch checking

        Args:
            What -- What we are looking for
        """
        self.ZorchEnable = True
        self.ZorchMessage = What

    def ZorchStop(self):        # Full mode
        """
        Stop zorch checking
        """
        self.ZorchEnable = False

    def StopCheck(self, Start, Stop, What):     # Full mode
        """
        Check to see if we stopped at the right place

        Args:
           Start -- Earliest stopping location
           Stop -- Latest stopping location
           What -- Our name
        """
        global MainWindow

        if (self.LastStop >= Start) and (self.LastStop <= Stop):
            return
        MainWindow.AddWarning("Failed to stop at %s" % What)

    def DingCheck(self, Start, Stop, What):     # Full mode
        """
        Check to see if enough dings occurred during an interval

        Args:
           Start -- Where the dings should start
           Stop -- Where the dings should stop
           What -- Our name
        """
        DingDingDing = self.DingCount(MainWindow.DingPosition, Start, Stop)

        if (DingDingDing < self.CROSSING_DING_COUNT):
            MainWindow.AddWarning("Failed to sound bell crossing %s" % What)

    def ModeSetRun(self, RunLevel):         # FullMode
        """
        Set the run level

        :param RunLevel: Run level selected

        :returns: True if we should continue, false if should reset
        """
        Continue = super().ModeSetRun(RunLevel)
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

        self.StopTime = 0               # Time of last stop (0 = no stop to judge)
        self.StopBellTime = None        # Time of first bell after that stop
        self.StoppedAt = 0              # When the trolley last came to a stop

    def ModeTick(self):           # FullMode
        """
        Return the updated speed
        """
        super().ModeTick()
        self.LastSpeed = self.CurrentSpeed
        self.CurrentSpeed = state.State.Speed
        if (not self.TutorialDone[FullMode.TutorialEnum.FULL_3.value]):
            if ((state.State.Speed <= 0) and 
                (MainWindow.Video.GetPosition() >= self.BROADWAY_STOP_BEGIN) and
                (MainWindow.Video.GetPosition() <= self.BROADWAY_STOP_END)):
                ShowModalTutorial('full.3.ui', self)
                self.TutorialDone[FullMode.TutorialEnum.FULL_3.value] = True

        if (not self.TutorialDone[FullMode.TutorialEnum.FULL_6.value]):
            if ((state.State.Speed <= 0) and 
                (MainWindow.Video.GetPosition() >= self.CB2_STOP_BEGIN) and
                (MainWindow.Video.GetPosition() <= self.CB2_STOP_END)):
                ShowModalTutorial('full.6.ui', self)
                self.TutorialDone[FullMode.TutorialEnum.FULL_6.value] = True

        if (not self.TutorialDone[FullMode.TutorialEnum.FULL_11.value]):
            if ((state.State.Speed <= 0) and 
                (MainWindow.Video.GetPosition() >= self.THOMAS_STOP_BEGIN) and
                (MainWindow.Video.GetPosition() <= self.THOMAS_STOP_END)):
                ShowModalTutorial('full.11.ui', self)
                self.TutorialDone[FullMode.TutorialEnum.FULL_11.value] = True

    def DingCount(self, DingPosition, Start, End):      # Full mode
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

    def CheckStartStopDing(self):       # Full mode
        """
        Checks to see if we started or stopped and did 
        the dings correctly

        Notes:
            DingTime -- When we did each ding

        """
        global MainWindow

        # See if we went from stopped to moving
        if (self.LastSpeed == 0) and (self.CurrentSpeed != 0):
            # Now check to see if the operator did ding-ding before moving
            # There must be two dings in the last 10 seconds
            # and they must be less than 2 seconds apart

            #
            # Only bells since the trolley stopped count, and not the stop
            # bell itself (when it was a proper single bell).  Otherwise a
            # stop bell followed by nothing was reported as a
            # "ding-wait-ding" start signal, and a ding-ding given before
            # the stop could count as the start signal after it.
            StartDings = self.StartSignalDings()

            # Do we have two dings
            if (len(StartDings) < 2):
                MainWindow.AddWarning("Started moving without sounding start signal")
            else:
                # Current time 1000 Ding time 999 Good=true
                # Current time 1000 Ding time 900 Good=false

                # Did we signal within the last 10 seconds
                if (state.SimTime() - StartDings[-2] > MAX_SIGNAL_START):
                    MainWindow.AddWarning("Started moving without sounding start signal")
                # Are the ding ding more than 2 seconds apart
                elif ((StartDings[-1] - StartDings[-2]) > MAX_START_BETWEEN):
                    MainWindow.AddWarning("Start signal is ding-ding not ding-wait-ding")

        # Stop signal: a single bell *after* the trolley has stopped, to say
        # it really has stopped.  Judged once per stop (self.StopTime != 0):
        #
        #   - No bell after stopping, and the trolley moves off
        #         -> "No stop signal"
        #   - No bell within STOP_TIME_CHECK seconds while still stopped
        #         -> "Stop Signal too slow or missing"
        #   - The first bell after stopping has another bell within
        #     STOP_SIGNAL_TIME of it (before or after), so it isn't a single
        #     bell -- typically the student skipped the stop bell and went
        #     straight to the ding-ding start signal
        #         -> "Stop Signal confused with other signals"
        #
        # The first bell after the stop isn't judged until STOP_SIGNAL_TIME
        # has passed (or the trolley moves), so that a second bell right
        # behind it is seen.  Judging it on the very next tick used to let
        # the first ding of the start signal pass as the stop signal.
        if (self.StopTime != 0):
            Now = state.SimTime()
            Moving = (self.CurrentSpeed != 0)

            if (self.StopBellTime is None):
                for ADing in MainWindow.DingTime:
                    if (ADing >= self.StopTime):
                        self.StopBellTime = ADing
                        break

            if (self.StopBellTime is None):
                if Moving:
                    MainWindow.AddWarning("No stop signal")
                    self.StopTime = 0
                elif (Now - self.StopTime >= STOP_TIME_CHECK):
                    MainWindow.AddWarning("Stop Signal too slow or missing")
                    self.StopTime = 0
            elif Moving or (Now - self.StopBellTime >= STOP_SIGNAL_TIME):
                if (not self.IsSingleBell(self.StopBellTime)):
                    MainWindow.AddWarning("Stop Signal confused with other signals")
                self.StopTime = 0       # This stop has been judged

        if (self.LastSpeed != 0) and (self.CurrentSpeed == 0):
            self.StopTime = state.SimTime()
            self.StoppedAt = self.StopTime
            self.StopBellTime = None    # First bell after this stop

    def IsSingleBell(self, DingTime):   # Full mode
        """
        :param DingTime: Time of one bell (an entry in MainWindow.DingTime)
        :returns: True if no other bell is within STOP_SIGNAL_TIME of it
        """
        for ADing in MainWindow.DingTime:
            if (ADing != DingTime) and (abs(ADing - DingTime) < STOP_SIGNAL_TIME):
                return False
        return True

    def StartSignalDings(self):         # Full mode
        """
        The bells that can make up a start signal: those rung since the
        trolley last stopped (since the run began, for the first start),
        minus the stop bell if it was a proper single bell.

        :returns: List of bell times, oldest first
        """
        Result = []
        for ADing in MainWindow.DingTime:
            if (ADing < self.StoppedAt):
                continue
            if ((ADing == self.StopBellTime) and self.IsSingleBell(ADing)):
                continue
            Result.append(ADing)
        return Result

    def RulesCheck(self):   # Full mode
        """
        Check to see if we violated any of the rules

        :returns: True if it's safe to continue
        """
        global MainWindow

        Continue = super().RulesCheck()
        if (not Continue):
            return (Continue)

        self.CheckStartStopDing()

        if (self.CurrentSpeed == 0):
            self.LastStop = MainWindow.Video.GetPosition()

        # Check Zorching
        if (self.ZorchEnable and state.State.RunLevel != 0):
            state.Log("Zorch at position %0.2f" % MainWindow.Video.GetPosition())
            sound.GlobalSound.Play(sound.SoundEnum.ZORCH, False)
            MainWindow.AddWarning("Zorched %s" % self.ZorchMessage)
            self.ZorchEnable = False

        return True

class SelectWindow(QDialog, mode_window.Ui_SelectWindow):
    """
    This class controls the select mode window
    """
    def __init__(self, parent=None):
        """
        Create the select window

        :param self: This class
        :param parent: Parent of this class
        """
        global ModeId 
        super().__init__(parent)
        self.setupUi(self)
        ModeId = ModeEnum.EASY

    def CenterOnParent(self):
        """
        Center this window over the main window, horizontally and
        vertically, title bars included.

        Works as a correction: measure where our frame's center is now and
        shift the window by the difference.  A pure shift behaves the same
        whether the window manager takes positions as frame or client
        coordinates (they differ between window managers), and repeating it
        once the window manager has added the title bar and reported the
        real frame size makes it exact.
        """
        Parent = self.parentWidget()
        if (Parent is None) or (not self.isVisible()):
            return
        if Parent.isFullScreen():
            # No frame; don't trust frameGeometry(), which can still include
            # the title bar the window had before it went full screen.
            Target = Parent.geometry().center()
        else:
            Target = Parent.frameGeometry().center()
        Delta = Target - self.frameGeometry().center()
        if (abs(Delta.x()) > 1) or (abs(Delta.y()) > 1):
            self.move(self.pos() + Delta)

    def showEvent(self, event):
        """
        Center over the main window every time the window is shown.

        Qt only centers a dialog over its parent the first time it is
        shown, and the window manager adds the title bar (changing our
        frame size) only after the window appears.  So center now, and
        re-check on the next few moves/resizes the window manager makes
        while placing and framing the window (_AutoCenter).  After that,
        the user can drag it wherever they like.
        """
        super().showEvent(event)
        self._AutoCenter = 4
        self.CenterOnParent()
        QtCore.QTimer.singleShot(0, self.CenterOnParent)

    def moveEvent(self, event):
        super().moveEvent(event)
        if getattr(self, "_AutoCenter", 0) > 0:
            self._AutoCenter -= 1
            self.CenterOnParent()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_AutoCenter", 0) > 0:
            self._AutoCenter -= 1
            self.CenterOnParent()

    def EasyHelpClicked(self):
        """
        The easy mode help button has been clicked
        """
        webbrowser.open("help.pdf")

    def EasyModeSartClicked(self):
        """
        The easy mode start button has been clicked
        """
        global ModeId 
        ModeId = ModeEnum.EASY
        self.hide()

    def EasyModeTutorialClicked(self):
        """
        The easy mode tutorial button has been clicked
        """
        global ModeId 
        ModeId = ModeEnum.EASY_TUTORIAL
        self.hide()

    def FullHelpClicked(self):
        """
        The full mode help button has been clicked
        """
        webbrowser.open("help.pdf")

    def FullModeStartClicked(self):
        """
        The full mode start button has been clicked
        """
        global ModeId 
        ModeId = ModeEnum.FULL
        self.hide()

    def FullModeTutorialClicked(self):
        """
        The full mode tutorial button has been clicked
        """
        global ModeId 
        ModeId = ModeEnum.FULL_TUTORIAL
        self.hide()

    def closeEvent(self, event):
        """
        Called only when this dialog is closed via the window manager's
        close decoration (the "X" in the title bar) -- every Start/
        Tutorial button handler above calls self.hide() instead of
        self.close(), and hide() does not trigger closeEvent(), so this
        never fires for a normal mode selection.

        self.exec() (called from MainReset()) runs its own *nested* Qt
        event loop, separate from the outer app.exec().  Simply accepting
        this event and letting the dialog close would only end that
        nested loop -- MainReset() would then carry right on past
        self.SelectWindow.exec() and build a Mode from whatever ModeId
        happens to already be set, exactly the same hazard documented on
        HandleSigInt() below for Ctrl-C.  Route this through
        MainWindow.close() (for its normal timer/mpv cleanup) followed by
        os._exit(0) (to guarantee the process actually ends), rather than
        letting the app limp on half-alive with no window visible.

        :param event: The close event
        """
        global MainWindow
        event.accept()
        state.Log("SelectWindow closed via window decoration, shutting down")
        if MainWindow is not None:
            try:
                MainWindow.close()
            except Exception:
                pass
        os._exit(0)

    def reject(self):
        """
        Esc key (and anything else that calls reject()).

        QDialog maps Esc to reject(), which ends the nested exec() in
        MainReset() without going through closeEvent() -- so MainReset()
        would carry on and build a Mode from whatever ModeId was left over
        from the previous run.  There is no "cancel" for the mode picker:
        the user has to choose a mode, so Esc is simply ignored.
        """
        state.Log("SelectWindow: reject() (Esc) ignored")

    def StartStopHelpClicked(self):
        webbrowser.open("help.pdf")

    def StartStopModeStartClicked(self):
        global ModeId 
        ModeId = ModeEnum.START_STOP
        self.hide()

    def StartStopModeTutorialClicked(self):
        """
        Handle when we get start/stop tutorial clicked
        """
        global ModeId 
        ModeId = ModeEnum.START_STOP_TUTORIAL
        self.hide()

class BrakeGraphics():
    """
    Handle the drawing and clicking of the brake controller.
    """
    def __init__(self):
        """
        Setup controller window

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

        MainWindow.BrakeGraphicsView.mousePressEvent = self.MouseClick
        MainWindow.BrakeGraphicsView.setScene(self.BrakeControlScene)
        MainWindow.BrakeGraphicsView.show()

    def MouseClick(self, Event):
        """
        Handle a mouse click in the brake controller graphics box

        :param Event: Mouse click event
        """
        global MainWindow

        CENTER_X = 129  # Center of the image
        CENTER_Y = 53   # Center of the Y image
        x = int(Event.position().x())
        y = int(Event.position().y())
        ClosestDelta = 9999

        for Index in range(len(self.BRAKE_STATE)):
            Angle = math.degrees(math.atan2(y-CENTER_Y, x-CENTER_X))
            if (abs(Angle-self.BRAKE_ANGLES[Index]) < ClosestDelta):
                BrakeLever = self.BRAKE_STATE[Index]
                ClosestDelta = abs(Angle-self.BRAKE_ANGLES[Index])

        self.MoveBrakeLever(BrakeLever)
        MainWindow.BrakeUi.SetBrake(BrakeLever)

    def MoveBrakeLever(self, State):
        """ Move the brake lever to the given location

        :param State: State of the brake lever
        """
        self.BrakeHandleItem.setRotation(self.BRAKE_MAP[State])


class DismissOnClick(QtCore.QObject):
    """
    Application-level event filter that ends a wait on the first mouse press
    anywhere in the application.

    The error dialog is shown *modeless* (so the rest of the application window
    keeps receiving mouse events) while ShowErrorMessage blocks on a local
    QEventLoop instead of exec().  This filter, installed on the QApplication,
    catches the first press -- whether it lands on the dialog, one of its child
    widgets, or anywhere in the main window -- and quits that loop, which
    dismisses the dialog.

    An application-modal exec() would not allow this: Qt blocks mouse events to
    the main window while a modal dialog is up, so clicks outside the dialog
    never arrive.  Showing modeless and looping ourselves keeps ShowErrorMessage
    blocking (caller control flow unchanged) while still letting a click
    anywhere in the window dismiss the dialog.

    The press is consumed (returns True) so the dismissing click does not also
    activate whatever sits underneath it.

    Lives on, and is installed/removed from, the GUI thread, so it never
    touches Qt objects from a foreign thread (unlike the old pynput hook).
    """
    def __init__(self, loop, OnPress=None):
        """
        :param loop: The QEventLoop to quit on the first press
        :param OnPress: Optional callable run on that press.  Because this
            filter consumes the press, application filters installed before
            it (ActivityFilter) never see it; this lets the caller still
            count it as user activity.
        """
        super().__init__(loop)
        self._loop = loop
        self._on_press = OnPress

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self._loop.quit()
            if self._on_press is not None:
                self._on_press()
            return True  # consume the dismissing click
        return super().eventFilter(obj, event)


class ActivityFilter(QtCore.QObject):
    """
    Application-level event filter that reports any user input.

    Installed on the QApplication, so it sees presses and keys no matter
    which widget receives them -- buttons, graphics views, tutorial
    popups, dialogs.  The old attract-mode reset lived in
    Window.mousePressEvent(), which only runs for clicks that land on
    bare main-window background; clicks on the controls themselves are
    consumed by those widgets and never got there, so attract mode could
    start in the middle of a run.

    Never consumes anything (always returns False).
    """
    ACTIVITY_EVENTS = (
        QEvent.Type.MouseButtonPress,
        QEvent.Type.KeyPress,
        QEvent.Type.TouchBegin,
        QEvent.Type.Wheel,
    )

    def __init__(self, Callback, parent=None):
        super().__init__(parent)
        self._callback = Callback

    def eventFilter(self, obj, event):
        if event.type() in self.ACTIVITY_EVENTS:
            self._callback()
        return False


class Window(QMainWindow, sim_ui4.Ui_MainWindow):
    """
    Main window in which everything happens
    """

    # Emitted from the pynput attract-mode listener thread; connected with a
    # queued connection so StopAttractVideo runs on the GUI thread.  A signal
    # is the canonical cross-thread marshal -- safer than QTimer.singleShot,
    # which creates a timer in a thread that has no Qt event loop and may
    # therefore never fire.
    StopAttractRequested = pyqtSignal()

    def __init__(self, app, parent=None):
        """
        Create the main window

        :param self: This class
        :param app: Qt app
        :param parent: Parent of this class
        """
        global FullScreen 
        global LeftMargin, RightMargin, TopMargin, BottomMargin
        global MainWindow
        global Mode

        super().__init__(parent)
        self.setupUi(self)

        # Tick() reentrancy / suspension state.  Must exist before anything
        # below can open a dialog (EasyMode() may show a modal tutorial) or
        # start self.Timer.
        #   _InTick           -- True while Tick() is executing
        #   _SuspendCount     -- >0 while a blocking dialog is up; Tick()
        #                        does nothing (see SimSuspended())
        #   _ResetGeneration  -- bumped by MainReset() so a Tick() that
        #                        triggered a reset can tell and bail out
        self._InTick = False
        self._SuspendCount = 0
        self._ResetGeneration = 0

        # Publish ourselves as the module-global MainWindow *immediately*,
        # before any of the helper objects below (video.Video,
        # controller.ControllerGraphics/ControllerButtons, brake_ui.BrakeUi,
        # BrakeGraphics, EasyMode, ...) are constructed. All of those reach
        # back through the MainWindow global (or main.MainWindow, from other
        # files) to get at widgets like VideoFrame, ControllerGraphicsView,
        # etc. setupUi() above has already created every one of those
        # widgets as attributes of self, so it's safe to publish "self" as
        # MainWindow now -- we don't need __init__ to have finished, only
        # setupUi(). Previously MainWindow wasn't assigned until Window(app)
        # returned at the bottom of this file, which was *after* all of
        # these helpers had already run, so they were reaching through a
        # MainWindow that was still None (or, from other modules, an
        # attribute that didn't exist yet at all).
        MainWindow = self

        if IS_LINUX:
            self.CommandPipe = CommandPipe()
        state.State.Reset()

        self.BrakeApply.clicked.connect(self.BrakeApplyClicked)
        self.BrakeRelease.clicked.connect(self.BrakeReleaseClicked)
        self.BrakeLap.clicked.connect(self.BrakeLapClicked)
        self.BrakeEmergency.clicked.connect(self.BrakeEmergencyClicked)
        self.MinusButton.clicked.connect(self.MinusButtonClicked)
        self.PlusButton.clicked.connect(self.PlusButtonClicked)

        Mode = EasyMode()
        ##@@ Make this from the Mode
        self.Video = video.Video(app, VideoFile, "scrm", IMAGE_DIR, SkipCount)

        self.BrakeUi = brake_ui.BrakeUi()

        self.BrakeView.setScene(self.BrakeUi.Scene)
        self.BrakeView.show()

        self.BrakeGraphics = BrakeGraphics()
        self.ControllerGraphics = controller.ControllerGraphics()
        self.ControllerButtons = controller.ControllerButtons()

        self.SelectWindow = SelectWindow(self)
        self.Timer = QtCore.QTimer(self)
        self.Timer.setInterval(100)
        self.Timer.timeout.connect(self.Tick)
        self.Timer.start()
        self.setWindowTitle("Trolley Simulator")
        Margins = self.centralwidget.contentsMargins()

        if (TopMargin is None):
            TopMargin = Margins.top()
        if (BottomMargin is None):
            BottomMargin = Margins.bottom()
        if (LeftMargin is None):
            LeftMargin = Margins.left()
        if (RightMargin is None):
            RightMargin = Margins.right()

        # left, top, right, bottom
        self.centralwidget.setContentsMargins(LeftMargin, TopMargin, RightMargin, BottomMargin)
        Margins = self.centralwidget.contentsMargins()
        self.ClickTargets.clicked.connect(self.ToggleTargets)
        self.Targets = True
        self.ClickClackPos = CLICK_CLACK_DISTANCE
        ##@@self.mousePressEvent = self.OnMouseClick

        if (AttractEnable):
            # ============================================================
            # Timer Setup (5 minutes = 300,000 milliseconds)
            # ============================================================
            # QTimer triggers an event after a specified interval
            # Reference: https://doc.qt.io/qt-6/qtimer.html
            self.AttractTimer = QtCore.QTimer()
            self.AttractTimer.timeout.connect(self.OnTimeout)
            self.AttractTimer.setSingleShot(True)  # Timer fires only once
            self.AttractTimer.start(ATTRACT_TIMEOUT)  # 5 minutes in milliseconds
            self.AttractMouseListener = None
            self.AttractIsPlayingVideo = False
            # In-process, self-looping player in its own full-screen window
            # (replaces launching an external player; see video.AttractPlayer).
            self.AttractPlayer = video.AttractPlayer(
                AttractVideoFile, self.StopAttractVideo, self)
            # Queued connection: signal is emitted from the pynput listener
            # thread, slot runs on the GUI thread.
            self.StopAttractRequested.connect(
                self.StopAttractVideo, Qt.ConnectionType.QueuedConnection
            )
            # Any input anywhere in the application counts as activity.
            self.ActivityFilter = ActivityFilter(self.NoteUserActivity, self)
            app.installEventFilter(self.ActivityFilter)

    @contextlib.contextmanager
    def SimSuspended(self):
        """
        Context manager: freeze the simulation while a blocking dialog is up.

        Every blocking popup in this program (error messages, warnings,
        the mode picker, modal tutorials) runs a *nested* Qt event loop.
        Qt will not re-fire a timer whose own timeout slot is still on the
        stack, so a dialog opened from inside Tick() is safe by accident.
        But a dialog opened from anywhere else -- the plus/minus buttons,
        the keyboard, the brake buttons, the named pipe, startup -- has
        self.Timer ticking right behind it, running the physics and rules
        checks.  A rule that is also being violated (e.g. the deadman) then
        opens a second dialog on top of the first.  The same happens behind
        the mode picker: MainReset() stops and restarts self.Timer, which
        registers a fresh timer that Qt's protection doesn't cover, so the
        old Mode keeps being ticked while the user picks the new one.

        The timer is deliberately left running rather than stopped: Python
        only runs signal handlers when it executes bytecode, and the
        (now nearly empty) Tick() calls are what let Ctrl-C (HandleSigInt)
        get through while a nested loop is blocking.

        The simulation clock (state.SimTime(), used for all rule timing)
        is paused for the same span, so time spent reading a dialog doesn't
        count against the run-time and signal-timing rules.

        Nestable: a counter, not a flag.
        """
        self._SuspendCount += 1
        state.Clock.Pause()
        try:
            yield
        finally:
            state.Clock.Resume()
            self._SuspendCount -= 1

    def moveEvent(self, event) -> None:
        """
        Keep the mode picker centered if the main window moves.
        """
        super().moveEvent(event)
        Picker = getattr(self, "SelectWindow", None)   # Not made yet early in __init__
        if (Picker is not None) and Picker.isVisible():
            Picker.CenterOnParent()
            # And again once the window manager has settled our frame.
            QtCore.QTimer.singleShot(0, Picker.CenterOnParent)

    def resizeEvent(self, event) -> None:
        """
        Notify the worker process of the label's new pixel dimensions by
        writing into the shared ``_shared_w`` / ``_shared_h`` Values.

        Qt calls this method after the layout engine has already recalculated
        all child widget sizes, so ``self.video_label.size()`` returns the
        correct new dimensions at the time this method runs.

        The worker reads ``shared_w.value`` and ``shared_h.value`` at the top
        of its loop, so the very next frame it processes after this write will
        be scaled to the new size.

        Frames already sitting in the queue were scaled to the previous size
        and are displayed as-is (centred by Qt.AlignCenter).

        Parameters
        ----------
        event : QResizeEvent
            Carries the old and new window sizes; passed to super() so that
            Qt's internal resize handling (layout recalculation, repainting)
            runs normally.
            https://doc.qt.io/qt-5/qresizeevent.html

        Overrides
        ---------
        QWidget.resizeEvent:
            https://doc.qt.io/qt-5/qwidget.html#resizeEvent
        """
        # Always call the base-class implementation first so Qt can finish its
        # own resize bookkeeping before we read the new label size.
        # https://doc.qt.io/qt-5/qwidget.html#resizeEvent
        super().resizeEvent(event)
        # At startup the mode picker opens while the window manager is
        # still making this window full screen / maximized; keep it
        # centered as we change size (also for the 'F' key toggle).
        Picker = getattr(self, "SelectWindow", None)   # Not made yet early in __init__
        if (Picker is not None) and Picker.isVisible():
            Picker.CenterOnParent()
            # And again once the window manager has settled our frame.
            QtCore.QTimer.singleShot(0, Picker.CenterOnParent)
        VideoSize = self.VideoFrame.size()
        self.Video.SharedWidth.value = VideoSize.width()
        self.Video.SharedHeight.value = VideoSize.height()

    def NoteUserActivity(self):
        """
        Someone is using the simulator (any click, key, touch, or panel
        command).  Restart the attract-mode idle timer, or, if the attract
        video is showing, stop it (which also restarts the timer).
        """
        if not AttractEnable:
            return
        if self.AttractIsPlayingVideo:
            self.StopAttractVideo()
        else:
            self.AttractTimer.start(ATTRACT_TIMEOUT)  # Restart 5-minute timer

    def AttractStartMouseListener(self):
        """
        Start global mouse listener using pynput library.
        
        The pynput mouse listener captures all mouse events system-wide,
        even outside the Qt application window.
        
        Reference: https://pynput.readthedocs.io/en/latest/mouse.html
        """
        if self.AttractMouseListener is None:
            # Create listener with callbacks for click and move events
            self.AttractMouseListener = pynput.mouse.Listener(
                on_click=self.OnMouseClick, on_move = self.OnMove
            )
            self.AttractMouseListener.start()

    def OnMove(self, X, Y):
        if self.AttractIsPlayingVideo:
            # Runs on pynput's thread. Marshal to the GUI thread via a queued
            # signal rather than calling Qt methods or creating a QTimer here.
            self.StopAttractRequested.emit()
            return False  # Stop the listener
        return True

    def OnMouseClick(self, X, Y, Button, Pressed):
        """
        Handle global mouse click events from pynput.
        
        Args:
            X (int): X coordinate of click
            Y (int): Y coordinate of click
            Button: Mouse button that was clicked
            Pressed (bool): True if button was pressed, False if released
            
        Returns:
            bool: False to stop listener, True to continue
            
        Reference: https://pynput.readthedocs.io/en/latest/mouse.html#monitoring-the-mouse
        """
        if self.AttractIsPlayingVideo and Pressed:
            # Runs on pynput's thread. Marshal to the GUI thread via a queued
            # signal rather than calling Qt methods or creating a QTimer here.
            self.StopAttractRequested.emit()
            return False  # Stop the listener
        return True

    def StopAttractVideo(self):
        """
        Stop the attract video and restore normal state.

        Called on the GUI thread, either through the queued
        StopAttractRequested signal (pynput listener) or directly by the
        AttractPlayer window when it gets a click, key, or touch.

        This method:
        1. Stops the global mouse listener
        2. Stops the attract player and hides its window
        3. Restarts the 5-minute timer
        """
        if not self.AttractIsPlayingVideo:
            return

        self.AttractIsPlayingVideo = False

        # Stop global mouse listener
        if self.AttractMouseListener:
            self.AttractMouseListener.stop()
            self.AttractMouseListener = None

        self.AttractPlayer.Stop()
        self.activateWindow()
        self.raise_()

        # Restart the 5-minute countdown timer
        self.AttractTimer.start(ATTRACT_TIMEOUT)

    def OnTimeout(self):
        """
        Handle timer timeout event.

        Called when 5 minutes elapse without button press.  Shows the
        attract video full screen, looping, until the user touches
        something.
        """
        self.AttractIsPlayingVideo = True

        if not self.AttractPlayer.Start():
            # Video missing: don't sit in "playing" state with nothing on
            # screen.  Try again after the next idle period.
            self.AttractIsPlayingVideo = False
            self.AttractTimer.start(ATTRACT_TIMEOUT)
            return

        # Global mouse listener: stops the video on any mouse movement or
        # click, even if mpv's native child window swallows the event.
        self.AttractStartMouseListener()

    def ToggleTargets(self, Checked):
        """
        Toggle the click targets
        """
        self.ControllerGraphics.ToggleDots()

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
        global Mode

        state.State.Deadman = Checked
        self.DeadmanButton.setChecked(Checked)
        self.DeadmanGraphic.setChecked(Checked)
        Mode.DeadmanClicked(Checked)

    def Tick(self):
        """ 
        The clock has ticked.  Take action

        Does nothing while a blocking dialog is up (see SimSuspended()), and
        is guarded against reentrancy as a backstop in case a dialog is ever
        opened without SimSuspended().
        """
        if self._InTick or self._SuspendCount > 0:
            return
        self._InTick = True
        try:
            self._TickBody()
        finally:
            self._InTick = False

    def _TickBody(self):
        """
        The real work of Tick().  Only called from Tick(), never reentered.
        """
        global Mode 

        # If anything in here calls MainReset(), a new Mode has been built
        # and the video rewound; the rest of this (stale) tick must not run
        # against that new state.
        Generation = self._ResetGeneration

        # Update the speed and acceleration
        self.BrakeUi.UpdateBrake()
        Mode.ModeTick()
        if (self._ResetGeneration != Generation):
            return
        Continue = Mode.RulesCheck()
        if (not Continue) or (self._ResetGeneration != Generation):
            return

        Position = self.Video.GetPosition()
        for Event in Mode.Events:
            Event.Check(Position)
            if (self._ResetGeneration != Generation):
                return

        self.Video.SetRate(state.State.Speed)

        if (Position > self.ClickClackPos):
            state.Log("ClickClackPlay Distance=%f" % self.ClickClackPos)
            sound.GlobalSound.Play(sound.SoundEnum.CLICK_CLACK, False)
            self.ClickClackPos += CLICK_CLACK_DISTANCE

        StatusMsg = f"Run {state.State.RunLevel:d} Pos {self.Video.GetPosition():.2f} " \
            f"Speed {state.State.Speed:.2f} Acc {state.State.Acceleration:.3f} Brake Acc. {state.State.BrakeAcceleration:.3f} " \
            f"Brake:{self.BrakeUi.RedPressure:2.2f} Res:{self.BrakeUi.BlackPressure:2.2f} Extend: {self.BrakeUi.Extend:.2f}"
        if (Verbose):
            state.Log(StatusMsg)
        self.StatusLabel.setText(StatusMsg)

        if (self.Video.GetPosition() > STORE_POSITION) and \
            (state.State.Speed <= 0.0):
            state.Log("Stopped correctly at store")
            self.DisplayWarnings()
            self.GoodStop();
            self.MainReset()
            return 

        if (self.Video.GetPosition() > END_OF_VIDEO):
            self.AddWarning("Failed to stop at store")
            self.DisplayWarnings()
            self.NoticeDone()
            self.MainReset()

    def Ding(self):
        """ 
        Ring the bell
        """
        sound.GlobalSound.Play(sound.SoundEnum.BELL, False)

        ThisDingTime = state.SimTime()
        DingPosition = self.Video.GetPosition()
        self.DingTime.append(ThisDingTime)
        self.DingPosition.append(DingPosition)
        state.Log("DING Time: %f Pos: %f" % (ThisDingTime, DingPosition))

    def PlusButtonClicked(self):
        """
        Plus button clicked when running
        """
        self.SetRun(state.State.RunLevel+1)

    def MinusButtonClicked(self):
        """
        Minus button clicked when running
        """
        self.SetRun(state.State.RunLevel-1)

    def ShowErrorMessage(self, icon, title, text, informative_text, button_text="OK"):
        """
        Display an error message that closes on a mouse press anywhere in the
        application window, on the dialog button, or after ERROR_TIMEOUT.

        The dialog is shown modeless and the method blocks on a local
        QEventLoop, rather than the application-modal QMessageBox.exec().  An
        application-modal dialog makes Qt discard mouse events sent to the main
        window, so clicks outside the dialog cannot dismiss it.  Showing
        modeless keeps the whole window live; the application-level
        DismissOnClick filter ends the loop on the first press anywhere.

        All objects here live on the GUI thread.  An earlier version started a
        pynput global mouse Listener and called MessageBox.accept() from that
        background thread, which is illegal in Qt: it produced
        'QObject::installEventFilter(): Cannot filter events for objects in a
        different thread' and, on Windows, ate the click on the button so
        'Restart' did nothing.

        :param icon: QMessageBox icon (e.g., QMessageBox.Icon.Critical)
        :param title: Window title
        :param text: Main message text
        :param informative_text: Detailed informative text
        :param button_text: Text for the OK button
        """
        MessageBox = QMessageBox(self)
        MessageBox.setIcon(icon)
        MessageBox.setText(text)
        MessageBox.setWindowTitle(title)
        MessageBox.setInformativeText(informative_text)
        MessageBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        ButtonOk = MessageBox.button(QMessageBox.StandardButton.Ok)
        ButtonOk.setText(button_text)

        # Modeless: keep the rest of the application window receiving input so a
        # click anywhere in it can dismiss the dialog.
        MessageBox.setModal(False)
        MessageBox.setWindowModality(Qt.WindowModality.NonModal)

        # Block here on our own loop instead of exec(), so caller flow is
        # unchanged while the dialog stays modeless.
        loop = QtCore.QEventLoop()

        # Auto-close after ERROR_TIMEOUT. Parent the timer to the dialog so it
        # lives on the GUI thread and is cleaned up with the dialog.
        timer = QtCore.QTimer(MessageBox)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(ERROR_TIMEOUT)  # 60 seconds

        # Button press / keyboard activation of the button also ends the loop.
        ButtonOk.clicked.connect(loop.quit)

        # First mouse press anywhere in the application ends the loop.
        dismiss = DismissOnClick(loop, self.NoteUserActivity)
        app = QApplication.instance()
        app.installEventFilter(dismiss)

        MessageBox.show()
        MessageBox.raise_()
        MessageBox.activateWindow()
        try:
            with self.SimSuspended():
                loop.exec()
        finally:
            app.removeEventFilter(dismiss)
            timer.stop()
            MessageBox.close()
        return QMessageBox.StandardButton.Ok


    def MainReset(self):
        """ 
        Reset to the starting position
        """
        global Mode
        global ModeId

        if (False):
            FrameList = inspect.getouterframes(inspect.currentframe())
            for AFrame in FrameList:
                print("DEBUG %s:%d(%s)" % (pathlib.Path(AFrame.filename).name, AFrame.lineno, AFrame.function))

        state.Log(f"MainReset: Mode {Mode.Name}")
        # Tell any Tick() further up the call stack that the world changed.
        self._ResetGeneration += 1
        Mode.TutorialCancel()   # Cancel any ongoing tutorial
        # Repeating sounds (the Central crossing bell, the pump, the brake
        # hiss) would otherwise carry on into the next run.
        sound.GlobalSound.StopAll()
        self.Video.Reset()
        self.ClickClackPos = CLICK_CLACK_DISTANCE

        self.Timer.stop()

        self.WarningList = []
        self.WarningLabel.setText("")
        for Event in Mode.Events:
            Event.Done = False

        self.DeadmanButton.setChecked(False)
        self.DeadmanGraphic.setChecked(False)

        self.SetRun(0)
        self.SetDirection(state.DirectionEnum.NEUTRAL)

        self.BrakeGraphics.MoveBrakeLever(state.BrakeEnum.APPLY)
        self.BrakeUi.SetBrake(state.BrakeEnum.APPLY)
        self.BrakeUi.BrakeReset()

        self.DingTime = []
        self.DingPosition = []
        self.Timer.start()

        # Suspended: the old Mode must not be ticked while the user is
        # choosing the new one.
        #
        # ModeId is cleared first and only a Start/Tutorial button sets it,
        # so if exec() ever ends without a choice (Esc is blocked in
        # SelectWindow.reject(), but hide() from elsewhere, a window-manager
        # quirk, etc.) we show the picker again instead of silently reusing
        # the previous run's mode.
        ModeId = None
        while ModeId is None:
            with self.SimSuspended():
                self.SelectWindow.exec()
            if ModeId is None:
                if not self.isVisible():
                    # The main window was closed underneath us (closeEvent
                    # calls QApplication.quit(), after which every new
                    # exec() returns at once).  Don't spin; finish exiting
                    # the same way SelectWindow.closeEvent() does.
                    state.Log("Main window closed during mode selection, exiting")
                    os._exit(0)
                state.Log("SelectWindow ended without a mode; showing it again")
        state.Log(f"Mode Selected {ModeId}")

        match (ModeId):
            case ModeEnum.EASY:
                Mode = EasyMode(False)
            case ModeEnum.EASY_TUTORIAL:
                Mode = EasyMode(True)
            case ModeEnum.START_STOP:
                Mode = StartStopMode(False)
            case ModeEnum.START_STOP_TUTORIAL:
                Mode = StartStopMode(True)
            case ModeEnum.FULL:
                Mode = FullMode(False)
            case ModeEnum.FULL_TUTORIAL:
                Mode = FullMode(True)
            case _:
                print("ERROR: Mode is unknown: ", Mode)
                sys.exit(8);

        self.ModeLabel.setText(Mode.Name)
        state.State.Reset()
        self.Video.SetRate(state.State.Speed)

        Mode.ModeReset()

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
        """
        Closing -- stop the tick timer, tear down mpv, and quit cleanly.

        Do NOT call sys.exit() here: raising SystemExit inside a Qt event
        handler is swallowed by PyQt on Windows, so the window never closes.
        Accept the event and let app.exec() return instead.
        """
        try:
            self.Timer.stop()
        except Exception:
            pass
        try:
            self.Video.Stop()
        except Exception:
            pass
        if getattr(self, "AttractPlayer", None) is not None:
            try:
                self.AttractPlayer.Shutdown()
            except Exception:
                pass
        if getattr(self, "CommandPipe", None) is not None:
            try:
                self.CommandPipe.shutDown()
            except Exception:
                pass
            self.CommandPipe = None     # closeEvent can run twice (Ctrl-C)
        event.accept()
        QtWidgets.QApplication.quit()

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
        MessageBox.setIcon(QMessageBox.Icon.Critical)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>You made some mistakes</B></H1>")
        MessageBox.setWindowTitle("Warnings")
        Message = "Warning:\n"
        for Index in range(len(self.WarningList)):
            Message += "%2d: %s\n" % (Index+1, self.WarningList[Index])
        MessageBox.setInformativeText(Message)
        MessageBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        ButtonOk = MessageBox.button(QMessageBox.StandardButton.Ok)
        ButtonOk.setText("Continue")
        with self.SimSuspended():
            MessageBox.exec()

    def ErrorDeadman(self):
        """
        You tried to run without setting the deadman
        """
        state.Log("ErrorDeadman")
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Deadman not engaged",
            "<H1 ALIGN=\"CENTER\"><B>Deadman not engaged</B></H1>",
            """<HTML>
<BODY>
<P>
The deadman must be pressed (or clicked) 
at all times while the trolley is moving.   
<P>
If it is released the trolley performs an emergency stop.
<P>
The deadman is located in the lower left corner.

<TABLE>
<TR><TD><IMG SRC="image/dead-off.png" height="100"></TD><TD><IMG SRC="image/dead-on.png" height=100></TD></TR>
<TR><TD>Wrong</TD><TD>Right</TD></TR>
</TABLE>
""",
            "Restart"
        )

    def SetDirection(self, Direction):
        """
        Change the direction we are going

        Parameters:
            :arg Direction; Direction for the reverser
        """
        global Mode

        if ((state.State.RunLevel != 0) and (Direction != state.DirectionEnum.FORWARD)):
            self.ErrorReverserMoved()
            Direction = state.DirectionEnum.FORWARD
            
        self.ControllerGraphics.SetReverse(Direction)
        self.ControllerButtons.SetReverse(Direction)

        state.State.Direction = Direction
        Mode.ModeSetDirection(Direction)

    def NoticeDone(self):
        """
        Display the information message that you completed the course
        """
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Icon.Information)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Congratulations: The run is complete</B></H1>")
        MessageBox.setWindowTitle("Finished")
        MessageBox.setInformativeText("""You've made it around the loop.

Press "Restart" to start another run""")
        MessageBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        ButtonOk = MessageBox.button(QMessageBox.StandardButton.Ok)
        ButtonOk.setText("Restart")
        with self.SimSuspended():
            MessageBox.exec()

    def GoodStop(self):
        """
        The player stopped at the correct position at the store
        """
        MessageBox = QMessageBox()
        MessageBox.setIcon(QMessageBox.Icon.Information)
        MessageBox.setText("<H1 ALIGN=\"CENTER\"><B>Congratulations: The run is complete</B></H1>")
        MessageBox.setWindowTitle("Finished")
        MessageBox.setInformativeText("""You've made it around the loop.

And you stopped back at the store.
Press "Restart" to start another run""")
        MessageBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        ButtonOk = MessageBox.button(QMessageBox.StandardButton.Ok)
        ButtonOk.setText("Restart")
        with self.SimSuspended():
            MessageBox.exec()

    def ErrorStart(self):
        """ 
        Handle all the stuff you need at the beginning of an error message
        """
        state.State.Acceleration = 0
        state.State.Speed = 0
        self.Video.SetRate(state.State.Speed)
        state.Log("Speed %f" % state.State.Speed)

    def ErrorMessageRun4(self):
        """
        Display the error message indicating that we exceeded the run limit
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Speed Limit Exceeded",
            "<H1 ALIGN=\"CENTER\"><B>Speed limit exceeded</B></H1>",
            """This is not a high speed trolley.
The loop line speed limit is 15mph.
It is not possible to use the controller at settings "Run-4" or above

Please try again, only slower""",
            "Restart"
        )

    def ErrorRunTooLong(self):
        """
        Display the error message when we stay in a run_x too long
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Overheated Resisters",
            "<H1 ALIGN=\"CENTER\"><B>Overheated Resisters</B></H1>",
            """You stayed in Run-%d too long.

The resister pack overheated.  

You can only stay in Run-%d for %d seconds.
""" % (state.State.RunLevel, state.State.RunLevel, MAX_RUN_TIME),
            "OK"
        )

    def ErrorRunTooLongDown(self):
        """
        Display the error message when we stay in a run_x too long on the way down
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Electrical Overload",
            "<H1 ALIGN=\"CENTER\"><B>Electrical Overload</B></H1>",
            """Going from Run-x to idle should be done
as quickly as possible.   Failure to do so causes the motors to act as
generators and create feedback which can damage the trolley.

So slam that controller back to idle and avoid this problem.
""",
            "OK"
        )

    def ErrorNoForward(self):
        """
        Display the error message we should be in forward before starting
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Reverser not set",
            "<H1 ALIGN=\"CENTER\"><B>Reverser not set</B></H1>",
            """You must select "Forward" on the reverser
before moving.

Controller has been reset to Run-0

Please set direction and try again.""",
            "OK"
        )

    def ErrorMoveWithBrakesOn(self):
        """
        Display the error message indicating that you can't run with the brakes on
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Move with brakes on",
            "<H1 ALIGN=\"CENTER\"><B>Attempt to move with brakes set</B></H1>",
            """The brakes and the motor should never be on at the same time.

Set the controller to "Run-0" before applying the brakes.
Release the brakes before entering "Run-1".

Simulation will now reset.
""",
            "OK"
        )

    def ErrorReverserMoved(self):
        """
        Display the error message indicating the reverser moved while car in motion
        """
        self.ErrorStart()
        self.ShowErrorMessage(
            QMessageBox.Icon.Critical,
            "Reverser move while car in motion",
            "<H1 ALIGN=\"CENTER\"><B>Reverser moved while car in motion</B></H1>",
            """You cannot change the reverser while the trolley is in motion.

Reverser has been returned to "Forward"

Press OK to continue""",
            "OK"
        )

    def SetRun(self, Level):        # Window
        """
        Used to change the run level.

        :param: Level the level to use

        :returns: True if we should continue our journey
        """
        global Mode

        state.Log("SetRun %d" % Level)
        if (Level > MAX_LEVEL):
            Level = MAX_LEVEL

        if (Level < 0):
            Level = 0

        self.ControllerGraphics.SetControllerRun(Level)
        self.ControllerButtons.SetControllerRun(Level)

        if (state.State.RunLevel != Level):
            if (MAX_SPEED[Level] < 0):
                self.ErrorMessageRun4()
                self.MainReset()
                return False

        KeepGoing = Mode.ModeSetRun(Level)
        
        if (not KeepGoing):
            state.State.Acceleration = 0
            state.State.Speed = 0
            self.Video.SetRate(state.State.Speed)
            state.Log("Speed %f" % state.State.Speed)
            return False

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
            f -- Toggle fullscreen
        """
        global FullScreen

        if (event.key() == ord('X')):
            self.BrakeUi.BrakeLapClicked()
            self.BrakeUi.RedPressure += 10.0
            if (self.BrakeUi.RedPressure > brake_ui.MAX_RED_PRESSURE):
                self.BrakeUi.RedPressure = brake_ui.MAX_RED_PRESSURE
            state.Log("DEBUG: 10 pound set %f" % self.BrakeUi.RedPressure)
        elif (event.key() == ord('M')):
            print("Mark Position %.2f" % self.Video.GetPosition())
            state.Log("Mark Position: %.2f" % self.Video.GetPosition())
        elif ((event.key() >= ord('0')) and (event.key() <= ord('8'))):
            RunLevel = event.key() - ord('0')
            self.ControllerGraphics.SetControllerRun(RunLevel)
        elif (event.key() == ord('F')):
            FullScreen = not FullScreen
            if (FullScreen):
                self.showFullScreen()
            else:
                self.showNormal()
                self.showMaximized()


def Usage():
    """ 
    Tell user what to do
    """
    print("""Usage is:
python3 main.py [-b<bottom>] [-t<top>] [-l<left>] [-r<right>] [-d] [-v] [-f] [-a] [-s<count>]

Where
        -b <bottom> -- Set bottom margin
        -t <top> -- Set top margin
        -l <left> -- Set left margin
        -r <right> -- Set right margin
        -d -- Debug (show button bar)
        -v -- Verbose
        -f -- Start in full screen
        -a -- Enable attract mode
        -s<count> -- Skip <count>-1 frames, then display 1 (faster video)
        -p<pointer-type> -- One of "touchscreen", "trackpad", "mouse"
    """)
    sys.exit(8)

def HandleSigInt(signum, frame):
    """
    Let Ctrl-C in the terminal shut the program down.

    Qt's C++ event loop doesn't reliably let Python's default SIGINT
    handling (raising KeyboardInterrupt) interrupt app.exec(); even when
    it does fire on a timer tick, PyQt6 just reports the exception via
    sys.excepthook and keeps running, so Ctrl-C would otherwise appear to
    do nothing. Route it through MainWindow.close() for its normal
    cleanup (timer stop, mpv teardown) -- then force the process to
    actually end, rather than trusting QApplication.quit() alone.

    QApplication.quit() only asks the *currently running* Qt event loop
    to stop. If Ctrl-C lands while a nested modal dialog is running --
    e.g. MainReset()'s self.SelectWindow.exec() -- quit() ends that
    dialog's loop instead of the outer app.exec(). MainReset() then just
    carries on as if a mode had been picked (reconstructing a fresh Mode
    from the stale ModeId), while the timer and video are already stopped
    from closeEvent(): the app is left half-alive instead of exiting.
    os._exit() sidesteps this entirely by ending the process outright
    once cleanup has had its chance to run.

    :param signum: Signal number (unused, required by signal.signal())
    :param frame: Current stack frame (unused, required by signal.signal())
    """
    global MainWindow
    state.Log("Caught SIGINT (Ctrl-C), shutting down")
    if MainWindow is not None:
        try:
            MainWindow.close()
        except Exception:
            pass
    os._exit(0)

if __name__ == "__main__":
    global MainWindow, Mode
    MainWindow = None
    Mode = None
    ModeId = ModeEnum.EASY_TUTORIAL

    try:
        opts, args = getopt.getopt(sys.argv[1:], "b:t:l:r:dvfas:p:")
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        Usage()

    ShowButtons = False
    for Option, Arg in opts:
        if Option == "-b":
            BottomMargin = int(Arg)
        elif Option == "-t":
            TopMargin = int(Arg)
        elif Option == "-l":
            LeftMargin = int(Arg)
        elif Option == "-r":
            RightMargin = int(Arg)
        elif Option == "-d":
            ShowButtons = True
        elif Option == "-v":
            Verbose = True
        elif Option == "-f":
            FullScreen = True
        elif Option == '-a':
            AttractEnable = True
        elif Option == '-s':
            SkipCount = int(Arg)
        elif Option == '-p':
            match (Arg):
                case 'mouse':
                    PointerType = PointerEnum.MOUSE
                case 'trackpad':
                    PointerType = PointerEnum.TRACKPAD
                case 'touchscreen':
                    PointerType = PointerEnum.TOUCHSCREEN
                case _:
                    print("ERROR: Pointer type (-p) must be one of 'mouse', 'trackpad', or 'touchscreen'")
                    sys.exit(8)
        else:
            print("unhandled option:", Option)
            Usage()

    sound.Init(DIR)

    # mpv wid-based embedding requires X11; force xcb on Linux so it works under Wayland too.
    if IS_LINUX:
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

    # Nested QOpenGLWidget (mpv video on macOS) needs shared GL contexts,
    # otherwise it paints one frame and then stops compositing.
    QtWidgets.QApplication.setAttribute(
        QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
    )
    app = QtWidgets.QApplication(sys.argv)  #pylint: disable=I1101

    # Must be installed after QApplication() exists (it can reset signal
    # handling during construction on some platforms), and before app.exec()
    # so Ctrl-C in the terminal actually shuts the program down cleanly.
    signal.signal(signal.SIGINT, HandleSigInt)

    # PyInstaller's bootloader splash screen is NOT supported on macOS: it runs
    # in a secondary thread, and macOS forbids UI work off the main thread, so
    # PyInstaller refuses to build a Splash() into the .app bundle. Instead, on
    # macOS we show a Qt-native QSplashScreen on the main thread. It stays up
    # during the slow Window() construction below and is dismissed once the main
    # window is ready (see mac_splash.finish() further down).
    if (False): # Buggy code
        mac_splash = None
        if IS_MAC:
            splash_path = os.path.join(DIR, 'image', 'splash.png')
            if os.path.exists(splash_path):
                mac_splash = QtWidgets.QSplashScreen(
                    QPixmap(splash_path),
                    QtCore.Qt.WindowType.WindowStaysOnTopHint,
                )
                mac_splash.show()
                app.processEvents()   # force it to paint before the slow startup work

    state.Init()
    MainWindow = Window(app)
    if (FullScreen):
        MainWindow.showFullScreen()
    else:
        #MainWindow.showNormal()
        MainWindow.showMaximized()
    MainWindow.MainReset()


    # There is no splash screen on macOS: PyInstaller can't build a bootloader
    # splash there, so we don't import pyi_splash on macOS (doing so would emit
    # the "environment does not allow connecting to the splash screen" warning
    # and a KeyError traceback for the missing _PYI_SPLASH_IPC).
    if not IS_MAC and '_PYI_APPLICATION_HOME_DIR' in os.environ:
        # Windows/Linux frozen build: close the PyInstaller bootloader splash.
        # Guard the import so a missing pyi_splash module can never crash startup.
        try:
            import pyi_splash
            # Close the splash screen. It does not matter when the call
            # to this function is made, the splash screen remains open until
            # this function is called or the Python program is terminated.
            pyi_splash.close()
        except (ImportError, ModuleNotFoundError):
            pass

    # this will remove minimized status
    # and restore window with keeping maximized/normal state
    MainWindow.setWindowState(MainWindow.windowState() & ~QtCore.Qt.WindowState.WindowMinimized | QtCore.Qt.WindowState.WindowActive)

    # this will activate the window
    MainWindow.activateWindow()
    MainWindow.Video.Reset()
    MainWindow.raise_()
    state.Log("New run----------------------------------------------------------------")

    app.exec()
    sys.exit(0)
