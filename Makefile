#${HOME}/tmp/10-minute.mp4 ${HOME}/tmp/trolley.mp4 mode_window.py

all: sim_ui4.py mode_window.py

help:
	@echo "make -- make local program"
	@echo "make clean -- remove built files "
	@echo "make linux -- make the linux single exe file"
	@echo "make windows -- make the windows single exe file (must be executed on windows)"
	@echo "make output -- Create a zip with the image of the program"

sim_ui4.py: sim_ui4.ui
	pyuic5 -o sim_ui4.py sim_ui4.ui

mode_window.py: mode_window.ui
	pyuic5 -o mode_window.py mode_window.ui

clean: 
	rm -f sim_ui4.py mode_window.py
	rm -rf __pycache__ build dist

linux: mode_window.py sim_ui4.py
	pyinstaller trolley-linux.spec
	# This is because we develop from a FAT32 usb stick and permissions don't work on it
	cp dist/trolley-linux /tmp
	chmod a+x /tmp/trolley-linux

windows: mode_window.py sim_ui4.py
	pyinstaller --log-level DEBUG trolley-windows.spec

# Files that go into the system
FILES= bugs.txt developers.txt help.pdf readme.txt LICENSE.txt
# Where to put the output
DIR=/tmp/trolley.sim
OLD_DIR := $(shell pwd)

output: $(FILES) dist/trolley-linux dist/trolley-windows.exe
	rm -rf $(DIR)
	mkdir $(DIR)
	cp $(FILES) $(DIR)
	mkdir $(DIR)/linux
	cp dist/trolley-linux $(DIR)/linux/trolley
	chmod a+x $(DIR)/linux/trolley
	mkdir $(DIR)/windows
	cp dist/trolley-windows.exe $(DIR)/windows/trolley.exe
	rm -f trolley.zip
	(cd $(DIR);zip -r $(OLD_DIR)/trolley.zip .)
