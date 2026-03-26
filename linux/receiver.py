import tkinter as tk
from tkinter import ttk, filedialog
import socket
import threading
import subprocess
import os

# ──────────────────────────────────────────
#  Bluetooth Constants
# ──────────────────────────────────────────
AF_BLUETOOTH   = 31
BTPROTO_RFCOMM = 3

def get_local_mac():
    """Automatically detect the Bluetooth MAC address of this machine."""
    try:
        result = subprocess.run(
            ["bluetoothctl", "show"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Controller" in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return ""

LAPTOP_MAC = get_local_mac()

# ──────────────────────────────────────────
#  State
# ──────────────────────────────────────────
save_location  = {"path": ""}
receive_active = {"active": False}
send_file      = {"path": "", "name": ""}

# ──────────────────────────────────────────
#  RECEIVE – Bluetooth Socket
# ──────────────────────────────────────────
def bluetooth_receive():
    receive_active["active"] = True
    start_button.config(state="disabled", text="Receiving...")

    if not LAPTOP_MAC:
        set_receive_status("❌ Bluetooth MAC not found. Is Bluetooth enabled?")
        receive_active["active"] = False
        start_button.config(state="normal", text="Start Receiving")
        return

    try:
        server_sock  = None
        found_port   = None

        for port in range(1, 31):
            try:
                server_sock = socket.socket(AF_BLUETOOTH, socket.SOCK_STREAM, BTPROTO_RFCOMM)
                server_sock.bind((LAPTOP_MAC, port))
                server_sock.listen(1)
                found_port = port
                break
            except Exception:
                if server_sock:
                    server_sock.close()
                server_sock = None

        if server_sock is None:
            set_receive_status("❌ No free Bluetooth port found!")
            return

        set_receive_status(f"Waiting for connection... (Port {found_port})")

        client_sock, address = server_sock.accept()
        set_receive_status(f"Connected to {address[0]}")

        raw_data  = client_sock.recv(1024)
        filename  = os.path.basename(raw_data.decode("utf-8").strip())
        filepath  = os.path.join(save_location["path"], filename)

        set_receive_status(f"Receiving: {filename}")
        progress_receive["value"] = 0

        received_bytes = 0
        with open(filepath, "wb") as f:
            while True:
                try:
                    data = client_sock.recv(4096)
                except Exception:
                    break
                if not data:
                    break
                f.write(data)
                received_bytes += len(data)
                progress_receive["value"] = min(received_bytes / 1024, 100)
                window.update_idletasks()

        progress_receive["value"] = 100
        file_list.insert(tk.END, f"✔  {filename}  ({received_bytes // 1024} KB)")
        set_receive_status(f"✅ Saved: {filepath}")

        try:
            client_sock.close()
            server_sock.close()
        except Exception:
            pass

    except Exception as error:
        set_receive_status(f"❌ Error: {error}")
    finally:
        receive_active["active"] = False
        start_button.config(state="normal", text="Start Receiving")


# ──────────────────────────────────────────
#  SEND – Bluetooth via OBEX
# ──────────────────────────────────────────
def bluetooth_send():
    if not send_file["path"]:
        set_send_status("⚠️  Please select a file first!")
        return

    selection = device_listbox.curselection()
    if not selection:
        set_send_status("⚠️  Please select a device first!")
        return

    mac = paired_devices[selection[0]]["mac"]
    send_button.config(state="disabled", text="Sending...")
    progress_send["value"] = 0
    set_send_status("Connecting...")

    def send_thread():
        try:
            set_send_status("Sending via OBEX...")
            result = subprocess.run(
                ["bluetooth-sendto", "--device=" + mac, send_file["path"]],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                progress_send["value"] = 100
                set_send_status(f"✅ Sent: {send_file['name']}")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                set_send_status(f"❌ Error: {error}")
        except subprocess.TimeoutExpired:
            set_send_status("❌ Timeout – Accept the file on your phone!")
        except Exception as e:
            set_send_status(f"❌ Error: {e}")
        finally:
            send_button.config(state="normal", text="Send File")

    threading.Thread(target=send_thread, daemon=True).start()


def select_file():
    path = filedialog.askopenfilename(title="Select File")
    if path:
        send_file["path"] = path
        send_file["name"] = os.path.basename(path)
        file_label.config(text=f"📄  {send_file['name']}")


def load_devices():
    """Load paired devices via bluetoothctl"""
    device_listbox.delete(0, tk.END)
    paired_devices.clear()

    try:
        result = subprocess.run(
            ["bluetoothctl", "devices", "Paired"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()

        if not lines:
            device_listbox.insert(tk.END, "No paired devices found.")
            return

        for line in lines:
            parts = line.strip().split(" ", 2)
            if len(parts) == 3 and parts[0] == "Device":
                mac  = parts[1]
                name = parts[2]
                paired_devices.append({"mac": mac, "name": name})
                device_listbox.insert(tk.END, f"  {name}  [{mac}]")

    except Exception as e:
        device_listbox.insert(tk.END, f"Error: {e}")


# ──────────────────────────────────────────
#  Helper Functions
# ──────────────────────────────────────────
def set_receive_status(text):
    receive_status.config(text=f"Status: {text}")

def set_send_status(text):
    send_status.config(text=f"Status: {text}")

def choose_folder():
    folder = filedialog.askdirectory(title="Choose Save Folder")
    if folder:
        save_location["path"] = folder
        folder_label.config(text=f"📁  {folder}")

def start_receiving():
    if save_location["path"] == "":
        set_receive_status("⚠️  Please choose a folder first!")
        return
    if receive_active["active"]:
        set_receive_status("⚠️  Already receiving!")
        return
    threading.Thread(target=bluetooth_receive, daemon=True).start()

def clear_list():
    file_list.delete(0, tk.END)
    progress_receive["value"] = 0
    set_receive_status("List cleared.")


# ──────────────────────────────────────────
#  Window & UI
# ──────────────────────────────────────────
window = tk.Tk()
window.title("📡 DaTra")
window.geometry("560x540")
window.resizable(False, False)
window.configure(bg="#1e1e2e")

# Load icon if available
try:
    icon = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "icon.png"))
    window.iconphoto(True, icon)
except Exception:
    pass

BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
TEXT    = "#cdd6f4"
SUBTEXT = "#6c7086"

tk.Label(window, text="DaTra",
         bg=BG, fg=ACCENT, font=("Courier New", 16, "bold")).pack(pady=(18, 3))
tk.Label(window, text="Linux  •  native socket + Tkinter",
         bg=BG, fg=SUBTEXT, font=("Courier New", 9)).pack(pady=(0, 10))

style = ttk.Style()
style.theme_use("default")
style.configure("TNotebook",     background=BG, borderwidth=0)
style.configure("TNotebook.Tab", background=CARD, foreground=TEXT,
                font=("Courier New", 10), padding=[12, 5])
style.map("TNotebook.Tab",       background=[("selected", ACCENT)],
                                 foreground=[("selected", BG)])
style.configure("custom.Horizontal.TProgressbar",
                troughcolor=BG, background=ACCENT, thickness=10)

tab_ctrl = ttk.Notebook(window)
tab_ctrl.pack(fill="both", expand=True, padx=16, pady=6)

tab_receive = tk.Frame(tab_ctrl, bg=BG)
tab_send    = tk.Frame(tab_ctrl, bg=BG)
tab_ctrl.add(tab_receive, text="  Receive  ")
tab_ctrl.add(tab_send,    text="  Send  ")


# ════════════════════════════════
#  TAB 1 – Receive
# ════════════════════════════════

frame_folder = tk.Frame(tab_receive, bg=CARD, padx=15, pady=12)
frame_folder.pack(fill="x", padx=14, pady=(14, 6))

tk.Label(frame_folder, text="Save Location", bg=CARD, fg=SUBTEXT,
         font=("Courier New", 9)).pack(anchor="w")
folder_label = tk.Label(frame_folder, text="No folder selected",
                         bg=CARD, fg=TEXT, font=("Courier New", 10),
                         wraplength=460, anchor="w")
folder_label.pack(anchor="w", pady=(2, 8))
tk.Button(frame_folder, text="  Choose Folder  ", command=choose_folder,
          bg=ACCENT, fg=BG, font=("Courier New", 10, "bold"),
          relief="flat", cursor="hand2", padx=10, pady=4).pack(anchor="w")

frame_status_r = tk.Frame(tab_receive, bg=CARD, padx=15, pady=12)
frame_status_r.pack(fill="x", padx=14, pady=6)

receive_status = tk.Label(frame_status_r, text="Status: Ready",
                           bg=CARD, fg=GREEN, font=("Courier New", 10), anchor="w")
receive_status.pack(fill="x")
progress_receive = ttk.Progressbar(frame_status_r,
                                    style="custom.Horizontal.TProgressbar",
                                    length=500, mode="determinate", maximum=100)
progress_receive.pack(pady=(8, 0))

frame_buttons_r = tk.Frame(tab_receive, bg=BG)
frame_buttons_r.pack(pady=8)

start_button = tk.Button(frame_buttons_r, text="Start Receiving",
                          command=start_receiving,
                          bg=GREEN, fg=BG, font=("Courier New", 11, "bold"),
                          relief="flat", cursor="hand2", padx=20, pady=6)
start_button.pack(side="left", padx=8)
tk.Button(frame_buttons_r, text="Clear List", command=clear_list,
          bg=CARD, fg=TEXT, font=("Courier New", 10),
          relief="flat", cursor="hand2", padx=15, pady=6).pack(side="left", padx=8)

frame_list = tk.Frame(tab_receive, bg=CARD, padx=15, pady=12)
frame_list.pack(fill="both", expand=True, padx=14, pady=(0, 14))

tk.Label(frame_list, text="Received Files", bg=CARD, fg=SUBTEXT,
         font=("Courier New", 9)).pack(anchor="w")
file_list = tk.Listbox(frame_list, bg=BG, fg=GREEN,
                        font=("Courier New", 10),
                        selectbackground=ACCENT, selectforeground=BG,
                        relief="flat", highlightthickness=0, bd=0)
file_list.pack(fill="both", expand=True, pady=(4, 0))


# ════════════════════════════════
#  TAB 2 – Send
# ════════════════════════════════

frame_devices = tk.Frame(tab_send, bg=CARD, padx=15, pady=12)
frame_devices.pack(fill="x", padx=14, pady=(14, 6))

tk.Label(frame_devices, text="Paired Devices", bg=CARD, fg=SUBTEXT,
         font=("Courier New", 9)).pack(anchor="w")

paired_devices = []
device_listbox = tk.Listbox(frame_devices, bg=BG, fg=TEXT,
                              font=("Courier New", 10),
                              selectbackground=ACCENT, selectforeground=BG,
                              relief="flat", highlightthickness=0, bd=0, height=4)
device_listbox.pack(fill="x", pady=(4, 8))

tk.Button(frame_devices, text="🔄  Load Devices", command=load_devices,
          bg=ACCENT, fg=BG, font=("Courier New", 10, "bold"),
          relief="flat", cursor="hand2", padx=10, pady=4).pack(anchor="w")

frame_file = tk.Frame(tab_send, bg=CARD, padx=15, pady=12)
frame_file.pack(fill="x", padx=14, pady=6)

tk.Label(frame_file, text="File", bg=CARD, fg=SUBTEXT,
         font=("Courier New", 9)).pack(anchor="w")
file_label = tk.Label(frame_file, text="No file selected",
                       bg=CARD, fg=TEXT, font=("Courier New", 10),
                       wraplength=460, anchor="w")
file_label.pack(anchor="w", pady=(2, 8))
tk.Button(frame_file, text="  Select File  ", command=select_file,
          bg=ACCENT, fg=BG, font=("Courier New", 10, "bold"),
          relief="flat", cursor="hand2", padx=10, pady=4).pack(anchor="w")

frame_status_s = tk.Frame(tab_send, bg=CARD, padx=15, pady=12)
frame_status_s.pack(fill="x", padx=14, pady=6)

send_status = tk.Label(frame_status_s, text="Status: Ready",
                        bg=CARD, fg=GREEN, font=("Courier New", 10), anchor="w")
send_status.pack(fill="x")
progress_send = ttk.Progressbar(frame_status_s,
                                 style="custom.Horizontal.TProgressbar",
                                 length=500, mode="determinate", maximum=100)
progress_send.pack(pady=(8, 0))

send_button = tk.Button(tab_send, text="Send File",
                         command=bluetooth_send,
                         bg=GREEN, fg=BG, font=("Courier New", 11, "bold"),
                         relief="flat", cursor="hand2", padx=20, pady=6)
send_button.pack(pady=12)

# ──────────────────────────────────────────
#  Start App
# ──────────────────────────────────────────
window.mainloop()
