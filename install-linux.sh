#!/usr/bin/bash
if [ ! -f ./trolley ] ; then
    echo "This script must be executed in the <DRIVE>/linux directory"
    exit 8
fi
mkdir -p ~/bin
cp trolley ~/bin
chmod a+x ~/bin/trolley

echo "Binary installed in $HOME/bin/trolley"
echo "Open a terminal window to run the program using the command"
echo "$HOME/bin/trolley"
