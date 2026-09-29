"""Giriş ekranı — modern kart tasarımı."""

import streamlit as st
from services import auth_service


def render() -> None:
    logout_reason = st.session_state.pop("logout_reason", None)

    # Ortalanmış kart
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("""
        <div style="
            text-align: center;
            padding: 48px 40px 32px 40px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            border: 1px solid #E2E8F0;
            margin-top: 60px;
        ">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">💊</div>
            <div style="font-size: 1.5rem; font-weight: 700; color: #1E293B; margin-bottom: 4px;">
                Eczane Borç Takip
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 28px;">
                Eczaneler Arası Borç Yönetim Sistemi
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

        if logout_reason:
            st.warning(logout_reason)

        with st.form("login_form", clear_on_submit=False):
            kullanici_adi = st.text_input(
                "Kullanıcı Adı",
                placeholder="Kullanıcı adınızı girin",
            )
            sifre = st.text_input(
                "Şifre",
                type="password",
                placeholder="Şifrenizi girin",
            )
            submitted = st.form_submit_button(
                "Giriş Yap",
                use_container_width=True,
                type="primary",
            )

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
            except Exception:
                st.error("Giriş sırasında bir hata oluştu. Lütfen tekrar deneyiniz.")

        st.markdown("""
        <div style="text-align: center; margin-top: 20px; font-size: 0.75rem; color: #94A3B8;">
            Sorun yaşıyorsanız sistem yöneticinizle iletişime geçin.
        </div>
        """, unsafe_allow_html=True)
