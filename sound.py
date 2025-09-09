"""
Handle all sound related activities
"""
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import enum
import state
import os
import threading

PlaySound = None        # The sound playing class (singleton)

# List of sounds
# Must match SoundFiles below
class SoundEnum(enum.IntEnum):
    BELL1 = 0,
    BELL2 = 1,
    BELL3 = 2,
    APPLY = 3,
    EMERGENCY = 4,
    PUMP_UP = 5,
    RELEASE = 6,
    NOT_USED = 7,
    CLICK_CLACK = 8,
    CENTRAL_BELL = 9,
    ZORCH = 10

def SoundEventHandler(bus, message, PlayerClass, Index):
    """
    Handle GStreamer bus messages for sound events.

    bus -- GStreamer bus
    message -- GStreamer message
    PlayerClass -- The player singleton
    Index -- Sound index
    """
    if message.type == Gst.MessageType.EOS:
        # End of stream - sound finished playing
        PlayerClass.Running[Index] = False
        PlayerClass.Players[Index].set_state(Gst.State.NULL)
        
        if PlayerClass.Repeat[Index]:
            state.Log("Sound %r Repeat %r" % (SoundEnum(Index), PlayerClass.Repeat[Index]))
            PlayerClass.Play(Index, True)
        else:
            PlayerClass.Stop(Index)
    
    elif message.type == Gst.MessageType.ERROR:
        # Handle errors
        err, debug = message.parse_error()
        state.Log("GStreamer Error for sound %d: %s" % (Index, err))
        PlayerClass.Running[Index] = False
        PlayerClass.Stop(Index)
    
    return True

class PlaySoundClass:
    def __init__(self):
        """ 
        Create a sound playing class for all our sounds
        """
        # Initialize GStreamer
        Gst.init(None)
        
        # Must match SoundEnum above
        self.SoundFiles = ( 
                "trolley-bell.mp3",     # 0
                "trolley-bell.mp3",     # 1
                "trolley-bell.mp3",     # 2
                "apply.mp3",            # 3
                "emergency.mp3",        # 4
                "pump-up-sound.mp3",    # 5
                "release.mp3",          # 6
                "NOT_USED",             # 7
                "click-clack.mp3",      # 8
                "central-bell.mp3",     # 9
                "electric-155027.mp3"   # 10 (zorch)
                )
        
        self.Players = []
        self.Repeat = []
        self.Running = []
        self.Buses = []
        
        for Index in range(len(self.SoundFiles)):
            self.Repeat.append(False)
            self.Running.append(False)
            self.Players.append(None)
            self.Buses.append(None)

    def Play(self, Sound, Repeat):
        """
        Play the given sound

        Parameters
            Sound -- Sound to play enum
            Repeat -- If true, play forever
        """
        state.Log("Start Sound %s Repeat %r Running %r" % (Sound.name, Repeat, self.Running[Sound]))
        
        if self.Running[Sound]:
            return
        
        # Skip NOT_USED sounds
        if self.SoundFiles[Sound] == "NOT_USED":
            return

        # Create pipeline if it doesn't exist
        if self.Players[Sound] is None:
            # Get absolute path for the sound file
            sound_file = os.path.abspath(self.SoundFiles[Sound])
            file_uri = "file://" + sound_file
            
            # Create playbin pipeline
            self.Players[Sound] = Gst.ElementFactory.make("playbin", f"player_{Sound}")
            if not self.Players[Sound]:
                state.Log("Error: Could not create playbin for sound %s" % Sound.name)
                return
            
            # Set the URI
            self.Players[Sound].set_property("uri", file_uri)
            
            # Set volume (1.0 = 100%)
            self.Players[Sound].set_property("volume", 1.0)
            
            # Get the bus and add a watch
            self.Buses[Sound] = self.Players[Sound].get_bus()
            self.Buses[Sound].add_watch(GLib.PRIORITY_DEFAULT, 
                                      lambda bus, msg, pc=self, idx=Sound: SoundEventHandler(bus, msg, pc, idx))

        self.Running[Sound] = True
        self.Repeat[Sound] = Repeat

        # Seek to beginning and play
        self.Players[Sound].seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        self.Players[Sound].set_state(Gst.State.PLAYING)

    def Stop(self, Sound):
        """
        Stop the given sound

        Parameters
             Sound -- Sound to stop enum
        """
        state.Log("Stop Sound %s" % Sound.name)
        
        if self.Players[Sound] is not None:
            self.Players[Sound].set_state(Gst.State.NULL)
        
        self.Repeat[Sound] = False
        self.Running[Sound] = False

    def Cleanup(self):
        """
        Clean up all GStreamer resources
        """
        for Sound in range(len(self.SoundFiles)):
            if self.Players[Sound] is not None:
                self.Stop(Sound)
                self.Players[Sound] = None
                self.Buses[Sound] = None

def Init():
    """ 
    Initialize the sound system
    """
    global PlaySound

    PlaySound = PlaySoundClass()

def Cleanup():
    """
    Clean up the sound system
    """
    global PlaySound
    
    if PlaySound is not None:
        PlaySound.Cleanup()
        PlaySound = None