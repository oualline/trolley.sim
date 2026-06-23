"""
Module to handle the playing of video using mpv.

On Linux and Windows, mpv is embedded into the VideoFrame Qt widget via its
window ID (X11 wid / HWND).

On macOS, mpv's Metal backend does not support --wid embedding, so the
OpenGL render context API is used instead: a QOpenGLWidget is created inside
VideoFrame and mpv renders into its framebuffer.

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
    compatibility with the resizeEvent() in main.py.
"""
import ctypes
import ctypes.util
import locale
import platform

import mpv
from PyQt6 import QtCore, QtWidgets

# mpv requires the C numeric locale for correct number parsing.
locale.setlocale(locale.LC_NUMERIC, 'C')

_SYSTEM = platform.system()


# ---------------------------------------------------------------------------
# macOS: OpenGL render context helpers
# ---------------------------------------------------------------------------

if _SYSTEM == 'Darwin':
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget

    _opengl_lib = None
    _ProcAddrFn = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)

    @_ProcAddrFn
    def _get_proc_address(_, name):
        """Return the OpenGL function pointer for mpv's render context."""
        global _opengl_lib
        if _opengl_lib is None:
            path = (ctypes.util.find_library('OpenGL') or
                    '/System/Library/Frameworks/OpenGL.framework/OpenGL')
            _opengl_lib = ctypes.cdll.LoadLibrary(path)
        try:
            return ctypes.cast(_opengl_lib[name], ctypes.c_void_p).value or 0
        except Exception:
            return 0

    class _MpvGLWidget(QOpenGLWidget):
        """QOpenGLWidget that pulls frames from an mpv render context."""

        def __init__(self, player, parent):
            super().__init__(parent)
            self._player = player
            self._ctx = None
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)

            # Fill the parent (VideoFrame) widget.
            layout = QtWidgets.QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self)

        def initializeGL(self):
            self._ctx = mpv.MpvRenderContext(
                self._player,
                'opengl',
                opengl_init_params={'get_proc_address': _get_proc_address},
            )
            # update_cb fires on the mpv render thread; use invokeMethod to
            # safely schedule a repaint on the Qt main thread.
            self._ctx.update_cb = self._on_mpv_update

        def _on_mpv_update(self):
            QtCore.QMetaObject.invokeMethod(
                self, 'update', QtCore.Qt.ConnectionType.QueuedConnection
            )

        def paintGL(self):
            if self._ctx:
                self._ctx.render(
                    flip_y=True,
                    opengl_fbo={
                        'fbo': self.defaultFramebufferObject(),
                        'w': self.width(),
                        'h': self.height(),
                    },
                )

        def shutdown(self):
            if self._ctx:
                self._ctx.free()
                self._ctx = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _SharedValue:
    """Minimal stand-in for multiprocessing.Value used by main.py resizeEvent."""
    def __init__(self):
        self.value = 0


# ---------------------------------------------------------------------------
# Public Video class
# ---------------------------------------------------------------------------

class Video:
    def __init__(self, app, MainWindow, VideoFile, Prefix, ImageDirectory, SkipCount):
        """
        Create video player.

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

        self.SharedWidth = _SharedValue()
        self.SharedHeight = _SharedValue()

        self.player = None
        self._gl_widget = None      # macOS only
        self._pending_rate = 0.0
        self.Rate = 0.0

        # Defer actual mpv creation until the event loop is running and the
        # window is on screen.
        QtCore.QTimer.singleShot(200, self._init_player)

    def _init_player(self):
        """Create and start the mpv player (called from the event loop)."""
        locale.setlocale(locale.LC_NUMERIC, 'C')

        if _SYSTEM == 'Darwin':
            self._init_player_macos()
        else:
            self._init_player_wid()

        if self._pending_rate > 0.0:
            try:
                self.player.speed = self._pending_rate
                self.player.pause = False
            except Exception:
                pass

    def _init_player_wid(self):
        """Linux / Windows: embed via X11 wid or HWND."""
        wid = int(self.ImageLabel.winId())
        if wid == 0:
            QtCore.QTimer.singleShot(100, self._init_player)
            return

        vo = 'x11' if _SYSTEM == 'Linux' else 'direct3d'
        self.player = mpv.MPV(
            wid=wid,
            vo=vo,
            keep_open='yes',
            pause='yes',
        )
        self.player.play(self.VideoFile)

    def _init_player_macos(self):
        """macOS: use the OpenGL render context API inside a QOpenGLWidget."""
        self.player = mpv.MPV(keep_open='yes', pause='yes',
                              log_handler=print, loglevel='debug')
        self._gl_widget = _MpvGLWidget(self.player, self.ImageLabel)
        self._gl_widget.show()
        self.player.play(self.VideoFile)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def Reset(self):
        """Pause and seek to the beginning of the video."""
        self.SetRate(0)
        if self.player is not None:
            try:
                self.player.seek(0, 'absolute')
            except Exception:
                pass

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

        try:
            if Rate <= 0.0:
                self.player.pause = True
            else:
                self.player.speed = Rate
                self.player.pause = False
        except Exception:
            pass

    def GetPosition(self):
        """Return current position as a fraction of total duration [0.0, 1.0]."""
        if self.player is None:
            return 0.0
        try:
            pos = self.player.time_pos
            duration = self.player.duration
        except Exception:
            return 0.0
        if pos is None or duration is None or duration == 0:
            return 0.0
        return min(1.0, pos / duration)
