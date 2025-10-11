	      Southern California Railroad Museum
		       Trolley Simulator

Support
=======

Only one person at the SCRM knows anything about this program,
so please don't call the store requesting support.  Unlike other 
software, you can return any USB drives you purchased at the SCRM
for a full refund.

Sorry, but this is a volunteer project and there's only so much 
one volunteer can do. Thank you for your understanding and please
don't call in with support questions.

Quick Start
===========

Linux:
     Open a terminal window.

     Go to the "linux" directory on the USB drive.

     Enter the command:

     $ sh install-linux.sh

     Run the program with the command:

     $ ~/bin/trolley

Windows:
   
Use the file manager to open the folder <usb-drive>\Windows.
Copy the directory trolley-windows on to your hard drive.
Inside the folder you'll find the file trolley-windows.exe
which you can now run.

You can run it directly from the USB drive, but it runs
very very slow.

WARNING: The program starts slow even when run from a hard
drive.

Apple:
     Not supported, but watch this space.

Introduction
============

You are now at the throttle of the LARY-1201 trolley.  The trolley
is running around the loop line at the Southern California
Railroad Museum.  See the file help.pdf for information on how
to run the trolley.

Command Line
============

Usage:
    python3 main.py [-b<bottom>] [-t<top>] [-l<left>] [-r<right>] [-d] [-v] [-f]

    Where
	    -b <bottom> -- Set bottom margin
	    -t <top> -- Set top margin
	    -l <left> -- Set left margin
	    -r <right> -- Set right margin
	    -d -- Debug (show button bar)
	    -v -- Verbose
	    -f -- Start in full screen

License
=======

The software is licensed under the Gnu Public License (GPL).
A copy is contained in the file LICENSE.TXT.

Basically you have the right to copy the software as much as you
want.  Give it to your friends and have fun with it.   

The only thing you can't do is change the software and then sell
the changes.  This software was made by people who wanted a
working trolley simulator and decided to share it.  So if you
improve it, please share your improvements.

Note: The above summary is not a legal description of the
rules.  For that you need to see the LICENSE.TXT file.

Developers
==========

Please read developers.txt for more information.
