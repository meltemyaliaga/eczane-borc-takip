"""
Uygulama genelinde kullanılan sabitler ve yapılandırma değerleri.
Gerçek secret değerler burada BULUNMAZ; Streamlit Secrets üzerinden okunur.
"""

# Zaman Dilimi
TIMEZONE = "Europe/Istanbul"

# Google Sheets — Sheet İsimleri
SHEET_CARILER = "CARILER"
SHEET_KULLANICILAR = "KULLANICILAR"
SHEET_ILACLAR = "ILACLAR"
SHEET_BORC_HAREKET = "BORC_HAREKET"

# Durum Değerleri
DURUM_AKTIF = "Aktif"
DURUM_PASIF = "Pasif"
DURUM_SILINDI = "Silindi"

# Roller
ROL_ADMIN = "ADMIN"
ROL_USER = "USER"

# Oturum Zaman Aşımı (saat cinsinden)
SESSION_TIMEOUT_HOURS = 8

# Belge Numarası Formatı
# Örnek: 2026-0000001
BELGE_NO_YAZI_UZUNLUGU = 7  # Sıra numarasının sıfırla tamamlanacak basamak sayısı

# Sheet Kolon İndeksleri (0-tabanlı)
CARILER_COLS = {
    "cari_id": 0,
    "cari_adi": 1,
    "durum": 2,
    "olusturulma_tarihi": 3,
}

KULLANICILAR_COLS = {
    "user_id": 0,
    "kullanici_adi": 1,
    "sifre_hash": 2,
    "cari_id": 3,
    "rol": 4,
    "reset_sifre": 5,
    "olusturulma_tarihi": 6,
}

ILACLAR_COLS = {
    "ilac_id": 0,
    "ilac_adi": 1,
    "durum": 2,
    "olusturulma_tarihi": 3,
}

BORC_HAREKET_COLS = {
    "belge_no": 0,
    "kalem_no": 1,
    "borc_veren_cari_id": 2,
    "ilac_id": 3,
    "lot_tarihi": 4,
    "birim_alis_fiyati": 5,
    "toplam_miktar": 6,
    "borc_alan_cari_id": 7,
    "kalem_miktari": 8,
    "olusturan_user_id": 9,
    "olusturulma_tarihi": 10,
    "durum": 11,
    "silen_user_id": 12,
    "silinme_tarihi": 13,
}

# Sheet başlık satırları
CARILER_HEADERS = [
    "Cari ID", "Cari Adı", "Durum", "Oluşturulma Tarihi"
]

KULLANICILAR_HEADERS = [
    "User ID", "Kullanıcı Adı", "Şifre Hash", "Cari ID",
    "Rol", "Reset Şifre", "Oluşturulma Tarihi"
]

ILACLAR_HEADERS = [
    "İlaç ID", "İlaç Adı", "Durum", "Oluşturulma Tarihi"
]

BORC_HAREKET_HEADERS = [
    "Belge No", "Kalem No", "Borç Veren Cari ID", "İlaç ID",
    "Lot Tarihi", "Birim Alış Fiyatı", "Toplam Miktar",
    "Borç Alan Cari ID", "Kalem Miktarı", "Oluşturan User ID",
    "Oluşturulma Tarihi", "Durum", "Silen User ID", "Silinme Tarihi"
]
