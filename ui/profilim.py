"""
Profilim ekranı.

Her kullanıcı erişebilir. İşlevler:
- Kendi kullanıcı adını değiştirme
- Kendi şifresini değiştirme (mevcut şifre doğrulaması gerekli)
- Kendi cari adını değiştirme
"""

import logging
from typing import Dict

import streamlit as st

from services import user_service, cari_service
from services.auth_service import (
    get_current_user_id,
    get_current_cari_id,
    refresh_user_data_in_session,
)

logger = logging.getLogger(__name__)


def render(user: Dict) -> None:
    user_id = get_current_user_id()
    cari_id = get_current_cari_id()

    kullanici_adi = str(user.get("Kullanıcı Adı", ""))
    rol = str(user.get("Rol", ""))

    # Cari bilgisini al
    try:
        cari = cari_service.get_cari_by_id(cari_id)
        cari_adi = str(cari.get("Cari Adı", "")) if cari else "?"
    except Exception:
        cari_adi = "?"

    st.markdown("## 👤 Profilim")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Kullanıcı Adı:** {kullanici_adi}")
        st.markdown(f"**Rol:** {rol}")
    with col2:
        st.markdown(f"**Cari:** {cari_adi}")
        st.markdown(f"**Cari ID:** {cari_id} _(değiştirilemez)_")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["✏️ Kullanıcı Adı", "🔒 Şifre", "🏥 Cari Adı"])

    # ---- Kullanıcı Adı Değiştir ----
    with tab1:
        st.markdown("### Kullanıcı Adını Değiştir")
        with st.form("kullanici_adi_form"):
            yeni_adi = st.text_input("Yeni Kullanıcı Adı", value=kullanici_adi)
            submitted = st.form_submit_button("💾 Kaydet", type="primary")

        if submitted:
            if yeni_adi.strip() == kullanici_adi:
                st.info("Kullanıcı adı değiştirilmedi.")
            else:
                try:
                    user_service.update_kullanici_adi(user_id, yeni_adi)
                    refresh_user_data_in_session()
                    st.success("✅ Kullanıcı adı güncellendi.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    # ---- Şifre Değiştir ----
    with tab2:
        st.markdown("### Şifre Değiştir")
        with st.form("sifre_form"):
            mevcut = st.text_input("Mevcut Şifre", type="password")
            yeni = st.text_input("Yeni Şifre", type="password")
            yeni_tekrar = st.text_input("Yeni Şifre (Tekrar)", type="password")
            submitted2 = st.form_submit_button("🔒 Şifreyi Değiştir", type="primary")

        if submitted2:
            if not mevcut:
                st.error("Mevcut şifre boş olamaz.")
            elif not yeni:
                st.error("Yeni şifre boş olamaz.")
            elif yeni != yeni_tekrar:
                st.error("Yeni şifreler eşleşmiyor.")
            else:
                try:
                    user_service.change_password(user_id, mevcut, yeni, yeni_tekrar)
                    st.success("✅ Şifre başarıyla değiştirildi.")
                except ValueError as e:
                    st.error(str(e))

    # ---- Cari Adı Değiştir ----
    with tab3:
        st.markdown("### Cari Adını Değiştir")
        st.info("Bu değişiklik yalnızca cari adını günceller; geçmiş işlemler de yeni adı gösterir.")
        with st.form("cari_adi_form"):
            yeni_cari_adi = st.text_input("Yeni Cari Adı", value=cari_adi)
            submitted3 = st.form_submit_button("💾 Kaydet", type="primary")

        if submitted3:
            if yeni_cari_adi.strip() == cari_adi:
                st.info("Cari adı değiştirilmedi.")
            else:
                try:
                    cari_service.update_cari_adi(cari_id, yeni_cari_adi)
                    st.success("✅ Cari adı güncellendi.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
