"""
Module to handle the playing of video

Uses QMediaPlayer for video output running in a separate QThread

The QMediaPlayer is created in the main thread but its playback control
operations are delegated to a worker thread to prevent blocking the GUI.

API Documentation References:
- QMediaPlayer: https://doc.qt.io/qt-5/qmediaplayer.html
- QMediaContent: https://doc.qt.io/qt-5/qmediacontent.html
- QVideoWidget: https://doc.qt.io/qt-5/qvideowidget.html
- QUrl: https://doc.qt.io/qt-5/qurl.html
- QThread: https://doc.qt.io/qt-5/qthread.html
- QObject: https://doc.qt.io/qt-5/qobject.html
- QMetaObject: https://doc.qt.io/qt-5/qmetaobject.html
"""
import time

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl, QThread, QObject, pyqtSignal, pyqtSlot, QMetaObject, Qt, Q_ARG

import state


class VideoPlayerWorker(QObject):
    """
    Worker class that handles QMediaPlayer control operations in a separate thread
    
    IMPORTANT: The QMediaPlayer itself is NOT created in this worker thread.
    It must be created in the main thread where the QVideoWidget lives to avoid
    cross-thread parenting issues. This worker only handles playback control.
    
    QObject API: https://doc.qt.io/qt-5/qobject.html
    Signals and Slots: https://doc.qt.io/qt-5/signalsandslots.html
    """
    
    # Signals for thread-safe communication from worker to main thread
    # https://doc.qt.io/qt-5/qobject.html#Q_SIGNALS
    positionChanged = pyqtSignal(float)  # Emits position as 0.0-1.0 fraction
    playingStateChanged = pyqtSignal(bool)  # Emits True if playing, False otherwise
    
    def __init__(self):
        """
        Initialize the video player worker
        """
        super().__init__()
        self.MediaPlayer = None
        
    def setMediaPlayer(self, player):
        """
        Set the media player reference that this worker will control
        
        Args:
            player -- QMediaPlayer instance created in the main thread
        """
        self.MediaPlayer = player
        
        # Connect internal signals for monitoring state changes
        # https://doc.qt.io/qt-5/qmediaplayer.html#positionChanged
        self.MediaPlayer.positionChanged.connect(self._onPositionChanged)
        # https://doc.qt.io/qt-5/qmediaplayer.html#stateChanged
        self.MediaPlayer.stateChanged.connect(self._onStateChanged)

    @pyqtSlot(str)
    def reset(self, VideoFile):
        """
        Reset the video to the beginning and prepare for playback
        
        This method loads (or reloads) the video file, sets the playback
        rate to normal speed, and positions the video at the first frame
        in a paused state.
        
        QMediaContent API: https://doc.qt.io/qt-5/qmediacontent.html
        QUrl API: https://doc.qt.io/qt-5/qurl.html
        
        Args:
            VideoFile -- Path to the video file to play
        """
        if self.MediaPlayer is None:
            return
            
        # Create a QMediaContent object from the video file path
        # QUrl.fromLocalFile() converts a local file path to a proper URL
        # https://doc.qt.io/qt-5/qurl.html#fromLocalFile
        media_content = QMediaContent(QUrl.fromLocalFile(VideoFile))
        
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
        
    @pyqtSlot(float)
    def setRate(self, Rate):
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
                   Values between 0.0 and 1.0 will play in slow motion
        """
        if self.MediaPlayer is None:
            return
            
        # Ensure rate is non-negative
        if Rate < 0:
            Rate = 0.0
        
        # Determine if we should be playing or paused
        # Rate > 0 means we want playback (even if slow), Rate = 0 means pause
        should_play = Rate > 0.0
        
        # Check current state
        # https://doc.qt.io/qt-5/qmediaplayer.html#state-prop
        is_playing = self.MediaPlayer.state() == QMediaPlayer.PlayingState
        
        # Update play/pause state before setting rate
        # This ensures smooth transitions when changing speed
        if should_play and not is_playing:
            state.Log("MediaPlayer.play()")
            # Start playback
            # https://doc.qt.io/qt-5/qmediaplayer.html#play
            self.MediaPlayer.play()
        elif not should_play and is_playing:
            state.Log("MediaPlayer.pause()")
            # Pause playback
            # https://doc.qt.io/qt-5/qmediaplayer.html#pause
            self.MediaPlayer.pause()
        
        # Set the playback rate after ensuring correct play/pause state
        # Note: Some QMediaPlayer backends may not support all playback rates
        # Rates between 0.0 and 1.0 should produce slow motion
        # https://doc.qt.io/qt-5/qmediaplayer.html#playbackRate-prop
        self.MediaPlayer.setPlaybackRate(Rate)
    
    @pyqtSlot(float)
    def setPosition(self, Position):
        """
        Set the playback position as a fraction of total duration
        
        Takes a position value from 0.0 to 1.0 and converts it to
        milliseconds for the QMediaPlayer API.
        
        Position API: https://doc.qt.io/qt-5/qmediaplayer.html#position-prop
        Duration API: https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop

        Args:
            Position -- Desired position as a fraction from 0.0 (start) to 1.0 (end)
        """
        if self.MediaPlayer is None:
            return
            
        # Get total duration in milliseconds
        # https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop
        duration = self.MediaPlayer.duration()
        
        if duration > 0:
            # Convert fractional position (0.0-1.0) to milliseconds
            new_position = int(Position * duration)
            
            # Seek to the new position
            # https://doc.qt.io/qt-5/qmediaplayer.html#setPosition
            self.MediaPlayer.setPosition(new_position)
    
    def getPosition(self):
        """
        Return the current playback position as a fraction of total duration
        
        QMediaPlayer uses milliseconds for position and duration internally,
        but this method converts to a 0.0-1.0 range for easier handling.
        
        Position API: https://doc.qt.io/qt-5/qmediaplayer.html#position-prop
        Duration API: https://doc.qt.io/qt-5/qmediaplayer.html#duration-prop
        
        Returns:
            Float between 0.0 (start) and 1.0 (end), or 0.0 if duration is unknown
        """
        if self.MediaPlayer is None:
            return 0.0
            
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
    
    def isPlaying(self):
        """
        Check if the video is currently playing
        
        State API: https://doc.qt.io/qt-5/qmediaplayer.html#State-enum
        
        Returns:
            True if media player is in PlayingState, False otherwise
        """
        if self.MediaPlayer is None:
            return False
            
        # Compare current state to PlayingState enum value
        # https://doc.qt.io/qt-5/qmediaplayer.html#state-prop
        return self.MediaPlayer.state() == QMediaPlayer.PlayingState
    
    def _onPositionChanged(self, position):
        """
        Internal slot called when media position changes
        
        Converts position to fraction and emits signal to main thread
        
        Args:
            position -- Position in milliseconds
        """
        duration = self.MediaPlayer.duration()
        if duration > 0:
            fraction = position / duration
            self.positionChanged.emit(fraction)
    
    def _onStateChanged(self, state):
        """
        Internal slot called when media player state changes
        
        Emits playing state to main thread
        
        Args:
            state -- QMediaPlayer.State enum value
        """
        is_playing = (state == QMediaPlayer.PlayingState)
        self.playingStateChanged.emit(is_playing)


class Video:
    """
    Main Video class that manages the video player with worker thread
    
    The QMediaPlayer is created in the main thread (to avoid cross-thread
    parenting issues with QVideoWidget), but control operations are delegated
    to a worker thread to prevent GUI blocking.
    
    QThread API: https://doc.qt.io/qt-5/qthread.html
    Thread Basics: https://doc.qt.io/qt-5/thread-basics.html
    """
    
    def __init__(self, MainWindow, VideoFile):
        """
        Create video player with worker thread
        
        The QMediaPlayer is created in the main thread where the VideoWidget
        lives, but operations are controlled through a worker in a separate thread.
        
        QThread API: https://doc.qt.io/qt-5/qthread.html

        Args:
            MainWindow -- Window in which we display the video
                         MainWindow.VideoFrame must be a QVideoWidget
            VideoFile -- Path to the video file to play
        """
        #-----------------------------------------------------------
        # Setup video player in main thread
        #-----------------------------------------------------------
        self.VideoFile = VideoFile
        
        # Create QMediaPlayer instance in the MAIN thread
        # This avoids cross-thread parenting issues with QVideoWidget
        # https://doc.qt.io/qt-5/qmediaplayer.html#QMediaPlayer
        self.MediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        
        # Set the video output widget where frames will be rendered
        # Both QMediaPlayer and QVideoWidget live in the main thread
        # https://doc.qt.io/qt-5/qmediaplayer.html#setVideoOutput
        self.MediaPlayer.setVideoOutput(MainWindow.VideoFrame)
        
        # Mute the audio output
        # https://doc.qt.io/qt-5/qmediaplayer.html#muted-prop
        self.MediaPlayer.setMuted(True)
        
        # Set volume to 0 as an additional safeguard
        # Volume range is 0-100
        # https://doc.qt.io/qt-5/qmediaplayer.html#volume-prop
        self.MediaPlayer.setVolume(0)
        
        #-----------------------------------------------------------
        # Setup worker thread for playback control
        #-----------------------------------------------------------
        
        # Create a new thread for video playback control operations
        # https://doc.qt.io/qt-5/qthread.html#QThread
        self.thread = QThread()
        
        # Create the worker object (will be moved to thread)
        self.worker = VideoPlayerWorker()
        
        # Move the worker to the thread
        # After this, all of worker's slots will execute in the thread
        # https://doc.qt.io/qt-5/qobject.html#moveToThread
        self.worker.moveToThread(self.thread)
        
        # Start the thread
        # https://doc.qt.io/qt-5/qthread.html#start
        self.thread.start()
        
        # Give the worker a reference to the media player
        # The media player stays in the main thread, but the worker
        # will control it through queued connections
        self.worker.setMediaPlayer(self.MediaPlayer)

    def Reset(self):
        """
        Reset the video to the beginning
        
        This call is thread-safe - it uses Qt's signal/slot mechanism
        to invoke the reset method in the worker thread.
        
        QMetaObject.invokeMethod: https://doc.qt.io/qt-5/qmetaobject.html#invokeMethod
        """
        # Invoke the reset slot in the worker thread
        # Using Qt.QueuedConnection ensures thread safety
        QMetaObject.invokeMethod(self.worker, "reset", Qt.QueuedConnection, Q_ARG(str, self.VideoFile))
        
    def SetRate(self, Rate):
        """
        Tell video player we are going at a different speed
        
        This call is thread-safe - it uses Qt's signal/slot mechanism
        to invoke the setRate method in the worker thread.

        Args:
            Rate -- Rate to play the video at
        """
        # Invoke the setRate slot in the worker thread
        QMetaObject.invokeMethod(self.worker, "setRate", Qt.QueuedConnection, Q_ARG(float, Rate))

    def GetPosition(self):
        """
        Return the position of the video as a fraction of the total video
        
        Note: This performs a direct call to the worker. For high-frequency
        position updates, consider connecting to the worker's positionChanged signal.
        
        Returns:
            Float between 0.0 and 1.0
        """
        return self.worker.getPosition()

    def SetPosition(self, Position):
        """
        Set the position of the video as a fraction of the total video
        
        This call is thread-safe - it uses Qt's signal/slot mechanism
        to invoke the setPosition method in the worker thread.

        Args:
            Position -- Position from 0.0 to 1.0
        """
        # Invoke the setPosition slot in the worker thread
        QMetaObject.invokeMethod(self.worker, "setPosition", Qt.QueuedConnection, Q_ARG(float, Position))

    def IsPlaying(self):
        """
        Is the video playing
        
        Note: This performs a direct call to the worker. For state change
        notifications, consider connecting to the worker's playingStateChanged signal.
        
        Returns:
            True if playing, False otherwise
            
        ##Check for use
        """
        return self.worker.isPlaying()
    
    def cleanup(self):
        """
        Clean up the worker thread
        
        Should be called when the video player is no longer needed.
        This ensures the thread is properly stopped and cleaned up.
        
        QThread cleanup: https://doc.qt.io/qt-5/qthread.html#quit
        """
        # Request the thread to stop its event loop
        # https://doc.qt.io/qt-5/qthread.html#quit
        self.thread.quit()
        
        # Wait for the thread to finish (with timeout)
        # https://doc.qt.io/qt-5/qthread.html#wait
        self.thread.wait(2000)  # Wait up to 2 seconds
