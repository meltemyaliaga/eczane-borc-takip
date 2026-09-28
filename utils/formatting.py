"""
Türkçe sayı ve tarih formatlama yardımcıları.
UI katmanında tüm gösterimler bu modülden geçirilmelidir.
"""

from decimal import Decimal
from datetime import date, datetime
from typing import Union


def format_para(tutar: int) -> str:
    """
    Tam sayı TL tutarını Türkçe formatta gösterir.

    Örnek:
        3500 → "3.500 TL"
        1000000 → "1.000.000 TL"
    """
    formatted = f"{abs(tutar):,}".replace(",", ".")
    return f"{formatted} TL"


def format_bakiye(tutar: int) -> str:
    """
    İşaretli bakiyeyi Türkçe formatta gösterir.

    Örnek:
        5000  → "+5.000 TL"
        -3500 → "-3.500 TL"
        0     → "0 TL"
    """
    if tutar > 0:
        return f"+{format_para(tutar)}"
    elif tutar < 0:
        return f"-{format_para(abs(tutar))}"
    else:
        return "0 TL"


def format_birim_fiyat(fiyat: Union[Decimal, str, float]) -> str:
    """
    Birim alış fiyatını 4 ondalık basamak, Türkçe formatta gösterir.

    Örnek:
        Decimal("10.1234") → "10,1234 TL"
        "9.5"              → "9,5000 TL"
    """
    d = Decimal(str(fiyat))
    tam_kisim = int(d)
    ondalik = d - Decimal(str(tam_kisim))
    tam_str = f"{tam_kisim:,}".replace(",", ".")
    ondalik_str = f"{ondalik:.4f}"[2:]  # "0.xxxx" → "xxxx"
    return f"{tam_str},{ondalik_str} TL"


def format_miktar(miktar: int) -> str:
    """
    Miktar gösterimi (ondalıksız).

    Örnek:
        750 → "750"
        1500 → "1.500"
    """
    return f"{miktar:,}".replace(",", ".")


def format_tarih(tarih: Union[str, date, datetime]) -> str:
    """
    Tarihi DD.MM.YYYY formatında gösterir.

    Giriş formatları:
        str: "YYYY-MM-DD" veya "DD.MM.YYYY"
        date / datetime nesnesi
    """
    if isinstance(tarih, str):
        tarih = tarih.strip()
        if not tarih:
            return ""
        if "." in tarih:
            # Zaten Türkçe formatta
            return tarih
        try:
            tarih = datetime.strptime(tarih, "%Y-%m-%d").date()
        except ValueError:
            return tarih  # Bilinmeyen format; olduğu gibi döndür
    if isinstance(tarih, datetime):
        tarih = tarih.date()
    return tarih.strftime("%d.%m.%Y")


def format_datetime_tr(dt: datetime) -> str:
    """
    datetime nesnesini Türkçe formatta gösterir.

    Örnek: "28.09.2026 19:30:15"
    """
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def parse_tarih_from_tr(tarih_str: str) -> date:
    """
    "DD.MM.YYYY" formatındaki string'i date nesnesine çevirir.
    """
    return datetime.strptime(tarih_str.strip(), "%d.%m.%Y").date()


def bakiye_rengi(tutar: int) -> str:
    """
    Bakiye rengini Streamlit markdown renk kodu olarak döndürür.
    """
    if tutar > 0:
        return "green"
    elif tutar < 0:
        return "red"
    else:
        return "gray"


def renkli_bakiye_html(tutar: int) -> str:
    """
    Renkli bakiyeyi HTML span olarak döndürür (Streamlit st.markdown için).
    """
    renk = bakiye_rengi(tutar)
    metin = format_bakiye(tutar)
    return f'<span style="color:{renk}; font-weight:bold">{metin}</span>'
