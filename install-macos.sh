#!/bin/sh
#
# Install the trolley simulator for the current user (macOS).
#
# Works from the USB drive / zip produced by "make output":
#     <DRIVE>/install-macos.sh
#     <DRIVE>/macos/trolley
# and, for developers, from a source tree after "make macos":
#     ./install-macos.sh
#     ./dist/trolley-macos
#
# Usage (from any directory):
#     sh /path/to/install-macos.sh
#
# The script finds the binary relative to its own location, so it
# doesn't matter which directory you run it from.

# Directory this script lives in
HERE=$(cd "$(dirname "$0")" && pwd)

if [ -f "$HERE/macos/trolley" ] ; then
    SRC="$HERE/macos/trolley"             # USB drive layout
elif [ -f "$HERE/dist/trolley-macos" ] ; then
    SRC="$HERE/dist/trolley-macos"        # Source tree after "make macos"
else
    echo "ERROR: Can't find the trolley program."
    echo "Looked for:"
    echo "    $HERE/macos/trolley"
    echo "    $HERE/dist/trolley-macos"
    echo "Run this script from the top directory of the trolley USB drive."
    exit 8
fi

DEST_DIR="$HOME/bin"
DEST="$DEST_DIR/trolley"

mkdir -p "$DEST_DIR" || exit 8

# Copy to a temporary name first, so a failed or interrupted copy (the
# file is big, and USB drives are slow) never leaves a half-written
# program behind under the real name.
echo "Copying the program (this can take a minute from a USB drive)..."
if ! cp "$SRC" "$DEST.tmp" ; then
    rm -f "$DEST.tmp"
    echo "ERROR: Copy failed.  Is there enough free space in $DEST_DIR?"
    exit 8
fi
# USB drives are usually FAT formatted and have no "execute" permission,
# so always set it on the copy.
chmod a+x "$DEST.tmp"
mv -f "$DEST.tmp" "$DEST" || exit 8

# If the program arrived by download (e.g. the zip from a web page), macOS
# marks it "quarantined" and Gatekeeper refuses to run an unsigned program.
# Clear the mark.  Harmless if it isn't there.
xattr -d com.apple.quarantine "$DEST" 2>/dev/null

echo
echo "Installed: $DEST"
echo "To run the simulator, open a Terminal window and enter:"
echo "    $DEST"
case ":$PATH:" in
    *":$DEST_DIR:"*)
        echo "(or just: trolley)" ;;
esac
