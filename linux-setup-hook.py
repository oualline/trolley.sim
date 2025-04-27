import os

print("Getting ready.  This may take a little time")

os.environ['PYTHON_VLC_LIB_PATH'] = os.environ['_PYI_APPLICATION_HOME_DIR'] + '/libvlc.so.5'

