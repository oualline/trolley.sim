"""
Module to handle the playing of video

Uses QMediaPlayer for video output

API Documentation References:
- QMediaPlayer: https://doc.qt.io/qt-5/qmediaplayer.html
- QMediaContent: https://doc.qt.io/qt-5/qmediacontent.html
- QVideoWidget: https://doc.qt.io/qt-5/qvideowidget.html
- QUrl: https://doc.qt.io/qt-5/qurl.html
"""
import time

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl

import state


class Video:
    def __init__(self, MainWindow, VideoFile):
        """
        Create video player using Qt's QMediaPlayer
        
        QMediaPlayer API: https://doc.qt.io/qt-5/qmediaplayer.html
        QVideoWidget API: https://doc.qt.io/qt-5/qvideowidget.html

        Args:
            MainWindow -- Window in which we display the video
                         MainWindow.VideoFrame must be a QVideoWidget
            VideoFile -- Path to the video file to play
        """
        #-----------------------------------------------------------
        # Setup video player
        #-----------------------------------------------------------
        self.VideoFile = VideoFile
        
        # Create QMediaPlayer instance with VideoSurface flag
        # This tells Qt we want to render video to a surface (QVideoWidget)
        # https://doc.qt.io/qt-5/qmediaplayer.html#QMediaPlayer
        self.MediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        
        # Set the video output widget where frames will be rendered
        # MainWindow.VideoFrame should be a QVideoWidget instance
        # https://doc.qt.io/qt-5/qmediaplayer.html#setVideoOutput
        self.MediaPlayer.setVideoOutput(MainWindow.VideoFrame)
        
        # Mute the audio output
        # https://doc.qt.io/qt-5/qmediaplayer.html#muted-prop
        self.MediaPlayer.setMuted(True)
        
        # Set volume to 0 as an additional safeguard
        # Volume range is 0-100
        # https://doc.qt.io/qt-5/qmediaplayer.html#volume-prop
        self.MediaPlayer.setVolume(0)

        self.OldRate = -1.0

    def Reset(self):
        """
        Reset the video to the beginning and prepare for playback
        
        This method loads (or reloads) the video file, sets the playback
        rate to normal speed, and positions the video at the first frame
        in a paused state.
        
        QMediaContent API: https://doc.qt.io/qt-5/qmediacontent.html
        QUrl API: https://doc.qt.io/qt-5/qurl.html
        """
        # Create a QMediaContent object from the video file path
        # QUrl.fromLocalFile() converts a local file path to a proper URL
        # https://doc.qt.io/qt-5/qurl.html#fromLocalFile
        media_content = QMediaContent(QUrl.fromLocalFile(self.VideoFile))
        
        # Load the media content into the player
        # https://doc.qt.io/qt-5/qmediaplayer.html#setMedia
        self.MediaPlayer.setMedia(media_content)
        
        # Set playback rate to 1.0 (normal speed)
        # Rate values: 0.0 = paused, 1.0 = normal, 2.0 = double speed, etc.
        # https://doc.qt.io/qt-5/qmediaplayer.html#playbackRate-prop
        self.MediaPlayer.setPlaybackRate(1.0)
        
        # Play briefly to load the first frame, then pause
        # This ensures the video is ready and the first frame is displayed
        # https://doc.qt.io/qt-5/qmediaplayer.html#play
        state.Log("Reset: Play")
        self.MediaPlayer.play()
        
        # Brief sleep to allow the media player to load the first frame
        time.sleep(0.01)
        
        # Pause the video at the first frame
        # https://doc.qt.io/qt-5/qmediaplayer.html#pause
        state.Log("Reset: Pause")
        self.MediaPlayer.pause()
        
    def SetRate(self, Rate):
        """
        Set the video playback speed and update play/pause state
        
        This method adjusts the playback rate and ensures the player
        is in the correct state (playing or paused) based on the rate
        and the current speed from the state module.
        
        QMediaPlayer States: https://doc.qt.io/qt-5/qmediaplayer.html#State-enum
        - StoppedState: The media player is not playing content
        - PlayingState: The media player is currently playing content
        - PausedState: The media player has paused playback

        Args:
            Rate -- Playback rate (0.0 = paused, 1.0 = normal speed, 2.0 = 2x speed, etc.)
        """
        state.Log("SetRate(%f)" % Rate)
        if (Rate == self.OldRate):
            return
        self.OldRate = Rate
        # Ensure rate is non-negative
        if Rate < 0:
            Rate = 0.0
        
        # Check if we should be playing but aren't
        # state() returns the current player state (Stopped, Playing, or Paused)
        # https://doc.qt.io/qt-5/qmediaplayer.html#state-prop
        if self.MediaPlayer.state() != QMediaPlayer.PlayingState and state.State.Speed > 0.0:
            state.Log("MediaPlayer.play()")
            # Start playback
            # https://doc.qt.io/qt-5/qmediaplayer.html#play
            self.MediaPlayer.play()

        if (Rate > 0.0):
            state.Log("MediaPlayer.setPlaybackRate(%f)" % Rate)
            # Set the playback rate
            # https://doc.qt.io/qt-5/qmediaplayer.html#playbackRate-prop
            self.MediaPlayer.setPlaybackRate(Rate)
        
            
        # Check if we should be paused but are playing
        elif self.MediaPlayer.state() == QMediaPlayer.PlayingState and state.State.Speed <= 0.0:
            state.Log("MediaPlayer.pause()")
            # Pause playback
            # https://doc.qt.io/qt-5/qmediaplayer.html#pause
            self.MediaPlayer.pause()

    def GetPosition(self):
        """
        Return the current playback position as a fraction of total duration
        
        QMediaPlayer uses milliseconds for position and duration internally,
        but this method converts to a 0.0-1.0 range for easier handling.
        
        Position API: https://doc.qt.io/qt-5/qmediaplayer.html#position-prop
        Duration API: https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop
        
        Returns:
            Float between 0.0 (start) and 1.0 (end), or 0.0 if duration is unknown
        """
        # Get total duration in milliseconds
        # Returns 0 if duration is unknown
        # https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop
        duration = self.MediaPlayer.duration()
        
        if duration > 0:
            # Get current position in milliseconds
            # https://doc.qt.io/qt-5/qmediaplayer.html#position-prop
            position = self.MediaPlayer.position()
            
            # Convert to fraction (0.0 to 1.0)
            return position / duration
        
        # Return 0.0 if duration is not available yet
        return 0.0

    def SetPosition(self, Position):
        """
        Set the playback position as a fraction of total duration
        
        Takes a position value from 0.0 to 1.0 and converts it to
        milliseconds for the QMediaPlayer API.
        
        Position API: https://doc.qt.io/qt-5/qmediaplayer.html#position-prop
        Duration API: https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop

        Args:
            Position -- Desired position as a fraction from 0.0 (start) to 1.0 (end)
        """
        # Get total duration in milliseconds
        # https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop
        duration = self.MediaPlayer.duration()
        
        if duration > 0:
            # Convert fractional position (0.0-1.0) to milliseconds
            new_position = int(Position * duration)
            
            # Seek to the new position
            # https://doc.qt.io/qt-5/qmediaplayer.html#setPosition
            self.MediaPlayer.setPosition(new_position)

    def IsPlaying(self):
        """
        Check if the video is currently playing
        
        State API: https://doc.qt.io/qt-5/qmediaplayer.html#State-enum
        
        Returns:
            True if media player is in PlayingState, False otherwise
            
        ##Check for use
        """
        # Compare current state to PlayingState enum value
        # https://doc.qt.io/qt-5/qmediaplayer.html#state-prop
        return self.MediaPlayer.state() == QMediaPlayer.PlayingState
