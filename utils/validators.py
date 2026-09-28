"""
İş kuralı validasyon fonksiyonları.
Her validasyon fonksiyonu (gecerli: bool, hata_mesaji: str) tuple döndürür.
Tüm doğrulamalar hem UI katmanında hem de service katmanında çağrılmalıdır.
"""

from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Dict, Optional


def validate_miktar(deger) -> Tuple[bool, str]:
    """
    Miktar değerini doğrular.
    - Pozitif tam sayı olmalıdır.
    - 0, negatif veya ondalıklı olamaz.
    """
    try:
        # String ise trim et
        if isinstance(deger, str):
            deger = deger.strip()

        # Ondalıklı kontrol (string)
        if isinstance(deger, str) and ("." in deger or "," in deger):
            return False, "Miktar tam sayı olmalıdır; ondalıklı değer kabul edilmez."

        sayi = int(deger)
        if sayi <= 0:
            return False, "Miktar 0'dan büyük olmalıdır."
        return True, ""
    except (ValueError, TypeError):
        return False, "Miktar tam sayı olmalıdır."


def validate_birim_fiyat(deger) -> Tuple[bool, str]:
    """
    Birim alış fiyatını doğrular.
    - Pozitif sayısal değer olmalıdır.
    - 0 veya negatif olamaz.
    """
    try:
        if isinstance(deger, str):
            deger = deger.strip().replace(",", ".")
        fiyat = Decimal(str(deger))
        if fiyat <= 0:
            return False, "Birim alış fiyatı 0'dan büyük olmalıdır."
        return True, ""
    except (InvalidOperation, TypeError, ValueError):
        return False, "Geçerli bir fiyat giriniz."


def validate_cari_adi(adi: str, mevcut_adlar: List[str], guncellenen_cari_id: Optional[int] = None) -> Tuple[bool, str]:
    """
    Cari adı doğrulaması.
    - Boş olamaz.
    - Büyük/küçük harf duyarsız benzersiz olmalıdır.
    """
    adi = adi.strip() if adi else ""
    if not adi:
        return False, "Cari adı boş olamaz."
    # Benzersizlik kontrolü (case-insensitive)
    for mevcut in mevcut_adlar:
        if mevcut.strip().lower() == adi.lower():
            return False, f"'{adi}' adında bir cari zaten mevcut."
    return True, ""


def validate_ilac_adi(adi: str, mevcut_adlar: List[str]) -> Tuple[bool, str]:
    """
    İlaç adı doğrulaması.
    - Boş olamaz.
    - Büyük/küçük harf duyarsız benzersiz olmalıdır (pasifler dahil).
    """
    adi = adi.strip() if adi else ""
    if not adi:
        return False, "İlaç adı boş olamaz."
    for mevcut in mevcut_adlar:
        if mevcut.strip().lower() == adi.lower():
            return False, f"'{adi}' adında bir ilaç zaten mevcut."
    return True, ""


def validate_kullanici_adi(adi: str, mevcut_adlar: List[str]) -> Tuple[bool, str]:
    """
    Kullanıcı adı doğrulaması.
    - Boş olamaz.
    - Büyük/küçük harf duyarsız benzersiz olmalıdır.
    """
    adi = adi.strip() if adi else ""
    if not adi:
        return False, "Kullanıcı adı boş olamaz."
    for mevcut in mevcut_adlar:
        if mevcut.strip().lower() == adi.lower():
            return False, f"'{adi}' kullanıcı adı zaten kullanılıyor."
    return True, ""


def validate_sifre(sifre: str, sifre_tekrar: str) -> Tuple[bool, str]:
    """
    Şifre doğrulaması.
    - Boş olamaz.
    - İki giriş eşleşmelidir.
    """
    if not sifre:
        return False, "Şifre boş olamaz."
    if sifre != sifre_tekrar:
        return False, "Şifreler eşleşmiyor."
    return True, ""


def validate_borc_verme_form(
    ilac_id: Optional[int],
    lot_tarihi,
    birim_fiyat,
    toplam_miktar,
    dagitim: List[Dict],  # [{"cari_id": int, "miktar": int}, ...]
    borc_veren_cari_id: int,
) -> Tuple[bool, str]:
    """
    Borç verme formunun tüm iş kuralı doğrulamaları.

    Returns:
        (True, "") — geçerliyse
        (False, hata_mesajı) — geçersizse
    """
    # İlaç seçilmiş mi?
    if not ilac_id:
        return False, "Lütfen bir ilaç seçiniz."

    # Lot tarihi?
    if not lot_tarihi:
        return False, "Lütfen lot / alış tarihini giriniz."

    # Birim fiyat
    ok, msg = validate_birim_fiyat(birim_fiyat)
    if not ok:
        return False, msg

    # Toplam miktar
    ok, msg = validate_miktar(toplam_miktar)
    if not ok:
        return False, f"Toplam miktar: {msg}"

    # En az bir borç alan olmalı
    if not dagitim:
        return False, "En az bir borç alan cari ekleyiniz."

    # Her satır kontrolü
    cari_ids_goruldu = set()
    toplam_dagitim = 0

    for satir in dagitim:
        cari_id = satir.get("cari_id")
        miktar = satir.get("miktar")

        # Borç veren = borç alan?
        if cari_id == borc_veren_cari_id:
            return False, "Borç veren ve borç alan aynı eczane olamaz."

        # Aynı cari iki kez?
        if cari_id in cari_ids_goruldu:
            return False, "Aynı cari aynı belgede birden fazla kez eklenemez."
        cari_ids_goruldu.add(cari_id)

        # Miktar kontrolü
        ok, msg = validate_miktar(miktar)
        if not ok:
            return False, f"Kalem miktarı: {msg}"

        toplam_dagitim += int(miktar)

    # Toplam eşleşiyor mu?
    if toplam_dagitim != int(toplam_miktar):
        return (
            False,
            f"Borç alan carilerin toplam miktarı ({toplam_dagitim}), "
            f"toplam miktara ({int(toplam_miktar)}) eşit olmalıdır.",
        )

    return True, ""


def validate_esit_dagit(toplam_miktar: int, cari_sayisi: int) -> Tuple[bool, str]:
    """
    Eşit dağıtımın mümkün olup olmadığını kontrol eder.
    """
    if cari_sayisi == 0:
        return False, "En az bir borç alan cari seçmelisiniz."
    if toplam_miktar % cari_sayisi != 0:
        return False, "Miktar seçilen carilere eşit olarak dağıtılamıyor."
    return True, ""
