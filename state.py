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

    BrakeValve  -- Brake valve position
    RunLevel -- Current run level
    Reverser -- Reverser position
    Deadman -- Deadman on or off

    Speed -- Current speed
    Acceleration -- Current acceleration
    """
    def Reset(self):
        self.BrakeValve = BrakeEnum.APPLY  # Brake valve position
        self.RunLevel = 0       # Current run level
        self.Reverser = DirectionEnum.FORWARD   # Reverser position
        self.Deadman = False    # Deadman on or off

        self.Speed = 0          # Current speed
        self.Acceleration = 0   # Current acceleration from motor
        self.BrakeAcceleration = 0   # Current acceleration from braking
        self.BrakeValvePosition = BrakeEnum.APPLY
        
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
            if (os.environ["TEMP"] != None):
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
