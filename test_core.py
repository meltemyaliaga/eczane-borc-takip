"""
Kapsamlı birim testler — Google Sheets bağlantısı gerekmez.
Çalıştırma: python test_core.py
"""
import sys
sys.path.insert(0, '.')

from decimal import Decimal
from utils.calculations import (
    hesapla_kalem_tutari, hesapla_belge_toplami,
    hesapla_tum_cari_bakiyeleri, hesapla_cari_net_bakiye,
    hesapla_iliski_bakiyesi, hesapla_kumulatif_bakiye, to_decimal,
)
from utils.validators import (
    validate_miktar, validate_birim_fiyat, validate_esit_dagit,
    validate_borc_verme_form,
)
from utils.formatting import format_bakiye, format_birim_fiyat, format_para

PASS = 0
FAIL = 0


def test(ad, beklenen, gercek):
    global PASS, FAIL
    if beklenen == gercek:
        print(f"  PASS: {ad}")
        PASS += 1
    else:
        print(f"  FAIL: {ad}: beklenen={beklenen!r}, gercek={gercek!r}")
        FAIL += 1


# ─────────────────────────────────────────────────────────
# 1. ROUNDING
# ─────────────────────────────────────────────────────────
print("\n=== 1. ROUNDING TESTLERİ ===")
test("333 × 10.1234 → 3371", 3371, hesapla_kalem_tutari(333, to_decimal("10.1234")))
test("333 × 10.1252 → 3372", 3372, hesapla_kalem_tutari(333, to_decimal("10.1252")))
test("750 × 10.0000 → 7500", 7500, hesapla_kalem_tutari(750, to_decimal("10.0000")))
test("300 × 15.0000 → 4500", 4500, hesapla_kalem_tutari(300, to_decimal("15.0000")))
test("1 × 0.5000 → 1 (ROUND_HALF_UP)", 1, hesapla_kalem_tutari(1, to_decimal("0.5000")))
test("1 × 0.4999 → 0", 0, hesapla_kalem_tutari(1, to_decimal("0.4999")))
test("10000 × 0.0001 → 1", 1, hesapla_kalem_tutari(10000, to_decimal("0.0001")))
test("Belge toplamı 750 × 10 → 7500", 7500, hesapla_belge_toplami(750, to_decimal("10.0000")))

# ─────────────────────────────────────────────────────────
# 2. BAKİYE (Madde 73 senaryosu)
# ─────────────────────────────────────────────────────────
print("\n=== 2. BAKİYE TESTLERİ (Madde 73) ===")

hareketler_73 = [
    # Ahmet(1) → Mehmet(2): 300 × 10 = 3000
    {"borc_veren_cari_id": 1, "borc_alan_cari_id": 2, "kalem_miktari": 300, "birim_alis_fiyati": "10.0000", "durum": "Aktif"},
    # Ahmet(1) → Ayşe(3): 100 × 10 = 1000
    {"borc_veren_cari_id": 1, "borc_alan_cari_id": 3, "kalem_miktari": 100, "birim_alis_fiyati": "10.0000", "durum": "Aktif"},
    # Ahmet(1) → Fatma(4): 350 × 10 = 3500
    {"borc_veren_cari_id": 1, "borc_alan_cari_id": 4, "kalem_miktari": 350, "birim_alis_fiyati": "10.0000", "durum": "Aktif"},
    # Mehmet(2) → Ahmet(1): 300 × 15 = 4500
    {"borc_veren_cari_id": 2, "borc_alan_cari_id": 1, "kalem_miktari": 300, "birim_alis_fiyati": "15.0000", "durum": "Aktif"},
]

bakiyeler = hesapla_tum_cari_bakiyeleri(hareketler_73, [1, 2, 3, 4])
# Ahmet: verdi 7500 (3000+1000+3500), aldı 4500 → net = +3000 TL
test("Ahmet genel bakiye: +3000", 3000, bakiyeler[1])
# Mehmet: verdi 4500, aldı 3000 → net = +1500
test("Mehmet genel bakiye: +1500", 1500, bakiyeler[2])
test("Ayşe genel bakiye: -1000", -1000, bakiyeler[3])
test("Fatma genel bakiye: -3500", -3500, bakiyeler[4])

# İlişki bakiyesi
test("Ahmet-Mehmet ilişki (Ahmet açısından): -1500", -1500,
     hesapla_iliski_bakiyesi(hareketler_73, 1, 2))
test("Mehmet-Ahmet ilişki (Mehmet açısından): +1500", 1500,
     hesapla_iliski_bakiyesi(hareketler_73, 2, 1))
test("Ahmet-Ayşe ilişki (Ahmet açısından): +1000", 1000,
     hesapla_iliski_bakiyesi(hareketler_73, 1, 3))

# ─────────────────────────────────────────────────────────
# 3. SİLİNMİŞ HAREKETLERİN DIŞLANMASI
# ─────────────────────────────────────────────────────────
print("\n=== 3. SİLİNMİŞ HAREKET TESTLERİ ===")

hareketler_silme = [
    {"borc_veren_cari_id": 1, "borc_alan_cari_id": 2, "kalem_miktari": 500, "birim_alis_fiyati": "10.0000", "durum": "Aktif"},
    {"borc_veren_cari_id": 1, "borc_alan_cari_id": 2, "kalem_miktari": 300, "birim_alis_fiyati": "10.0000", "durum": "Silindi"},
]
test("Silinen hareket bakiyeden dışlanır: 5000", 5000, hesapla_cari_net_bakiye(hareketler_silme, 1))
test("Silinen hareket istatistik: 2. cari -5000", -5000, hesapla_cari_net_bakiye(hareketler_silme, 2))

