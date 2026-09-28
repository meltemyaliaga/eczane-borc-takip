"""
Giriş ekranı.
"""

import streamlit as st
from services import auth_service


def render() -> None:
    """Login ekranını gösterir."""
    st.markdown(
        """
        <style>
        .login-box {max-width: 420px; margin: auto; padding-top: 80px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Önceki oturumdan gelen mesaj varsa göster
    logout_reason = st.session_state.pop("logout_reason", None)
    if logout_reason:
        st.warning(logout_reason)

    with st.container():
        st.markdown("## 💊 Eczane Borç Takip Sistemi")
        st.markdown("---")

        with st.form("login_form", clear_on_submit=False):
            kullanici_adi = st.text_input("Kullanıcı Adı", placeholder="kullanıcı adınızı giriniz")
            sifre = st.text_input("Şifre", type="password", placeholder="şifrenizi giriniz")
            submitted = st.form_submit_button("🔐 Giriş Yap", use_container_width=True)

        if submitted:
            if not kullanici_adi.strip() or not sifre:
                st.error("Kullanıcı adı ve şifre boş olamaz.")
                return
            try:
                user_data = auth_service.login(kullanici_adi.strip(), sifre)
                auth_service.create_session(user_data)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error("Giriş sırasında bir hata oluştu. Lütfen tekrar deneyiniz.")
