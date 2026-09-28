"""
Dashboard ekranı — 3 seviyeli drill-down yapısı.

Seviye 1: Tüm cariler + net bakiye
Seviye 2: Seçilen carinin ilişkileri
Seviye 3: İki cari arasındaki hareketler + belge detayı
"""

import io
import logging
from typing import Dict, List, Optional

import streamlit as st
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from services import borc_service, cari_service
from services.auth_service import get_current_cari_id
from utils.formatting import (
    format_bakiye,
    format_para,
    format_tarih,
    format_birim_fiyat,
    format_miktar,
    renkli_bakiye_html,
    bakiye_rengi,
)
from utils.calculations import hesapla_kalem_tutari, to_decimal
from config import DURUM_AKTIF, DURUM_SILINDI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _init_dashboard_state() -> None:
    if "dashboard_seviye" not in st.session_state:
        st.session_state["dashboard_seviye"] = 1
    if "dashboard_cari_id" not in st.session_state:
        st.session_state["dashboard_cari_id"] = None
    if "dashboard_karsi_cari_id" not in st.session_state:
        st.session_state["dashboard_karsi_cari_id"] = None
    if "dashboard_belge_no" not in st.session_state:
        st.session_state["dashboard_belge_no"] = None
    if "goster_silinenleri" not in st.session_state:
        st.session_state["goster_silinenleri"] = False


def _go_level1() -> None:
    st.session_state["dashboard_seviye"] = 1
    st.session_state["dashboard_cari_id"] = None
    st.session_state["dashboard_karsi_cari_id"] = None
    st.session_state["dashboard_belge_no"] = None


def _go_level2(cari_id: int) -> None:
    st.session_state["dashboard_seviye"] = 2
    st.session_state["dashboard_cari_id"] = cari_id
    st.session_state["dashboard_karsi_cari_id"] = None
    st.session_state["dashboard_belge_no"] = None


def _go_level3(cari_id: int, karsi_cari_id: int) -> None:
    st.session_state["dashboard_seviye"] = 3
    st.session_state["dashboard_cari_id"] = cari_id
    st.session_state["dashboard_karsi_cari_id"] = karsi_cari_id
    st.session_state["dashboard_belge_no"] = None


def _renk_html(tutar: int, metin: str) -> str:
    renk = bakiye_rengi(tutar)
    return f'<span style="color:{renk}; font-weight:bold">{metin}</span>'


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------


