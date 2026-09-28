"""
Cari Yönetimi ekranı — Yalnızca Admin.

İşlevler:
- Tüm carileri ve bağlı kullanıcıları listele
- Yeni cari + kullanıcı oluştur
- Cari adını değiştir
- Cari aktif/pasif yap
- Kullanıcı adını değiştir
- Kullanıcıyı başka cariye taşı
"""

import logging
import secrets
import string
from typing import Dict, List

import streamlit as st

from services import cari_service, user_service
from services.auth_service import get_current_cari_id, is_admin
from config import DURUM_AKTIF, DURUM_PASIF, ROL_ADMIN

logger = logging.getLogger(__name__)


def _assert_admin() -> bool:
    if not is_admin():
        st.error("Bu sayfaya erişim yetkiniz yok.")
        return False
    return True


def _generate_temp_password(length: int = 12) -> str:
    """Rastgele geçici şifre üretir."""
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(length))


def render(user: Dict) -> None:
    if not _assert_admin():
        return

    st.markdown("## 🏥 Cari Yönetimi")
    st.markdown("---")

    tab1, tab2 = st.tabs(["📋 Cari Listesi", "➕ Yeni Cari Oluştur"])

    with tab1:
        _render_cari_listesi(user)

    with tab2:
        _render_yeni_cari()


# ---------------------------------------------------------------------------
# Cari Listesi
# ---------------------------------------------------------------------------


