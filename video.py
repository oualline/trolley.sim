"""
Module to handle the playing of video using mpv.

mpv is embedded directly into the VideoFrame Qt widget via its window ID,
so no frame extraction or manual image display is needed.

Initialisation is deferred until the first Qt event-loop iteration
(via QTimer.singleShot) so that the VideoFrame widget has a real X11
window handle by the time it is passed to mpv.

API
---
Video(app, MainWindow, VideoFile, Prefix, ImageDirectory, SkipCount)
    Create the video player.  Prefix, ImageDirectory, and SkipCount are
    accepted for interface compatibility but are ignored.

Video.SetRate(rate)
    Set playback speed.  0 (or negative) pauses; positive values set the
    mpv ``speed`` property and resume playback.

Video.GetPosition()
    Return current playback position as a fraction in [0.0, 1.0].

Video.Reset()
    Pause and seek back to the beginning.

Video.SharedWidth / Video.SharedHeight
    Dummy objects with a writable ``.value`` attribute kept for
    compatibility with the resizeEvent() in main.py.  mpv scales its own
    output to fill the embedded window, so these values are not used.
"""
import locale

import mpv

from PyQt6 import QtCore

# mpv requires the C numeric locale for correct number parsing.
locale.setlocale(locale.LC_NUMERIC, 'C')


class _SharedValue:
    """Minimal stand-in for multiprocessing.Value used by main.py resizeEvent."""
    def __init__(self):
        self.value = 0


class Video:
    def __init__(self, app, MainWindow, VideoFile, Prefix, ImageDirectory, SkipCount):
        """
        Create video player.

        mpv is not started here; it is started on the first Qt event-loop
        tick so that the VideoFrame widget has a valid native X11 window
        handle by the time we need it.

        Args:
            app            -- The Qt application
            MainWindow     -- Window containing the VideoFrame widget
            VideoFile      -- Video file to play
            Prefix         -- (unused) frame-extraction prefix
            ImageDirectory -- (unused) frame image directory
            SkipCount      -- (unused) frame-skip count
        """
        self.VideoFile = VideoFile
        self.ImageLabel = MainWindow.VideoFrame

        # Dummy shared values kept so main.py's resizeEvent() can write to
        # SharedWidth.value / SharedHeight.value without error.
        self.SharedWidth = _SharedValue()
        self.SharedHeight = _SharedValue()

        self.player = None
        self._pending_rate = 0.0   # rate requested before player exists
        self.Rate = 0.0

        # Force a native (X11) window on the label now so the handle is
        # ready by the time _init_player fires.
        self.ImageLabel.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow, True)

        # Defer actual mpv creation until the event loop is running and the
        # window is on screen; a zero-millisecond single-shot is enough.
        QtCore.QTimer.singleShot(0, self._init_player)

    def _init_player(self):
        """Create and start the mpv player (called from the event loop)."""
        wid = int(self.ImageLabel.winId())

        locale.setlocale(locale.LC_NUMERIC, 'C')
        self.player = mpv.MPV(
            wid=str(wid),
            keep_open='yes',
            pause='yes',
        )

        self.player.play(self.VideoFile)

        # Apply any rate that was set before the player existed.
        if self._pending_rate > 0.0:
            self.player.speed = self._pending_rate
            self.player.pause = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def Reset(self):
        """Pause and seek to the beginning of the video."""
        self.SetRate(0)
        if self.player is not None:
            self.player.seek(0, 'absolute')

    def SetRate(self, Rate):
        """
        Set playback speed.

        Args:
            Rate -- Speed multiplier.  <= 0 pauses; > 0 sets mpv speed and plays.
        """
        if Rate < 0:
            Rate = 0.0
        self.Rate = Rate

        if self.player is None:
            self._pending_rate = Rate
            return

        if Rate <= 0.0:
            self.player.pause = True
        else:
            self.player.speed = Rate
            self.player.pause = False

    def GetPosition(self):
        """
        Return current position as a fraction of total duration [0.0, 1.0].
        """
        if self.player is None:
            return 0.0
        pos = self.player.time_pos
        duration = self.player.duration
        if pos is None or duration is None or duration == 0:
            return 0.0
        return min(1.0, pos / duration)