def _excel_dashboard(data: List[Dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dashboard"

    header_fill = PatternFill("solid", fgColor="2E4057")
    header_font = Font(bold=True, color="FFFFFF")
    headers = ["Cari No", "Cari Adı", "Net Bakiye (TL)", "Durum"]

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, row in enumerate(data, 2):
        ws.cell(row=row_idx, column=1, value=row["cari_id"])
        ws.cell(row=row_idx, column=2, value=row["cari_adi"])
        ws.cell(row=row_idx, column=3, value=row["net_bakiye"])
        ws.cell(row=row_idx, column=4, value=row["durum"])

        # Bakiye hücresine renk
        bakiye_cell = ws.cell(row=row_idx, column=3)
        if row["net_bakiye"] > 0:
            bakiye_cell.font = Font(color="1B7A1B", bold=True)
        elif row["net_bakiye"] < 0:
            bakiye_cell.font = Font(color="CC0000", bold=True)

    for col in range(1, 5):
        ws.column_dimensions[get_column_letter(col)].auto_size = True
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 10

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _excel_hareket_detay(
    hareketler: List[Dict],
    cari_a_adi: str,
    cari_b_adi: str,
    cari_map: Dict[int, str],
    ilac_map: Dict[int, str],
) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hareket Detayı"

    header_fill = PatternFill("solid", fgColor="2E4057")
    header_font = Font(bold=True, color="FFFFFF")
    headers = [
        "Belge No", "Alış/Lot Tarihi", "Hareket", "İlaç",
        "Miktar", "Birim Alış Fiyatı", "Tutar (TL)",
        "Kümülatif Bakiye (TL)", "Durum",
    ]

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, h in enumerate(hareketler, 2):
        veren = int(h.get("borc_veren_cari_id", 0))
        hareket_str = "Borç Verildi" if veren == st.session_state.get("dashboard_cari_id") else "Borç Alındı"
        tutar = hesapla_kalem_tutari(int(h.get("kalem_miktari", 0)), h.get("birim_alis_fiyati", "0"))
        kumul = h.get("kumulatif_bakiye", 0)
        ilac_adi = ilac_map.get(int(h.get("İlaç ID", 0)), "?")
        lot = format_tarih(str(h.get("Lot Tarihi", "")))

        ws.cell(row=row_idx, column=1, value=h.get("Belge No", ""))
        ws.cell(row=row_idx, column=2, value=lot)
        ws.cell(row=row_idx, column=3, value=hareket_str)
        ws.cell(row=row_idx, column=4, value=ilac_adi)
        ws.cell(row=row_idx, column=5, value=int(h.get("kalem_miktari", 0)))
        ws.cell(row=row_idx, column=6, value=float(to_decimal(h.get("birim_alis_fiyati", "0"))))
        ws.cell(row=row_idx, column=7, value=tutar)
        ws.cell(row=row_idx, column=8, value=kumul)
        ws.cell(row=row_idx, column=9, value=h.get("durum", ""))

    col_widths = [16, 14, 14, 20, 8, 18, 14, 20, 10]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Belge Detayı Dialog
# ---------------------------------------------------------------------------


def _show_belge_detay(belge_no: str, cari_map: Dict, ilac_map: Dict, current_user_id: int) -> None:
    """Belge detayını modal benzeri expanded bölümde gösterir."""
    with st.expander(f"📄 Belge Detayı: {belge_no}", expanded=True):
        satirlar = borc_service.get_belge_detay(belge_no)
        if not satirlar:
            st.warning("Belge bulunamadı.")
            return

        ilk = satirlar[0]
        veren_id = int(ilk.get("borc_veren_cari_id", 0))
        ilac_id = int(ilk.get("İlaç ID", 0))
        lot = format_tarih(str(ilk.get("Lot Tarihi", "")))
        birim = ilk.get("birim_alis_fiyati", "0")
        toplam_miktar = int(ilk.get("Toplam Miktar", 0))
        durum = str(ilk.get("durum", ""))

        from utils.calculations import hesapla_belge_toplami
        belge_toplami = hesapla_belge_toplami(toplam_miktar, to_decimal(birim))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Borç Veren:** {cari_map.get(veren_id, '?')}")
            st.markdown(f"**İlaç:** {ilac_map.get(ilac_id, '?')}")
            st.markdown(f"**Lot / Alış Tarihi:** {lot}")
        with col2:
            st.markdown(f"**Birim Alış Fiyatı:** {format_birim_fiyat(birim)}")
            st.markdown(f"**Toplam Miktar:** {format_miktar(toplam_miktar)}")
            st.markdown(f"**Toplam Tutar:** {format_para(belge_toplami)}")

        if durum == DURUM_SILINDI:
            silen_id = str(ilk.get("Silen User ID", ""))
            silinme = str(ilk.get("Silinme Tarihi", ""))
            st.error(f"⛔ Bu belge silinmiştir. Silinme: {silinme}")
        else:
            st.success("✅ Aktif")

        st.markdown("**Dağıtım:**")
        for s in satirlar:
            alan_id = int(s.get("borc_alan_cari_id", 0))
            miktar = int(s.get("kalem_miktari", 0))
            tutar = hesapla_kalem_tutari(miktar, to_decimal(birim))
            sat_durum = "✅" if s.get("durum") != DURUM_SILINDI else "⛔"
            st.markdown(
                f"&nbsp;&nbsp;&nbsp;{sat_durum} **{cari_map.get(alan_id, '?')}** — "
                f"{format_miktar(miktar)} adet — {format_para(tutar)}",
                unsafe_allow_html=True,
            )

        # Silme butonu
        if durum != DURUM_SILINDI:
            st.markdown("---")
            olusturan = int(ilk.get("Oluşturan User ID", 0))
            if olusturan == current_user_id:
                if st.button(f"🗑️ Bu Belgeyi Sil ({belge_no})", key=f"del_{belge_no}", type="secondary"):
                    st.session_state[f"confirm_delete_{belge_no}"] = True

                if st.session_state.get(f"confirm_delete_{belge_no}"):
                    st.warning(f"**Bu belge silinecek. Devam etmek istiyor musunuz?**")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🗑️ Sil", key=f"confirm_yes_{belge_no}", type="primary"):
                            try:
                                borc_service.delete_borc_belgesi(belge_no, current_user_id)
                                st.success(f"{belge_no} numaralı belge silindi.")
                                st.session_state.pop(f"confirm_delete_{belge_no}", None)
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with c2:
                        if st.button("Vazgeç", key=f"confirm_no_{belge_no}"):
                            st.session_state.pop(f"confirm_delete_{belge_no}", None)
                            st.rerun()
            else:
                st.info("ℹ️ Bu belgeyi yalnızca oluşturan kullanıcı silebilir.")


# ---------------------------------------------------------------------------
# Seviye 1 — Tüm Cariler
# ---------------------------------------------------------------------------


def _render_seviye1() -> None:
    st.markdown("## 📊 Dashboard — Genel Bakiye")

    try:
        data = borc_service.get_dashboard_data()
    except Exception as e:
        st.error(f"Veriler yüklenemedi: {e}")
        return

    # Excel export
    excel_bytes = _excel_dashboard(data)
    st.download_button(
        label="⬇️ Excel İndir",
        data=excel_bytes,
        file_name="dashboard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dashboard_export",
    )

    st.markdown("---")
    st.markdown("_Bakiye: Bir cariye tıklayarak detayına girebilirsiniz._")

    # Tablo başlıkları
    h_col1, h_col2, h_col3 = st.columns([4, 3, 2])
    with h_col1:
        st.markdown("**Cari Adı**")
    with h_col2:
        st.markdown("**Net Bakiye**")
    with h_col3:
        st.markdown("**Durum**")
    st.markdown("---")

    for row in data:
        col1, col2, col3 = st.columns([4, 3, 2])
        with col1:
            etiket = row["cari_adi"]
            if st.button(etiket, key=f"l1_{row['cari_id']}", use_container_width=True):
                _go_level2(row["cari_id"])
                st.rerun()
        with col2:
            tutar = row["net_bakiye"]
            renk = bakiye_rengi(tutar)
            st.markdown(
                f'<span style="color:{renk}; font-weight:bold">{format_bakiye(tutar)}</span>',
                unsafe_allow_html=True,
            )
        with col3:
            if row["durum"] == DURUM_AKTIF:
                st.markdown("🟢 Aktif")
            else:
                st.markdown("🔴 Pasif")


# ---------------------------------------------------------------------------
# Seviye 2 — Seçilen Cari
# ---------------------------------------------------------------------------


def _render_seviye2(cari_id: int) -> None:
    cari_map = {int(c["Cari ID"]): str(c["Cari Adı"]) for c in cari_service.get_all_cariler()}
    cari_adi = cari_map.get(cari_id, f"Cari#{cari_id}")

    # Breadcrumb
    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Geri", key="l2_back"):
            _go_level1()
            st.rerun()
    with col_title:
        st.markdown(f"## 📊 {cari_adi}")

    # Toplam net bakiye
    try:
        dashboard_data = borc_service.get_dashboard_data()
        net_bakiye = next((d["net_bakiye"] for d in dashboard_data if d["cari_id"] == cari_id), 0)
    except Exception as e:
        st.error(f"Veri yüklenemedi: {e}")
        return

    renk = bakiye_rengi(net_bakiye)
    st.markdown(
        f'**Genel Net Bakiye:** <span style="color:{renk}; font-size:1.3em; font-weight:bold">'
        f'{format_bakiye(net_bakiye)}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # İlişkiler
    try:
        iliskiler = borc_service.get_cari_iliskiler(cari_id)
    except Exception as e:
        st.error(f"İlişkiler yüklenemedi: {e}")
        return

    if not iliskiler:
        st.info("Bu carinin henüz hiç hareketi bulunmuyor.")
        return

    st.markdown("_Bir karşı cariye tıklayarak hareket detayını görüntüleyebilirsiniz._")
    h_col1, h_col2, h_col3 = st.columns([4, 3, 2])
    with h_col1:
        st.markdown("**Karşı Cari**")
    with h_col2:
        st.markdown("**Net Bakiye**")
    with h_col3:
        st.markdown("**Durum**")
    st.markdown("---")

    for row in iliskiler:
        col1, col2, col3 = st.columns([4, 3, 2])
        with col1:
            if st.button(row["cari_adi"], key=f"l2_{row['cari_id']}", use_container_width=True):
                _go_level3(cari_id, row["cari_id"])
                st.rerun()
        with col2:
            tutar = row["net_bakiye"]
            renk = bakiye_rengi(tutar)
            st.markdown(
                f'<span style="color:{renk}; font-weight:bold">{format_bakiye(tutar)}</span>',
                unsafe_allow_html=True,
            )
        with col3:
            if row["durum"] == DURUM_AKTIF:
                st.markdown("🟢 Aktif")
            else:
                st.markdown("🔴 Pasif")


# ---------------------------------------------------------------------------
# Seviye 3 — İki Cari Arası Hareketler
# ---------------------------------------------------------------------------


def _render_seviye3(cari_a: int, cari_b: int, current_user_id: int) -> None:
    from services.ilac_service import get_ilac_map

    cari_map = {int(c["Cari ID"]): str(c["Cari Adı"]) for c in cari_service.get_all_cariler()}
    ilac_map = get_ilac_map()

    cari_a_adi = cari_map.get(cari_a, f"Cari#{cari_a}")
    cari_b_adi = cari_map.get(cari_b, f"Cari#{cari_b}")

    # Breadcrumb
    c_back, c_title = st.columns([1, 8])
    with c_back:
        if st.button("← Geri", key="l3_back"):
            _go_level2(cari_a)
            st.rerun()
    with c_title:
        st.markdown(f"## 📊 {cari_a_adi} ↔ {cari_b_adi}")

    # Silinenleri göster toggle
    goster = st.checkbox(
        "Silinenleri Göster",
        value=st.session_state.get("goster_silinenleri", False),
        key="goster_silinenleri_check",
    )
    st.session_state["goster_silinenleri"] = goster

    try:
        hareketler = borc_service.get_iliski_hareketleri(cari_a, cari_b, goster)
    except Exception as e:
        st.error(f"Hareketler yüklenemedi: {e}")
        return

    if not hareketler:
        st.info("Bu ikili arasında hareket bulunmuyor.")
        return

    # Net bakiye
    from utils.calculations import hesapla_iliski_bakiyesi
    from services.borc_service import get_hareketler_normalized
    tum_h = get_hareketler_normalized()
    net = hesapla_iliski_bakiyesi(tum_h, cari_a, cari_b)
    renk = bakiye_rengi(net)
    st.markdown(
        f'**Net Bakiye ({cari_a_adi} açısından):** '
        f'<span style="color:{renk}; font-size:1.2em; font-weight:bold">{format_bakiye(net)}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Excel export
    excel_bytes = _excel_hareket_detay(hareketler, cari_a_adi, cari_b_adi, cari_map, ilac_map)
    st.download_button(
        label="⬇️ Excel İndir",
        data=excel_bytes,
        file_name=f"hareketler_{cari_a_adi}_{cari_b_adi}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="hareket_export",
    )

    st.markdown("---")

    # Hareket tablosu başlıkları
    cols = st.columns([2, 2, 2, 3, 2, 2, 2, 2, 2])
    basliklar = ["Belge No", "Lot Tarihi", "Hareket", "İlaç", "Miktar", "Birim Fiyat", "Tutar", "Kümülatif", "Durum"]
    for col, baslik in zip(cols, basliklar):
        col.markdown(f"**{baslik}**")
    st.markdown("---")

    secili_belge = st.session_state.get("dashboard_belge_no")

    for h in hareketler:
        veren = int(h.get("borc_veren_cari_id", 0))
        hareket_str = "📤 Borç Verildi" if veren == cari_a else "📥 Borç Alındı"
        tutar = hesapla_kalem_tutari(int(h.get("kalem_miktari", 0)), h.get("birim_alis_fiyati", "0"))
        kumul = h.get("kumulatif_bakiye", 0)
        ilac_adi = ilac_map.get(int(h.get("İlaç ID", 0)), "?")
        lot = format_tarih(str(h.get("Lot Tarihi", "")))
        belge_no = str(h.get("Belge No", ""))
        durum = str(h.get("durum", ""))
        miktar = int(h.get("kalem_miktari", 0))

        renk_tutar = bakiye_rengi(tutar if veren == cari_a else -tutar)
        renk_kumul = bakiye_rengi(kumul)

        cols = st.columns([2, 2, 2, 3, 2, 2, 2, 2, 2])

        with cols[0]:
            if st.button(belge_no, key=f"belge_{belge_no}_{h.get('Kalem No', 0)}", use_container_width=True):
                if secili_belge == belge_no:
                    st.session_state["dashboard_belge_no"] = None
                else:
                    st.session_state["dashboard_belge_no"] = belge_no
                st.rerun()

        cols[1].markdown(lot)
        cols[2].markdown(hareket_str)
        cols[3].markdown(ilac_adi)
        cols[4].markdown(format_miktar(miktar))
        cols[5].markdown(format_birim_fiyat(h.get("birim_alis_fiyati", "0")))
        cols[6].markdown(
            f'<span style="color:{renk_tutar}; font-weight:bold">{format_para(tutar)}</span>',
            unsafe_allow_html=True,
        )
        cols[7].markdown(
            f'<span style="color:{renk_kumul}; font-weight:bold">{format_bakiye(kumul)}</span>',
            unsafe_allow_html=True,
        )
        if durum == DURUM_SILINDI:
            cols[8].markdown("⛔ Silindi")
        else:
            cols[8].markdown("✅ Aktif")

    # Seçili belge detayı
    if secili_belge:
        st.markdown("---")
        _show_belge_detay(secili_belge, cari_map, ilac_map, current_user_id)


# ---------------------------------------------------------------------------
# Ana Render
# ---------------------------------------------------------------------------


def render(user: Dict) -> None:
    _init_dashboard_state()
    current_user_id = int(user.get("User ID", 0))
    seviye = st.session_state.get("dashboard_seviye", 1)

    if seviye == 1:
        _render_seviye1()
    elif seviye == 2:
        cari_id = st.session_state.get("dashboard_cari_id")
        if cari_id:
            _render_seviye2(cari_id)
        else:
            _go_level1()
            st.rerun()
    elif seviye == 3:
        cari_id = st.session_state.get("dashboard_cari_id")
        karsi_id = st.session_state.get("dashboard_karsi_cari_id")
        if cari_id and karsi_id:
            _render_seviye3(cari_id, karsi_id, current_user_id)
        else:
            _go_level1()
            st.rerun()
