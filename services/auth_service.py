"""
Kimlik doğrulama ve oturum yönetimi servisi.

Sorumluluklar:
- Kullanıcı girişi (bcrypt hash doğrulaması)
- Oturum oluşturma ve sonlandırma
- 8 saatlik inactivity timeout
- Cari aktiflik kontrolü
- Reset şifre mekanizması
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

import bcrypt
import pytz
import streamlit as st

from config import (
    SHEET_KULLANICILAR,
    SHEET_CARILER,
    TIMEZONE,
    SESSION_TIMEOUT_HOURS,
    DURUM_AKTIF,
    DURUM_PASIF,
)
from data import sheets_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Şifre Yardımcıları
# ---------------------------------------------------------------------------


def hash_sifre(plaintext: str) -> str:
    """Şifreyi bcrypt ile hash'ler."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_sifre(plaintext: str, hashed: str) -> bool:
    """Şifreyi hash ile karşılaştırır."""
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Reset Şifre İşlemi
# ---------------------------------------------------------------------------


def _handle_reset_sifre_if_needed(user_row: Dict) -> Dict:
    """
    KULLANICILAR sheet'indeki Reset Şifre alanını kontrol eder.
    Doluysa: hash'ler, Şifre Hash'i günceller, Reset Şifre'yi temizler.

    Returns:
        Güncellenmiş user satırı (şifre hash güncellenmiş).
    """
    reset_sifre = str(user_row.get("Reset Şifre", "")).strip()
    if not reset_sifre:
        return user_row

    logger.info("Reset şifre algılandı; kullanıcı ID=%s", user_row.get("User ID"))
    new_hash = hash_sifre(reset_sifre)
    user_id = str(user_row["User ID"])

    try:
        # Şifre hash'i güncelle
        sheets_client.update_multiple_fields(
            SHEET_KULLANICILAR,
            "User ID",
            user_id,
            {
                "Şifre Hash": new_hash,
                "Reset Şifre": "",
            },
        )
        user_row = {**user_row, "Şifre Hash": new_hash, "Reset Şifre": ""}
        logger.info("Reset şifre işlendi ve temizlendi: User ID=%s", user_id)
    except Exception as e:
        logger.error("Reset şifre güncellenemedi: %s", e)
        # İşleme devam et; eski hash ile giriş yapabilir

    return user_row


# ---------------------------------------------------------------------------
# Giriş
# ---------------------------------------------------------------------------


def login(kullanici_adi: str, sifre: str) -> Dict:
    """
    Kullanıcı girişini doğrular.

    Returns:
        Başarılıysa kullanıcı verilerini içeren dict.

    Raises:
        ValueError: Hatalı kimlik bilgileri veya pasif cari.
    """
    kullanici_adi = kullanici_adi.strip()

    # Tüm kullanıcıları oku
    try:
        users = sheets_client.get_all_records_cached(SHEET_KULLANICILAR)
    except Exception as e:
        raise RuntimeError("Kullanıcı verileri okunamadı.") from e

    # Kullanıcıyı bul (case-insensitive)
    bulunan_user = None
    for u in users:
        if str(u.get("Kullanıcı Adı", "")).strip().lower() == kullanici_adi.lower():
            bulunan_user = u
            break

    if bulunan_user is None:
        raise ValueError("Kullanıcı adı veya şifre hatalı.")

    # Reset şifre kontrolü
    bulunan_user = _handle_reset_sifre_if_needed(bulunan_user)

    # Şifre doğrulama
    sifre_hash = str(bulunan_user.get("Şifre Hash", ""))
    if not verify_sifre(sifre, sifre_hash):
        raise ValueError("Kullanıcı adı veya şifre hatalı.")

    # Cari aktiflik kontrolü
    cari_id = int(bulunan_user["Cari ID"])
    cari = get_cari_by_id(cari_id)
    if cari is None:
        raise ValueError("Kullanıcıya bağlı cari bulunamadı.")
    if str(cari.get("Durum", "")) != DURUM_AKTIF:
        raise ValueError("Bağlı olduğunuz cari pasif durumdadır. Giriş yapamazsınız.")

    return bulunan_user


