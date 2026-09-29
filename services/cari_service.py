"""
Cari yönetimi servisi.

Sorumluluklar:
- Cari listesi sorgulama
- Cari oluşturma (benzersizlik kontrolü)
- Cari adı güncelleme
- Cari aktif/pasif durumu değiştirme
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pytz

from config import (
    SHEET_CARILER,
    TIMEZONE,
    DURUM_AKTIF,
    DURUM_PASIF,
)
from data import sheets_client
from utils.validators import validate_cari_adi

logger = logging.getLogger(__name__)


def _now_istanbul() -> datetime:
    return datetime.now(pytz.timezone(TIMEZONE))


def get_all_cariler() -> List[Dict]:
    """Tüm carileri döndürür (aktif + pasif)."""
    return sheets_client.get_all_records_cached(SHEET_CARILER)


def get_aktif_cariler() -> List[Dict]:
    """Yalnızca aktif carileri döndürür."""
    return [c for c in get_all_cariler() if str(c.get("Durum", "")) == DURUM_AKTIF]


def get_cari_by_id(cari_id: int) -> Optional[Dict]:
    """Belirli bir cariyi ID ile getirir."""
    for c in get_all_cariler():
        if int(c.get("Cari ID", -1)) == cari_id:
            return c
    return None


def get_cari_map() -> Dict[int, str]:
    return {
        int(c["Cari ID"]): str(c["Cari Adı"])
        for c in get_all_cariler()
        if c.get("Cari ID")
    }


def _get_next_cari_id() -> int:
    cariler = get_all_cariler()
    if not cariler:
        return 1
    return max(int(c.get("Cari ID", 0)) for c in cariler) + 1


def create_cari(cari_adi: str) -> Dict:
    cari_adi = cari_adi.strip()
    mevcut_adlar = [str(c.get("Cari Adı", "")) for c in get_all_cariler()]
    ok, msg = validate_cari_adi(cari_adi, mevcut_adlar)
    if not ok:
        raise ValueError(msg)

    new_id = _get_next_cari_id()
    olusturulma = _now_istanbul().strftime("%Y-%m-%d %H:%M:%S")
    row = [new_id, cari_adi, DURUM_AKTIF, olusturulma]
    sheets_client.append_row(SHEET_CARILER, row)
    sheets_client.invalidate_cache()
    return {"Cari ID": new_id, "Cari Adı": cari_adi, "Durum": DURUM_AKTIF, "Oluşturulma Tarihi": olusturulma}


def update_cari_adi(cari_id: int, yeni_ad: str, guncelleme_yapan_cari_id: Optional[int] = None) -> None:
    yeni_ad = yeni_ad.strip()
    if not yeni_ad:
        raise ValueError("Cari adı boş olamaz.")

    mevcut_cariler = get_all_cariler()
    diger_adlar = [
        str(c.get("Cari Adı", ""))
        for c in mevcut_cariler
        if int(c.get("Cari ID", -1)) != cari_id
    ]
    ok, msg = validate_cari_adi(yeni_ad, diger_adlar)
    if not ok:
        raise ValueError(msg)

    updated = sheets_client.update_row_field(
        SHEET_CARILER, "Cari ID", str(cari_id), "Cari Adı", yeni_ad, []
    )
    if not updated:
        raise ValueError("Cari bulunamadı.")
    sheets_client.invalidate_cache()


def set_cari_durum(cari_id: int, yeni_durum: str, yapan_cari_id: Optional[int] = None) -> None:
    if yeni_durum == DURUM_PASIF and cari_id == yapan_cari_id:
        raise ValueError("Kendi bağlı olduğunuz cariyi pasif yapamazsınız.")
    if yeni_durum not in [DURUM_AKTIF, DURUM_PASIF]:
        raise ValueError(f"Geçersiz durum: {yeni_durum}")

    updated = sheets_client.update_row_field(
        SHEET_CARILER, "Cari ID", str(cari_id), "Durum", yeni_durum, []
    )
    if not updated:
        raise ValueError("Cari bulunamadı.")
    sheets_client.invalidate_cache()

