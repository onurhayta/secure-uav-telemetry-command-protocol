# app.py  —  GCS Kokpit / Web Paneli
# ----------------------------------------------------------------------
# Yer istasyonunu bir WEB PANELİ (kokpit) olarak sunar:
#   1) Arka planda İHA'dan telemetri dinler (UDP 9998)
#   2) Tarayıcıya canlı kokpit sayfasını gösterir
#   3) Sayfadaki butonlar İHA'ya komut yollar (UDP 9999)
#
# Böylece sunumda terminal yerine gerçek bir uçuş ekranı görünür.
# NOT: Bu v1 (güvensiz) sisteme bağlanır. Aşama 4'te güvenli sürüme bağlanacak.
# ----------------------------------------------------------------------

import socket
import json
import time
import threading
from collections import deque
from flask import Flask, jsonify, request, render_template

# --- Ayarlar ---
GCS_PORT = 9998                      # telemetri bu porta gelir
UAV_ADDRESS = ("127.0.0.1", 9999)    # komutları İHA'ya buraya yollarız

# --- Paylaşılan durum (telemetri + olay kaydı) ---
latest = {"altitude": 0, "speed": 0, "heading": 0, "battery": 0, "active": True, "seq": 0,
          "x": 0.0, "y": 0.0, "vspeed": 0.0, "roll": 0.0, "pitch": 0.0,
          "flight_time": 0, "returning": False}
log = deque(maxlen=60)               # son 60 olay (komut, uyarı...)
link = {"last": 0.0}                 # en son telemetrinin geldiği an

# UDP soketi: telemetri dinlemek + komut yollamak için
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", GCS_PORT))


def listen_telemetry():
    """Arka planda sürekli telemetri dinler ve 'latest' durumunu günceller."""
    while True:
        data, _ = sock.recvfrom(4096)
        try:
            packet = json.loads(data.decode("utf-8"))
            latest.update(packet["data"])
            latest["seq"] = packet["seq"]
            link["last"] = time.time()
        except Exception:
            pass   # bozuk paket gelirse yoksay


threading.Thread(target=listen_telemetry, daemon=True).start()

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def state():
    """Kokpit her yarım saniyede bunu çağırır; güncel durumu JSON döner."""
    connected = (time.time() - link["last"]) < 3    # 3 sn veri yoksa bağlantı kopuk
    return jsonify({
        "telemetry": latest,
        "log": list(log),
        "connected": connected,
        "secure": False          # v1 güvensiz -> kokpitte kırmızı "UNENCRYPTED" yanar
    })


@app.route("/api/command", methods=["POST"])
def command():
    """Kokpitteki butonlardan gelen komutu İHA'ya yollar."""
    cmd = request.json.get("command")
    packet = {"type": "COMMAND", "seq": 0, "timestamp": int(time.time()), "data": cmd}
    sock.sendto(json.dumps(packet).encode("utf-8"), UAV_ADDRESS)
    log.appendleft({"t": time.strftime("%H:%M:%S"), "msg": f"Command sent: {cmd}", "kind": "cmd"})
    return jsonify({"ok": True})


if __name__ == "__main__":
    # NOT: macOS'ta 5000 portunu AirPlay kullandığı için 5050 seçtik
    print("=== GCS KOKPIT ===")
    print("Tarayicida ac: http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)