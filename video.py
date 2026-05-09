# TODO: No fps, no files
"""
Module to handle the playing of video

Currently uses a series of extracted frames
as video.  

As soon as I figure out how to get the media player working
this will be fixed.

Architecture
------------

  ┌───────────────────────────────────────────┐                  ┌──────────────────────────┐
  │  Worker process  (frame_loader_proc)      │  mp.Queue(N)     │  Main process            │
  │                                           │ ───────────────► │  (Qt event loop)         │
  │  reads shared_w / shared_h before each    │  (bytes, w, h)   │                          │
  │  frame → Pillow resize to that size       │  or None         │  QTimer(0) fires         │
  │  → put( (bytes, w, h) ) into queue        │                  │  → QImage from bytes     │
  │                                           │                  │  → QPixmap.fromImage()   │
  │                                           │◄──────────────── │  → label.setPixmap()     │
  │  shared_w, shared_h:  multiprocessing     │  size change     │                          │
  │  Value('i') pair updated by main on resize│  (via Values)    │  resizeEvent() writes    │
  └───────────────────────────────────────────┘                  │  shared_w / shared_h     │
                                                                 └──────────────────────────┘

Resize handling
---------------
Two ``multiprocessing.Value('i', …)`` objects (``shared_w`` and ``shared_h``)
act as a lock-protected shared-memory channel between the main process and the
worker process.

When the QLabel is resized (detected via ``resizeEvent`` on the main window),
the main process writes the new pixel dimensions into ``shared_w`` and
``shared_h``.  The worker reads these values **before scaling each frame**, so
every frame produced after a resize is already at the correct size.

Frames that are already sitting in the queue were scaled to the previous size
and are displayed at that size — the user asked that these not be rescaled.
``QLabel.setAlignment(Qt.AlignCenter)`` centres them inside the label if they
are smaller than the current label size.

Why ``multiprocessing.Value`` for the size signal?
--------------------------------------------------
A second queue could carry resize messages, but the worker would need to drain
it before every frame, complicating the hot path.  A shared ``Value`` is a
single read of shared memory — essentially free.  The built-in lock inside
``Value`` prevents a torn read (seeing half of an update), and the values are
only ever written by one process (main) and read by one process (worker), so
no additional synchronisation is needed.

Reference: https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value

API documentation references
-----------------------------
Python multiprocessing:
  multiprocessing:          https://docs.python.org/3/library/multiprocessing.html
  multiprocessing.Process:  https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process
  multiprocessing.Queue:    https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue
  multiprocessing.Event:    https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Event
  multiprocessing.Value:    https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value

Pillow (PIL):
  Image.open:    https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open
  Image.convert: https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert
  Image.resize:  https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize
  Image.tobytes: https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.tobytes
"""
import time
import os
import glob
import sys
import multiprocessing

from PIL import Image  # Pillow – https://pillow.readthedocs.io/en/stable/

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QBrush, QPen, QFont, QPixmap, QPainter, QImage
from PyQt5.QtCore import Qt

import state
import frames_ui
import video_to_frames

# ---------------------------------------------------------------------------
# Queue capacity
# ---------------------------------------------------------------------------
# The worker blocks on put() when QUEUE_SIZE items are already waiting.
# Items are Pillow-scaled raw bytes. At 1920×1080 RGB that is ~6 MB each,
# so 8 items ≈ 48 MB peak.
QUEUE_SIZE = 8

# ===========================================================================
# frame_loader_proc – top-level worker function (runs in the child process)
# ===========================================================================
# Must be a module-level function so Python's pickle machinery can locate it
# by name when spawning on Windows / macOS.
# https://docs.python.org/3/library/multiprocessing.html#programming-guidelines

