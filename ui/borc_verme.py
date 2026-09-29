"""
Borç Verme ekranı — sade, sorunsuz form.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

import streamlit as st

from services import borc_service
from services.cari_service import get_aktif_cariler, get_cari_by_id
from services.ilac_service import get_aktif_ilaclar
from services.auth_service import get_current_cari_id, get_current_user_id
from utils.calculations import hesapla_kalem_tutari, hesapla_belge_toplami, to_decimal
from utils.formatting import format_para, format_birim_fiyat, format_miktar, format_tarih
from utils.validators import validate_miktar, validate_birim_fiyat

logger = logging.getLogger(__name__)


def _parse_fiyat(s: str) -> Optional[str]:
    try:
        return str(Decimal(str(s).strip().replace(",", ".")).quantize(Decimal("0.0001")))
    except (InvalidOperation, ValueError):
        return None


def _reset():
    for k in list(st.session_state.keys()):
        if k.startswith("bv_"):
            del st.session_state[k]


def render(user: Dict) -> None:
    user_id = get_current_user_id()
    cari_id = get_current_cari_id()

    cari = get_cari_by_id(cari_id)
    if not cari:
        st.error("Bağlı olduğunuz cari bulunamadı.")
        return
    veren_adi = str(cari.get("Cari Adı", "?"))

    st.markdown("# 💊 Borç Verme")
    st.markdown("---")

    # ── Başarı ekranı ─────────────────────────────────────────────────────────
    if st.session_state.get("bv_success_belge_no"):
        belge_no = st.session_state["bv_success_belge_no"]
        st.markdown(f"""
        <div style="background:#F0FDF4; border:1px solid #86EFAC; border-radius:14px;
                    padding:36px; text-align:center; margin:20px 0;">
            <div style="font-size:2.5rem; margin-bottom:12px;">✅</div>
            <div style="font-size:1.3rem; font-weight:700; color:#166534; margin-bottom:8px;">
                Belge başarıyla kaydedildi!
            </div>
            <div style="font-size:1rem; color:#15803D; font-weight:500;">
                Belge No: <span style="font-family:monospace; background:#DCFCE7;
                padding:4px 12px; border-radius:6px;">{belge_no}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("➕ Yeni Borç Gir", type="primary", key="bv_yeni"):
            del st.session_state["bv_success_belge_no"]
            st.rerun()
        return

    # ── Onay modu ─────────────────────────────────────────────────────────────
    if st.session_state.get("bv_confirm_mode"):
        _render_onay(user_id, cari_id, veren_adi)
        return

    # Veri yükle
    aktif_ilaclar = get_aktif_ilaclar()
    aktif_cariler = [c for c in get_aktif_cariler() if int(c["Cari ID"]) != cari_id]

    if not aktif_ilaclar:
        st.warning("Sistemde aktif ilaç bulunmuyor. Önce ilaç ekleyin.")
        return
    if not aktif_cariler:
        st.warning("Sistemde başka aktif cari bulunmuyor.")
        return

    ilac_map = {int(i["İlaç ID"]): str(i["İlaç Adı"]) for i in aktif_ilaclar}
    ilac_ids = list(ilac_map.keys())
    ilac_adlar = [ilac_map[i] for i in ilac_ids]

    cari_map = {int(c["Cari ID"]): str(c["Cari Adı"]) for c in aktif_cariler}
    cari_ids = list(cari_map.keys())
    cari_adlar = [cari_map[i] for i in cari_ids]

    # Borç veren bilgisi
    st.markdown(f"""
    <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px;
                padding:12px 16px; margin-bottom:20px; font-size:0.95rem; color:#1E40AF;">
        <b>Borç Veren:</b> {veren_adi}
    </div>
    """, unsafe_allow_html=True)

    # ── Form alanları ─────────────────────────────────────────────────────────
    secili_ilac_idx = st.selectbox(
        "İlaç *",
        options=range(len(ilac_ids)),
        format_func=lambda x: ilac_adlar[x],
        key="bv_ilac_idx",
    )
    secili_ilac_id = ilac_ids[secili_ilac_idx]

    col1, col2 = st.columns(2)
    with col1:
        lot_tarihi = st.date_input("Lot / Alış Tarihi *", key="bv_lot")
    with col2:
        birim_fiyat_str = st.text_input(
            "Birim Alış Fiyatı (TL) *",
            placeholder="Örn: 10.1234",
            key="bv_fiyat",
        )

    toplam_miktar_str = st.text_input(
        "Toplam Miktar *",
        placeholder="Tam sayı giriniz (örn: 750)",
        key="bv_toplam",
    )

    st.markdown("---")
    st.markdown("**Borç Alan Cariler**")

    secili_idxs = st.multiselect(
        "Borç Alan Cari(ler) Seçin *",
        options=range(len(cari_ids)),
        format_func=lambda x: cari_adlar[x],
        key="bv_karsi_idxs",
    )
    secili_cari_ids = [cari_ids[i] for i in secili_idxs]

    # Kalem miktarları
    dagitim_miktarlar: Dict[int, str] = {}
    if secili_cari_ids:
        st.markdown("**Kalem Miktarları:**")
        for cid in secili_cari_ids:
            dagitim_miktarlar[cid] = st.text_input(
                cari_map[cid],
                key=f"bv_miktar_{cid}",
                placeholder="0",
            )

    # ── Canlı önizleme ────────────────────────────────────────────────────────
    if secili_cari_ids and birim_fiyat_str:
        fiyat_p = _parse_fiyat(birim_fiyat_str)
        if fiyat_p:
            toplam_dagitim = 0
            satirlar = []
            for cid in secili_cari_ids:
                m_str = dagitim_miktarlar.get(cid, "") or "0"
                ok, _ = validate_miktar(m_str)
                if ok and int(m_str) > 0:
                    m = int(m_str)
                    tutar = hesapla_kalem_tutari(m, to_decimal(fiyat_p))
                    toplam_dagitim += m
                    satirlar.append(f"&nbsp;&nbsp;• **{cari_map[cid]}:** {format_miktar(m)} adet → **{format_para(tutar)}**")
            if satirlar:
                st.markdown("---")
                st.markdown("**Hesaplama Önizlemesi:**")
                for s in satirlar:
                    st.markdown(s)
                ok_t, _ = validate_miktar(toplam_miktar_str or "0")
                if ok_t and int(toplam_miktar_str or "0") > 0:
                    belge_t = hesapla_belge_toplami(int(toplam_miktar_str), to_decimal(fiyat_p))
                    st.markdown(f"**Belge Toplamı:** {format_para(belge_t)}")
                    if toplam_dagitim != int(toplam_miktar_str):
                        st.warning(
                            f"⚠️ Dağıtım toplamı ({format_miktar(toplam_dagitim)}) "
                            f"≠ Toplam miktar ({toplam_miktar_str})"
                        )

    # ── Kaydet ────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("💾 Kaydet", key="bv_kaydet_btn", type="primary", use_container_width=False,
                 disabled=st.session_state.get("bv_saving", False)):
        _handle_kaydet(
            cari_id, user_id, secili_ilac_id, lot_tarihi,
            birim_fiyat_str, toplam_miktar_str,
            secili_cari_ids, dagitim_miktarlar, cari_map, ilac_map, veren_adi,
        )


