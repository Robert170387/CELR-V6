"""Extracción de campos de recibos colombianos a partir de texto OCR.

Funciones puras (sin dependencias externas) para poder probarlas de forma
aislada. Cada extractor es defensivo: ante cualquier duda devuelve `None` en
lugar de inventar un valor, de modo que el endpoint pueda degradar a captura
manual.
"""

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

_MONEY_TOKEN_RE = re.compile(
    r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?"  # 1.234.567,89 / 1,234,567.89
    r"|\d+[.,]\d{1,2}"                          # 250.00 / 250,50
    r"|\d+"                                      # 250000
)

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_TOTAL_KEYWORDS_RE = re.compile(
    r"(total\s+a\s+pagar|valor\s+total|total\s+factura|gran\s+total|total\s+neto"
    r"|vr\.?\s*total|valor\s+a\s+pagar|\btotal\b|\bneto\b|\bimporte\b)",
    re.IGNORECASE,
)

_FACTURA_RE = re.compile(
    r"(?:factura|fact\.?|numero|n[uú]mero|consecutivo|remisi[oó]n|voucher|recibo)"
    r"\s*(?:n[°ºo]?\.?|#|n[uú]m(?:ero)?\.?)?\s*[:.\-]?\s*"
    r"(?=[A-Za-z0-9\-]*\d)([A-Za-z0-9][A-Za-z0-9\-]{2,})",
    re.IGNORECASE,
)

# Tolerante a confusiones típicas de OCR: NIT -> NTT / N1T / N.I.T.
_NIT_RE = re.compile(
    r"N[.\s]?[IIT1l][.\s]?T[.\s]*[:\-]?\s*([0-9][0-9.\-\s]{5,})",
    re.IGNORECASE,
)

_GALONES_RE = re.compile(
    r"(galones|gal[oó]n|\bgal\b|\bgln\b|gls)\s*[:\-]?\s*([0-9][0-9.,]*)",
    re.IGNORECASE,
)

_KM_RE = re.compile(
    r"(kilometraje|kil[oó]metros?|\bkm\b|od[oó]metro|recorrido)\s*[:\-]?\s*([0-9][0-9.,]*)",
    re.IGNORECASE,
)

_PROVEEDOR_LABEL_RE = re.compile(
    r"(?:raz[oó]n\s+social|proveedor|nombre)\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)

_EMPRESA_SUFFIX_RE = re.compile(
    r"(S\.?\s?A\.?\s?S|S\.?\s?A|LTDA|E\.?\s?S\.?\s?P|&?\s*C[IÍ]A|CORP|SAS)\b",
    re.IGNORECASE,
)

_NOISE_LINE_RE = re.compile(
    r"(factura|recibo|nit|fecha|total|subtotal|iva|impuesto|tel[eé]fono"
    r"|direcci[oó]n|correo|resoluci[oó]n|autorizaci[oó]n|cufe|dian"
    r"|valor|cliente|vendedor|cajero)",
    re.IGNORECASE,
)


def strip_accents(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Parsers escalares
# ---------------------------------------------------------------------------


def parse_money(raw: Optional[str]) -> Optional[Decimal]:
    """Convierte '1.234.567,89' / '$1,234,567.89' / '250.000' en Decimal."""
    if raw is None:
        return None

    cleaned = re.sub(r"[^\d.,-]", "", str(raw).strip())
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        if cleaned.rfind(".") > cleaned.rfind(","):
            cleaned = cleaned.replace(",", "")            # punto decimal
        else:
            cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        parts = cleaned.split(",")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3):
            cleaned = cleaned.replace(",", "")            # 250,000 -> miles
        else:
            cleaned = cleaned.replace(",", ".")
    elif has_dot:
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3):
            cleaned = cleaned.replace(".", "")            # 250.000 -> miles

    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_date(raw: Optional[str]) -> Optional[date]:
    """Acepta 2026-09-16, 16/09/2026, 16-09-26, 16 de septiembre de 2026."""
    if not raw:
        return None
    value = strip_accents(str(raw)).strip().lower()

    numeric = re.search(r"(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})", value)
    if numeric:
        first, second, third = numeric.groups()
        if len(first) == 4:
            year, month, day = int(first), int(second), int(third)
        else:
            year = int(third)
            if year < 100:
                year += 2000
            a, b = int(first), int(second)
            if a > 12 and b <= 12:
                day, month = a, b
            elif b > 12 and a <= 12:
                day, month = b, a
            else:
                day, month = a, b
        return _safe_date(year, month, day)

    textual = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de(?:l)?\s+(\d{2,4})", value)
    if textual:
        day = int(textual.group(1))
        month = _MONTHS.get(textual.group(2))
        year = int(textual.group(3))
        if year < 100:
            year += 2000
        if month:
            return _safe_date(year, month, day)

    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    if 2000 <= value.year <= 2100:
        return value
    return None


