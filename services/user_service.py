"""
Kullanıcı yönetimi servisi.

Sorumluluklar:
- Kullanıcı listeleme
- Yeni kullanıcı oluşturma (Admin)
- Kullanıcı adı değiştirme
- Şifre değiştirme (yalnızca kendi şifresi)
- Kullanıcıyı başka cariye taşıma (Admin)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pytz

from config import (
    SHEET_KULLANICILAR,
    SHEET_CARILER,
    TIMEZONE,
    DURUM_AKTIF,
    ROL_USER,
)
from data import sheets_client
from services.auth_service import hash_sifre
from utils.validators import validate_kullanici_adi, validate_sifre

logger = logging.getLogger(__name__)


def _now_istanbul() -> datetime:
    return datetime.now(pytz.timezone(TIMEZONE))


def get_all_users() -> List[Dict]:
    """Tüm kullanıcıları döndürür."""
    return sheets_client.get_all_records(SHEET_KULLANICILAR)


def get_user_by_id(user_id: int) -> Optional[Dict]:
    for u in get_all_users():
        if int(u.get("User ID", -1)) == user_id:
            return u
    return None


def get_user_by_kullanici_adi(kullanici_adi: str) -> Optional[Dict]:
    for u in get_all_users():
        if str(u.get("Kullanıcı Adı", "")).strip().lower() == kullanici_adi.strip().lower():
            return u
    return None


def _get_next_user_id() -> int:
    users = get_all_users()
    if not users:
        return 1
    return max(int(u.get("User ID", 0)) for u in users) + 1


def create_user(kullanici_adi: str, sifre: str, cari_id: int) -> Dict:
    """
    Yeni kullanıcı oluşturur. Rol otomatik olarak USER atanır.

    Raises:
        ValueError: Duplicate kullanıcı adı veya cari zaten başka kullanıcıya bağlı.
    """
    kullanici_adi = kullanici_adi.strip()

    # Kullanıcı adı benzersizlik
    mevcut_adlar = [str(u.get("Kullanıcı Adı", "")) for u in get_all_users()]
    ok, msg = validate_kullanici_adi(kullanici_adi, mevcut_adlar)
    if not ok:
        raise ValueError(msg)

    # Cari zaten başka kullanıcıya bağlı mı?
    for u in get_all_users():
        if int(u.get("Cari ID", -1)) == cari_id:
            raise ValueError(f"Cari ID {cari_id} zaten başka bir kullanıcıya bağlı.")

    sifre_hash = hash_sifre(sifre)
    new_id = _get_next_user_id()
    olusturulma = _now_istanbul().strftime("%Y-%m-%d %H:%M:%S")

    row = [new_id, kullanici_adi, sifre_hash, cari_id, ROL_USER, "", olusturulma]
    sheets_client.append_row(SHEET_KULLANICILAR, row)

    return {
        "User ID": new_id,
        "Kullanıcı Adı": kullanici_adi,
        "Cari ID": cari_id,
        "Rol": ROL_USER,
    }


def update_kullanici_adi(user_id: int, yeni_ad: str) -> None:
    """
    Kullanıcı adını günceller.

    Raises:
        ValueError: Duplicate kullanıcı adı.
    """
    yeni_ad = yeni_ad.strip()
    mevcut_users = get_all_users()
    diger_adlar = [
        str(u.get("Kullanıcı Adı", ""))
        for u in mevcut_users
        if int(u.get("User ID", -1)) != user_id
    ]
    ok, msg = validate_kullanici_adi(yeni_ad, diger_adlar)
    if not ok:
        raise ValueError(msg)

    updated = sheets_client.update_row_field(
        SHEET_KULLANICILAR, "User ID", str(user_id), "Kullanıcı Adı", yeni_ad, []
    )
    if not updated:
        raise ValueError("Kullanıcı bulunamadı.")


def change_password(user_id: int, mevcut_sifre: str, yeni_sifre: str, yeni_sifre_tekrar: str) -> None:
    """
    Kullanıcının kendi şifresini değiştirir.
    Mevcut şifre doğrulanır.

    Raises:
        ValueError: Geçersiz mevcut şifre veya eşleşmeyen yeni şifre.
    """
    from services.auth_service import verify_sifre

    ok, msg = validate_sifre(yeni_sifre, yeni_sifre_tekrar)
    if not ok:
        raise ValueError(msg)

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı.")

    mevcut_hash = str(user.get("Şifre Hash", ""))
    if not verify_sifre(mevcut_sifre, mevcut_hash):
        raise ValueError("Mevcut şifre hatalı.")

    new_hash = hash_sifre(yeni_sifre)
    sheets_client.update_row_field(
        SHEET_KULLANICILAR, "User ID", str(user_id), "Şifre Hash", new_hash, []
    )


def move_user_to_cari(user_id: int, yeni_cari_id: int) -> None:
    """
    Kullanıcıyı başka bir cariye taşır (Admin işlemi).

    Kurallar:
    - Hedef cari başka bir kullanıcıya bağlıysa hata.
    - Hedef cari pasifse otomatik Aktif yapılır.
    - Tarihsel işlemler değiştirilmez.

    Raises:
        ValueError: İş kuralı ihlali.
    """
    # Hedef cari başka kullanıcıya bağlı mı?
    for u in get_all_users():
        if int(u.get("Cari ID", -1)) == yeni_cari_id and int(u.get("User ID", -1)) != user_id:
            raise ValueError("Hedef cari zaten başka bir kullanıcıya bağlı.")

    # Hedef cariyi Aktif yap (pasifse)
    cariler = sheets_client.get_all_records(SHEET_CARILER)
    hedef_cari = None
    for c in cariler:
        if int(c.get("Cari ID", -1)) == yeni_cari_id:
            hedef_cari = c
            break

    if hedef_cari is None:
        raise ValueError("Hedef cari bulunamadı.")

    if str(hedef_cari.get("Durum", "")) != DURUM_AKTIF:
        sheets_client.update_row_field(
            SHEET_CARILER, "Cari ID", str(yeni_cari_id), "Durum", DURUM_AKTIF, []
        )

    # Kullanıcının Cari ID'sini güncelle
    updated = sheets_client.update_row_field(
        SHEET_KULLANICILAR, "User ID", str(user_id), "Cari ID", yeni_cari_id, []
    )
    if not updated:
        raise ValueError("Kullanıcı bulunamadı.")
