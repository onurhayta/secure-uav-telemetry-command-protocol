# uav.py  —  Güvensiz İHA / Unmanned Aerial Vehicle (v1)
# ----------------------------------------------------------------------
# Bu dosya İHA'yı (sabit kanatlı insansız hava aracı) temsil eder ve İKİ iş yapar:
#   1) Her saniye yer istasyonuna telemetri yollar  (araç -> yer, "downlink")
#   2) Yer istasyonundan gelen komutları dinler ve uygular (yer -> araç, "uplink")
#
# Gerçekçi uçuş modeli: irtifa/hız kademeli değişir, araç konumu (x,y) takip edilir,
# yatış (roll) / burun (pitch) açıları ve dönüş oranı hesaplanır, RETURN_HOME ile
# araç eve doğru süzülür.
#
# DİKKAT: Burada hiçbir şifreleme veya kimlik doğrulama YOKTUR. Kasıtlı güvensiz.
# ----------------------------------------------------------------------

import socket
import json
import time
import threading
import math

# --- Ayarlar ---
UAV_PORT = 9999                      # İHA bu portu dinler; komutlar buraya gelir
GCS_ADDRESS = ("127.0.0.1", 9998)    # telemetriyi yer istasyonuna buraya yollarız

HOME = (0.0, 0.0)   # eve dönüş noktası (metre, başlangıç)

# --- İHA'nın anlık durumu ---
state = {
    "altitude": 100,          # mevcut irtifa (m)
    "target_altitude": 100,   # hedef irtifa (komutlar bunu değiştirir)
    "speed": 30,              # mevcut hız (km/s)
    "target_speed": 30,       # hedef hız
    "heading": 90,            # mevcut yön (derece)
    "target_heading": 90,     # hedef yön
    "battery": 95,            # batarya (%)
    "active": True,           # motorlar çalışıyor mu
    "x": 0.0,                 # eve göre doğu-batı konumu (m)
    "y": 0.0,                 # eve göre kuzey-güney konumu (m)
    "vspeed": 0.0,            # dikey hız (m/s) — tırmanma/alçalma
    "roll": 0.0,              # yatış açısı (derece) — turn coordinator için
    "pitch": 0.0,             # burun açısı (derece) — attitude için
    "flight_time": 0,         # uçuş süresi (saniye)
    "returning": False        # eve dönüş modunda mı
}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", UAV_PORT))

seq = 0
tick = 0


def glide(current, target, step):
    """Bir değeri hedefe doğru 'step' kadar kademeli yaklaştırır (ani zıplama olmaz)."""
    if current < target:
        return min(current + step, target)
    elif current > target:
        return max(current - step, target)
    return current


def update_physics():
    """Her saniye İHA'nın fiziksel durumunu bir adım ilerletir."""
    # --- İrtifa: hedefe doğru süzül (max 4 m/s) ---
    old_alt = state["altitude"]
    state["altitude"] = glide(state["altitude"], state["target_altitude"], 4)
    state["vspeed"] = round(state["altitude"] - old_alt, 1)       # dikey hız
    state["pitch"] = max(-15, min(15, state["vspeed"] * 3))       # burun açısı

    # --- Hız: hedefe doğru süzül (max 3 km/s) ---
    state["speed"] = glide(state["speed"], state["target_speed"], 3)

    # --- Eve dönüş: hedefi eve çevir ---
    if state["returning"]:
        dx = HOME[0] - state["x"]
        dy = HOME[1] - state["y"]
        dist = math.hypot(dx, dy)
        if dist < 15:
            # Eve vardı: dur ve askıda kal
            state["returning"] = False
            state["target_speed"] = 0
        else:
            # Eve giden yönü (bearing) hedef yön yap
            state["target_heading"] = math.degrees(math.atan2(dx, dy)) % 360

    # --- Yön: hedefe doğru kademeli dön (max 12°/s) ---
    diff = (state["target_heading"] - state["heading"] + 540) % 360 - 180  # -180..180
    turn = max(-12, min(12, diff))
    state["heading"] = (state["heading"] + turn) % 360
    state["roll"] = max(-25, min(25, turn * 2))                   # yatış açısı

    # --- İleri hareket: yöne göre konumu güncelle ---
    # move_factor: harita okunabilir kalsın diye ölçekli demo hızı
    rad = math.radians(state["heading"])
    move = state["speed"] * 0.15
    state["x"] += move * math.sin(rad)
    state["y"] += move * math.cos(rad)


