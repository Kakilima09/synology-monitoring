import os
import sys
import logging
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PID_FILE = os.path.join(BASE_DIR, "server.pid")

os.chdir(BASE_DIR)
os.makedirs(LOG_DIR, exist_ok=True)

with open(PID_FILE, "w", encoding="utf-8") as f:
    f.write(str(os.getpid()))

handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "server.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)

root = logging.getLogger()
root.setLevel("INFO")
root.addHandler(handler)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
    )