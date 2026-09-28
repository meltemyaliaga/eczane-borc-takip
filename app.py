"""
Streamlit uygulaması giriş noktası.

Sorumluluklar:
- Sayfa yapılandırması
- Oturum kontrolü
- Sidebar navigasyon
- Sayfa yönlendirme
"""

import logging

import streamlit as st

from config import ROL_ADMIN
from services import auth_service
from ui import login, dashboard, borc_verme, cari_yonetimi, ilac_yonetimi, profilim

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sayfa Yapılandırması
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Eczane Borç Takip",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal stil ayarlamaları
st.markdown(
    """
    <style>
    /* Sidebar başlık */
    .css-1d391kg { padding-top: 1rem; }
    /* Tablo hücre sınırlarını belirginleştir */
    div[data-testid="stHorizontalBlock"] > div { border-bottom: 1px solid #f0f0f0; padding: 4px 0; }
    /* Hata kutusu */
    div[data-testid="stAlert"] { border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Oturum Kontrolü
# ---------------------------------------------------------------------------

def _check_session() -> bool:
    """
    Oturumu kontrol eder.
    Geçersizse destroy_session çağırır ve False döndürür.
    """
    if not st.session_state.get("authenticated"):
        return False
    return auth_service.check_and_refresh_session()


# ---------------------------------------------------------------------------
# Sidebar Navigasyon
# ---------------------------------------------------------------------------

def _render_sidebar(user: dict) -> str:
    """
    Sidebar'ı çizer ve seçilen sayfayı döndürür.
    """
    with st.sidebar:
        st.markdown("## 💊 Eczane Borç Takip")
        st.markdown("---")

        kullanici_adi = user.get("Kullanıcı Adı", "")
        cari_id = int(user.get("Cari ID", 0))

        try:
            from services.cari_service import get_cari_by_id
            cari = get_cari_by_id(cari_id)
            cari_adi = cari.get("Cari Adı", "") if cari else ""
        except Exception:
            cari_adi = ""

        st.markdown(f"**{kullanici_adi}**")
        if cari_adi:
            st.markdown(f"_{cari_adi}_")
        st.markdown("---")

        # Menü yapılandırması
        rol = str(user.get("Rol", "")).upper()
        if rol == ROL_ADMIN:
            sayfa_listesi = [
                "📊 Dashboard",
                "💊 Borç Verme",
                "🏥 Cari Yönetimi",
                "📋 İlaç Yönetimi",
                "👤 Profilim",
            ]
        else:
            sayfa_listesi = [
                "📊 Dashboard",
                "💊 Borç Verme",
                "📋 İlaç Yönetimi",
                "👤 Profilim",
            ]

        secili = st.radio(
            "Menü",
            sayfa_listesi,
            label_visibility="collapsed",
        )

        st.markdown("---")
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            auth_service.destroy_session()
            st.rerun()

    return secili


# ---------------------------------------------------------------------------
# Ana Uygulama
# ---------------------------------------------------------------------------

def main() -> None:
    # Oturum kontrolü
    if not _check_session():
        # Çıkış sebebi varsa session_state'te tutulur, login ekranında gösterilir
        login.render()
        return

    user = auth_service.get_current_user()
    if not user:
        login.render()
        return

    # Sidebar + sayfa seçimi
    secili_sayfa = _render_sidebar(user)

    # Yetki koruması: Cari Yönetimi yalnızca Admin
    rol = str(user.get("Rol", "")).upper()
    if "Cari Yönetimi" in secili_sayfa and rol != ROL_ADMIN:
        st.error("Bu sayfaya erişim yetkiniz yok.")
        return

    # Sayfa yönlendirme
    if "Dashboard" in secili_sayfa:
        dashboard.render(user)
    elif "Borç Verme" in secili_sayfa:
        borc_verme.render(user)
    elif "Cari Yönetimi" in secili_sayfa:
        cari_yonetimi.render(user)
    elif "İlaç Yönetimi" in secili_sayfa:
        ilac_yonetimi.render(user)
    elif "Profilim" in secili_sayfa:
        profilim.render(user)


main()
