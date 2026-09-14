#!/bin/bash
set -e

LOCAL_FILE="receiver.py"
LOCAL_ICON="icon.png"

# ──────────────────────────────────────────
#  Dependency install – distro-agnostic
# ──────────────────────────────────────────
install_deps() {
    echo "Detecting package manager..."

    if command -v pacman >/dev/null 2>&1; then
        PKG_MGR="pacman"
        INSTALL_CMD="sudo pacman -S --needed --noconfirm"
        PACKAGES="tk bluez bluez-utils python-pybluez base-devel"
    elif command -v apt-get >/dev/null 2>&1; then
        PKG_MGR="apt"
        INSTALL_CMD="sudo apt-get install -y"
        sudo apt-get update
        PACKAGES="python3-tk bluez libbluetooth-dev python3-bluez build-essential python3-pip"
    elif command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
        INSTALL_CMD="sudo dnf install -y"
        PACKAGES="python3-tkinter bluez bluez-libs-devel python3-bluez gcc python3-pip"
    elif command -v zypper >/dev/null 2>&1; then
        PKG_MGR="zypper"
        INSTALL_CMD="sudo zypper install -y"
        PACKAGES="python3-tk bluez bluez-devel python3-pybluez gcc python3-pip"
    elif command -v apk >/dev/null 2>&1; then
        PKG_MGR="apk"
        INSTALL_CMD="sudo apk add"
        PACKAGES="py3-tkinter bluez bluez-dev py3-bluez build-base python3-dev py3-pip"
    else
        echo "Warning: Kein unterstützter Paketmanager gefunden (pacman/apt/dnf/zypper/apk)."
        echo "Bitte installiere manuell: Tk-Bindings für Python, bluez, und PyBluez."
        PKG_MGR=""
    fi

    if [ -n "$PKG_MGR" ]; then
        echo "Installiere Abhängigkeiten via $PKG_MGR..."
        $INSTALL_CMD $PACKAGES || echo "Warnung: mindestens ein Paket konnte nicht installiert werden, versuche trotzdem weiterzumachen."
    fi
}

# ──────────────────────────────────────────
#  Python-Interpreter finden
# ──────────────────────────────────────────
find_python() {
    for candidate in python3.14 python3.13 python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PYTHON_BIN="$(command -v "$candidate")"
            return
        fi
    done
    echo "Error: Kein Python 3 gefunden."
    exit 1
}

# ──────────────────────────────────────────
#  Verifizieren: tkinter + bluetooth importierbar?
# ──────────────────────────────────────────
verify_modules() {
    echo "Prüfe tkinter..."
    if ! "$PYTHON_BIN" -c "import tkinter" 2>/dev/null; then
        echo "Warnung: tkinter ist unter $PYTHON_BIN weiterhin nicht importierbar."
        echo "Prüfe, ob dein Interpreter zum installierten Tk-Paket passt (System-Python vs. eigene Installation z.B. pyenv/uv)."
    fi

    echo "Prüfe PyBluez (bluetooth-Modul)..."
    if ! "$PYTHON_BIN" -c "import bluetooth" 2>/dev/null; then
        echo "PyBluez nicht gefunden, versuche Installation via pip als Fallback..."
        "$PYTHON_BIN" -m pip install --break-system-packages "git+https://github.com/pybluez/pybluez.git" \
            || echo "Warnung: PyBluez-Fallback-Installation fehlgeschlagen. Bitte manuell prüfen (Build-Tools + Bluetooth-Header nötig)."
    fi
}

# ──────────────────────────────────────────
#  Haupt-Setup
# ──────────────────────────────────────────
if [ ! -f "$LOCAL_FILE" ]; then
    echo "Error: $LOCAL_FILE not found"
    exit 1
fi

if [ ! -f "$LOCAL_ICON" ]; then
    echo "Warning: $LOCAL_ICON not found, desktop entry wird ohne Icon erstellt"
fi

install_deps
find_python
verify_modules

echo "Verwende Python-Interpreter: $PYTHON_BIN"
echo "Setting up $LOCAL_FILE..."
sleep 1

mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/DaTra.desktop << EOF
[Desktop Entry]
Name=DaTra
Exec=$PYTHON_BIN $(pwd)/$LOCAL_FILE
Icon=$(pwd)/$LOCAL_ICON
Terminal=false
Type=Application
Categories=Utility;
EOF

update-desktop-database ~/.local/share/applications/ 2>/dev/null

sleep 1
echo "Everything is ready to use."