def frame_loader_proc(
    paths: list[str],
    shared_w: multiprocessing.Value,
    shared_h: multiprocessing.Value,
    out_queue: multiprocessing.Queue,
    stop_event: multiprocessing.Event,
) -> None:
    """
    Worker function executed in a separate OS process.

    For each path in *paths*:
      1. Read the current target dimensions from *shared_w* / *shared_h*.
         These are updated by the main process whenever the label is resized,
         so reading them here means each new frame uses the most recent size.
      2. Load the BMP with Pillow and convert to 24-bit RGB.
      3. Compute a scale factor that fits the frame inside the target box
         while preserving aspect ratio (mirrors Qt.KeepAspectRatio).
      4. Resize with nearest-neighbour resampling (Image.NEAREST – fastest).
      5. Serialise to raw bytes and put ``(raw_bytes, width, height)`` into
         *out_queue*, blocking with a short-timeout loop so *stop_event* can
         be checked if the queue is full.

    After the last frame (or when *stop_event* is set) enqueues ``None`` as
    an end-of-sequence sentinel.

    Parameters
    ----------
    paths : list[str]
        Ordered list of BMP file paths as plain strings (pickle-safe).
    shared_w, shared_h : multiprocessing.Value
        Shared-memory integers holding the current display dimensions.
        Written by the main process on resize; read here before each frame.
        https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value
    out_queue : multiprocessing.Queue
        Destination queue shared with the main process.
        https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue
    stop_event : multiprocessing.Event
        When set by the main process, the worker exits its loop early.
        https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Event
    """
    for path_str in paths:

        # Check for early-exit signal from the main process (non-blocking).
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Event.is_set
        if stop_event.is_set():
            break

        # ----------------------------------------------------------------
        # Snapshot the current target size from shared memory
        # ----------------------------------------------------------------
        # multiprocessing.Value exposes the underlying C integer through its
        # ``.value`` attribute.  The Value's built-in lock ensures we see a
        # complete write (no torn reads where we catch shared_w mid-update).
        # Reading both under the same lock would require explicit acquire/
        # release; the small risk of seeing w from one resize and h from the
        # next is acceptable because the aspect-ratio calculation below
        # constrains both dimensions together anyway.
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value
        target_w = shared_w.value
        target_h = shared_h.value

        # ----------------------------------------------------------------
        # Load the BMP with Pillow
        # ----------------------------------------------------------------
        # Image.open() is lazy; .convert("RGB") forces a full decode and
        # normalises any palette, grayscale, or RGBA source to packed 24-bit
        # RGB — exactly 3 bytes per pixel, which is what QImage.Format_RGB888
        # expects.
        # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open
        # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.convert
        try:
            img = Image.open(path_str).convert("RGB")
        except Exception as exc:
            print(f"Warning: could not load '{path_str}': {exc} – skipping",
                  file=sys.stderr)
            continue

        # ----------------------------------------------------------------
        # Compute aspect-ratio-preserving target dimensions
        # ----------------------------------------------------------------
        # Mirrors Qt.KeepAspectRatio: find the largest box that fits inside
        # (target_w, target_h) while keeping the original width/height ratio.
        src_w, src_h = img.size
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))

        # ----------------------------------------------------------------
        # Resize with nearest-neighbour resampling
        # ----------------------------------------------------------------
        # Image.NEAREST (= 0) is the fastest Pillow filter — no interpolation,
        # just pixel dropping or duplication.  Use Image.BILINEAR or
        # Image.LANCZOS for higher quality at greater CPU cost.
        # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize
        # https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters-comparison-table
        img = img.resize((new_w, new_h), Image.NEAREST)

        # ----------------------------------------------------------------
        # Serialise to raw bytes
        # ----------------------------------------------------------------
        # tobytes() returns a bytes object: new_w × new_h × 3 bytes, row-
        # major, no row padding.  The main process wraps this in a QImage
        # with Format_RGB888 and calls setPixmap() directly — no further
        # scaling needed for frames produced at the current target size.
        # https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.tobytes
        raw: bytes = img.tobytes()

        # ----------------------------------------------------------------
        # Enqueue with back-pressure
        # ----------------------------------------------------------------
        # Loop with a short timeout so stop_event can be checked while the
        # queue is full, preventing a shutdown deadlock.
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue.put
        while not stop_event.is_set():
            try:
                out_queue.put((raw, new_w, new_h), timeout=0.05)
                break  # successfully enqueued
            except Exception:
                continue  # queue full; retry

    # Enqueue end-of-sequence sentinel.  None is always picklable and is
    # never a valid (bytes, int, int) tuple.
    if not stop_event.is_set():
        out_queue.put(None)


