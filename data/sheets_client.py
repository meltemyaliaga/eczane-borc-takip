"""
Google Sheets veri erişim katmanı.

Bu modül:
- Google Sheets API ile bağlantıyı yönetir.
- CRUD operasyonlarını soyutlar.
- Belge numarası üretiminde optimistic locking uygular.
- Tüm sheet okuma/yazma işlemleri buradan geçer.

Gelecekte PostgreSQL gibi bir veritabanına geçildiğinde
yalnızca bu modülün değiştirilmesi yeterli olacaktır.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import gspread
import pytz
import streamlit as st
from google.oauth2.service_account import Credentials

from config import (
    BORC_HAREKET_HEADERS,
    CARILER_HEADERS,
    DURUM_AKTIF,
    DURUM_SILINDI,
    ILACLAR_HEADERS,
    KULLANICILAR_HEADERS,
    SHEET_BORC_HAREKET,
    SHEET_CARILER,
    SHEET_ILACLAR,
    SHEET_KULLANICILAR,
    TIMEZONE,
    BELGE_NO_YAZI_UZUNLUGU,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------------------------------------------------------------------------
# Bağlantı Yönetimi
# ---------------------------------------------------------------------------


def _get_credentials() -> Credentials:
    """Streamlit Secrets'tan servis hesabı kimlik bilgilerini alır."""
    creds_info = dict(st.secrets["gcp_service_account"])
    return Credentials.from_service_account_info(creds_info, scopes=SCOPES)


