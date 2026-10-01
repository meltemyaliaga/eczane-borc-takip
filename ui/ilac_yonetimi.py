"""
İlaç Yönetimi ekranı — KDV oranı desteğiyle.
"""

import logging
from typing import Dict

import streamlit as st

from services import ilac_service
from services.auth_service import is_admin
from config import DURUM_AKTIF, DURUM_PASIF, KDV_ORANLARI

logger = logging.getLogger(__name__)

_KDV_SECENEKLER = {
    "0": "%0 — KDV Muaf",
    "1": "%1",
    "10": "%10",
    "20": "%20",
}


def render(user: Dict) -> None:
    admin = is_admin()
    st.markdown("## 📋 İlaç Yönetimi")
    st.markdown("---")

    tab1, tab2 = st.tabs(["📋 İlaç Listesi", "➕ Yeni İlaç Ekle"])

    with tab1:
        _render_ilac_listesi(admin)

    with tab2:
        _render_yeni_ilac()


# ---------------------------------------------------------------------------
# İlaç Listesi
# ---------------------------------------------------------------------------


def _kdv_label(kdv: str) -> str:
    return _KDV_SECENEKLER.get(str(kdv), f"%{kdv}")


def _render_ilac_listesi(admin: bool) -> None:
    try:
        ilaclar = ilac_service.get_all_ilaclar()
    except Exception as e:
        st.error(f"İlaçlar yüklenemedi: {e}")
        return

    ilaclar_sorted = sorted(ilaclar, key=lambda i: str(i.get("İlaç Adı", "")).lower())

    aktif_list = [i for i in ilaclar_sorted if str(i.get("Durum", "")) == DURUM_AKTIF]
    pasif_list = [i for i in ilaclar_sorted if str(i.get("Durum", "")) != DURUM_AKTIF]

    st.markdown(f"**Aktif:** {len(aktif_list)} | **Pasif:** {len(pasif_list)}")
    st.markdown("---")

    for ilac in ilaclar_sorted:
        ilac_id = int(ilac.get("İlaç ID", 0))
        ilac_adi = str(ilac.get("İlaç Adı", ""))
        durum = str(ilac.get("Durum", ""))
        kdv = str(ilac.get("KDV Oranı", "0") or "0")

        icon = "🟢" if durum == DURUM_AKTIF else "🔴"
        kdv_badge = f'<span style="background:#EFF6FF;color:#1D4ED8;padding:2px 8px;border-radius:10px;font-size:0.8rem;font-weight:600">{_kdv_label(kdv)}</span>'

        with st.expander(f"{icon} {ilac_adi}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**İlaç ID:** {ilac_id} | **Durum:** {durum}")
            with col2:
                st.markdown(f"**KDV:** {kdv_badge}", unsafe_allow_html=True)

            # Ad değiştirme
            with st.form(f"ilac_ad_{ilac_id}"):
                yeni_ad = st.text_input("İlaç Adı", value=ilac_adi, key=f"ilac_ad_inp_{ilac_id}")
                if st.form_submit_button("✏️ Adı Güncelle"):
                    if yeni_ad.strip() == ilac_adi:
                        st.info("Ad değiştirilmedi.")
                    else:
                        try:
                            ilac_service.update_ilac_adi(ilac_id, yeni_ad)
                            st.success("İlaç adı güncellendi.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

            # KDV değiştirme (tüm kullanıcılar)
            kdv_idx = KDV_ORANLARI.index(kdv) if kdv in KDV_ORANLARI else 0
            with st.form(f"ilac_kdv_{ilac_id}"):
                yeni_kdv = st.selectbox(
                    "KDV Oranı",
                    options=KDV_ORANLARI,
                    format_func=_kdv_label,
                    index=kdv_idx,
                    key=f"ilac_kdv_sel_{ilac_id}",
                )
                if st.form_submit_button("💾 KDV Güncelle"):
                    if str(yeni_kdv) == kdv:
                        st.info("KDV oranı değiştirilmedi.")
                    else:
                        try:
                            ilac_service.update_ilac_kdv(ilac_id, str(yeni_kdv))
                            st.success(f"KDV oranı güncellendi → {_kdv_label(str(yeni_kdv))}")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

            # Aktif/Pasif — yalnızca Admin
            if admin:
                if durum == DURUM_AKTIF:
                    if st.button("🔴 Pasif Yap", key=f"ilac_pasif_{ilac_id}"):
                        try:
                            ilac_service.set_ilac_durum(ilac_id, DURUM_PASIF)
                            st.success(f"'{ilac_adi}' pasif yapıldı.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                else:
                    if st.button("🟢 Aktif Yap", key=f"ilac_aktif_{ilac_id}"):
                        try:
                            ilac_service.set_ilac_durum(ilac_id, DURUM_AKTIF)
                            st.success(f"'{ilac_adi}' aktif yapıldı.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            else:
                if durum != DURUM_AKTIF:
                    st.info("ℹ️ Bu ilacı yalnızca Admin aktif yapabilir.")


# ---------------------------------------------------------------------------
# Yeni İlaç Ekle
# ---------------------------------------------------------------------------


def _render_yeni_ilac() -> None:
    st.markdown("### Yeni İlaç Ekle")
    st.info(
        "Yeni eklenen ilaç otomatik olarak Aktif olur. "
        "Benzersizlik kontrolü pasif ilaçlar dahil tüm ilaçlar üzerinde yapılır."
    )

    with st.form("yeni_ilac_form"):
        ilac_adi = st.text_input("İlaç Adı *", placeholder="Örn: Parol")
        kdv_orani = st.selectbox(
            "KDV Oranı *",
            options=KDV_ORANLARI,
            format_func=_kdv_label,
            index=0,
        )
        submitted = st.form_submit_button("➕ Ekle", type="primary")

    if submitted:
        if not ilac_adi.strip():
            st.error("İlaç adı boş olamaz.")
            return
        try:
            ilac_service.create_ilac(ilac_adi.strip(), str(kdv_orani))
            st.success(f"✅ **'{ilac_adi}'** başarıyla eklendi. KDV: {_kdv_label(str(kdv_orani))}")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            logger.error("İlaç ekleme hatası: %s", e)
            st.error("İlaç eklenirken bir hata oluştu.")
