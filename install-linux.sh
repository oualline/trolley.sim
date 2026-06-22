#!/usr/bin/bash
if [ ! -f ./dist/trolley-linux ] ; then
    echo "This script must be executed in the <DRIVE> directory"
    exit 8
fi
mkdir -p ~/bin
cp ./dist/trolley-linux ~/bin/trolley
chmod a+x ~/bin/trolley

echo "Binary installed in $HOME/bin/trolley"
echo "Open a terminal window to run the program using the command"
echo "$HOME/bin/trolley"