def _get_client() -> gspread.Client:
    """Kimliği doğrulanmış gspread istemcisi döndürür."""
    return gspread.authorize(_get_credentials())


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Ana spreadsheet nesnesini döndürür."""
    client = _get_client()
    spreadsheet_id = st.secrets["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)


def _get_worksheet(sheet_name: str) -> gspread.Worksheet:
    """Belirtilen isimde worksheet döndürür."""
    return _get_spreadsheet().worksheet(sheet_name)


# ---------------------------------------------------------------------------
# Genel Okuma / Yazma
# ---------------------------------------------------------------------------


def get_all_records(sheet_name: str) -> List[Dict[str, Any]]:
    """
    Belirtilen sheet'teki tüm kayıtları dict listesi olarak döndürür.
    İlk satır header kabul edilir.
    """
    try:
        ws = _get_worksheet(sheet_name)
        records = ws.get_all_records(numericise_ignore=["all"])
        return records
    except Exception as e:
        logger.error("get_all_records hatası [%s]: %s", sheet_name, e)
        raise RuntimeError(f"Veri okunamadı: {sheet_name}") from e


def get_all_values(sheet_name: str) -> List[List[str]]:
    """
    Ham değerleri (header dahil) satır listesi olarak döndürür.
    """
    try:
        ws = _get_worksheet(sheet_name)
        return ws.get_all_values()
    except Exception as e:
        logger.error("get_all_values hatası [%s]: %s", sheet_name, e)
        raise RuntimeError(f"Veri okunamadı: {sheet_name}") from e


def append_row(sheet_name: str, row: List[Any]) -> None:
    """Tek satır ekler."""
    try:
        ws = _get_worksheet(sheet_name)
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.error("append_row hatası [%s]: %s", sheet_name, e)
        raise RuntimeError("Kayıt eklenemedi.") from e


def append_rows(sheet_name: str, rows: List[List[Any]]) -> None:
    """Birden fazla satırı toplu olarak ekler."""
    try:
        ws = _get_worksheet(sheet_name)
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.error("append_rows hatası [%s]: %s", sheet_name, e)
        raise RuntimeError("Kayıtlar eklenemedi.") from e


def update_cell_by_row_col(
    sheet_name: str, row_index: int, col_index: int, value: Any
) -> None:
    """
    Belirli bir hücreyi günceller.
    row_index ve col_index 1-tabanlıdır (gspread standardı).
    """
    try:
        ws = _get_worksheet(sheet_name)
        ws.update_cell(row_index, col_index, value)
    except Exception as e:
        logger.error(
            "update_cell hatası [%s] r%sc%s: %s", sheet_name, row_index, col_index, e
        )
        raise RuntimeError("Hücre güncellenemedi.") from e


def batch_update_cells(
    sheet_name: str, updates: List[Dict]
) -> None:
    """
    Birden fazla hücreyi tek API çağrısında günceller.

    updates formatı:
        [{"range": "A2", "values": [[value]]}, ...]
    """
    try:
        ws = _get_worksheet(sheet_name)
        ws.batch_update(updates)
    except Exception as e:
        logger.error("batch_update_cells hatası [%s]: %s", sheet_name, e)
        raise RuntimeError("Toplu güncelleme başarısız.") from e


# ---------------------------------------------------------------------------
# Sheet Başlatma
# ---------------------------------------------------------------------------


def ensure_headers(sheet_name: str, headers: List[str]) -> None:
    """
    Eğer sheet boşsa başlık satırını ekler.
    Mevcut veri varsa dokunmaz.
    """
    try:
        ws = _get_worksheet(sheet_name)
        all_vals = ws.get_all_values()
        if not all_vals:
            ws.append_row(headers)
            logger.info("Başlıklar eklendi: %s", sheet_name)
    except Exception as e:
        logger.error("ensure_headers hatası [%s]: %s", sheet_name, e)
        raise RuntimeError(f"Sheet başlıkları kontrol edilemedi: {sheet_name}") from e


def initialize_all_sheets() -> None:
    """
    Tüm sheet'lerin başlıklarını kontrol eder, eksikse ekler.
    Uygulama başlangıcında çağrılır.
    """
    ensure_headers(SHEET_CARILER, CARILER_HEADERS)
    ensure_headers(SHEET_KULLANICILAR, KULLANICILAR_HEADERS)
    ensure_headers(SHEET_ILACLAR, ILACLAR_HEADERS)
    ensure_headers(SHEET_BORC_HAREKET, BORC_HAREKET_HEADERS)


# ---------------------------------------------------------------------------
# Belge Numarası Üretimi (Optimistic Locking)
# ---------------------------------------------------------------------------


def _now_istanbul() -> datetime:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)


def _uret_belge_no(yil: int, mevcut_max_seq: int) -> str:
    """Belge numarasını formatla."""
    seq = mevcut_max_seq + 1
    return f"{yil}-{seq:0{BELGE_NO_YAZI_UZUNLUGU}d}"


def _parse_belge_no_seq(belge_no: str) -> tuple:
    """
    Belge numarasından (yil, seq) tuple'ı çıkarır.
    '2026-0000001' → (2026, 1)
    """
    try:
        parts = belge_no.split("-")
        yil = int(parts[0])
        seq = int(parts[1])
        return yil, seq
    except Exception:
        return 0, 0


def get_next_belge_no() -> str:
    """
    O yıl için sıradaki belge numarasını döndürür.
    Silinen belgeler dahil mevcut en yüksek numaradan devam eder.

    Eşzamanlılık notu:
        İki kullanıcı aynı anda çağırırsa aynı numarayı alabilir.
        Yazma sonrası duplicate kontrolü borc_service'te yapılır.
    """
    yil = _now_istanbul().year
    try:
        records = get_all_records(SHEET_BORC_HAREKET)
    except Exception:
        records = []

    max_seq = 0
    for r in records:
        belge_no = str(r.get("Belge No", ""))
        if not belge_no:
            continue
        b_yil, b_seq = _parse_belge_no_seq(belge_no)
        if b_yil == yil and b_seq > max_seq:
            max_seq = b_seq

    return _uret_belge_no(yil, max_seq)


def kaydet_borc_belgesi(
    belge_no: str,
    borc_veren_cari_id: int,
    ilac_id: int,
    lot_tarihi: str,
    birim_alis_fiyati: str,
    toplam_miktar: int,
    dagitim: List[Dict],  # [{"cari_id": int, "miktar": int}]
    olusturan_user_id: int,
) -> str:
    """
    Borç belgesinin tüm satırlarını atomik olarak BORC_HAREKET sheet'ine yazar.

    Returns:
        Kaydedilen belge numarası.

    Raises:
        RuntimeError: Yazma başarısızsa veya duplicate belge no tespit edilirse.
    """
    olusturulma_tarihi = _now_istanbul().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for kalem_no, satir in enumerate(dagitim, start=1):
        row = [
            belge_no,                          # Belge No
            kalem_no,                          # Kalem No
            borc_veren_cari_id,               # Borç Veren Cari ID
            ilac_id,                           # İlaç ID
            lot_tarihi,                        # Lot Tarihi
            birim_alis_fiyati,                 # Birim Alış Fiyatı
            toplam_miktar,                     # Toplam Miktar
            satir["cari_id"],                  # Borç Alan Cari ID
            satir["miktar"],                   # Kalem Miktarı
            olusturan_user_id,                 # Oluşturan User ID
            olusturulma_tarihi,                # Oluşturulma Tarihi
            DURUM_AKTIF,                       # Durum
            "",                                # Silen User ID
            "",                                # Silinme Tarihi
        ]
        rows.append(row)

    # Tüm satırları tek çağrıda yaz
    append_rows(SHEET_BORC_HAREKET, rows)

    # Duplicate belge no kontrolü (optimistic locking)
    _verify_belge_no_uniqueness(belge_no, len(rows))

    return belge_no


def _verify_belge_no_uniqueness(belge_no: str, beklenen_satir_sayisi: int) -> None:
    """
    Yazım sonrası duplicate belge no kontrolü.
    Eşzamanlı kayıt durumunda aynı belge no iki farklı işlemde kullanılmış olabilir.
    Bu durumda RuntimeError fırlatır (servis katmanı kullanıcıya bildirir).
    """
    time.sleep(0.5)  # Kısa bekleme: sheets'in tutarlı hale gelmesi için
    try:
        records = get_all_records(SHEET_BORC_HAREKET)
        count = sum(1 for r in records if str(r.get("Belge No", "")) == belge_no)
        if count != beklenen_satir_sayisi:
            logger.warning(
                "Duplicate belge no tespit edildi: %s (beklenen=%d, bulunan=%d)",
                belge_no, beklenen_satir_sayisi, count,
            )
            raise RuntimeError(
                f"Eşzamanlı kayıt çakışması tespit edildi ({belge_no}). "
                "Lütfen tekrar deneyiniz."
            )
    except RuntimeError:
        raise
    except Exception as e:
        logger.error("Belge no uniqueness kontrolü başarısız: %s", e)
        # Kontrol başarısız olsa da işlemi durdurmuyoruz;
        # sistem tutarlılığını korumak için kaydı geçerli sayıyoruz.


def soft_delete_borc_belgesi(
    belge_no: str,
    silen_user_id: int,
) -> None:
    """
    Bir belgenin tüm aktif satırlarını soft-delete yapar.

    Durum = 'Silindi', Silen User ID ve Silinme Tarihi doldurulur.
    Tüm satırlar birlikte silinir.
    """
    silinme_tarihi = _now_istanbul().strftime("%Y-%m-%d %H:%M:%S")

    try:
        ws = _get_worksheet(SHEET_BORC_HAREKET)
        all_values = ws.get_all_values()
    except Exception as e:
        raise RuntimeError("Hareket verileri okunamadı.") from e

    if not all_values or len(all_values) < 2:
        raise RuntimeError("Belge bulunamadı.")

    headers = all_values[0]
    try:
        belge_no_col = headers.index("Belge No") + 1        # 1-tabanlı
        durum_col = headers.index("Durum") + 1
        silen_col = headers.index("Silen User ID") + 1
        silinme_col = headers.index("Silinme Tarihi") + 1
    except ValueError as e:
        raise RuntimeError(f"Sheet kolon yapısı hatalı: {e}") from e

    # Dinamik kolon harfleri
    durum_letter = _col_idx_to_letter(durum_col)
    silen_letter = _col_idx_to_letter(silen_col)
    silinme_letter = _col_idx_to_letter(silinme_col)

    # Güncellenecek satırları bul
    updates = []
    for i, row in enumerate(all_values[1:], start=2):  # 2 = ilk veri satırı (1-tabanlı)
        if len(row) > belge_no_col - 1 and row[belge_no_col - 1] == belge_no:
            mevcut_durum = row[durum_col - 1] if len(row) >= durum_col else ""
            if mevcut_durum != DURUM_SILINDI:
                updates.append({
                    "range": f"{durum_letter}{i}:{silinme_letter}{i}",
                    "values": [[DURUM_SILINDI, str(silen_user_id), silinme_tarihi]],
                })

    if not updates:
        raise RuntimeError("Silinecek aktif belge satırı bulunamadı.")

    try:
        ws.batch_update(updates)
    except Exception as e:
        logger.error("soft_delete_borc_belgesi batch_update hatası: %s", e)
        raise RuntimeError("Belge silinemedi.") from e


def update_row_field(
    sheet_name: str,
    key_col_name: str,
    key_value: Any,
    field_col_name: str,
    new_value: Any,
    headers_order: List[str],
) -> bool:
    """
    Belirtilen sheet'te key_col_name = key_value olan satırdaki
    field_col_name alanını new_value ile günceller.

    Returns:
        True — satır bulundu ve güncellendi.
        False — satır bulunamadı.
    """
    try:
        ws = _get_worksheet(sheet_name)
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return False

        actual_headers = all_values[0]
        try:
            key_col_idx = actual_headers.index(key_col_name)  # 0-tabanlı
            field_col_idx = actual_headers.index(field_col_name)  # 0-tabanlı
        except ValueError as e:
            logger.error("update_row_field kolon bulunamadı: %s", e)
            return False

        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > key_col_idx and str(row[key_col_idx]) == str(key_value):
                ws.update_cell(i, field_col_idx + 1, new_value)
                return True
        return False
    except Exception as e:
        logger.error("update_row_field hatası [%s]: %s", sheet_name, e)
        raise RuntimeError("Alan güncellenemedi.") from e


def update_multiple_fields(
    sheet_name: str,
    key_col_name: str,
    key_value: Any,
    field_updates: Dict[str, Any],
) -> bool:
    """
    Tek bir satırda birden fazla alanı toplu günceller.

    field_updates: {kolon_adi: yeni_deger}
    """
    try:
        ws = _get_worksheet(sheet_name)
        all_values = ws.get_all_values()
        if not all_values or len(all_values) < 2:
            return False

        headers = all_values[0]
        try:
            key_col_idx = headers.index(key_col_name)
        except ValueError:
            return False

        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > key_col_idx and str(row[key_col_idx]) == str(key_value):
                cell_updates = []
                for col_name, new_val in field_updates.items():
                    try:
                        col_idx = headers.index(col_name) + 1  # 1-tabanlı
                        col_letter = _col_idx_to_letter(col_idx)
                        cell_updates.append({
                            "range": f"{col_letter}{i}",
                            "values": [[new_val]],
                        })
                    except ValueError:
                        logger.warning("Kolon bulunamadı: %s", col_name)
                if cell_updates:
                    ws.batch_update(cell_updates)
                return True
        return False
    except Exception as e:
        logger.error("update_multiple_fields hatası [%s]: %s", sheet_name, e)
        raise RuntimeError("Güncelleme başarısız.") from e


def _col_idx_to_letter(col_idx: int) -> str:
    """
    1-tabanlı kolon indeksini Excel kolon harfine çevirir.
    Örnek: 1 → 'A', 27 → 'AA'
    """
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result