def _render_cari_listesi(admin_user: Dict) -> None:
    admin_cari_id = get_current_cari_id()

    try:
        cariler = cari_service.get_all_cariler()
        users = user_service.get_all_users()
    except Exception as e:
        st.error(f"Veriler yüklenemedi: {e}")
        return

    # Cari → kullanıcı eşlemesi
    cari_user_map: Dict[int, Dict] = {}
    for u in users:
        cid = int(u.get("Cari ID", 0))
        cari_user_map[cid] = u

    # Tüm cari listesi
    cariler_sorted = sorted(cariler, key=lambda c: str(c.get("Cari Adı", "")).lower())

    for cari in cariler_sorted:
        cari_id = int(cari.get("Cari ID", 0))
        cari_adi = str(cari.get("Cari Adı", ""))
        durum = str(cari.get("Durum", ""))
        bagli_user = cari_user_map.get(cari_id)

        with st.expander(
            f"{'🟢' if durum == DURUM_AKTIF else '🔴'} {cari_adi} "
            f"({'Aktif' if durum == DURUM_AKTIF else 'Pasif'})"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Cari ID:** {cari_id}")
                st.markdown(f"**Durum:** {durum}")
                if bagli_user:
                    st.markdown(f"**Bağlı Kullanıcı:** {bagli_user.get('Kullanıcı Adı', '?')}")
                    st.markdown(f"**Rol:** {bagli_user.get('Rol', '?')}")
                else:
                    st.markdown("**Bağlı Kullanıcı:** _(yok)_")

            with col2:
                # Cari adını değiştir
                with st.form(f"cari_ad_{cari_id}"):
                    yeni_ad = st.text_input("Cari Adı", value=cari_adi, key=f"cari_ad_inp_{cari_id}")
                    if st.form_submit_button("✏️ Adı Güncelle"):
                        if yeni_ad.strip() == cari_adi:
                            st.info("Ad değiştirilmedi.")
                        else:
                            try:
                                cari_service.update_cari_adi(cari_id, yeni_ad)
                                st.success("Cari adı güncellendi.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

            # Aktif/Pasif butonu
            if durum == DURUM_AKTIF:
                if cari_id == admin_cari_id:
                    st.info("Kendi bağlı olduğunuz cariyi pasif yapamazsınız.")
                else:
                    if st.button(f"🔴 Pasif Yap", key=f"pasif_{cari_id}"):
                        try:
                            cari_service.set_cari_durum(cari_id, DURUM_PASIF, admin_cari_id)
                            st.success(f"'{cari_adi}' pasif yapıldı.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            else:
                if st.button(f"🟢 Aktif Yap", key=f"aktif_{cari_id}"):
                    try:
                        cari_service.set_cari_durum(cari_id, DURUM_AKTIF, admin_cari_id)
                        st.success(f"'{cari_adi}' aktif yapıldı.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

            # Kullanıcı işlemleri
            if bagli_user:
                st.markdown("**Kullanıcı İşlemleri:**")
                user_id = int(bagli_user.get("User ID", 0))

                with st.form(f"user_ad_{user_id}"):
                    yeni_kullanici_adi = st.text_input(
                        "Kullanıcı Adı",
                        value=str(bagli_user.get("Kullanıcı Adı", "")),
                        key=f"user_ad_inp_{user_id}",
                    )
                    if st.form_submit_button("✏️ Kullanıcı Adını Güncelle"):
                        try:
                            user_service.update_kullanici_adi(user_id, yeni_kullanici_adi)
                            st.success("Kullanıcı adı güncellendi.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

                # Kullanıcıyı başka cariye taşı
                diger_cariler = [
                    c for c in cariler if int(c["Cari ID"]) != cari_id
                ]
                if diger_cariler:
                    with st.form(f"user_tas_{user_id}"):
                        hedef_secenek = {
                            int(c["Cari ID"]): str(c["Cari Adı"]) for c in diger_cariler
                        }
                        hedef_ids = list(hedef_secenek.keys())
                        hedef_adlar = [hedef_secenek[i] for i in hedef_ids]
                        hedef_idx = st.selectbox(
                            "Hedef Cari",
                            options=range(len(hedef_ids)),
                            format_func=lambda x: hedef_adlar[x],
                            key=f"hedef_cari_{user_id}",
                        )
                        if st.form_submit_button("🔀 Cariye Taşı"):
                            hedef_cari_id = hedef_ids[hedef_idx]
                            try:
                                user_service.move_user_to_cari(user_id, hedef_cari_id)
                                st.success(
                                    f"Kullanıcı '{bagli_user.get('Kullanıcı Adı')}' "
                                    f"'{hedef_secenek[hedef_cari_id]}' carisine taşındı."
                                )
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))


# ---------------------------------------------------------------------------
# Yeni Cari Oluştur
# ---------------------------------------------------------------------------


def _render_yeni_cari() -> None:
    st.markdown("### Yeni Cari ve Kullanıcı Oluştur")
    st.markdown(
        "_Yeni bir cari ile birlikte bir kullanıcı hesabı oluşturulacaktır. "
        "Oluşturma sonrası ilk şifre yalnızca bir kez gösterilir._"
    )

    with st.form("yeni_cari_form"):
        cari_adi = st.text_input("Cari Adı *", placeholder="Ahmet Eczanesi")
        kullanici_adi = st.text_input("Kullanıcı Adı *", placeholder="ahmet")
        ilk_sifre = st.text_input(
            "İlk Şifre *",
            type="password",
            placeholder="En az 6 karakter",
            help="Kullanıcıya güvenli kanaldan iletiniz.",
        )
        ilk_sifre_tekrar = st.text_input("İlk Şifre (Tekrar) *", type="password")

        submitted = st.form_submit_button("➕ Oluştur", type="primary")

    if submitted:
        hatalar = []
        if not cari_adi.strip():
            hatalar.append("Cari adı boş olamaz.")
        if not kullanici_adi.strip():
            hatalar.append("Kullanıcı adı boş olamaz.")
        if not ilk_sifre:
            hatalar.append("Şifre boş olamaz.")
        if ilk_sifre != ilk_sifre_tekrar:
            hatalar.append("Şifreler eşleşmiyor.")
        if len(ilk_sifre) < 6:
            hatalar.append("Şifre en az 6 karakter olmalıdır.")

        if hatalar:
            for h in hatalar:
                st.error(h)
            return

        try:
            # Önce cari oluştur
            yeni_cari = cari_service.create_cari(cari_adi.strip())
            # Ardından kullanıcı oluştur
            user_service.create_user(
                kullanici_adi.strip(),
                ilk_sifre,
                int(yeni_cari["Cari ID"]),
            )
            st.success(
                f"✅ Cari **'{cari_adi}'** ve kullanıcı **'{kullanici_adi}'** başarıyla oluşturuldu.\n\n"
                f"🔑 İlk şifre kullanıcıya güvenli kanaldan iletilmelidir."
            )
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            logger.error("Cari oluşturma hatası: %s", e)
            st.error("Oluşturma sırasında bir hata oluştu.")
