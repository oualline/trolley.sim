# Detect OS once. On native Windows make, OS=Windows_NT is set by the
# environment. On Unix, fall back to uname -s (Linux / Darwin).
ifeq ($(OS),Windows_NT)
    DETECTED_OS := Windows
else
    DETECTED_OS := $(shell uname -s)
endif

ifneq ($(filter linux,$(MAKECMDGOALS)),)
    ifneq ($(DETECTED_OS),Linux)
        $(error 'make linux' can only be run on Linux (detected: $(DETECTED_OS)))
    endif
endif

ifneq ($(filter windows,$(MAKECMDGOALS)),)
    ifneq ($(DETECTED_OS),Windows)
        $(error 'make windows' can only be run on Windows (detected: $(DETECTED_OS)))
    endif
endif

ifneq ($(filter macos,$(MAKECMDGOALS)),)
    ifneq ($(DETECTED_OS),Darwin)
        $(error 'make macos' can only be run on macOS (detected: $(DETECTED_OS)))
    endif
endif

.PHONY: linux windows macos

GENERATED=mode_window.py sim_ui4.py frames_ui.py
HELP=quick.pdf help.pdf
all: $(HELP) $(GENERATED)

help:
	@echo "make -- make local program"
	@echo "make clean -- remove built files "
	@echo "make linux -- make the linux single exe file"
	@echo "make windows -- make the windows single exe file (must be executed on windows)"
	@echo "make output -- Create a zip with the image of the program"

quick.pdf: quick.odt
	libreoffice --headless --convert-to pdf  quick.odt

help.pdf: help.odt
	libreoffice --headless --convert-to pdf  help.odt

sim_ui4.py: sim_ui4.ui
	pyuic6 -o sim_ui4.py sim_ui4.ui

frames_ui.py: frames_ui.ui
	pyuic6 -o frames_ui.py frames_ui.ui

mode_window.py: mode_window.ui
	pyuic6 -o mode_window.py mode_window.ui

clean: 
	rm -f sim_ui4.py mode_window.py frames_ui.py
	rm -rf __pycache__ build dist build.macos
	rm -f quick.pdf help.pdf
	rm -rf frames
	rm -rf venv
	rm -rf .DS_Store ._.DS_Store
	rm -f trolley.zip

linux: $(GENERATED) $(HELP)
	pyinstaller trolley-linux.spec
	chmod a+x dist/trolley-linux

windows: $(GENERATED) $(HELP)
	pyinstaller -y trolley-windows.spec

macos: $(GENERATED) $(HELP)
	if [ "$$VIRTUAL_ENV" == "" ] ; then echo "Must be inside the venv."; echo "source ~/venv/bin/activate";exit 8; fi
	pyinstaller --workpath build.macos -y trolley-macos.spec
	chmod a+x dist/trolley-macos

junk:
	#pyinstaller --distpath=/home/user/dist --log-level DEBUG -y trolley-windows.spec
	#pyinstaller trolley-windows.spec

# Files that go into the system
FILES= bugs.txt developers.txt help.pdf readme.txt LICENSE.txt
# Where to put the output
DIR=/tmp/trolley.sim
OLD_DIR := $(shell pwd)

output: $(FILES) dist/trolley-linux dist/trolley-windows dist/trolley-macos
	rm -rf $(DIR)
	mkdir $(DIR)
	cp $(FILES) $(DIR)
	mkdir $(DIR)/linux
	mkdir $(DIR)/macos
	cp dist/trolley-linux $(DIR)/linux/trolley
	cp dist/trolley-macos $(DIR)/macos/trolley
	cp install-linux.sh $(DIR)
	cp install-macos.sh $(DIR)
	chmod a+x $(DIR)/linux/trolley
	#
	mkdir $(DIR)/windows
	cp -r dist/trolley-windows $(DIR)/windows
	#
	rm -f trolley.zip
	(cd $(DIR);zip -r $(OLD_DIR)/trolley.zip .)
