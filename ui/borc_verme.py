"""
Borç Verme ekranı.

Özellikler:
- Tek ekranda tüm form
- Borç veren cari otomatik (giriş yapan kullanıcının carisi)
- Aktif ilaç ve cari seçimi
- Çoklu borç alan cari
- Eşit Dağıt butonu
- Onay popup'ı (session state ile)
- Save sırasında tüm iş kuralı kontrolleri
- Idempotency: Save işlemi sırasında buton devre dışı
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import streamlit as st

from services import borc_service
from services.cari_service import get_all_cariler, get_aktif_cariler, get_cari_by_id
from services.ilac_service import get_aktif_ilaclar
from services.auth_service import get_current_cari_id, get_current_user_id
from utils.calculations import hesapla_kalem_tutari, hesapla_belge_toplami, to_decimal
from utils.formatting import (
    format_para,
    format_bakiye,
    format_birim_fiyat,
    format_miktar,
    format_tarih,
)
from utils.validators import validate_miktar, validate_birim_fiyat, validate_esit_dagit
from config import DURUM_AKTIF

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _init_form_state() -> None:
    if "bv_dagitim" not in st.session_state:
        st.session_state["bv_dagitim"] = []  # [{"cari_id": int, "miktar": int}]
    if "bv_confirm_mode" not in st.session_state:
        st.session_state["bv_confirm_mode"] = False
    if "bv_saving" not in st.session_state:
        st.session_state["bv_saving"] = False


def _reset_form() -> None:
    keys = [
        "bv_ilac_id", "bv_lot_tarihi", "bv_birim_fiyat", "bv_toplam_miktar",
        "bv_dagitim", "bv_confirm_mode", "bv_saving",
        "bv_secili_karsi_cari_ids",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _parse_fiyat(fiyat_str: str) -> Optional[str]:
    """Fiyat girişini normalize eder: virgülü noktaya çevirir."""
    try:
        fiyat_str = str(fiyat_str).strip().replace(",", ".")
        d = Decimal(fiyat_str)
        # 4 ondalık basamak olarak sakla
        return str(d.quantize(Decimal("0.0001")))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# Ana Render
# ---------------------------------------------------------------------------


def render(user: Dict) -> None:
    _init_form_state()

    current_user_id = get_current_user_id()
    current_cari_id = get_current_cari_id()

    # Borç veren carinin adını göster
    cari_bilgisi = get_cari_by_id(current_cari_id)
    if cari_bilgisi is None:
        st.error("Bağlı olduğunuz cari bulunamadı.")
        return
    veren_adi = str(cari_bilgisi.get("Cari Adı", "?"))

    st.markdown("## 💊 Borç Verme")
    st.markdown("---")

    # Onay modu mu?
    if st.session_state.get("bv_confirm_mode"):
        _render_confirmation(current_user_id, current_cari_id, veren_adi)
        return

    # Aktif ilaç ve cariler
    aktif_ilaclar = get_aktif_ilaclar()
    aktif_cariler = [c for c in get_aktif_cariler() if int(c["Cari ID"]) != current_cari_id]

    if not aktif_ilaclar:
        st.warning("Sistemde aktif ilaç bulunmuyor. Lütfen önce ilaç ekleyiniz.")
        return
    if not aktif_cariler:
        st.warning("Sistemde başka aktif cari bulunmuyor.")
        return

    # ---- FORM ----
    with st.form("borc_form", clear_on_submit=False):
        st.markdown(f"**Borcu Veren:** {veren_adi}")
        st.markdown("---")

        # İlaç seçimi
        ilac_secenekleri = {int(i["İlaç ID"]): str(i["İlaç Adı"]) for i in aktif_ilaclar}
        ilac_id_list = list(ilac_secenekleri.keys())
        ilac_adi_list = [ilac_secenekleri[i] for i in ilac_id_list]

        secili_ilac_idx = st.selectbox(
            "İlaç *",
            options=range(len(ilac_id_list)),
            format_func=lambda x: ilac_adi_list[x],
            key="bv_ilac_select_idx",
        )
        secili_ilac_id = ilac_id_list[secili_ilac_idx]

        col1, col2 = st.columns(2)
        with col1:
            lot_tarihi = st.date_input(
                "Lot / Alış Tarihi *",
                key="bv_lot_tarihi_input",
                help="Geçmiş, bugün veya gelecek tarih girilebilir.",
            )
        with col2:
            birim_fiyat_str = st.text_input(
                "Birim Alış Fiyatı (TL) *",
                placeholder="Örn: 10.1234",
                key="bv_birim_fiyat_input",
                help="4 ondalık basamağa kadar girebilirsiniz.",
            )

        toplam_miktar_str = st.text_input(
            "Toplam Miktar *",
            placeholder="Örn: 750",
            key="bv_toplam_miktar_input",
            help="Yalnızca tam sayı giriniz.",
        )

        st.markdown("---")
        st.markdown("**Borç Alan Cariler**")

        # Çoklu cari seçimi
        cari_secenekleri = {int(c["Cari ID"]): str(c["Cari Adı"]) for c in aktif_cariler}
        cari_id_list = list(cari_secenekleri.keys())
        cari_adi_list = [cari_secenekleri[i] for i in cari_id_list]

        secili_cari_idxs = st.multiselect(
            "Borç Alan Cari(ler) Seçin",
            options=range(len(cari_id_list)),
            format_func=lambda x: cari_adi_list[x],
            key="bv_karsi_cari_idxs",
        )
        secili_cari_ids = [cari_id_list[i] for i in secili_cari_idxs]

        # Dağıtım miktarları (seçili cariler için)
        dagitim_miktarlar = {}
        if secili_cari_ids:
            st.markdown("**Kalem Miktarları:**")
            for cid in secili_cari_ids:
                miktar_key = f"bv_miktar_{cid}"
                dagitim_miktarlar[cid] = st.text_input(
                    f"{cari_secenekleri[cid]}",
                    key=miktar_key,
                    placeholder="0",
                )

        st.markdown("---")
        col_esit, col_hesapla, col_kaydet = st.columns([2, 2, 3])

        with col_esit:
            esit_dagit = st.form_submit_button("⚖️ Eşit Dağıt")
        with col_kaydet:
            kaydet = st.form_submit_button("💾 Kaydet", type="primary", disabled=st.session_state.get("bv_saving", False))

    # ---- HESAPLAMA GÖSTERİMİ ----
    if secili_cari_ids and birim_fiyat_str:
        fiyat_norm = _parse_fiyat(birim_fiyat_str)
        if fiyat_norm:
            st.markdown("**Hesaplanan Tutarlar:**")
            toplam_dagitim = 0
            for cid in secili_cari_ids:
                m_str = dagitim_miktarlar.get(cid, "0") or "0"
                ok, _ = validate_miktar(m_str)
                if ok:
                    m = int(m_str)
                    tutar = hesapla_kalem_tutari(m, to_decimal(fiyat_norm))
                    toplam_dagitim += m
                    st.markdown(f"&nbsp;&nbsp;• **{cari_secenekleri[cid]}:** {format_miktar(m)} × {format_birim_fiyat(fiyat_norm)} = {format_para(tutar)}")

            # Toplam
            toplam_ok, _ = validate_miktar(toplam_miktar_str or "0")
            if toplam_ok:
                belge_toplami = hesapla_belge_toplami(int(toplam_miktar_str), to_decimal(fiyat_norm))
                st.markdown(f"**Belge Toplamı:** {format_para(belge_toplami)}")
                if toplam_dagitim != int(toplam_miktar_str or 0):
                    st.warning(f"⚠️ Dağıtım toplamı ({toplam_dagitim}) ≠ Toplam miktar ({toplam_miktar_str})")

    # ---- EŞİT DAĞIT ----
    if esit_dagit:
        ok_m, msg_m = validate_miktar(toplam_miktar_str or "")
        if not ok_m:
            st.error(f"Toplam miktar: {msg_m}")
        else:
            ok_e, msg_e = validate_esit_dagit(int(toplam_miktar_str), len(secili_cari_ids))
            if not ok_e:
                st.error(msg_e)
            else:
                esit = int(toplam_miktar_str) // len(secili_cari_ids)
                for cid in secili_cari_ids:
                    st.session_state[f"bv_miktar_{cid}"] = str(esit)
                st.rerun()

    # ---- KAYDET ----
    if kaydet:
        _handle_kaydet(
            current_cari_id=current_cari_id,
            current_user_id=current_user_id,
            secili_ilac_id=secili_ilac_id,
            lot_tarihi=lot_tarihi,
            birim_fiyat_str=birim_fiyat_str,
            toplam_miktar_str=toplam_miktar_str,
            secili_cari_ids=secili_cari_ids,
            dagitim_miktarlar=dagitim_miktarlar,
            cari_secenekleri=cari_secenekleri,
            ilac_secenekleri=ilac_secenekleri,
            veren_adi=veren_adi,
        )


def _handle_kaydet(
    current_cari_id, current_user_id, secili_ilac_id, lot_tarihi,
    birim_fiyat_str, toplam_miktar_str, secili_cari_ids, dagitim_miktarlar,
    cari_secenekleri, ilac_secenekleri, veren_adi,
):
    """Kaydet butonuna basıldığında çalışır: validasyon + onay moduna geç."""
    hatalar = []

    # Birim fiyat
    fiyat_norm = _parse_fiyat(birim_fiyat_str or "")
    if fiyat_norm is None:
        hatalar.append("Geçerli bir birim alış fiyatı giriniz.")
    else:
        ok, msg = validate_birim_fiyat(fiyat_norm)
        if not ok:
            hatalar.append(msg)

    # Toplam miktar
    ok_m, msg_m = validate_miktar(toplam_miktar_str or "")
    if not ok_m:
        hatalar.append(f"Toplam miktar: {msg_m}")

    # En az bir borç alan
    if not secili_cari_ids:
        hatalar.append("En az bir borç alan cari seçmelisiniz.")

    # Kalem miktarları ve toplam kontrolü
    dagitim = []
    toplam_dagitim = 0
    if secili_cari_ids:
        cari_set = set()
        for cid in secili_cari_ids:
            if cid == current_cari_id:
                hatalar.append("Borç veren ve borç alan aynı eczane olamaz.")
                break
            if cid in cari_set:
                hatalar.append("Aynı cari aynı belgede birden fazla kez eklenemez.")
                break
            cari_set.add(cid)
            m_str = dagitim_miktarlar.get(cid, "") or ""
            ok_ki, msg_ki = validate_miktar(m_str)
            if not ok_ki:
                hatalar.append(f"{cari_secenekleri.get(cid, cid)}: {msg_ki}")
            else:
                m = int(m_str)
                dagitim.append({"cari_id": cid, "miktar": m})
                toplam_dagitim += m

    if ok_m and dagitim and toplam_dagitim != int(toplam_miktar_str):
        hatalar.append(
            f"Borç alan carilerin toplam miktarı ({toplam_dagitim}), "
            f"toplam miktara ({toplam_miktar_str}) eşit olmalıdır."
        )

    if hatalar:
        for h in hatalar:
            st.error(h)
        return

    # Onay moduna geç
    st.session_state["bv_confirm_data"] = {
        "ilac_id": secili_ilac_id,
        "ilac_adi": ilac_secenekleri.get(secili_ilac_id, "?"),
        "lot_tarihi": str(lot_tarihi),
        "birim_fiyat": fiyat_norm,
        "toplam_miktar": int(toplam_miktar_str),
        "dagitim": dagitim,
        "cari_secenekleri": cari_secenekleri,
        "veren_adi": veren_adi,
    }
    st.session_state["bv_confirm_mode"] = True
    st.rerun()


def _render_confirmation(current_user_id: int, current_cari_id: int, veren_adi: str) -> None:
    """Onay ekranı."""
    data = st.session_state.get("bv_confirm_data", {})
    if not data:
        st.session_state["bv_confirm_mode"] = False
        st.rerun()
        return

    ilac_adi = data["ilac_adi"]
    lot = format_tarih(data["lot_tarihi"])
    birim = data["birim_fiyat"]
    toplam_miktar = data["toplam_miktar"]
    dagitim = data["dagitim"]
    cari_secenekleri = data["cari_secenekleri"]

    from utils.calculations import hesapla_belge_toplami
    belge_toplami = hesapla_belge_toplami(toplam_miktar, to_decimal(birim))

    st.markdown("## ✅ Kayıt Onayı")
    st.markdown("Lütfen bilgileri kontrol edin ve onaylayın.")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Borç Veren:** {veren_adi}")
        st.markdown(f"**İlaç:** {ilac_adi}")
        st.markdown(f"**Lot / Alış Tarihi:** {lot}")
    with col2:
        st.markdown(f"**Birim Alış Fiyatı:** {format_birim_fiyat(birim)}")
        st.markdown(f"**Toplam Miktar:** {format_miktar(toplam_miktar)}")
        st.markdown(f"**Toplam Tutar:** {format_para(belge_toplami)}")

    st.markdown("**Dağıtım:**")
    for satir in dagitim:
        cid = satir["cari_id"]
        m = satir["miktar"]
        tutar = hesapla_kalem_tutari(m, to_decimal(birim))
        st.markdown(
            f"&nbsp;&nbsp;• **{cari_secenekleri.get(cid, cid)}** — "
            f"{format_miktar(m)} adet — {format_para(tutar)}"
        )

    st.markdown("---")
    col_onayla, col_vazgec = st.columns(2)

    with col_onayla:
        if st.button("✅ Onayla ve Kaydet", type="primary", key="confirm_onayla",
                     disabled=st.session_state.get("bv_saving", False)):
            _execute_kaydet(current_user_id, current_cari_id, data)

    with col_vazgec:
        if st.button("❌ Vazgeç", key="confirm_vazgec"):
            st.session_state["bv_confirm_mode"] = False
            st.rerun()


def _execute_kaydet(current_user_id: int, current_cari_id: int, data: Dict) -> None:
    """Gerçek kayıt işlemi."""
    st.session_state["bv_saving"] = True
    try:
        belge_no = borc_service.create_borc_belgesi(
            borc_veren_cari_id=current_cari_id,
            ilac_id=data["ilac_id"],
            lot_tarihi=data["lot_tarihi"],
            birim_alis_fiyati=data["birim_fiyat"],
            toplam_miktar=data["toplam_miktar"],
            dagitim=data["dagitim"],
            olusturan_user_id=current_user_id,
        )
        st.success(f"✅ Belge başarıyla oluşturuldu: **{belge_no}**")
        _reset_form()
        st.rerun()
    except ValueError as e:
        st.error(str(e))
        st.session_state["bv_saving"] = False
    except Exception as e:
        logger.error("Borç belgesi kayıt hatası: %s", e)
        st.error("Kayıt sırasında beklenmedik bir hata oluştu. Lütfen tekrar deneyiniz.")
        st.session_state["bv_saving"] = False
