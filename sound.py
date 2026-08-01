"""
Handle all sound related activities
"""
import playsound3
import enum
import state
import os
import threading
import time

global GlobalSound
GlobalSound = None        # The sound playing class (singleton)

# List of sounds
# Must match SoundFiles below
class SoundEnum(enum.IntEnum):
    BELL = 0
    NOT_USED1 = 1
    NOT_USED2 = 2
    APPLY = 3
    EMERGENCY = 4
    PUMP_UP = 5
    RELEASE = 6
    NOT_USED3 = 7
    CLICK_CLACK = 8
    CENTRAL_BELL = 9
    ZORCH = 10

class PlaySoundClass:
    def __init__(self, BaseDir):
        """ 
        Create a sound playing class for all our sounds

        Args:
            BaseDir -- Dir in which the application resides
        """
        self.BaseDir = BaseDir
        # Must match SoundEnum above
        self.SoundFiles = ( 
                "trolley-bell.mp3",     # 0
                "NOT_USED",             # 1
                "NOT_USED",             # 2
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
        self.StopFlag = []
        self.SoundObjects = []
        
        for Index in range(len(self.SoundFiles)):
            self.Players.append(None)
            self.StopFlag.append(False)
            self.SoundObjects.append(None)

    def PlaySound(self, Sound, Repeat):
        """
        Thread to actually play the given sound

        Args:
            Sound -- Sound to play enum
            Repeat -- Repeat the sound
        """
        while not self.StopFlag[Sound]:
            self.SoundObjects[Sound] = playsound3.playsound(os.path.join(self.BaseDir, 'mp3', self.SoundFiles[Sound]), block=False)
            self.SoundObjects[Sound].wait()
            if not Repeat:
                break
        self.SoundObjects[Sound] = None
        
    def Play(self, Sound, Repeat):
        """
        Play the given sound

        Parameters
            Sound -- Sound to play enum
            Repeat -- If true, play forever
        """
        state.Log("Start Sound %s Repeat %r " % (Sound.name, Repeat))
        
        # Bell is special.  We let it repeat
        if Sound != SoundEnum.BELL:
            if self.Players[Sound] is not None:
                if (self.Players[Sound].is_alive()):
                    return
        
        # Skip NOT_USED sounds
        if self.SoundFiles[Sound] == "NOT_USED":
            return

        self.StopFlag[Sound] = False
        self.Players[Sound] = threading.Thread(target=self.PlaySound, args=(Sound,Repeat,), daemon=True)
        self.Players[Sound].start()

    def Stop(self, Sound, Quick):
        """
        Stop the given sound

        Parameters
             Sound -- Sound to stop enum
             Quick -- Shut down sound even if playing
        """
        state.Log("Stop Sound %s" % Sound)
        self.StopFlag[Sound] = True
        if (Quick):
            if (self.SoundObjects[Sound] is not None):
                self.SoundObjects[Sound].stop()
        
def Init(BaseDir):
    """ 
    Initialize the sound system

    Args:
        BaseDir -- Dir in which the application resides
    """
    global GlobalSound

    GlobalSound = PlaySoundClass(BaseDir)

def Main():
    global GlobalSound

    Init(os.getcwd())
    print("Bell")
    GlobalSound.Play(SoundEnum.BELL, False)
    time.sleep(5)
    print("Bell")
    GlobalSound.Play(SoundEnum.BELL, False)
    time.sleep(0.1)
    print("Bell")
    GlobalSound.Play(SoundEnum.BELL, False)
    time.sleep(0.1)
    print("Bell")
    GlobalSound.Play(SoundEnum.BELL, False)
    time.sleep(5)
    print("Bell/repeat")
    GlobalSound.Play(SoundEnum.BELL, True)
    time.sleep(10)
    print("Stop")
    GlobalSound.Stop(SoundEnum.BELL)
    time.sleep(10)

if __name__ == "__main__":
    Main()

