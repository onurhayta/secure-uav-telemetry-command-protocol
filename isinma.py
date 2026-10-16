# ---- 1. Değişkenler: tek bir veriyi tutar ----
arac_adi = "Drone-01"
irtifa = 120          # metre
batarya = 87          # yüzde

print("Araç:", arac_adi, "| İrtifa:", irtifa, "m | Batarya:", batarya, "%")

# ---- 2. Sözlük (dictionary): bir telemetri paketi gibi ----
# Projede araçtan yere giden veriyi aynen böyle tutacağız
telemetri = {
    "arac": "Drone-01",
    "enlem": 39.92,
    "boylam": 32.85,
    "hiz": 45
}
print("\nTelemetri paketi:", telemetri)
print("Aracın hızı:", telemetri["hiz"], "km/s")

# ---- 3. Fonksiyon: bir işi yapan kod bloğu ----
# Bir komut güvenli mi diye kontrol eden basit fonksiyon
def komut_kontrol(komut):
    tehlikeli = ["KENDINI_IMHA", "MOTORU_DURDUR"]
    if komut in tehlikeli:
        return "⚠️ TEHLİKELİ KOMUT reddedildi: " + komut
    else:
        return "✅ Komut kabul edildi: " + komut

# ---- 4. Fonksiyonu deneyelim ----
print("\n--- Komut Testi ---")
print(komut_kontrol("SOLA_DON"))
print(komut_kontrol("KENDINI_IMHA"))