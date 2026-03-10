#!/bin/bash

LOCAL_FILE=receiver.py
LOCAL_ICON=icon.png

if [ ! -f "$LOCAL_FILE" ]; then
    echo "File not found"
    exit 1
fi

echo "Setting up the $LOCAL_FILE..."

sleep 2

echo -e "[Desktop Entry]\nName=DaTra\nExec=python $(pwd)/$LOCAL_FILE\nIcon=$(pwd)/$LOCAL_ICON\nTerminal=false\nType=Application\nCategories=Utility;" > ~/.local/share/applications/DaTra.desktop

sleep 2

echo "Everything is ready to use."


