#!/bin/bash

LOCAL_FILE="receiver.py"
LOCAL_ICON="icon.png"

# Prüfen ob beide Dateien existieren
if [ ! -f "$LOCAL_FILE" ]; then
    echo "Error: $LOCAL_FILE not found"
    exit 1
fi

if [ ! -f "$LOCAL_ICON" ]; then
    echo "Warning: $LOCAL_ICON not found, desktop entry wird ohne Icon erstellt"
fi

echo "Setting up $LOCAL_FILE..."
sleep 2

# Heredoc statt echo -e (sauberer und weniger fehleranfällig)
cat > ~/.local/share/applications/DaTra.desktop << EOF
[Desktop Entry]
Name=DaTra
Exec=python3 $(pwd)/$LOCAL_FILE
Icon=$(pwd)/$LOCAL_ICON
Terminal=false
Type=Application
Categories=Utility;
EOF

# Desktop-Datenbank aktualisieren damit der Eintrag sofort erscheint
update-desktop-database ~/.local/share/applications/ 2>/dev/null

sleep 2
echo "Everything is ready to use."
