#${HOME}/tmp/10-minute.mp4 ${HOME}/tmp/trolley.mp4 mode_window.py

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
	pyuic5 -o sim_ui4.py sim_ui4.ui

frames_ui.py: frames_ui.ui
	pyuic5 -o frames_ui.py frames_ui.ui

mode_window.py: mode_window.ui
	pyuic5 -o mode_window.py mode_window.ui

clean: 
	rm -f sim_ui4.py mode_window.py frames_ui.py
	rm -rf __pycache__ build dist build.macos
	rm -f quick.pdf help.pdf
	rm -rf frames
	rm -rf venv
	rm -rf .DS_Store ._.DS_Store

linux: $(GENERATED) $(HELP)
	pyinstaller trolley-linux.spec
	chmod a+x dist/trolley-linux

windows: $(GENERATED) $(HELP)
	pyinstaller -y trolley-windows.spec

macos: $(GENERATED) $(HELP)
	if [ x$$VIRTUAL_ENV_PROMPT == x ] ; then echo "Must be inside the venv."; exit 8; fi
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
