"""
İlaç Yönetimi ekranı.

İşlevler:
- Tüm ilaçları listele (aktif + pasif)
- Yeni ilaç ekle (tüm kullanıcılar)
- İlaç adını değiştir (tüm kullanıcılar)
- İlaç aktif/pasif yap (yalnızca Admin)
"""

import logging
from typing import Dict

import streamlit as st

from services import ilac_service
from services.auth_service import is_admin
from config import DURUM_AKTIF, DURUM_PASIF

logger = logging.getLogger(__name__)


def render(user: Dict) -> None:
    admin = is_admin()
    st.markdown("## 💊 İlaç Yönetimi")
    st.markdown("---")

    tab1, tab2 = st.tabs(["📋 İlaç Listesi", "➕ Yeni İlaç Ekle"])

    with tab1:
        _render_ilac_listesi(admin)

    with tab2:
        _render_yeni_ilac()


# ---------------------------------------------------------------------------
# İlaç Listesi
# ---------------------------------------------------------------------------


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

        icon = "🟢" if durum == DURUM_AKTIF else "🔴"
        with st.expander(f"{icon} {ilac_adi} ({'Aktif' if durum == DURUM_AKTIF else 'Pasif'})"):
            st.markdown(f"**İlaç ID:** {ilac_id}")
            st.markdown(f"**Durum:** {durum}")

            # Ad değiştirme (tüm kullanıcılar)
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
        submitted = st.form_submit_button("➕ Ekle", type="primary")

    if submitted:
        if not ilac_adi.strip():
            st.error("İlaç adı boş olamaz.")
            return
        try:
            yeni = ilac_service.create_ilac(ilac_adi.strip())
            st.success(f"✅ **'{ilac_adi}'** başarıyla eklendi.")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            logger.error("İlaç ekleme hatası: %s", e)
            st.error("İlaç eklenirken bir hata oluştu.")
