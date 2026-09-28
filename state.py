#
# Copyright 2024 by Steve Oualline
# Licensed under the GNU Public License (GPL)
#
import enum
import inspect
import pathlib
import datetime
import platform
import sys
import os
import time

class DirectionEnum(enum.Enum):
    FORWARD = 0         # Direction is forward
    NEUTRAL = 1         # Direction is neutral
    REVERSE = 2         # Direction is reverse

class BrakeEnum(enum.Enum):
    APPLY = 0         # Brake is in apply
    RELEASE = 1       # Brake is in release
    LAP = 2           # Brake is in lap
    EMERGENCY = 3     # Brake is in emergency

class TrolleyState:
    """
    The current state of the trolley

    RunLevel -- Current run level
    Reverser -- Reverser position
    Deadman -- Deadman on or off

    Speed -- Current speed
    Acceleration -- Current acceleration
    """
    def Reset(self):
        self.RunLevel = 0       # Current run level
        # Neutral, matching what MainReset() draws.  This used to be
        # FORWARD: the screen showed the reverser in Neutral while the rules
        # saw Forward, so the "must be in Forward" check never fired.
        self.Direction = DirectionEnum.NEUTRAL   # Reverser position
        self.Deadman = False    # Deadman on or off

        self.Speed = 0.0        # Current speed
        self.Acceleration = 0   # Current acceleration from motor
        self.BrakeAcceleration = 0   # Current acceleration from braking
        self.BrakeValvePosition = BrakeEnum.APPLY
        
class SimClock:
    """
    The simulation's clock: seconds that stop counting while the
    simulation is frozen.

    Every blocking dialog freezes the simulation (Window.SimSuspended() in
    main.py), but wall-clock time kept running.  A student who spent more
    than MAX_RUN_TIME reading a modal tutorial popup while in Run-N got
    "ran too long" on the very next tick, and the bell-signal timings were
    skewed the same way.  Rule timing uses this clock instead.

    Based on time.monotonic(), so it also can't jump if the system clock
    is changed (NTP, daylight saving) during a run.

    Pause()/Resume() nest: only the outermost pair stops and starts the
    clock.
    """
    def __init__(self):
        self._PausedTotal = 0.0     # Seconds spent paused, completed pauses
        self._PauseStart = None     # time.monotonic() when current pause began
        self._Depth = 0             # Pause() nesting depth

    def Now(self):
        """
        Current simulation time in seconds.  Only differences between two
        readings are meaningful.
        """
        Real = time.monotonic()
        Paused = self._PausedTotal
        if self._PauseStart is not None:
            Paused += Real - self._PauseStart
        return Real - Paused

    def Pause(self):
        """Stop the clock (nestable)."""
        self._Depth += 1
        if self._Depth == 1:
            self._PauseStart = time.monotonic()

    def Resume(self):
        """Undo one Pause(); the clock runs again when the last one is undone."""
        if self._Depth == 0:
            return
        self._Depth -= 1
        if self._Depth == 0:
            self._PausedTotal += time.monotonic() - self._PauseStart
            self._PauseStart = None

# Created at import time, so it exists before anything can ask for the time.
Clock = SimClock()

def SimTime():
    """Current simulation time in seconds (see SimClock)."""
    return Clock.Now()

def Init():
    """
    Initialize the module
    """
    global State
    State = TrolleyState()

LogFile = None          # File to log to

def Log(Message):
    """
    Write a message to the log file

    :param Message: Message to write
    """
    global LogFile

    if (LogFile is None):
        if platform.system() == "Linux": # for Linux using the X Server
            LogFile = open("/tmp/trolley.log", "a", buffering=1)
        elif platform.system() == "Windows": # for Windows
            if "TEMP" in os.environ:
                LogFile = open(os.path.join(os.environ["TEMP"], "trolley.log"), "a", buffering=1)
            else:
                print("ERROR: No 'TEMP' environment variable")
                sys.exit(99)
        elif platform.system() == "Darwin": # for MacOS
            LogFile = open("/tmp/trolley.log", "a", buffering=1)
        else:
            print("ERROR: Unknown platform: %s" % platform.system())
            sys.exit(99)

    FrameList = inspect.getouterframes(inspect.currentframe())
    LogFile.write("%s:%s:%d(%s) %s\n" % (datetime.datetime.now(), 
        pathlib.Path(FrameList[1].filename).name, FrameList[1].lineno, FrameList[1].function,
        Message))
