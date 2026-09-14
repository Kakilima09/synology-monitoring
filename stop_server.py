import os
import sys
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(BASE_DIR, "server.pid")

if not os.path.exists(PID_FILE):
    print("Server tidak sedang berjalan (server.pid tidak ditemukan).")
    sys.exit(0)

with open(PID_FILE, encoding="utf-8") as f:
    try:
        pid = int(f.read().strip())
    except ValueError:
        print("server.pid tidak valid.")
        sys.exit(1)

try:
    os.kill(pid, signal.SIGTERM)
    print(f"Server dihentikan (PID {pid}).")
except (OSError, ProcessLookupError):
    print(f"Proses PID {pid} sudah tidak ada.")

try:
    os.remove(PID_FILE)
except OSError:
    pass