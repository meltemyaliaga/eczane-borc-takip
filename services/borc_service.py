"""
Borç verme iş mantığı servisi.

Sorumluluklar:
- Borç belgesi oluşturma (validasyon + belge no üretimi + yazma)
- Belge silme (soft delete)
- Hareket ve bakiye sorgulama
- Excel export verisi hazırlama
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from config import (
    SHEET_BORC_HAREKET,
    DURUM_AKTIF,
    DURUM_SILINDI,
)
from data import sheets_client
from services.cari_service import get_all_cariler, get_aktif_cariler, get_cari_by_id
from services.ilac_service import get_aktif_ilaclar, get_ilac_by_id
from utils.calculations import (
    hesapla_kalem_tutari,
    hesapla_belge_toplami,
    hesapla_tum_cari_bakiyeleri,
    hesapla_cari_net_bakiye,
    hesapla_iliski_bakiyesi,
    hesapla_cari_iliskiler,
    hesapla_kumulatif_bakiye,
    to_decimal,
)
from utils.validators import validate_borc_verme_form, validate_esit_dagit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hareket Sorgulama
# ---------------------------------------------------------------------------


def get_all_hareketler() -> List[Dict]:
    """Tüm BORC_HAREKET kayıtlarını döndürür (aktif + silindi)."""
    return sheets_client.get_all_records(SHEET_BORC_HAREKET)


def get_aktif_hareketler() -> List[Dict]:
    """Yalnızca aktif (silinmemiş) hareketleri döndürür."""
    return [h for h in get_all_hareketler() if str(h.get("Durum", "")) == DURUM_AKTIF]


def _normalize_hareket(h: Dict) -> Dict:
    """
    Sheet'ten gelen ham dict'i normalize eder.
    (ID'leri int'e çevirir, string değerleri temizler.)
    """
    try:
        return {
            **h,
            "Belge No": str(h.get("Belge No", "")),
            "Kalem No": int(h.get("Kalem No", 0)),
            "Borç Veren Cari ID": int(h.get("Borç Veren Cari ID", 0)),
            "İlaç ID": int(h.get("İlaç ID", 0)),
            "Lot Tarihi": str(h.get("Lot Tarihi", "")),
            "Birim Alış Fiyatı": str(h.get("Birim Alış Fiyatı", "0")),
            "Toplam Miktar": int(h.get("Toplam Miktar", 0)),
            "Borç Alan Cari ID": int(h.get("Borç Alan Cari ID", 0)),
            "Kalem Miktarı": int(h.get("Kalem Miktarı", 0)),
            "Oluşturan User ID": int(h.get("Oluşturan User ID", 0)),
            "Oluşturulma Tarihi": str(h.get("Oluşturulma Tarihi", "")),
            "Durum": str(h.get("Durum", "")),
            "Silen User ID": str(h.get("Silen User ID", "")),
            "Silinme Tarihi": str(h.get("Silinme Tarihi", "")),
            # Hesaplama için alias'lar (calculations.py uyumluluğu)
            "borc_veren_cari_id": int(h.get("Borç Veren Cari ID", 0)),
            "borc_alan_cari_id": int(h.get("Borç Alan Cari ID", 0)),
            "kalem_miktari": int(h.get("Kalem Miktarı", 0)),
            "birim_alis_fiyati": str(h.get("Birim Alış Fiyatı", "0")),
            "durum": str(h.get("Durum", "")),
        }
    except (ValueError, TypeError) as e:
        logger.warning("Hareket normalize hatası: %s — %s", e, h)
        return h


def get_hareketler_normalized() -> List[Dict]:
    """Normalize edilmiş tüm hareketleri döndürür."""
    return [_normalize_hareket(h) for h in get_all_hareketler()]


# ---------------------------------------------------------------------------
# Bakiye Sorgulama
# ---------------------------------------------------------------------------


def get_dashboard_data() -> List[Dict]:
    """
    Dashboard için tüm cariler ve net bakiyelerini döndürür.
    Alfabetik sıralı.

    Returns:
        [{"cari_id": int, "cari_adi": str, "durum": str, "net_bakiye": int}, ...]
    """
    cariler = get_all_cariler()
    hareketler = get_hareketler_normalized()
    cari_ids = [int(c["Cari ID"]) for c in cariler]
    bakiyeler = hesapla_tum_cari_bakiyeleri(hareketler, cari_ids)

    result = []
    for c in cariler:
        cid = int(c["Cari ID"])
        result.append({
            "cari_id": cid,
            "cari_adi": str(c["Cari Adı"]),
            "durum": str(c["Durum"]),
            "net_bakiye": bakiyeler.get(cid, 0),
        })

    return sorted(result, key=lambda x: x["cari_adi"].lower())


def get_cari_iliskiler(cari_id: int) -> List[Dict]:
    """
    Belirli bir carinin ilişkide olduğu diğer carileri ve bakiyelerini döndürür.
    Sıralama: Net bakiye büyükten küçüğe.
    En az bir aktif işlemi olan cariler gösterilir.

    Returns:
        [{"cari_id": int, "cari_adi": str, "durum": str, "net_bakiye": int}, ...]
    """
    hareketler = get_hareketler_normalized()
    cari_map = {int(c["Cari ID"]): c for c in get_all_cariler()}

    iliskiler = hesapla_cari_iliskiler(hareketler, cari_id)

    # Toplam net bakiye (tüm aktif hareketler üzerinden)
    result = []
    for karsi_id, bakiye in iliskiler.items():
        karsi_cari = cari_map.get(karsi_id, {})
        result.append({
            "cari_id": karsi_id,
            "cari_adi": str(karsi_cari.get("Cari Adı", f"Cari#{karsi_id}")),
            "durum": str(karsi_cari.get("Durum", "")),
            "net_bakiye": bakiye,
        })

    return sorted(result, key=lambda x: x["net_bakiye"], reverse=True)


def get_iliski_hareketleri(
    cari_a: int,
    cari_b: int,
    goster_silinenleri: bool = False,
) -> List[Dict]:
    """
    İki cari arasındaki hareketleri döndürür.
    Sıralama: Lot Tarihi, Belge No, Kalem No.
    Kümülatif bakiye dahildir.

    Returns:
        Her hareket için normalize edilmiş dict listesi, 'kumulatif_bakiye' alanıyla.
    """
    hareketler = get_hareketler_normalized()

    # Yalnızca A-B veya B-A hareketleri
    ilgili = []
    for h in hareketler:
        veren = h["borc_veren_cari_id"]
        alan = h["borc_alan_cari_id"]
        if (veren == cari_a and alan == cari_b) or (veren == cari_b and alan == cari_a):
            ilgili.append(h)

    if not goster_silinenleri:
        ilgili = [h for h in ilgili if h["durum"] != DURUM_SILINDI]

    # Sıralama: Lot Tarihi, Belge No, Kalem No
    def sort_key(h):
        lot = str(h.get("Lot Tarihi", ""))
        belge = str(h.get("Belge No", ""))
        kalem = int(h.get("Kalem No", 0))
        return (lot, belge, kalem)

    ilgili_sirali = sorted(ilgili, key=sort_key)

    # Kümülatif bakiye hesapla (silinmişler dahil — kümülatif bunları atlar)
    # Önce tüm (silinenler dahil) sıralı hareketler için hesapla
    tum_sirali = sorted(
        [h for h in hareketler
         if (h["borc_veren_cari_id"] == cari_a and h["borc_alan_cari_id"] == cari_b)
         or (h["borc_veren_cari_id"] == cari_b and h["borc_alan_cari_id"] == cari_a)],
        key=sort_key,
    )
    tum_kumulatif = hesapla_kumulatif_bakiye(tum_sirali, cari_a, cari_b)

    # Kümülatif bakiyeyi belge_no + kalem_no bazında indeksle
    kumul_index = {}
    for h in tum_kumulatif:
        key = (str(h["Belge No"]), int(h["Kalem No"]))
        kumul_index[key] = h["kumulatif_bakiye"]

    # goster_silinenleri = False ise silinmişleri filtrele, kümülatif koru
    result = []
    if goster_silinenleri:
        for h in tum_kumulatif:
            result.append({**h})
    else:
        for h in tum_kumulatif:
            if h["durum"] != DURUM_SILINDI:
                result.append({**h})

    return result


def get_belge_detay(belge_no: str) -> List[Dict]:
    """
    Bir belgenin tüm satırlarını (aktif + silindi) döndürür.
    """
    hareketler = get_hareketler_normalized()
    return [h for h in hareketler if h["Belge No"] == belge_no]


# ---------------------------------------------------------------------------
# Borç Belgesi Oluşturma
# ---------------------------------------------------------------------------


def validate_lot_uniqueness(
    borc_veren_cari_id: int,
    ilac_id: int,
    lot_tarihi: str,
    exclude_belge_no: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Aynı Borç Veren + İlaç + Lot Tarihi kombinasyonu için
    aktif belge olup olmadığını kontrol eder.

    Returns:
        (True, "") — benzersiz
        (False, hata_mesaji) — duplicate mevcut
    """
    hareketler = get_hareketler_normalized()
    for h in hareketler:
        if h["durum"] == DURUM_SILINDI:
            continue
        if (
            h["borc_veren_cari_id"] == borc_veren_cari_id
            and h["İlaç ID"] == ilac_id
            and str(h["Lot Tarihi"]) == str(lot_tarihi)
        ):
            belge_no = h["Belge No"]
            if exclude_belge_no and belge_no == exclude_belge_no:
                continue
            return False, (
                f"Bu ilaç ve lot tarihi için {belge_no} numaralı belge "
                f"zaten bulunmaktadır."
            )
    return True, ""


