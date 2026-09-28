"""
Merkezi hesaplama modülü.
Tüm tutar, bakiye ve rounding hesaplamaları bu modülden yapılır.
Python'ın banker's rounding davranışından kaçınmak için Decimal + ROUND_HALF_UP kullanılır.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Dict, Optional


def to_decimal(value) -> Decimal:
    """Herhangi bir değeri güvenli şekilde Decimal'e çevirir."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Geçersiz sayısal değer: {value!r}")


def round_half_up_to_int(value: Decimal) -> int:
    """Decimal değeri ROUND_HALF_UP yöntemiyle tam sayıya yuvarlar."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def hesapla_kalem_tutari(kalem_miktari: int, birim_alis_fiyati) -> int:
    """
    Kalem tutarını hesaplar.

    Formül: kalem_miktari × birim_alis_fiyati
    Sonuç tam TL'ye ROUND_HALF_UP ile yuvarlanır.

    Örnek:
        333 × 10.1234 = 3371.0922 → 3371 TL
        333 × 10.1252 = 3371.6916 → 3372 TL
    """
    fiyat = to_decimal(birim_alis_fiyati)
    miktar = Decimal(str(kalem_miktari))
    sonuc = miktar * fiyat
    return round_half_up_to_int(sonuc)


def hesapla_belge_toplami(toplam_miktar: int, birim_alis_fiyati) -> int:
    """
    Belge toplamını hesaplar.

    Formül: toplam_miktar × birim_alis_fiyati → tam TL
    """
    return hesapla_kalem_tutari(toplam_miktar, birim_alis_fiyati)


def hesapla_cari_net_bakiye(hareketler: List[Dict], cari_id: int) -> int:
    """
    Tek bir carinin genel net bakiyesini hesaplar.

    Seçili cari perspektifinden:
    - Borç Verdi (veren == cari_id) → +tutar
    - Borç Aldı  (alan  == cari_id) → -tutar

    Silinmiş hareketler dahil edilmez.
    """
    bakiye = 0
    for h in hareketler:
        if h.get("durum") == "Silindi":
            continue
        tutar = hesapla_kalem_tutari(
            int(h["kalem_miktari"]),
            h["birim_alis_fiyati"],
        )
        if int(h["borc_veren_cari_id"]) == cari_id:
            bakiye += tutar
        if int(h["borc_alan_cari_id"]) == cari_id:
            bakiye -= tutar
    return bakiye


def hesapla_tum_cari_bakiyeleri(
    hareketler: List[Dict], tum_cari_ids: List[int]
) -> Dict[int, int]:
    """
    Tüm cariler için net bakiyeleri tek geçişte hesaplar.
    Performans: O(n) — yalnızca bir kez hareket listesi taranır.

    Returns:
        {cari_id: net_bakiye} — her cari kendi perspektifinden.
    """
    bakiyeler: Dict[int, int] = {cid: 0 for cid in tum_cari_ids}

    for h in hareketler:
        if h.get("durum") == "Silindi":
            continue
        tutar = hesapla_kalem_tutari(
            int(h["kalem_miktari"]),
            h["birim_alis_fiyati"],
        )
        veren = int(h["borc_veren_cari_id"])
        alan = int(h["borc_alan_cari_id"])

        if veren in bakiyeler:
            bakiyeler[veren] += tutar  # Borç verdi → alacağı artar
        if alan in bakiyeler:
            bakiyeler[alan] -= tutar  # Borç aldı → borcu artar

    return bakiyeler


def hesapla_iliski_bakiyesi(
    hareketler: List[Dict], cari_a: int, cari_b: int
) -> int:
    """
    Cari A ile Cari B arasındaki net bakiyeyi, A perspektifinden hesaplar.

    Yalnızca A→B veya B→A hareketleri dahil edilir.
    Silinmiş hareketler dahil edilmez.
    """
    bakiye = 0
    for h in hareketler:
        if h.get("durum") == "Silindi":
            continue
        veren = int(h["borc_veren_cari_id"])
        alan = int(h["borc_alan_cari_id"])

        if veren == cari_a and alan == cari_b:
            # A borç verdi → A'nın bakiyesi artar
            tutar = hesapla_kalem_tutari(int(h["kalem_miktari"]), h["birim_alis_fiyati"])
            bakiye += tutar
        elif veren == cari_b and alan == cari_a:
            # A borç aldı → A'nın bakiyesi azalır
            tutar = hesapla_kalem_tutari(int(h["kalem_miktari"]), h["birim_alis_fiyati"])
            bakiye -= tutar

    return bakiye


def hesapla_cari_iliskiler(
    hareketler: List[Dict], cari_id: int
) -> Dict[int, int]:
    """
    Belirli bir carinin, ilişkide olduğu diğer tüm carilerle bakiyelerini hesaplar.

    Returns:
        {karsi_cari_id: net_bakiye_cari_perspektifinden}
    """
    iliskiler: Dict[int, int] = {}

    for h in hareketler:
        if h.get("durum") == "Silindi":
            continue
        veren = int(h["borc_veren_cari_id"])
        alan = int(h["borc_alan_cari_id"])

        # Bu hareket seçili cari ile ilgili mi?
        if veren != cari_id and alan != cari_id:
            continue

        tutar = hesapla_kalem_tutari(int(h["kalem_miktari"]), h["birim_alis_fiyati"])

        if veren == cari_id:
            # Cari A borç verdi; karşı cari = alan
            karsi = alan
            iliskiler[karsi] = iliskiler.get(karsi, 0) + tutar
        else:
            # Cari A borç aldı; karşı cari = veren
            karsi = veren
            iliskiler[karsi] = iliskiler.get(karsi, 0) - tutar

    return iliskiler


def hesapla_kumulatif_bakiye(
    hareketler_sirali: List[Dict],
    cari_a: int,
    cari_b: int,
) -> List[Dict]:
    """
    A-B arasındaki sıralanmış hareketlere kümülatif bakiye alanı ekler.

    Sıralama (çağıran tarafından yapılmış olmalıdır):
        1. Lot Tarihi
        2. Belge No
        3. Kalem No

    Silinmiş hareketler kümülatife dahil edilmez; önceki kümülatif değer korunur.

    Returns:
        Her hareket dict'ine 'kumulatif_bakiye' eklenmiş liste.
    """
    kumulatif = 0
    result = []

    for h in hareketler_sirali:
        if h.get("durum") != "Silindi":
            tutar = hesapla_kalem_tutari(
                int(h["kalem_miktari"]), h["birim_alis_fiyati"]
            )
            veren = int(h["borc_veren_cari_id"])
            if veren == cari_a:
                kumulatif += tutar
            else:
                kumulatif -= tutar

        result.append({**h, "kumulatif_bakiye": kumulatif})

    return result
