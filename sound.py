"""
Handle all sound related activities
"""
import vlc
import enum
import state

PlaySound = None        # The sound playing class (signleton)
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

def SoundEventHandler(Event, PlayerClass, Index):
    """
    Handle a sound end event.

    Event -- Event to handle (not used)
    PlayerClass -- The player singleton
    Index -- Sound that stopped us
    """
    PlayerClass.Players[Index] = None
    PlayerClass.Running[Index] = False
    PlayerClass.Stop(Index)
    if (PlayerClass.Repeat[Index]):
        state.Log("Sound %r Repeat %r" % (SoundEnum(Index), Repeat))
        PlayerClass.Play(Index, True);

class PlaySoundClass:
    def __init__(self):
        """ 
        Create a sound playing class for all our sounds
        """
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
        for Index in range(len(self.SoundFiles)):
            self.Repeat.append(False)
            self.Running.append(False)
            self.Players.append(None)
        self.Instance = vlc.Instance()

    def Play(self, Sound, Repeat):
        """
        Play the given sound

        Parameters
            Sound -- Sound to play enum
            Repeat -- If true, play forever
        """
        state.Log("Start Sound %s Repeat %r Running %r" % (Sound.name, Repeat, self.Running[Sound]))
        if (self.Running[Sound]):
            return

        if (self.Players[Sound] is None):
            Media = self.Instance.media_new(self.SoundFiles[Sound])

            self.Players[Sound] = self.Instance.media_player_new()
            self.Players[Sound].set_media(Media)
            self.Players[Sound].audio_set_mute(False)
            self.Players[Sound].audio_set_volume(100)
            self.Players[Sound].event_manager().event_attach(
                vlc.EventType.MediaPlayerEndReached, SoundEventHandler, self, Sound) 

        self.Running[Sound] = True
        self.Repeat[Sound] = Repeat

        self.Players[Sound].set_position(0)
        self.Players[Sound].play()

    def Stop(self, Sound):
        """
        Stop the given sound

        Parameters
             Sound -- Sound to stop enum
        """
        state.Log("Stop Sound %s" % Sound.name)
        if (self.Players[Sound] is not None):
            self.Players[Sound].stop()
        self.Players[Sound] = None
        self.Repeat[Sound] = False
        self.Running[Sound] = False

def Init():
    """ 
    Initialize the sound system

    """
    global PlaySound

    PlaySound = PlaySoundClass()