class Video:
    def __init__(self, app, MainWindow, VideoFile, Prefix, ImageDirectory, SkipCount):
        """
        Create video player

        Args:
            app -- The qt application 
            MainWindow -- Window in which we display the stuff
            VideoFile -- Video file to play
            ImageDirectory -- Where the images go
        """
        self.app = app
        self.VideoFile = VideoFile
        self.Prefix = Prefix
        self.ImageDirectory = ImageDirectory
        self.ImageLabel = MainWindow.VideoFrame

        video_to_frames.SetFPS(Prefix)
        FullFpsFile = os.path.join(self.ImageDirectory, video_to_frames.FPS_FILE)
        NeedRebuild = False
        if (not os.path.isfile(FullFpsFile)):
            NeedRebuild = True
        else:
            if os.path.getmtime(FullFpsFile) < os.path.getmtime(self.VideoFile):
                NeedRebuild = True

        if (not NeedRebuild):
            self.LoadImages()
        if (NeedRebuild or len(self.ImageFiles) == 0):
            self.ExtractImages()
            self.LoadImages()
            if (len(self.ImageFiles) == 0):
                print("FATAL ERROR: Unable to get video files")
                sys.exit(8)
        self.SkipCount = SkipCount
        self.Reset()

    def CallBack(self, Code, Message):
        """
        Called when extracting frames

        Args
            Code -- Message type code
            Message -- Message
        """
        self.app.processEvents()
        if (Code == 1):
            self.Progress.VideoInfoLabel.setText(Message)
        elif (Code == 2):
            self.Progress.ProgressLabel.setText(Message)
        else:
            print("INTERNAL ERROR: Illegal callback code:", Code)

    def ExtractImages(self):
        """
        Extract the frames from the video
        """
        self.ProgressDialog = QtWidgets.QDialog()

        self.Progress = frames_ui.Ui_FramePopup()
        self.Progress.setupUi(self.ProgressDialog)

        self.ProgressDialog.show()
        self.ProgressDialog.raise_()
        self.ProgressDialog.activateWindow()
        self.app.processEvents()
        video_to_frames.extract_frames(self.VideoFile, self.ImageDirectory, self.CallBack, self.Prefix)
        self.ProgressDialog.hide()

    def StartBackgroundProcess(self):
        """
        Start the background process to load the frames
        """
        if (self.ImageFiles):
            first_img = Image.open(str(self.ImageFiles[0]))
            self.native_w, self.native_h = first_img.size
            first_img.close()
        else:
            self.native_w = -1
            self.native_h = -1
        # -------------------------------------------------------------------
        # Shared-memory size channel  (main → worker)
        # -------------------------------------------------------------------
        # multiprocessing.Value(typecode, initial_value) allocates a typed
        # value in shared memory backed by a multiprocessing.Lock.
        # Typecode 'i' = signed 32-bit C int (sufficient for any screen size).
        # The worker reads .value before scaling each frame; the main process
        # writes .value in resizeEvent().
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value
        #
        # Initial values = the label's size after the window has been laid out.
        # We use native_w/native_h here; the layout engine may adjust the
        # label slightly before the first frame, but that causes at most one
        # or two frames at a slightly wrong size — acceptable.
        self._shared_w = multiprocessing.Value('i', self.native_w)
        self._shared_h = multiprocessing.Value('i', self.native_h)

        # -------------------------------------------------------------------
        # Multiprocessing queue and stop event
        # -------------------------------------------------------------------
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Event
        self._stop_event = multiprocessing.Event()

        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue
        self._frame_queue: multiprocessing.Queue = multiprocessing.Queue(
            maxsize=QUEUE_SIZE
        )

        # -------------------------------------------------------------------
        # Launch the worker process
        # -------------------------------------------------------------------
        # daemon=True: child is killed automatically if the main process exits.
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process
        self._worker = multiprocessing.Process(
            target=frame_loader_proc,
            args=(
                self.ImageFiles,                 # plain strings – picklable
                self._shared_w,                  # shared target width
                self._shared_h,                  # shared target height
                self._frame_queue,
                self._stop_event,
            ),
            daemon=True,
        )
        # start() spawns the child process and returns immediately.
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.start
        self._worker.start()

    def LoadImages(self):
        """
        Load the image names into the system
        """
        FpsFile = open(os.path.join(self.ImageDirectory, video_to_frames.FPS_FILE), "r")
        Line = FpsFile.readline()
        if (Line == ''):
            self.ImageFiles = []
            return
        self.BaseFps = float(Line.strip())               # Get the video speed
        # Find all files matching the pattern frame_XXXX.bmp
        Pattern = os.path.join(self.ImageDirectory, f'{self.Prefix}.frame_*.bmp')
        Files = glob.glob(Pattern)
        
        # Sort files to ensure correct order
        self.ImageFiles = sorted(Files)

        self.StartBackgroundProcess()

        self.FrameTimer = QtCore.QTimer()
        self.FrameTimer.timeout.connect(self.NextFrame)
        
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
                Interval = int((1000.0 / (self.BaseFps * self.Rate)))
                self.FrameTimer.setInterval(Interval)
            else:
                state.Log("Ran out of video")
                self.FrameTimer.stop()

    def ShowCurrentFrame(self):
        """Display the current frame"""
        # If the system has not initialized things
        if (self.ImageLabel.width() == 100):
            return

        # Non-blocking dequeue.
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue.get
        try:
            item = self._frame_queue.get_nowait()
        except queue.Empty:
            return  # nothing ready; try again next idle cycle

        # Do we need to skip some frames
        if ((self.CurrentFrame % self.SkipCount) != 0):
            return

        if self.ImageFiles and 0 <= self.CurrentFrame < len(self.ImageFiles):
            # Unpack the pre-scaled payload.
            raw_bytes, w, h = item

            # -------------------------------------------------------------------
            # Reconstruct QImage from raw bytes
            # -------------------------------------------------------------------
            # QImage(data, width, height, bytes_per_line, format)
            # bytes_per_line = w * 3  (3 bytes per pixel, no row padding)
            # Format_RGB888: packed 24-bit RGB, no alpha.
            # https://doc.qt.io/qt-5/qimage.html#QImage-8
            # https://doc.qt.io/qt-5/qimage.html#Format-enum
            img = QImage(raw_bytes, w, h, w * 3, QImage.Format_RGB888)

            #
            self.ImageLabel.setPixmap(QPixmap.fromImage(img))

    def Reset(self):
        """
        Reset the video
        """
        self.SetRate(0)
        self.CurrentFrame = 0
        self.ShowCurrentFrame()

    #@profile
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

    #@profile
    def GetPosition(self):
        """
        Return the position of the video as a fraction of the total video
        """
        return ( float(self.CurrentFrame) / float(len(self.ImageFiles)) )
