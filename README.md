# 📡 DaTra

Transfer files between your Android phone and your laptop over Bluetooth – no cable, no cloud, no account needed.

---

## 📁 Repository Structure

```
datra/
├── linux/
│   ├── receiver.py
│   └── icon.png
├── windows/
│   ├── receiver_windows.py
│   └── icon.png
│   └── icon.ico
├── android/
│   └── DaTra.apk
└── README.md
```

---

## ⚙️ Setup

### Prerequisites
- Laptop and phone must be **paired via Bluetooth** before using the app
- Python 3.8 or newer installed on your laptop

---

### 🐧 Linux

**1. Install dependencies**
```bash
# Arch Linux
sudo pacman -S python-tk bluez bluez-utils

# Ubuntu / Debian
sudo apt install python3-tk bluez
```

```bash
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
```

**2. Allow Bluetooth without sudo (run once)**
```bash
sudo setcap cap_net_raw,cap_net_admin+eip $(which python3)
```

**3. Run the app**
```bash
python linux/receiver.py
```

**4. Create a desktop icon (optional)**

Create the file `~/.local/share/applications/bluetooth-transfer.desktop`:
```ini
[Desktop Entry]
Name=DaTra
Exec=python /path/to/linux/receiver.py
Icon=/path/to/linux/icon.png
Terminal=false
Type=Application
Categories=Utility;
```
Replace `/path/to/` with the actual path on your machine. The app will then appear in your application launcher.

---

### 🪟 Windows

**1. Install Python**

Download from [python.org](https://python.org) – make sure to check **"Add Python to PATH"** during installation.

**2. Run the app**
```cmd
python windows\receiver_windows.py
```

**3. Create a desktop shortcut with icon (optional)**

1. Right-click desktop → **New → Shortcut**
2. Location: `python C:\path\to\windows\receiver_windows.py`
3. Right-click shortcut → **Properties → Change Icon**
4. Select `windows\icon.ico`

---

### 📱 Android

Simply install the APK from the `android/` folder:

1. Copy `DaTra.apk` to your phone
2. Open the file on your phone
3. If prompted, allow installation from unknown sources
4. Install and open the app

---

## 📖 How to Use

### Phone → Laptop

1. Open the Python app on your laptop
2. Go to the **Receive** tab and choose a save folder
3. Click **Start Receiving**
4. Open the Android app, tap **Load Devices** and select your laptop
5. Tap **Select File**, choose a file, then tap **Send File**
6. The file will appear in your chosen folder

### Laptop → Phone

1. Open the Python app on your laptop
2. Go to the **Send** tab, load devices and select your phone
3. Select a file and click **Send File**
4. Accept the incoming file notification on your phone
5. The file lands in your phone's Downloads folder

---

## ✅ Why use this?

- No internet required – works purely over Bluetooth
- No third-party apps or accounts needed
- Works with any file type
- Simple and lightweight – just one Python file per platform
