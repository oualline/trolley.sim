"""
Module to handle the playing of video

Currently uses VLC for video output
"""
import time

import vlc
import platform

import state

class Video:
    def __init__(self, MainWindow, VideoFile):
        """
        Create video player

        Args:
            MainWindow -- Window in which we display the stuff
            VideoFile -- Video file to play
        """
        #-----------------------------------------------------------
        # Setup video player
        #-----------------------------------------------------------
        self.VideoFile = VideoFile
        self.Instance = vlc.Instance()  # Create an instance of the player
        self.MediaPlayer = self.Instance.media_player_new()
        self.MediaPlayer.audio_output_device_set("adummy", "/dev/null")
        self.MediaPlayer.audio_set_mute(True)

        if platform.system() == "Linux": # for Linux using the X Server
            self.MediaPlayer.set_xwindow(int(MainWindow.VideoFrame.winId()))
        elif platform.system() == "Windows": # for Windows
            self.MediaPlayer.set_hwnd(int(MainWindow.VideoFrame.winId()))
        elif platform.system() == "Darwin": # for MacOS
            self.MediaPlayer.set_nsobject(int(MainWindow.VideoFrame.winId()))

    def Reset(self):
        """
        Reset the video
        """
        self.Media = self.Instance.media_new(self.VideoFile)
        self.MediaPlayer.set_media(self.Media)
        self.Media.parse()

        self.MediaPlayer.audio_set_volume(0)
        state.Log("Reset: Pause")
        self.MediaPlayer.pause()
        self.MediaPlayer.set_rate(1.0)
        self.MediaPlayer.play()
        state.Log("Reset: Play")
        time.sleep(0.01)
        state.Log("Reset: Pause")
        self.MediaPlayer.pause()
        
    def SetRate(self, Rate):
        """
        Tell video player we are going at a different speed.

        Args:
            Rate -- Rate to play the video at
        """
        if (Rate < 0):
            Rate = 0.0
        self.MediaPlayer.set_rate(Rate)
        if ((self.MediaPlayer.get_state() != vlc.State.Playing) and \
                    (state.State.Speed > 0.0)):
            state.Log("MediaPlayer.play()")
            Result = self.MediaPlayer.play()

        elif ((self.MediaPlayer.get_state() == vlc.State.Playing) and \
                    (state.State.Speed <= 0.0)):
            state.Log("MediaPlayer.pause()")
            Result = self.MediaPlayer.pause()

    def GetPosition(self):
        """
        Return the position of the video as a fraction of the total video
        """
        return (self.MediaPlayer.get_position())

    def SetPosition(self, Position):
        """
        Set the position of the video as a fraction of the total video

        Args:
            Position -- Position from 0.0 to 1.0
        """
        self.MediaPlayer.set_position(Position)

    def IsPlaying(self):
        """
        Is the video playing.
        ##Check for use
        """
        return (self.MediaPlayer.get_state() == vlc.State.Playing)
