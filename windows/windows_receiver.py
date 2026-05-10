import tkinter as tk
from tkinter import ttk, filedialog
import socket
import threading
import subprocess
import os

# ──────────────────────────────────────────
#  Windows Bluetooth Constants
# ──────────────────────────────────────────
AF_BLUETOOTH   = 32
BTPROTO_RFCOMM = 3

# ──────────────────────────────────────────
#  Get Laptop Bluetooth MAC automatically
# ──────────────────────────────────────────
def get_local_mac():
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject Win32_NetworkAdapter | Where-Object {$_.Name -like '*Bluetooth*'}).MACAddress"],
            capture_output=True, text=True, timeout=10
        )
        mac = result.stdout.strip()
        if mac:
            return mac.replace("-", ":")
    except Exception:
        pass
    return ""

LAPTOP_MAC = get_local_mac()

# ──────────────────────────────────────────
#  State
# ──────────────────────────────────────────
save_location  = {"path": ""}
receive_active = {"active": False}
send_file      = {"paths": [], "names": []}

# ──────────────────────────────────────────
#  RECEIVE – Bluetooth Socket (multi-file)
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
        server_sock = None
        found_port  = None

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

        files_received = 0

        # Keep accepting connections until stopped
        while receive_active["active"]:
            set_receive_status(f"Waiting for connection... (Port {found_port})"
                               + (f"  –  {files_received} received" if files_received > 0 else ""))

            server_sock.settimeout(2.0)
            try:
                client_sock, address = server_sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            # Handle each file in its own thread so server immediately accepts next
            def handle_file(sock):
                nonlocal files_received
                try:
                    raw_data = sock.recv(1024)
                    if not raw_data:
                        return

                    filename = os.path.basename(raw_data.decode("utf-8").strip())
                    filepath = os.path.join(save_location["path"], filename)

                    set_receive_status(f"Receiving: {filename}")
                    progress_receive["value"] = 0

                    received_bytes = 0
                    with open(filepath, "wb") as f:
                        while True:
                            try:
                                data = sock.recv(4096)
                            except Exception:
                                break
                            if not data:
                                break
                            f.write(data)
                            received_bytes += len(data)
                            progress_receive["value"] = min(received_bytes / 1024, 100)
                            window.update_idletasks()

                    progress_receive["value"] = 100
                    files_received += 1
                    file_list.insert(tk.END, f"✔  {filename}  ({received_bytes // 1024} KB)")
                    set_receive_status(f"✅ Saved: {filename}  –  {files_received} file(s) received")

                except Exception as error:
                    set_receive_status(f"❌ Error receiving file: {error}")
                finally:
                    try:
                        sock.close()
                    except Exception:
                        pass

            threading.Thread(target=handle_file, args=(client_sock,), daemon=True).start()

        try:
            server_sock.close()
        except Exception:
            pass

    except Exception as error:
        set_receive_status(f"❌ Error: {error}")
    finally:
        receive_active["active"] = False
        start_button.config(state="normal", text="Start Receiving")


# ──────────────────────────────────────────
#  SEND – via Windows fsquirt (multi-file)
# ──────────────────────────────────────────
def bluetooth_send():
    if not send_file["paths"]:
        set_send_status("⚠️  Please select files first!")
        return

    selection = device_listbox.curselection()
    if not selection:
        set_send_status("⚠️  Please select a device first!")
        return

    total = len(send_file["paths"])
    send_button.config(state="disabled", text="Sending...")
    progress_send["value"] = 0

    def send_thread():
        for i, path in enumerate(send_file["paths"]):
            name = os.path.basename(path)
            set_send_status(f"Sending {i + 1} / {total}: {name} – Accept on your phone!")
            try:
                proc = subprocess.Popen(["fsquirt"])
                proc.wait(timeout=60)
                progress_send["value"] = int((i + 1) / total * 100)
            except subprocess.TimeoutExpired:
                set_send_status(f"❌ Timeout on {name}")
                send_button.config(state="normal", text="Send Files")
                return
            except Exception as e:
                set_send_status(f"❌ Error: {e}")
                send_button.config(state="normal", text="Send Files")
                return

        progress_send["value"] = 100
        set_send_status(f"✅ Done – {total} file(s) sent.")
        send_button.config(state="normal", text="Send Files")

    threading.Thread(target=send_thread, daemon=True).start()