def get_cari_by_id(cari_id: int) -> Optional[Dict]:
    """Cari ID'ye göre cari kaydını döndürür."""
    try:
        cariler = sheets_client.get_all_records_cached(SHEET_CARILER)
    except Exception:
        return None
    for c in cariler:
        if str(c.get("Cari ID", "")) == str(cari_id):
            return c
    return None


# ---------------------------------------------------------------------------
# Oturum Yönetimi
# ---------------------------------------------------------------------------


def create_session(user_data: Dict) -> None:
    """
    Streamlit session_state'e oturum bilgilerini yazar.
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    st.session_state["authenticated"] = True
    st.session_state["user_id"] = int(user_data["User ID"])
    st.session_state["user_data"] = user_data
    st.session_state["last_activity"] = now
    st.session_state["session_created"] = now


def destroy_session(reason: str = "") -> None:
    """
    Oturumu sonlandırır ve session_state'i temizler.
    """
    keys_to_clear = [
        "authenticated", "user_id", "user_data",
        "last_activity", "session_created",
        "dashboard_level", "selected_cari_id", "selected_karsi_cari_id",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    if reason:
        st.session_state["logout_reason"] = reason


def check_and_refresh_session() -> bool:
    """
    Oturumun geçerliliğini kontrol eder ve son aktivite zamanını günceller.

    Kontroller:
    1. Authenticated flag var mı?
    2. 8 saatlik inactivity timeout aşıldı mı?
    3. Bağlı cari hâlâ aktif mi?

    Returns:
        True — oturum geçerli
        False — oturum sonlandırıldı
    """
    if not st.session_state.get("authenticated"):
        return False

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    last_activity = st.session_state.get("last_activity")

    if last_activity is None:
        destroy_session("Oturum bilgisi hatalı.")
        return False

    # Inactivity timeout
    if now - last_activity > timedelta(hours=SESSION_TIMEOUT_HOURS):
        destroy_session("Uzun süre işlem yapılmadığı için oturumunuz sonlandırıldı.")
        return False

    # Cari aktiflik kontrolü (her request'te)
    user_data = st.session_state.get("user_data", {})
    cari_id = user_data.get("Cari ID")
    if cari_id:
        cari = get_cari_by_id(int(cari_id))
        if cari is None or str(cari.get("Durum", "")) != DURUM_AKTIF:
            destroy_session("Bağlı olduğunuz cari pasif hale getirildi. Oturumunuz sonlandırıldı.")
            return False

    # Aktivite zamanını güncelle
    st.session_state["last_activity"] = now
    return True


def get_current_user() -> Optional[Dict]:
    """
    Aktif oturumdaki kullanıcı verisini döndürür.
    """
    return st.session_state.get("user_data")


def get_current_user_id() -> Optional[int]:
    return st.session_state.get("user_id")


def get_current_cari_id() -> Optional[int]:
    user = get_current_user()
    if user:
        return int(user.get("Cari ID", 0)) or None
    return None


def is_admin() -> bool:
    user = get_current_user()
    if not user:
        return False
    return str(user.get("Rol", "")).upper() == "ADMIN"


def refresh_user_data_in_session() -> None:
    """
    Session'daki kullanıcı verisini sheet'ten tazeleyerek günceller.
    Kullanıcı kendi bilgilerini değiştirdiğinde çağrılır.
    """
    user_id = get_current_user_id()
    if not user_id:
        return
    try:
        users = sheets_client.get_all_records_cached(SHEET_KULLANICILAR)
        for u in users:
            if int(u.get("User ID", 0)) == user_id:
                st.session_state["user_data"] = u
                return
    except Exception as e:
        logger.error("refresh_user_data_in_session hatası: %s", e)