def send_telemetry():
    """Her saniye yer istasyonuna İHA'nın güncel durumunu yollar."""
    global seq, tick
    while True:
        tick += 1

        if state["active"]:
            state["flight_time"] += 1

            # Batarya her 15 saniyede %1 düşer
            if tick % 15 == 0 and state["battery"] > 0:
                state["battery"] -= 1

            if state["battery"] <= 0:
                # Batarya bitti -> iniş yap ve dur
                state["battery"] = 0
                state["active"] = False
                state["target_altitude"] = 0
                state["altitude"] = 0
                state["target_speed"] = 0
                state["speed"] = 0
                print("  !!! Batarya bitti — İHA iniş yaptı ve durdu !!!")
            else:
                update_physics()

        seq += 1
        packet = {
            "type": "TELEMETRY",
            "seq": seq,
            "timestamp": int(time.time()),
            "data": {
                "altitude": round(state["altitude"]),
                "speed": round(state["speed"]),
                "heading": round(state["heading"]),
                "battery": state["battery"],
                "active": state["active"],
                "x": round(state["x"], 1),
                "y": round(state["y"], 1),
                "vspeed": state["vspeed"],
                "roll": round(state["roll"], 1),
                "pitch": round(state["pitch"], 1),
                "flight_time": state["flight_time"],
                "returning": state["returning"]
            }
        }
        # AÇIK METİN, şifresiz! (v1 zafiyeti)
        message = json.dumps(packet).encode("utf-8")
        sock.sendto(message, GCS_ADDRESS)
        time.sleep(1)


def apply_command(command):
    """Gelen komutu İHA'nın durumuna uygular (kademeli değişim)."""
    if not state["active"]:
        print("      (İHA pasif durumda — komut yok sayıldı)")
        return

    if command == "CLIMB":
        state["target_altitude"] += 20
    elif command == "DESCEND":
        state["target_altitude"] = max(0, state["target_altitude"] - 20)
    elif command == "SPEED_UP":
        state["target_speed"] += 10
    elif command == "SLOW_DOWN":
        state["target_speed"] = max(0, state["target_speed"] - 10)
    elif command == "TURN_LEFT":
        state["target_heading"] = (state["target_heading"] - 15) % 360
        state["returning"] = False
    elif command == "TURN_RIGHT":
        state["target_heading"] = (state["target_heading"] + 15) % 360
        state["returning"] = False
    elif command == "RETURN_HOME":
        state["returning"] = True
        if state["target_speed"] == 0:
            state["target_speed"] = 30   # dönebilmek için hız ver
    elif command == "SELF_DESTRUCT":
        state["active"] = False
        state["altitude"] = 0
        state["target_altitude"] = 0
        state["speed"] = 0
        print("  !!! CRITICAL: SELF_DESTRUCT executed — UAV down !!!")


def listen_commands():
    """Yer istasyonundan gelen komutları dinler ve uygular."""
    print(f"[UAV] Listening on port {UAV_PORT}. Waiting for commands...")
    while True:
        data, sender = sock.recvfrom(4096)
        packet = json.loads(data.decode("utf-8"))
        command = packet.get("data")
        print(f"[UAV] Command received: {command}  (from {sender[0]}:{sender[1]})")
        apply_command(command)
        print(f"      State -> alt:{round(state['altitude'])}m  speed:{round(state['speed'])}  "
              f"heading:{round(state['heading'])}  active:{state['active']}")


threading.Thread(target=send_telemetry, daemon=True).start()
listen_commands()