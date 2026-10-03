"""
Module to handle the playing of video using mpv.

Linux / Windows
    mpv is embedded into the VideoFrame widget via its native window handle
    (X11 wid / HWND) -- mpv owns its own GPU context inside that window.

macOS
    mpv's gpu video output cannot create a GPU context inside an embedded
    NSView ("Failed initializing any suitable GPU context"), so --wid
    embedding is not usable.  Instead the libmpv OpenGL *render context* API is
    used: a QOpenGLWidget supplies the GL context and mpv renders into its
    framebuffer.

    IMPORTANT: because the QOpenGLWidget is nested inside another widget,
    main.py MUST set

        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    *before* the QApplication is constructed.  Without it, a nested
    QOpenGLWidget on macOS paints its first frame and then never composites
    again -- the "one frame and freeze" symptom.

Initialisation is deferred until the first Qt event-loop iteration
(via QTimer.singleShot) so that the VideoFrame widget has a real window
handle by the time it is passed to mpv.

API
---
Video(app, VideoFile, Prefix, ImageDirectory, SkipCount)
    Create the video player.  Prefix, ImageDirectory, and SkipCount are
    accepted for interface compatibility but are ignored.

Video.SetRate(rate)
    Set playback speed.  0 (or negative) pauses; positive values set the
    mpv ``speed`` property and resume playback.

Video.Pause()
    Pause playback, remembering the current rate for Resume().

Video.Resume()
    Resume playback at the rate in effect before Pause() was called
    (defaults to 1.0 if no rate was recorded).

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
import os
import locale
import platform

import mpv
from PyQt6 import QtCore, QtGui, QtWidgets

# NOTE: intentionally "import __main__ as main", NOT "import main".
#
# When this program is launched as "python3 main.py", the interpreter loads
# main.py as the module __main__ -- there is no module literally named
# "main" yet. A plain "import main" then makes Python go find main.py on
# disk and import it a SECOND time under the name "main", creating a
# completely separate module object that re-runs main.py's top-level code
# but never executes its "if __name__ == '__main__':" block (its __name__
# is "main", not "__main__"). That second copy's MainWindow attribute is
# never set, which is why "main.MainWindow" raised
# "AttributeError: module 'main' has no attribute 'MainWindow'" even though
# the real, running window had already been assigned.
#
# "import __main__" always gives you the actual entry-point script's module
# object, no matter what it's named or how it was launched, so there is only
# ever one copy and MainWindow is visible here exactly as main.py set it.
import __main__ as main

# mpv requires the C numeric locale for correct number parsing.
locale.setlocale(locale.LC_NUMERIC, 'C')

_SYSTEM = platform.system()


# ---------------------------------------------------------------------------
# macOS: OpenGL render context helpers
# ---------------------------------------------------------------------------

if _SYSTEM == 'Darwin':
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget

    _fmt = QtGui.QSurfaceFormat()
    _fmt.setVersion(3, 3)
    _fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    _fmt.setRenderableType(QtGui.QSurfaceFormat.RenderableType.OpenGL)
    _fmt.setSwapBehavior(QtGui.QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QtGui.QSurfaceFormat.setDefaultFormat(_fmt)

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
            self._timer = None
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
            self.setFormat(QtGui.QSurfaceFormat.defaultFormat())

            layout = QtWidgets.QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self)

        def initializeGL(self):
            self._ctx = mpv.MpvRenderContext(
                self._player,
                'opengl',
                opengl_init_params={'get_proc_address': _get_proc_address},
            )
            # mpv signals "new frame ready" on its render thread; bounce to the
            # GUI thread to schedule a repaint.
            self._ctx.update_cb = self._on_mpv_update

            # Belt-and-suspenders: also repaint on a timer, so playback keeps
            # advancing even if a given update callback is dropped.  render()
            # is cheap when there is no new frame.
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(16)   # ~60 fps
            self._timer.timeout.connect(self.update)
            self._timer.start()

            self.update()

        @QtCore.pyqtSlot()
        def _do_update(self):
            self.update()

        def _on_mpv_update(self, *args):
            QtCore.QMetaObject.invokeMethod(
                self, '_do_update', QtCore.Qt.ConnectionType.QueuedConnection
            )

        def paintGL(self):
            if self._ctx is None:
                return
            ratio = self.devicePixelRatioF()
            w = max(1, round(self.width() * ratio))
            h = max(1, round(self.height() * ratio))
            self._ctx.render(
                flip_y=True,
                opengl_fbo={
                    'fbo': self.defaultFramebufferObject(),
                    'w': w,
                    'h': h,
                },
            )

        def shutdown(self):
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
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
    def __init__(self, app, VideoFile, Prefix, ImageDirectory, SkipCount):
        """
        Create video player.

        Args:
            app            -- The Qt application
            VideoFile      -- Video file to play
            Prefix         -- (unused) frame-extraction prefix
            ImageDirectory -- (unused) frame image directory
            SkipCount      -- (unused) frame-skip count
        """
        self.VideoFile = VideoFile
        self.ImageLabel = main.MainWindow.VideoFrame

        self.SharedWidth = _SharedValue()
        self.SharedHeight = _SharedValue()

        self.player = None
        self._gl_widget = None      # macOS only
        self._pending_rate = 0.0
        self.Rate = 0.0
        self._rate_before_pause = 1.0   # rate Resume() restores after Pause()

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
            # Window handle not ready yet; try again shortly.
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
        """macOS: render into a QOpenGLWidget via the libmpv render context."""
        # gpu_dumb_mode forces mpv's minimal single-pass render path.  The
        # full path glitches (a dashed black line) on macOS's software/indirect
        # GL context, especially with 10-bit content; dumb mode is robust here.
        #
        # audio='no': mpv's default A/V sync uses the audio device as the
        # master clock.  This Mac's coreaudio device fails to report its
        # layout/sample-rate, so that clock never advances and the video --
        # slaved to it -- freezes on frame 0.  Disabling mpv audio lets the
        # video run on the system clock.  (The simulator plays its own sounds
        # via the sound module, so no app audio is lost.)
        self.player = mpv.MPV(
            vo='libmpv',
            audio='no',
            hwdec='no',
            gpu_dumb_mode='yes',
            keep_open='yes',
            pause='yes',
            #log_handler=print,
            #loglevel='info',   # bump to 'debug' if you need to diagnose
        )
        self._gl_widget = _MpvGLWidget(self.player, self.ImageLabel)
        self._gl_widget.show()
        self.player.play(self.VideoFile)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def Stop(self):
        """
        Tear down the mpv player (and the macOS GL widget).  MUST be called
        before the process exits: python-mpv's GC-time cleanup deadlocks
        against the embedded direct3d/X11 window on Windows, so an explicit
        terminate() is required.  Idempotent.
        """
        if _SYSTEM == 'Darwin' and self._gl_widget is not None:
            try:
                self._gl_widget.shutdown()
            except Exception:
                pass
            self._gl_widget = None

        if self.player is not None:
            try:
                self.player.terminate()
            except Exception:
                pass
            self.player = None

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

    def Pause(self):
        """
        Pause playback, remembering the current rate so Resume() can
        restore it.  Equivalent to SetRate(0) except that the rate in
        effect at the time of the call is preserved for Resume().
        """
        if self.Rate > 0.0:
            self._rate_before_pause = self.Rate
        self.SetRate(0)

    def Resume(self):
        """Resume playback at the rate in effect before Pause() was called."""
        rate = self._rate_before_pause if self._rate_before_pause > 0.0 else 1.0
        self.SetRate(rate)

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


# ---------------------------------------------------------------------------
# Attract-mode player
# ---------------------------------------------------------------------------

class AttractPlayer(QtWidgets.QWidget):
    """
    Full-screen, always-on-top window that loops the attract video with an
    in-process libmpv player.

    This replaces launching an external player (video_player.play_video()).
    On Windows ("powershell Start-Process") and macOS ("open -a") the process
    that launched returned immediately after handing the file to the real
    player, so the "has the player exited?" poll restarted the video every
    500 ms, and terminate() killed the launcher instead of the player, leaving
    the player window up.  Here mpv loops the file itself (loop-file=inf) and
    Stop() tears down the one player we actually own.

    The embedding is the same as Video uses -- X11 wid / HWND on Linux and
    Windows, a libmpv render context in a QOpenGLWidget on macOS -- so it
    works wherever the main simulator video already works.

    Dismissal: any mouse press, key press, or touch that reaches this window
    calls OnDismiss.  main.py also keeps its global pynput mouse listener, so
    the video stops even if the native mpv child window swallows a click.

    API
    ---
    AttractPlayer(VideoFile, OnDismiss, parent=None)
    AttractPlayer.Start()      -- show full screen and start looping
    AttractPlayer.Stop()       -- stop playback and hide.  Idempotent.
    AttractPlayer.Shutdown()   -- free mpv; call before exit.  Idempotent.
    AttractPlayer.IsPlaying()

    The mpv player is created on the first Start() and reused afterwards
    (Stop() just unloads the file), so the macOS GL widget is built once.
    """
    def __init__(self, VideoFile, OnDismiss, parent=None):
        """
        Args:
            VideoFile -- Absolute path of the video to loop
            OnDismiss -- Callable (no args) invoked on user input
            parent    -- Parent widget (usually the main window).  The
                         window is still top-level; the parent just ties
                         its lifetime and screen to the main window.
        """
        super().__init__(
            parent,
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint,
        )
        self.VideoFile = VideoFile
        self.OnDismiss = OnDismiss
        self.player = None
        self._gl_widget = None      # macOS only
        self._playing = False

        self.setWindowTitle("Trolley Simulator")
        self.setStyleSheet("background-color: black;")
        self.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AcceptTouchEvents)

        # The video surface.  Deliberately has no layout of its own:
        # _MpvGLWidget installs one on it on macOS.
        self._surface = QtWidgets.QWidget(self)
        self._surface.setCursor(QtCore.Qt.CursorShape.BlankCursor)
        if _SYSTEM != 'Darwin':
            # mpv needs a real native window handle to draw into.
            self._surface.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow)
            self._surface.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_DontCreateNativeAncestors)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._surface)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def IsPlaying(self):
        """True between Start() and Stop()."""
        return self._playing

    def Start(self):
        """
        Show the window full screen and start looping the video.

        Returns False (and shows nothing) if the video file is missing.
        """
        if self._playing:
            return True
        if not os.path.isfile(self.VideoFile):
            print(f"Attract video not found: {self.VideoFile}")
            return False

        self._playing = True
        # Cover the screen the main window is on, not necessarily screen 0.
        if self.parentWidget() is not None:
            Screen = self.parentWidget().screen()
            if Screen is not None:
                self.setGeometry(Screen.geometry())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        # Create mpv once the window is actually mapped, so the native
        # handle exists (same reason Video defers its init).
        QtCore.QTimer.singleShot(0, self._init_player)
        return True

    def Stop(self):
        """
        Stop playback and hide the window.  The player is kept for the
        next Start().  Safe to call at any time, any number of times.
        """
        self._playing = False
        if self.player is not None:
            try:
                self.player.command('stop')     # unload the file
            except Exception:
                pass
        self.hide()

    def Shutdown(self):
        """
        Free the mpv player.  MUST be called before the process exits:
        python-mpv's GC-time cleanup deadlocks against an embedded window
        on Windows (see Video.Stop()).  Idempotent.
        """
        self.Stop()
        if self._gl_widget is not None:
            try:
                self._gl_widget.shutdown()
            except Exception:
                pass
            self._gl_widget = None
        if self.player is not None:
            try:
                self.player.terminate()
            except Exception:
                pass
            self.player = None

    # ------------------------------------------------------------------
    # Player creation
    # ------------------------------------------------------------------

    def _init_player(self):
        """Create mpv if needed and start looping (called from the event loop)."""
        if not self._playing:
            return      # Stopped before we got here
        locale.setlocale(locale.LC_NUMERIC, 'C')

        try:
            if self.player is None:
                self._create_player()
                if self.player is None:
                    return      # Native handle not ready; retry scheduled
            self.player.play(self.VideoFile)
            self.player.pause = False
        except Exception as Error:
            print(f"Attract video failed to start: {Error}")
            self.Stop()
            # Give the main window its normal state back.
            self.OnDismiss()

    def _create_player(self):
        """Build the mpv player, embedded the same way Video does it."""
        if _SYSTEM == 'Darwin':
            # Same options as Video._init_player_macos(); see the comments
            # there for why audio/hwdec/gpu_dumb_mode are set.
            self.player = mpv.MPV(
                vo='libmpv',
                audio='no',
                hwdec='no',
                gpu_dumb_mode='yes',
                loop_file='inf',
            )
            self._gl_widget = _MpvGLWidget(self.player, self._surface)
            self._gl_widget.setCursor(QtCore.Qt.CursorShape.BlankCursor)
            self._gl_widget.show()
        else:
            wid = int(self._surface.winId())
            if wid == 0:
                QtCore.QTimer.singleShot(100, self._init_player)
                return
            vo = 'x11' if _SYSTEM == 'Linux' else 'direct3d'
            self.player = mpv.MPV(
                wid=wid,
                vo=vo,
                loop_file='inf',
                # Don't let mpv's native child window consume pointer
                # input; let it fall through to this Qt window.
                input_cursor='no',
                cursor_autohide='always',
            )

    # ------------------------------------------------------------------
    # Input: any interaction dismisses the attract video
    # ------------------------------------------------------------------

    def _dismiss(self, event):
        event.accept()
        if self._playing:
            self.OnDismiss()

    def mousePressEvent(self, event):
        self._dismiss(event)

    def keyPressEvent(self, event):
        self._dismiss(event)

    def event(self, event):
        if event.type() == QtCore.QEvent.Type.TouchBegin:
            self._dismiss(event)
            return True
        return super().event(event)

    def closeEvent(self, event):
        # Alt-F4 or similar on the attract window: treat as a dismissal
        # rather than letting the window vanish with mpv still running.
        event.ignore()
        if self._playing:
            self.OnDismiss()