def normalize_nit(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    return digits or None


def _money_tokens(text: str) -> List[Decimal]:
    tokens = []
    for match in _MONEY_TOKEN_RE.finditer(text):
        value = parse_money(match.group(0))
        if value is not None:
            tokens.append(value)
    return tokens


# ---------------------------------------------------------------------------
# Extractores de campo
# ---------------------------------------------------------------------------


def find_valor_total(text: str) -> Optional[Decimal]:
    candidates: List[Decimal] = []
    for line in text.splitlines():
        if _TOTAL_KEYWORDS_RE.search(line):
            candidates.extend(_money_tokens(line))
    if candidates:
        return max(candidates)

    # Respaldo: el mayor monto precedido por '$' (evita confundir con fechas/IDs).
    dollar_values = [
        value
        for match in re.finditer(r"\$\s*([0-9][0-9.,]*)", text)
        if (value := parse_money(match.group(1))) is not None
    ]
    if dollar_values:
        return max(dollar_values)
    return None


def find_fecha(text: str) -> Optional[date]:
    for line in text.splitlines():
        if re.search(r"fecha|emisi[oó]n|expedici[oó]n", line, re.IGNORECASE):
            parsed = parse_date(line)
            if parsed:
                return parsed
    parsed = parse_date(text)
    return parsed


def find_nit(text: str) -> Optional[str]:
    match = _NIT_RE.search(text)
    if not match:
        return None
    raw = match.group(1).strip().strip(".-")
    return raw or None


def find_proveedor(text: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        labeled = _PROVEEDOR_LABEL_RE.search(line)
        if labeled:
            value = labeled.group(1).strip(" :-\t")
            if len(value) >= 3 and re.search(r"[A-Za-zÁÉÍÓÚÑ]{3}", value):
                return value[:150]

    for line in lines:
        if _EMPRESA_SUFFIX_RE.search(line) and len(line) >= 3:
            return line[:150]

    for line in lines:
        if _NOISE_LINE_RE.search(line):
            continue
        letters = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}", line)
        if len(" ".join(letters)) >= 3 and len(line) <= 80:
            return line[:150]

    return None


def find_num_factura(text: str) -> Optional[str]:
    for line in text.splitlines():
        if not re.search(r"factura|recibo|remisi[oó]n|voucher|consecutivo", line, re.IGNORECASE):
            continue
        match = _FACTURA_RE.search(line)
        if match and re.search(r"\d", match.group(1)):
            return match.group(1).strip().upper()
    return None


def find_galones(text: str) -> Optional[Decimal]:
    match = _GALONES_RE.search(text)
    return parse_money(match.group(2)) if match else None


def find_km(text: str) -> Optional[Decimal]:
    match = _KM_RE.search(text)
    return parse_money(match.group(2)) if match else None


def extract_receipt_fields(text: Optional[str]) -> Dict[str, object]:
    """Devuelve los campos del recibo. Los no reconocidos quedan en None."""
    cleaned = clean_text(text)
    if not cleaned:
        return {
            "nit": None,
            "proveedor": None,
            "fecha_gasto": None,
            "valor_total": None,
            "num_factura": None,
            "cantidad_galones": None,
            "km_registro": None,
        }

    return {
        "nit": find_nit(cleaned),
        "proveedor": find_proveedor(cleaned),
        "fecha_gasto": find_fecha(cleaned),
        "valor_total": find_valor_total(cleaned),
        "num_factura": find_num_factura(cleaned),
        "cantidad_galones": find_galones(cleaned),
        "km_registro": find_km(cleaned),
    }
