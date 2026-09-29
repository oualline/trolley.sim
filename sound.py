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
        
        self.Players = []           # Thread playing each sound (latest one for BELL)
        self.StopFlag = []          # Set to ask a sound's thread to finish
        self.SoundObjects = []      # Set of playsound3 objects now playing
                                    # (more than one only for the bell)

        for Index in range(len(self.SoundFiles)):
            self.Players.append(None)
            self.StopFlag.append(False)
            self.SoundObjects.append(set())

        # Guards Players, StopFlag and SoundObjects.  They are shared between
        # the GUI thread (Play/Stop) and the playback threads (PlaySound).
        # Never held while waiting for a clip to finish.
        self._Lock = threading.Lock()

    def PlaySound(self, Sound, Repeat):
        """
        Thread to actually play the given sound

        Args:
            Sound -- Sound to play enum
            Repeat -- Repeat the sound
        """
        FileName = os.path.join(self.BaseDir, 'mp3', self.SoundFiles[Sound])
        Obj = None
        try:
            while True:
                with self._Lock:
                    if self.StopFlag[Sound]:
                        break
                    Obj = playsound3.playsound(FileName, block=False)
                    self.SoundObjects[Sound].add(Obj)
                Obj.wait()                      # Outside the lock
                with self._Lock:
                    self.SoundObjects[Sound].discard(Obj)
                Obj = None
                if not Repeat:
                    break
        except Exception as Error:
            # A missing file or a broken audio backend should cost us the
            # sound, not leave a half-dead thread and a stale SoundObjects
            # entry behind.
            state.Log("Sound %s failed: %s" % (Sound.name, Error))
        finally:
            if Obj is not None:
                with self._Lock:
                    self.SoundObjects[Sound].discard(Obj)

    def Play(self, Sound, Repeat):
        """
        Play the given sound

        Parameters
            Sound -- Sound to play enum
            Repeat -- If true, play forever
        """
        state.Log("Start Sound %s Repeat %r " % (Sound.name, Repeat))

        # Skip NOT_USED sounds
        if self.SoundFiles[Sound] == "NOT_USED":
            return

        with self._Lock:
            # Bell is special.  We let it overlap itself.
            if Sound != SoundEnum.BELL:
                Player = self.Players[Sound]
                if (Player is not None) and Player.is_alive():
                    # Already playing.  If a Stop() is pending (the thread
                    # is finishing its current clip), cancel it so the sound
                    # carries on instead of going silent until the old
                    # thread exits and a later Play() starts a new one.
                    self.StopFlag[Sound] = False
                    return

            self.StopFlag[Sound] = False
            self.Players[Sound] = threading.Thread(
                target=self.PlaySound, args=(Sound, Repeat,), daemon=True)
            self.Players[Sound].start()

    def Stop(self, Sound, Quick):
        """
        Stop the given sound

        Parameters
             Sound -- Sound to stop enum
             Quick -- Shut down sound even if playing
        """
        state.Log("Stop Sound %s" % Sound.name)
        with self._Lock:
            self.StopFlag[Sound] = True
            # Take a snapshot under the lock.  The playback threads remove
            # clips as they finish; the old code checked the entry and then
            # used it, so a clip ending in between meant calling .stop() on
            # None.  (For the bell, this stops every overlapping ding.)
            Playing = list(self.SoundObjects[Sound])
        if Quick:
            for Obj in Playing:
                try:
                    Obj.stop()
                except Exception as Error:
                    state.Log("Stop sound %s failed: %s" % (Sound.name, Error))

    def StopAll(self):
        """
        Stop every sound immediately.

        For resets: a repeating sound (the Central crossing bell, the pump,
        the brake hiss) would otherwise keep going into the next run.
        """
        for Sound in SoundEnum:
            if self.SoundFiles[Sound] != "NOT_USED":
                self.Stop(Sound, True)

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
    GlobalSound.Stop(SoundEnum.BELL, True)
    time.sleep(10)

if __name__ == "__main__":
    Main()