def _handle_kaydet(cari_id, user_id, ilac_id, lot_tarihi, birim_fiyat_str,
                   toplam_miktar_str, secili_cari_ids, dagitim_miktarlar,
                   cari_map, ilac_map, veren_adi):
    hatalar = []

    fiyat = _parse_fiyat(birim_fiyat_str or "")
    if fiyat is None:
        hatalar.append("Geçerli bir birim alış fiyatı giriniz (örn: 10.1234).")
    else:
        ok, msg = validate_birim_fiyat(fiyat)
        if not ok:
            hatalar.append(msg)

    ok_m, msg_m = validate_miktar(toplam_miktar_str or "")
    if not ok_m:
        hatalar.append(f"Toplam miktar: {msg_m}")

    if not secili_cari_ids:
        hatalar.append("En az bir borç alan cari seçmelisiniz.")

    dagitim = []
    toplam_dagitim = 0
    cari_set = set()
    for cid in secili_cari_ids:
        if cid == cari_id:
            hatalar.append("Borç veren ve borç alan aynı eczane olamaz.")
            break
        if cid in cari_set:
            hatalar.append("Aynı cari iki kez eklenemez.")
            break
        cari_set.add(cid)
        m_str = dagitim_miktarlar.get(cid, "") or ""
        ok_k, msg_k = validate_miktar(m_str)
        if not ok_k:
            hatalar.append(f"{cari_map.get(cid, cid)}: {msg_k}")
        else:
            m = int(m_str)
            dagitim.append({"cari_id": cid, "miktar": m})
            toplam_dagitim += m

    ok_m2, _ = validate_miktar(toplam_miktar_str or "")
    if ok_m2 and dagitim and toplam_dagitim != int(toplam_miktar_str):
        hatalar.append(
            f"Dağıtım toplamı ({format_miktar(toplam_dagitim)}) "
            f"≠ Toplam miktar ({toplam_miktar_str})."
        )

    if hatalar:
        for h in hatalar:
            st.error(h)
        return

    st.session_state["bv_confirm_data"] = {
        "ilac_id": ilac_id,
        "ilac_adi": ilac_map.get(ilac_id, "?"),
        "lot_tarihi": str(lot_tarihi),
        "birim_fiyat": fiyat,
        "toplam_miktar": int(toplam_miktar_str),
        "dagitim": dagitim,
        "cari_map": cari_map,
        "veren_adi": veren_adi,
    }
    st.session_state["bv_confirm_mode"] = True
    st.rerun()