def select_file():
    paths = filedialog.askopenfilenames(title="Select Files")
    if paths:
        send_file["paths"] = list(paths)
        send_file["names"] = [os.path.basename(p) for p in paths]
        if len(paths) == 1:
            file_label.config(text=f"📄  {send_file['names'][0]}")
        else:
            file_label.config(text=f"📦  {len(paths)} files selected")


def load_devices():
    """Load paired devices via PowerShell registry"""
    device_listbox.delete(0, tk.END)
    paired_devices.clear()

    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-ChildItem 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Devices' | ForEach-Object { $mac = $_.PSChildName -replace '(..)','$1:' -replace ':$',''; $name = (Get-ItemProperty $_.PSPath).Name; [PSCustomObject]@{MAC=$mac; Name=$name} } | Format-List"],
            capture_output=True, text=True, timeout=10
        )

        lines = result.stdout.strip().splitlines()
        mac, name = "", ""

        for line in lines:
            line = line.strip()
            if line.startswith("MAC"):
                mac = line.split(":", 1)[-1].strip().upper()
            elif line.startswith("Name"):
                name = line.split(":", 1)[-1].strip()
                if mac and name:
                    paired_devices.append({"mac": mac, "name": name})
                    device_listbox.insert(tk.END, f"  {name}  [{mac}]")
                    mac, name = "", ""

        if not paired_devices:
            device_listbox.insert(tk.END, "No paired devices found.")

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

def stop_receiving():
    receive_active["active"] = False
    set_receive_status("Stopped.")

def clear_list():
    file_list.delete(0, tk.END)
    progress_receive["value"] = 0
    set_receive_status("List cleared.")


# ──────────────────────────────────────────
#  Window & UI
# ──────────────────────────────────────────
window = tk.Tk()
window.title("📡 DaTra")
window.geometry("680x700")
window.resizable(True, True)
window.configure(bg="#1e1e2e")

try:
    window.iconbitmap(os.path.join(os.path.dirname(__file__), "icon.ico"))
except Exception:
    try:
        icon = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "icon.png"))
        window.iconphoto(True, icon)
    except Exception:
        pass

BG      = "#1e1e2e"
CARD    = "#2a2a3e"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
TEXT    = "#cdd6f4"
SUBTEXT = "#6c7086"
PAD     = 20

tk.Label(window, text="DaTra",
         bg=BG, fg=ACCENT, font=("Courier New", 20, "bold")).pack(pady=(22, 3))
tk.Label(window, text="Windows  •  Bluetooth File Transfer",
         bg=BG, fg=SUBTEXT, font=("Courier New", 10)).pack(pady=(0, 12))

style = ttk.Style()
style.theme_use("default")
style.configure("TNotebook",     background=BG, borderwidth=0)
style.configure("TNotebook.Tab", background=CARD, foreground=TEXT,
                font=("Courier New", 11), padding=[18, 7])
style.map("TNotebook.Tab",       background=[("selected", ACCENT)],
                                 foreground=[("selected", BG)])
style.configure("custom.Horizontal.TProgressbar",
                troughcolor=CARD, background=ACCENT, thickness=12)

tab_ctrl = ttk.Notebook(window)
tab_ctrl.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))

tab_receive = tk.Frame(tab_ctrl, bg=BG)
tab_send    = tk.Frame(tab_ctrl, bg=BG)
tab_ctrl.add(tab_receive, text="  Receive  ")
tab_ctrl.add(tab_send,    text="  Send  ")


def make_card(parent, title):
    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="x", padx=0, pady=(0, 10))
    tk.Label(outer, text=title, bg=BG, fg=SUBTEXT,
             font=("Courier New", 8)).pack(anchor="w", padx=2, pady=(0, 3))
    card = tk.Frame(outer, bg=CARD, padx=16, pady=14)
    card.pack(fill="x")
    return card


def make_btn(parent, text, cmd, color, **kw):
    return tk.Button(parent, text=text, command=cmd,
                     bg=color, fg=BG if color != CARD else TEXT,
                     font=("Courier New", 11, "bold"),
                     relief="flat", cursor="hand2",
                     width=kw.get("width", 16), pady=7,
                     anchor="center")


# ════════════════════════════════
#  TAB 1 – Receive
# ════════════════════════════════

recv_wrap = tk.Frame(tab_receive, bg=BG)
recv_wrap.pack(fill="both", expand=True, padx=0, pady=12)

