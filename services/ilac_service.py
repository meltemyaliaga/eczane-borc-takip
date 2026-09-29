"""
İlaç yönetimi servisi.

Sorumluluklar:
- İlaç listesi sorgulama
- İlaç oluşturma (benzersizlik kontrolü — pasifler dahil)
- İlaç adı güncelleme
- İlaç aktif/pasif durumu değiştirme (yalnızca Admin)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pytz

from config import (
    SHEET_ILACLAR,
    TIMEZONE,
    DURUM_AKTIF,
    DURUM_PASIF,
)
from data import sheets_client
from utils.validators import validate_ilac_adi

logger = logging.getLogger(__name__)


def _now_istanbul() -> datetime:
    return datetime.now(pytz.timezone(TIMEZONE))


def get_all_ilaclar() -> List[Dict]:
    """Tüm ilaçları döndürür (aktif + pasif)."""
    return sheets_client.get_all_records_cached(SHEET_ILACLAR)


def get_aktif_ilaclar() -> List[Dict]:
    return [i for i in get_all_ilaclar() if str(i.get("Durum", "")) == DURUM_AKTIF]


def get_ilac_by_id(ilac_id: int) -> Optional[Dict]:
    for i in get_all_ilaclar():
        if int(i.get("İlaç ID", -1)) == ilac_id:
            return i
    return None


def get_ilac_map() -> Dict[int, str]:
    return {
        int(i["İlaç ID"]): str(i["İlaç Adı"])
        for i in get_all_ilaclar()
        if i.get("İlaç ID")
    }


def _get_next_ilac_id() -> int:
    ilaclar = get_all_ilaclar()
    if not ilaclar:
        return 1
    return max(int(i.get("İlaç ID", 0)) for i in ilaclar) + 1


def create_ilac(ilac_adi: str) -> Dict:
    ilac_adi = ilac_adi.strip()
    mevcut_adlar = [str(i.get("İlaç Adı", "")) for i in get_all_ilaclar()]
    ok, msg = validate_ilac_adi(ilac_adi, mevcut_adlar)
    if not ok:
        raise ValueError(msg)

    new_id = _get_next_ilac_id()
    olusturulma = _now_istanbul().strftime("%Y-%m-%d %H:%M:%S")
    row = [new_id, ilac_adi, DURUM_AKTIF, olusturulma]
    sheets_client.append_row(SHEET_ILACLAR, row)
    sheets_client.invalidate_cache()
    return {"İlaç ID": new_id, "İlaç Adı": ilac_adi, "Durum": DURUM_AKTIF, "Oluşturulma Tarihi": olusturulma}


def update_ilac_adi(ilac_id: int, yeni_ad: str) -> None:
    yeni_ad = yeni_ad.strip()
    if not yeni_ad:
        raise ValueError("İlaç adı boş olamaz.")

    mevcut_ilaclar = get_all_ilaclar()
    diger_adlar = [
        str(i.get("İlaç Adı", ""))
        for i in mevcut_ilaclar
        if int(i.get("İlaç ID", -1)) != ilac_id
    ]
    ok, msg = validate_ilac_adi(yeni_ad, diger_adlar)
    if not ok:
        raise ValueError(msg)

    updated = sheets_client.update_row_field(
        SHEET_ILACLAR, "İlaç ID", str(ilac_id), "İlaç Adı", yeni_ad, []
    )
    if not updated:
        raise ValueError("İlaç bulunamadı.")
    sheets_client.invalidate_cache()


def set_ilac_durum(ilac_id: int, yeni_durum: str) -> None:
    if yeni_durum not in [DURUM_AKTIF, DURUM_PASIF]:
        raise ValueError(f"Geçersiz durum: {yeni_durum}")

    updated = sheets_client.update_row_field(
        SHEET_ILACLAR, "İlaç ID", str(ilac_id), "Durum", yeni_durum, []
    )
    if not updated:
        raise ValueError("İlaç bulunamadı.")
    sheets_client.invalidate_cache()