def create_borc_belgesi(
    borc_veren_cari_id: int,
    ilac_id: int,
    lot_tarihi: str,
    birim_alis_fiyati: str,
    toplam_miktar: int,
    dagitim: List[Dict],  # [{"cari_id": int, "miktar": int}]
    olusturan_user_id: int,
) -> str:
    """
    Borç belgesini doğrular ve kaydeder.

    Validasyonlar (Save sırasında tekrar):
    1. Kullanıcı girişi ve cari aktiflik (çağıran tarafından kontrol edilmeli)
    2. İlaç aktif mi?
    3. Borç alan cariler aktif mi?
    4. Form iş kuralları
    5. Lot uniqueness

    Returns:
        Oluşturulan belge numarası.

    Raises:
        ValueError: İş kuralı ihlali.
        RuntimeError: Yazma hatası.
    """
    # 1. İlaç aktif mi?
    ilac = get_ilac_by_id(ilac_id)
    if ilac is None:
        raise ValueError("Seçilen ilaç bulunamadı.")
    if str(ilac.get("Durum", "")) != DURUM_AKTIF:
        raise ValueError("Seçilen ilaç pasif durumdadır. İşlem oluşturulamaz.")

    # 2. Borç alan cariler aktif mi?
    for satir in dagitim:
        cari = get_cari_by_id(satir["cari_id"])
        if cari is None:
            raise ValueError(f"Borç alan cari bulunamadı (ID: {satir['cari_id']}).")
        if str(cari.get("Durum", "")) != DURUM_AKTIF:
            cari_adi = cari.get("Cari Adı", f"ID:{satir['cari_id']}")
            raise ValueError(f"'{cari_adi}' carisi pasif durumdadır. İşlem oluşturulamaz.")

    # 3. Form iş kuralları
    ok, msg = validate_borc_verme_form(
        ilac_id=ilac_id,
        lot_tarihi=lot_tarihi,
        birim_fiyat=birim_alis_fiyati,
        toplam_miktar=toplam_miktar,
        dagitim=dagitim,
        borc_veren_cari_id=borc_veren_cari_id,
    )
    if not ok:
        raise ValueError(msg)

    # 4. Lot uniqueness
    ok, msg = validate_lot_uniqueness(borc_veren_cari_id, ilac_id, lot_tarihi)
    if not ok:
        raise ValueError(msg)

    # 5. Belge numarası üret
    belge_no = sheets_client.get_next_belge_no()

    # 6. Kaydet
    belge_no = sheets_client.kaydet_borc_belgesi(
        belge_no=belge_no,
        borc_veren_cari_id=borc_veren_cari_id,
        ilac_id=ilac_id,
        lot_tarihi=lot_tarihi,
        birim_alis_fiyati=birim_alis_fiyati,
        toplam_miktar=toplam_miktar,
        dagitim=dagitim,
        olusturan_user_id=olusturan_user_id,
    )

    return belge_no


