"""
Module to handle the playing of video

Currently uses VLC for video output
"""
import time
import os
import glob
import sys

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QBrush, QPen, QFont, QPixmap, QPainter
from PyQt5.QtCore import Qt

import state
import video_to_frames

class Video:
    def __init__(self, MainWindow, VideoFile, ImageDirectory):
        """
        Create video player

        Args:
            MainWindow -- Window in which we display the stuff
            VideoFile -- Video file to play
        """
        self.VideoFile = VideoFile
        self.ImageDirectory = ImageDirectory
        self.ImageLabel = MainWindow.VideoFrame

        self.LoadImages()
        if (len(self.ImageFiles) == 0):
            self.ExtractImages()
            self.LoadImages()
            if (len(self.ImageFiles) == 0):
                print("FATAL ERROR: Unable to get video files")
                sys.exit(8)
        self.Reset()

    def ExtractImages(self):
        """
        Extract the frames from the video
        """
        video_to_frames.extract_frames(self.VideoFile, self.ImageDirectory)

    def LoadImages(self):
        """
        Load the image names into the system
        """
        # Find all files matching the pattern frame_XXXX.png
        Pattern = os.path.join(self.ImageDirectory, 'frame_*.png')
        Files = glob.glob(Pattern)
        
        # Sort files to ensure correct order
        self.ImageFiles = sorted(Files)

        self.FrameTimer = QtCore.QTimer()
        self.FrameTimer.timeout.connect(self.NextFrame)
        
        self.BaseFps = 25               # Make sure this matches the video
        self.SpeedMultiplier = 1.0

    def NextFrame(self):
        """
        Display the next frame

        Stop at end
        """
        if self.ImageFiles:
            if (self.CurrentFrame < len(self.ImageFiles)):
                self.CurrentFrame = self.CurrentFrame + 1
                self.ShowCurrentFrame()

                # Calculate interval in milliseconds
                # interval = 1000ms / (fps * speed_multiplier)
                Interval = int(1000 / (self.BaseFps * self.Rate))
                self.FrameTimer.setInterval(Interval)
            else:
                state.Log("Ran out of video")
                self.FrameTimer.stop()

    def ShowCurrentFrame(self):
        """Display the current frame"""
        # If the system has not initilized things
        if (self.ImageLabel.width() == 100):
            return
        if self.ImageFiles and 0 <= self.CurrentFrame < len(self.ImageFiles):
            Pixmap = QPixmap(self.ImageFiles[self.CurrentFrame])
            
            # Scale pixmap to fit label while maintaining aspect ratio
            ScaledPixmap = Pixmap.scaled(
                self.ImageLabel.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            #
            self.ImageLabel.setPixmap(ScaledPixmap)
            #self.ImageLabel.setPixmap(Pixmap)

    def Reset(self):
        """
        Reset the video
        """
        self.SetRate(0)
        self.CurrentFrame = 0
        self.ShowCurrentFrame()

    def SetRate(self, Rate):
        """
        Tell video player we are going at a different speed.

        Args:
            Rate -- Rate to play the video at
        """
        if (Rate < 0):
            Rate = 0.0
        self.Rate = Rate

        # Do we need to pause
        if (Rate <= 0.0):
            if (self.FrameTimer.isActive()):
                self.FrameTimer.stop()
                state.Log("FrameTimer stop")
            return

        # Do we need to start
        if Rate > 0.0:
            if (not self.FrameTimer.isActive()):
                self.FrameTimer.start()
                state.Log("FrameTimer start")

                self.NextFrame()

    def GetPosition(self):
        """
        Return the position of the video as a fraction of the total video
        """
        return ( float(self.CurrentFrame) / float(len(self.ImageFiles)) )
