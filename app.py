"""
Streamlit uygulaması giriş noktası.
"""

import logging
import streamlit as st

from config import ROL_ADMIN
from services import auth_service
from ui import login, dashboard, borc_verme, cari_yonetimi, ilac_yonetimi, profilim

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Eczane Borç Takip",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Modern CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Genel font */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Ana arka plan */
.stApp { background-color: #F1F5F9; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
    border-right: none;
}
section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
section[data-testid="stSidebar"] .stRadio label {
    color: #CBD5E1 !important;
    font-size: 0.95rem;
    padding: 6px 0;
}
section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    color: #94A3B8 !important;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* Başlıklar */
h1 { font-size: 1.75rem !important; font-weight: 700 !important; color: #1E293B !important; }
h2 { font-size: 1.4rem !important; font-weight: 600 !important; color: #1E293B !important; }
h3 { font-size: 1.1rem !important; font-weight: 600 !important; color: #334155 !important; }

/* Metric kartları */
[data-testid="metric-container"] {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-testid="metric-container"] label {
    font-size: 0.8rem !important;
    color: #64748B !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}

/* Form alanları */
.stTextInput input, .stSelectbox select, .stDateInput input {
    border-radius: 8px !important;
    border: 1px solid #CBD5E1 !important;
    font-size: 0.95rem !important;
    transition: border-color 0.2s;
}
.stTextInput input:focus { border-color: #2563EB !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important; }

/* Butonlar */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s !important;
    border: none !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8, #1E40AF) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    background: white !important;
    color: #374151 !important;
    border: 1px solid #D1D5DB !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #F9FAFB !important;
    border-color: #9CA3AF !important;
}

/* Uyarı ve bilgi kutuları */
.stAlert {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* Expander */
.streamlit-expanderHeader {
    border-radius: 10px !important;
    background: white !important;
    border: 1px solid #E2E8F0 !important;
    font-weight: 600 !important;
    color: #1E293B !important;
    padding: 12px 16px !important;
}
.streamlit-expanderContent {
    border: 1px solid #E2E8F0 !important;
    border-top: none !important;
    border-radius: 0 0 10px 10px !important;
    background: white !important;
    padding: 16px !important;
}

/* Tab */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid #E2E8F0;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-weight: 500 !important;
    color: #64748B !important;
}
.stTabs [aria-selected="true"] {
    background: #2563EB !important;
    color: white !important;
}

/* Tablo satır vurgusu */
[data-testid="stHorizontalBlock"]:hover { background: rgba(37,99,235,0.03); border-radius: 8px; }

/* Download butonu */
.stDownloadButton > button {
    background: white !important;
    color: #2563EB !important;
    border: 1px solid #2563EB !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stDownloadButton > button:hover {
    background: #EFF6FF !important;
}

/* Divider */
hr { border-color: #E2E8F0 !important; margin: 12px 0 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #F1F5F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }

/* ── Geçiş Animasyonu Overlay ── */
#agy-loading-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(241, 245, 249, 0.80);
    backdrop-filter: blur(3px);
    z-index: 99999;
    justify-content: center;
    align-items: center;
    flex-direction: column;
    gap: 14px;
}
#agy-loading-overlay.visible { display: flex; }

.agy-spinner {
    width: 44px; height: 44px;
    border: 4px solid #E2E8F0;
    border-top: 4px solid #2563EB;
    border-radius: 50%;
    animation: agy-spin 0.75s linear infinite;
}
.agy-loading-text {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 500;
    color: #64748B;
}
@keyframes agy-spin { to { transform: rotate(360deg); } }
</style>
""", unsafe_allow_html=True)

# ─── Loading Overlay HTML + JS ────────────────────────────────────────────────
st.markdown("""
<div id="agy-loading-overlay">
    <div class="agy-spinner"></div>
    <div class="agy-loading-text">Yükleniyor...</div>
</div>

<script>
(function() {
    var overlay = document.getElementById('agy-loading-overlay');
    if (!overlay) return;

    // Buton tıklamalarında overlay'i göster
    document.addEventListener('click', function(e) {
        var el = e.target;
        for (var i = 0; i < 5; i++) {
            if (!el) break;
            if (el.tagName === 'BUTTON' || el.tagName === 'INPUT') {
                overlay.classList.add('visible');
                break;
            }
            el = el.parentElement;
        }
    }, true);

    // Streamlit rerun tamamlandığında overlay'i gizle
    var appRoot = document.querySelector('.stApp') || document.body;
    var observer = new MutationObserver(function() {
        if (overlay.classList.contains('visible')) {
            overlay.classList.remove('visible');
        }
    });
    observer.observe(appRoot, { childList: true, subtree: true });

    // Güvenlik: max 6 sn sonra her durumda kapat
    document.addEventListener('click', function() {
        setTimeout(function() {
            overlay.classList.remove('visible');
        }, 6000);
    }, true);
})();
</script>
""", unsafe_allow_html=True)


# ─── Oturum Kontrolü ─────────────────────────────────────────────────────────
def _check_session() -> bool:
    if not st.session_state.get("authenticated"):
        return False
    return auth_service.check_and_refresh_session()


# ─── Sidebar ─────────────────────────────────────────────────────────────────
def _render_sidebar(user: dict) -> str:
    with st.sidebar:
        # Logo / Başlık
        st.markdown("""
        <div style="padding: 8px 0 20px 0; border-bottom: 1px solid #334155; margin-bottom: 20px;">
            <div style="font-size: 1.5rem; font-weight: 700; color: #F8FAFC; letter-spacing: -0.5px;">
                💊 Borç Takip
            </div>
            <div style="font-size: 0.75rem; color: #64748B; margin-top: 2px;">
                Eczaneler Arası Borç Sistemi
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Kullanıcı bilgisi
        kullanici_adi = user.get("Kullanıcı Adı", "")
        rol = str(user.get("Rol", "")).upper()
        cari_id = int(user.get("Cari ID", 0))

        try:
            from services.cari_service import get_cari_by_id
            cari = get_cari_by_id(cari_id)
            cari_adi = cari.get("Cari Adı", "") if cari else ""
        except Exception:
            cari_adi = ""

        rol_badge = "🔴 Admin" if rol == ROL_ADMIN else "🟢 Kullanıcı"
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.06); border-radius: 10px; padding: 12px 14px; margin-bottom: 20px;">
            <div style="font-weight: 600; font-size: 0.95rem; color: #F1F5F9;">{kullanici_adi}</div>
            <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 2px;">{cari_adi}</div>
            <div style="font-size: 0.75rem; color: #64748B; margin-top: 6px;">{rol_badge}</div>
        </div>
        """, unsafe_allow_html=True)

        # Menü
        st.markdown('<div style="font-size:0.7rem; color:#475569; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">MENÜ</div>', unsafe_allow_html=True)

        if rol == ROL_ADMIN:
            sayfalar = ["📊 Dashboard", "💊 Borç Verme", "🏥 Cari Yönetimi", "📋 İlaç Yönetimi", "👤 Profilim"]
        else:
            sayfalar = ["📊 Dashboard", "💊 Borç Verme", "📋 İlaç Yönetimi", "👤 Profilim"]

        secili = st.radio("", sayfalar, label_visibility="collapsed")

        st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)
        if st.button("🚪 Çıkış Yap", use_container_width=True, type="secondary"):
            auth_service.destroy_session()
            st.rerun()

    return secili


# ─── Ana Uygulama ─────────────────────────────────────────────────────────────
def main() -> None:
    if not _check_session():
        login.render()
        return

    user = auth_service.get_current_user()
    if not user:
        login.render()
        return

    secili = _render_sidebar(user)
    rol = str(user.get("Rol", "")).upper()

    if "Cari Yönetimi" in secili and rol != ROL_ADMIN:
        st.error("Bu sayfaya erişim yetkiniz yok.")
        return

    if "Dashboard" in secili:
        dashboard.render(user)
    elif "Borç Verme" in secili:
        borc_verme.render(user)
    elif "Cari Yönetimi" in secili:
        cari_yonetimi.render(user)
    elif "İlaç Yönetimi" in secili:
        ilac_yonetimi.render(user)
    elif "Profilim" in secili:
        profilim.render(user)


main()
