# gcs.py  —  Yer Kontrol İstasyonu / Ground Control Station (v1)
# ----------------------------------------------------------------------
# Bu dosya yer istasyonunu temsil eder ve İKİ iş yapar:
#   1) İHA'dan gelen telemetriyi dinler ve ekrana yazar
#   2) Klavyeden komut alıp İHA'ya yollar
#
# DİKKAT: Hiçbir şifreleme veya kimlik doğrulama YOKTUR. Kasıtlı güvensiz.
# ----------------------------------------------------------------------

import socket
import json
import time
import threading

# --- Ayarlar ---
GCS_PORT = 9998                      # telemetri bu porta gelir
UAV_ADDRESS = ("127.0.0.1", 9999)    # komutları İHA'ya buraya yollarız

# UDP soketi oluştur ve kendi portuna bağla
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", GCS_PORT))

seq = 0   # yolladığımız her komuta artan numara


def listen_telemetry():
    """İHA'dan gelen telemetriyi sürekli dinler ve ekrana yazar."""
    while True:
        data, _ = sock.recvfrom(4096)
        packet = json.loads(data.decode("utf-8"))
        d = packet["data"]
        print(f"[TELEMETRY] seq:{packet['seq']}  alt:{d['altitude']}m  "
              f"speed:{d['speed']}km/h  battery:{d['battery']}%  active:{d['active']}")


def send_command(command):
    """Verilen komutu paketleyip İHA'ya yollar."""
    global seq
    seq += 1
    packet = {
        "type": "COMMAND",
        "seq": seq,
        "timestamp": int(time.time()),
        "data": command
    }
    message = json.dumps(packet).encode("utf-8")
    sock.sendto(message, UAV_ADDRESS)
    print(f"[GCS] Command sent: {command}")


# Telemetri dinlemeyi arka planda başlat
threading.Thread(target=listen_telemetry, daemon=True).start()

print("=== Ground Control Station (INSECURE v1) ===")
print("Commands: CLIMB, DESCEND, SPEED_UP, TURN_LEFT, TURN_RIGHT, SELF_DESTRUCT")
print("Type EXIT to quit")
print()

# Ana iş: klavyeden komut al ve yolla
while True:
    command = input("Enter command > ").strip().upper()
    if command == "EXIT":
        print("Shutting down...")
        break
    if command == "":
        continue
    send_command(command)