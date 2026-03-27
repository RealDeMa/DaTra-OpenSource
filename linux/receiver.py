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
send_files     = {"paths": [], "names": []}

# ──────────────────────────────────────────
#  RECEIVE – multi-file loop
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

        files_received = [0]

        def handle_file(sock):
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
                files_received[0] += 1
                file_list.insert(tk.END, f"✔  {filename}  ({received_bytes // 1024} KB)")
                set_receive_status(f"✅ Saved: {filename}  –  {files_received[0]} file(s) received")
            except Exception as error:
                set_receive_status(f"❌ Error: {error}")
            finally:
                try:
                    sock.close()
                except Exception:
                    pass

        while receive_active["active"]:
            set_receive_status(
                f"Waiting... (Port {found_port})" +
                (f"  –  {files_received[0]} received" if files_received[0] > 0 else "")
            )
            server_sock.settimeout(2.0)
            try:
                client_sock, _ = server_sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
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
#  SEND – OBEX multi-file sequential
# ──────────────────────────────────────────
def bluetooth_send():
    if not send_files["paths"]:
        set_send_status("⚠️  Please select files first!")
        return
    selection = device_listbox.curselection()
    if not selection:
        set_send_status("⚠️  Please select a device first!")
        return

    mac   = paired_devices[selection[0]]["mac"]
    total = len(send_files["paths"])
    send_button.config(state="disabled", text="Sending...")
    progress_send["value"] = 0

    def send_thread():
        for i, path in enumerate(send_files["paths"]):
            name = os.path.basename(path)
            set_send_status(f"Sending {i + 1} / {total}: {name}  –  Accept on phone!")
            try:
                result = subprocess.run(
                    ["bluetooth-sendto", "--device=" + mac, path],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    progress_send["value"] = int((i + 1) / total * 100)
                    window.update_idletasks()
                    # Wait for phone to be ready for next file
                    import time; time.sleep(2)
                else:
                    err = result.stderr.strip() or result.stdout.strip()
                    set_send_status(f"❌ Error on {name}: {err}")
                    send_button.config(state="normal", text="Send Files")
                    return
            except subprocess.TimeoutExpired:
                set_send_status(f"❌ Timeout – Accept the file on your phone!")
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


def select_files():
    paths = filedialog.askopenfilenames(title="Select Files")
    if paths:
        send_files["paths"] = list(paths)
        send_files["names"] = [os.path.basename(p) for p in paths]
        if len(paths) == 1:
            file_label.config(text=f"📄  {send_files['names'][0]}")
        else:
            file_label.config(text=f"📦  {len(paths)} files selected")


def load_devices():
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
PAD     = 20   # consistent outer padding everywhere

tk.Label(window, text="DaTra",
         bg=BG, fg=ACCENT, font=("Courier New", 20, "bold")).pack(pady=(22, 3))
tk.Label(window, text="Linux  •  Bluetooth File Transfer",
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
    """Helper – creates a labelled CARD frame with consistent padding."""
    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="x", padx=0, pady=(0, 10))
    tk.Label(outer, text=title, bg=BG, fg=SUBTEXT,
             font=("Courier New", 8)).pack(anchor="w", padx=2, pady=(0, 3))
    card = tk.Frame(outer, bg=CARD, padx=16, pady=14)
    card.pack(fill="x")
    return card


def make_btn(parent, text, cmd, color, **kw):
    """Helper – button with consistent height and centered text."""
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

# Save location card
card_folder = make_card(recv_wrap, "SAVE LOCATION")
folder_label = tk.Label(card_folder, text="No folder selected",
                         bg=CARD, fg=TEXT, font=("Courier New", 11),
                         wraplength=560, anchor="w")
folder_label.pack(fill="x", pady=(0, 10))
tk.Button(card_folder, text="Choose Folder", command=choose_folder,
          bg=ACCENT, fg=BG, font=("Courier New", 11, "bold"),
          relief="flat", cursor="hand2", width=18, pady=7,
          anchor="center").pack(anchor="w")

# Status card
card_status_r = make_card(recv_wrap, "STATUS")
receive_status = tk.Label(card_status_r, text="Status: Ready",
                           bg=CARD, fg=GREEN, font=("Courier New", 11), anchor="w")
receive_status.pack(fill="x")
progress_receive = ttk.Progressbar(card_status_r,
                                    style="custom.Horizontal.TProgressbar",
                                    mode="determinate", maximum=100)
progress_receive.pack(fill="x", pady=(10, 0))

# Buttons – all same width, centered in a row
frame_buttons_r = tk.Frame(recv_wrap, bg=BG)
frame_buttons_r.pack(pady=6)

start_button = make_btn(frame_buttons_r, "Start Receiving", start_receiving, GREEN, width=18)
start_button.pack(side="left", padx=6)
make_btn(frame_buttons_r, "Stop", stop_receiving, RED, width=8).pack(side="left", padx=6)
make_btn(frame_buttons_r, "Clear List", clear_list, CARD, width=12).pack(side="left", padx=6)

# Received files card
card_list = make_card(recv_wrap, "RECEIVED FILES")
card_list.pack_configure(pady=(0, 0))
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

# Devices card
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

# File card
card_file = make_card(send_wrap, "FILES")
file_label = tk.Label(card_file, text="No files selected",
                       bg=CARD, fg=TEXT, font=("Courier New", 11),
                       wraplength=560, anchor="w")
file_label.pack(fill="x", pady=(0, 10))
tk.Button(card_file, text="Select Files", command=select_files,
          bg=ACCENT, fg=BG, font=("Courier New", 11, "bold"),
          relief="flat", cursor="hand2", width=18, pady=7,
          anchor="center").pack(anchor="w")

# Status card
card_status_s = make_card(send_wrap, "STATUS")
send_status = tk.Label(card_status_s, text="Status: Ready",
                        bg=CARD, fg=GREEN, font=("Courier New", 11), anchor="w")
send_status.pack(fill="x")
progress_send = ttk.Progressbar(card_status_s,
                                 style="custom.Horizontal.TProgressbar",
                                 mode="determinate", maximum=100)
progress_send.pack(fill="x", pady=(10, 0))

# Send button – full width
send_button = tk.Button(send_wrap, text="Send Files",
                         command=bluetooth_send,
                         bg=GREEN, fg=BG, font=("Courier New", 13, "bold"),
                         relief="flat", cursor="hand2", pady=10, anchor="center")
send_button.pack(fill="x", pady=(6, 0))

# ──────────────────────────────────────────
#  Start App
# ──────────────────────────────────────────
window.mainloop()