card_folder = make_card(recv_wrap, "SAVE LOCATION")
folder_label = tk.Label(card_folder, text="No folder selected",
                         bg=CARD, fg=TEXT, font=("Courier New", 11),
                         wraplength=560, anchor="w")
folder_label.pack(fill="x", pady=(0, 10))
tk.Button(card_folder, text="Choose Folder", command=choose_folder,
          bg=ACCENT, fg=BG, font=("Courier New", 11, "bold"),
          relief="flat", cursor="hand2", width=18, pady=7,
          anchor="center").pack(anchor="w")

card_status_r = make_card(recv_wrap, "STATUS")
receive_status = tk.Label(card_status_r, text="Status: Ready",
                           bg=CARD, fg=GREEN, font=("Courier New", 11), anchor="w")
receive_status.pack(fill="x")
progress_receive = ttk.Progressbar(card_status_r,
                                    style="custom.Horizontal.TProgressbar",
                                    mode="determinate", maximum=100)
progress_receive.pack(fill="x", pady=(10, 0))

frame_buttons_r = tk.Frame(recv_wrap, bg=BG)
frame_buttons_r.pack(pady=6)

start_button = make_btn(frame_buttons_r, "Start Receiving", start_receiving, GREEN, width=18)
start_button.pack(side="left", padx=6)
make_btn(frame_buttons_r, "Stop", stop_receiving, RED, width=8).pack(side="left", padx=6)
make_btn(frame_buttons_r, "Clear List", clear_list, CARD, width=12).pack(side="left", padx=6)

card_list = make_card(recv_wrap, "RECEIVED FILES")
outer_list = card_list.master
outer_list.pack_configure(fill="both", expand=True)
card_list.pack_configure(fill="both", expand=True)

file_list = tk.Listbox(card_list, bg=BG, fg=GREEN,
                        font=("Courier New", 11),
                        selectbackground=ACCENT, selectforeground=BG,
                        relief="flat", highlightthickness=0, bd=0)
file_list.pack(fill="both", expand=True)


# ════════════════════════════════
#  TAB 2 – Send
# ════════════════════════════════

send_wrap = tk.Frame(tab_send, bg=BG)
send_wrap.pack(fill="both", expand=True, padx=0, pady=12)

card_devices = make_card(send_wrap, "PAIRED DEVICES")
paired_devices = []
device_listbox = tk.Listbox(card_devices, bg=BG, fg=TEXT,
                              font=("Courier New", 11),
                              selectbackground=ACCENT, selectforeground=BG,
                              relief="flat", highlightthickness=0, bd=0, height=4)
device_listbox.pack(fill="x", pady=(0, 10))
tk.Button(card_devices, text="Load Devices", command=load_devices,
          bg=ACCENT, fg=BG, font=("Courier New", 11, "bold"),
          relief="flat", cursor="hand2", width=18, pady=7,
          anchor="center").pack(anchor="w")

card_file = make_card(send_wrap, "FILES")
file_label = tk.Label(card_file, text="No files selected",
                       bg=CARD, fg=TEXT, font=("Courier New", 11),
                       wraplength=560, anchor="w")
file_label.pack(fill="x", pady=(0, 10))
tk.Button(card_file, text="Select Files", command=select_file,
          bg=ACCENT, fg=BG, font=("Courier New", 11, "bold"),
          relief="flat", cursor="hand2", width=18, pady=7,
          anchor="center").pack(anchor="w")

card_status_s = make_card(send_wrap, "STATUS")
send_status = tk.Label(card_status_s, text="Status: Ready",
                        bg=CARD, fg=GREEN, font=("Courier New", 11), anchor="w")
send_status.pack(fill="x")
progress_send = ttk.Progressbar(card_status_s,
                                 style="custom.Horizontal.TProgressbar",
                                 mode="determinate", maximum=100)
progress_send.pack(fill="x", pady=(10, 0))

send_button = tk.Button(send_wrap, text="Send Files",
                         command=bluetooth_send,
                         bg=GREEN, fg=BG, font=("Courier New", 13, "bold"),
                         relief="flat", cursor="hand2", pady=10, anchor="center")
send_button.pack(fill="x", pady=(6, 0))

# ──────────────────────────────────────────
#  Start App
# ──────────────────────────────────────────
window.mainloop()