# ---------------------------------------------------------------------------
# Belge Silme
# ---------------------------------------------------------------------------


def delete_borc_belgesi(belge_no: str, yapan_user_id: int) -> None:
    """
    Borç belgesini soft-delete ile siler.

    Yetki kuralı: Yalnızca belgeyi oluşturan kullanıcı silebilir.

    Raises:
        ValueError: Yetki hatası veya belge bulunamazsa.
        RuntimeError: Yazma hatası.
    """
    hareketler = get_hareketler_normalized()
    belge_satirlari = [h for h in hareketler if h["Belge No"] == belge_no]

    if not belge_satirlari:
        raise ValueError("Belge bulunamadı.")

    # Yetki kontrolü: oluşturan kullanıcı kim?
    olusturan_user_id = int(belge_satirlari[0].get("Oluşturan User ID", 0))
    if olusturan_user_id != yapan_user_id:
        raise ValueError("Bu belgeyi yalnızca oluşturan kullanıcı silebilir.")

    # Zaten silinmiş mi?
    aktif_satirlar = [h for h in belge_satirlari if h["durum"] == DURUM_AKTIF]
    if not aktif_satirlar:
        raise ValueError("Bu belge zaten silinmiş.")

    sheets_client.soft_delete_borc_belgesi(belge_no, yapan_user_id)


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------


def get_dashboard_export_data(goster_silinenleri: bool = False) -> List[Dict]:
    """
    Dashboard Excel export için veri döndürür.
    """
    return get_dashboard_data()


def get_hareket_detay_export_data(
    cari_a: int,
    cari_b: int,
    goster_silinenleri: bool = False,
) -> List[Dict]:
    """
    Hareket detayı Excel export için veri döndürür.
    """
    return get_iliski_hareketleri(cari_a, cari_b, goster_silinenleri)