# ─────────────────────────────────────────────────────────
# 4. KÜMÜLATİF BAKİYE
# ─────────────────────────────────────────────────────────
print("\n=== 4. KÜMÜLATİF BAKİYE TESTLERİ ===")

h_kum = [
    {"Belge No": "2026-0000001", "Kalem No": 1, "borc_veren_cari_id": 1, "borc_alan_cari_id": 2,
     "kalem_miktari": 500, "birim_alis_fiyati": "10.0000", "durum": "Aktif", "Lot Tarihi": "2026-09-10"},
    {"Belge No": "2026-0000002", "Kalem No": 1, "borc_veren_cari_id": 1, "borc_alan_cari_id": 2,
     "kalem_miktari": 300, "birim_alis_fiyati": "10.0000", "durum": "Silindi", "Lot Tarihi": "2026-09-12"},
    {"Belge No": "2026-0000003", "Kalem No": 1, "borc_veren_cari_id": 2, "borc_alan_cari_id": 1,
     "kalem_miktari": 200, "birim_alis_fiyati": "10.0000", "durum": "Aktif", "Lot Tarihi": "2026-09-15"},
]
sonuc = hesapla_kumulatif_bakiye(h_kum, 1, 2)
test("Kümülatif satır 1 (aktif +5000)", 5000, sonuc[0]["kumulatif_bakiye"])
test("Kümülatif satır 2 (silindi → önceki değer +5000)", 5000, sonuc[1]["kumulatif_bakiye"])
test("Kümülatif satır 3 (-2000 → kümülatif +3000)", 3000, sonuc[2]["kumulatif_bakiye"])

# ─────────────────────────────────────────────────────────
# 5. VALİDASYONLAR
# ─────────────────────────────────────────────────────────
print("\n=== 5. VALİDASYON TESTLERİ ===")

test("Miktar 750 geçerli", (True, ""), validate_miktar(750))
test("Miktar 1 geçerli", (True, ""), validate_miktar(1))
test("Miktar 0 geçersiz", False, validate_miktar(0)[0])
test("Miktar -10 geçersiz", False, validate_miktar(-10)[0])
test("Miktar 10.5 geçersiz", False, validate_miktar("10.5")[0])
test("Miktar '10,5' geçersiz", False, validate_miktar("10,5")[0])

test("Fiyat 10.1234 geçerli", (True, ""), validate_birim_fiyat("10.1234"))
test("Fiyat 0 geçersiz", False, validate_birim_fiyat("0")[0])
test("Fiyat -5 geçersiz", False, validate_birim_fiyat("-5")[0])

ok, _ = validate_esit_dagit(750, 3)
test("750/3 eşit dağıt OK", True, ok)
ok, _ = validate_esit_dagit(750, 4)
test("750/4 eşit dağıt HATA", False, ok)
ok, _ = validate_esit_dagit(750, 0)
test("0 cari eşit dağıt HATA", False, ok)

# Borç verme form validasyonu
ok, msg = validate_borc_verme_form(
    ilac_id=1, lot_tarihi="2026-09-15", birim_fiyat="10.0000",
    toplam_miktar=750,
    dagitim=[
        {"cari_id": 2, "miktar": 300},
        {"cari_id": 3, "miktar": 100},
        {"cari_id": 4, "miktar": 350},
    ],
    borc_veren_cari_id=1,
)
test("Geçerli borç verme formu", True, ok)

# Aynı cari iki kez
ok, msg = validate_borc_verme_form(
    ilac_id=1, lot_tarihi="2026-09-15", birim_fiyat="10.0000",
    toplam_miktar=750,
    dagitim=[{"cari_id": 2, "miktar": 300}, {"cari_id": 2, "miktar": 450}],
    borc_veren_cari_id=1,
)
test("Aynı cari iki kez → HATA", False, ok)

# Self-lending
ok, msg = validate_borc_verme_form(
    ilac_id=1, lot_tarihi="2026-09-15", birim_fiyat="10.0000",
    toplam_miktar=100,
    dagitim=[{"cari_id": 1, "miktar": 100}],
    borc_veren_cari_id=1,
)
test("Self-lending → HATA", False, ok)

# Miktar uyumsuzluğu
ok, msg = validate_borc_verme_form(
    ilac_id=1, lot_tarihi="2026-09-15", birim_fiyat="10.0000",
    toplam_miktar=750,
    dagitim=[{"cari_id": 2, "miktar": 300}, {"cari_id": 3, "miktar": 200}],
    borc_veren_cari_id=1,
)
test("Miktar uyumsuzluğu (500≠750) → HATA", False, ok)

# ─────────────────────────────────────────────────────────
# 6. FORMATLAMA
# ─────────────────────────────────────────────────────────
print("\n=== 6. FORMATLAMA TESTLERİ ===")
test("format_bakiye(+5000)", "+5.000 TL", format_bakiye(5000))
test("format_bakiye(-3500)", "-3.500 TL", format_bakiye(-3500))
test("format_bakiye(0)", "0 TL", format_bakiye(0))
test("format_para(7500)", "7.500 TL", format_para(7500))
test("format_birim_fiyat('10.1234')", "10,1234 TL", format_birim_fiyat("10.1234"))
test("format_birim_fiyat('9.5')", "9,5000 TL", format_birim_fiyat("9.5"))

# ─────────────────────────────────────────────────────────
# SONUÇ
# ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"TOPLAM: {PASS + FAIL} test — ✅ {PASS} başarılı, ❌ {FAIL} başarısız")
if FAIL == 0:
    print("🎉 TÜM TESTLER BAŞARILI!")
else:
    print("⚠️  BAZI TESTLER BAŞARISIZ!")
    sys.exit(1)
