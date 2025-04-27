import os
import sys

print("Getting ready.  This may take a little time")

base_path = sys._MEIPASS
os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(base_path, "VLC", "libvlc.dll")
os.environ['PYTHON_VLC_MODULE_PATH'] = os.path.join(base_path, "VLC")