def _render_onay(user_id: int, cari_id: int, veren_adi: str) -> None:
    data = st.session_state.get("bv_confirm_data", {})
    if not data:
        st.session_state["bv_confirm_mode"] = False
        st.rerun()
        return

    ilac_adi = data["ilac_adi"]
    lot = format_tarih(data["lot_tarihi"])
    birim = data["birim_fiyat"]
    toplam = data["toplam_miktar"]
    dagitim = data["dagitim"]
    cari_map = data["cari_map"]
    belge_t = hesapla_belge_toplami(toplam, to_decimal(birim))

    st.markdown("## ✅ Kayıt Onayı")
    st.markdown("Bilgileri kontrol edin, ardından onaylayın.")

    st.markdown(f"""
    <div style="background:white; border:1px solid #E2E8F0; border-radius:12px; padding:24px; margin:16px 0;">
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:20px;">
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">BORÇ VEREN</div>
                 <div style="font-weight:600;color:#1E293B">{veren_adi}</div></div>
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">İLAÇ</div>
                 <div style="font-weight:600;color:#1E293B">{ilac_adi}</div></div>
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">LOT / ALIŞ TARİHİ</div>
                 <div style="font-weight:600;color:#1E293B">{lot}</div></div>
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">BİRİM ALIŞ FİYATI</div>
                 <div style="font-weight:600;color:#1E293B">{format_birim_fiyat(birim)}</div></div>
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">TOPLAM MİKTAR</div>
                 <div style="font-weight:600;color:#1E293B">{format_miktar(toplam)} adet</div></div>
            <div><div style="font-size:0.75rem;color:#64748B;font-weight:500">TOPLAM TUTAR</div>
                 <div style="font-weight:700;color:#2563EB;font-size:1.1rem">{format_para(belge_t)}</div></div>
        </div>
        <div style="border-top:1px solid #F1F5F9;padding-top:16px;">
            <div style="font-size:0.75rem;color:#64748B;font-weight:500;margin-bottom:10px">DAĞITIM</div>
    """, unsafe_allow_html=True)

    for s in dagitim:
        cid = s["cari_id"]
        m = s["miktar"]
        tutar = hesapla_kalem_tutari(m, to_decimal(birim))
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #F8FAFC;">
            <span style="font-weight:500;color:#1E293B">{cari_map.get(cid, cid)}</span>
            <span style="color:#64748B">{format_miktar(m)} adet</span>
            <span style="font-weight:600;color:#1E293B">{format_para(tutar)}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Onayla ve Kaydet", type="primary", key="onay_evet",
                     use_container_width=True,
                     disabled=st.session_state.get("bv_saving", False)):
            _execute_kaydet(user_id, cari_id, data)
    with col2:
        if st.button("← Geri Dön", key="onay_hayir", use_container_width=True):
            st.session_state["bv_confirm_mode"] = False
            st.rerun()


def _execute_kaydet(user_id: int, cari_id: int, data: Dict) -> None:
    st.session_state["bv_saving"] = True
    try:
        belge_no = borc_service.create_borc_belgesi(
            borc_veren_cari_id=cari_id,
            ilac_id=data["ilac_id"],
            lot_tarihi=data["lot_tarihi"],
            birim_alis_fiyati=data["birim_fiyat"],
            toplam_miktar=data["toplam_miktar"],
            dagitim=data["dagitim"],
            olusturan_user_id=user_id,
        )
        # Tüm form state'ini temizle, başarı ekranına geç
        _reset()
        st.session_state["bv_success_belge_no"] = belge_no
        st.rerun()
    except ValueError as e:
        st.error(str(e))
        st.session_state["bv_saving"] = False
    except Exception as e:
        logger.error("Kayıt hatası: %s", e)
        st.error("Beklenmedik bir hata oluştu. Lütfen tekrar deneyiniz.")
        st.session_state["bv_saving"] = False

