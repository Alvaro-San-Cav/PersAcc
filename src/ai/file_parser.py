"""
file_parser.py — Parseo de ficheros bancarios legacy para PersAcc.

Soporta:
  - AEB Norma 43 / CSB (ficheros .csb, .aeb, .txt)
  - AEB SEPA / Norma 43 SEPA (detección automática por campo de divisa)
  - Excel (.xlsx, .xls) — primera hoja

El módulo es puro Python, sin dependencias de Streamlit.
"""
from __future__ import annotations

import io
import logging
import re
import sys
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos de fichero
# ---------------------------------------------------------------------------

class FileType(Enum):
    AEB_NORMA43 = "AEB Norma 43 (CSB)"
    AEB_SEPA    = "AEB SEPA / Norma 43 SEPA"
    EXCEL       = "Excel"
    UNKNOWN     = "Desconocido"


# ---------------------------------------------------------------------------
# Detección del tipo de fichero
# ---------------------------------------------------------------------------

def detect_file_type(filename: str, content_bytes: bytes) -> FileType:
    """Detecta el tipo de fichero bancario a partir del nombre y contenido."""
    fname = filename.lower()
    if fname.endswith((".xlsx", ".xls")):
        return FileType.EXCEL

    # Intentar decodificar como texto
    text = _decode(content_bytes)

    if text:
        lines = text.splitlines()
        # Buscar registro cabecera (tipo 11) y registros de movimiento (tipo 22)
        has_11 = any(l.startswith("11") for l in lines)
        has_22 = any(l.startswith("22") for l in lines)
        has_88 = any(l.startswith("88") for l in lines)

        if has_11 and has_22 and has_88:
            # Detectar si es SEPA: campo de divisa en posición 53-56 del registro 22
            # En Norma 43 estándar esa posición es numérica; en SEPA puede ser "EUR"
            for l in lines:
                if l.startswith("22") and len(l) >= 56:
                    currency_field = l[53:56].strip()
                    if currency_field.isalpha():
                        return FileType.AEB_SEPA
            return FileType.AEB_NORMA43

    # Fallback por extensión
    if fname.endswith((".csb", ".aeb", ".txt", ".n43")):
        return FileType.AEB_NORMA43

    return FileType.UNKNOWN


# ---------------------------------------------------------------------------
# Parseo AEB Norma 43
# ---------------------------------------------------------------------------

def _decode(content_bytes: bytes) -> Optional[str]:
    """Intenta decodificar bytes con varias codificaciones comunes en España."""
    for enc in ("latin-1", "utf-8", "cp1252", "iso-8859-15"):
        try:
            return content_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _parse_date_aeb(raw: str) -> str:
    """Convierte fecha AEB AAMMDD a YYYY-MM-DD."""
    try:
        yy = int(raw[0:2])
        mm = raw[2:4]
        dd = raw[4:6]
        year = 2000 + yy if yy < 70 else 1900 + yy
        return f"{year}-{mm}-{dd}"
    except Exception:
        return raw


def _parse_importe_aeb(raw: str, signo: str) -> float:
    """
    Importe AEB: 14 dígitos con 2 decimales implícitos.
    signo_campo: '1' = debe (entrada/ingreso positivo),
                 '2' = haber (salida/gasto, negativo para nuestra convención).
    Devolvemos siempre positivo — el tipo de movimiento lo deduce el LLM.
    """
    try:
        val = int(raw.strip()) / 100.0
        return val
    except Exception:
        return 0.0


def parse_aeb43(content_bytes: bytes) -> str:
    """
    Parsea un fichero AEB Norma 43 y devuelve una representación legible.

    Formato de los registros relevantes:
      - Tipo 11: cabecera de cuenta
      - Tipo 22: movimiento (posiciones fijas)
      - Tipo 23: concepto complementario del movimiento anterior
      - Tipo 33: totales de cuenta
      - Tipo 88: fin de fichero
    """
    text = _decode(content_bytes)
    if not text:
        return "[Error: no se pudo decodificar el fichero]"

    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    result_lines: list[str] = []
    account_info = ""
    pending_movement: Optional[dict] = None

    def flush_movement():
        nonlocal pending_movement
        if pending_movement:
            m = pending_movement
            sign_str = "+" if m["signo"] == "2" else "-"
            # Limpiar posible basura inicial en AEB43 (ej. "260302WWVXHMT9PMCA   0003524 " o "260217...3508 ")
            concepto_limpio = re.sub(r'^[a-zA-Z0-9]{12,30}(?:\s+\d{5,10})?\s+', '', m['concepto'])
            
            result_lines.append(
                f"{m['fecha_valor']} | {sign_str}{m['importe']:.2f} | {concepto_limpio}"
            )
            pending_movement = None

    for line in lines:
        if len(line) < 2:
            continue
        tipo = line[:2]

        # --- Cabecera de cuenta ---
        if tipo == "11" and len(line) >= 26:
            # Entidad(4) Oficina(4) DC(2) Cuenta(10) → posición 2..22
            iban_part = line[2:22]
            try:
                fecha_ini = _parse_date_aeb(line[22:28])
                fecha_fin = _parse_date_aeb(line[28:34])
            except Exception:
                fecha_ini = fecha_fin = "?"
            account_info = f"Cuenta: {iban_part}  |  Período: {fecha_ini} → {fecha_fin}"
            result_lines.append(f"=== {account_info} ===")
            result_lines.append("Fecha valor   | Importe    | Concepto")
            result_lines.append("-" * 60)

        # --- Movimiento ---
        elif tipo == "22" and len(line) >= 42:
            flush_movement()
            fecha_real = "?"
            try:
                fecha_real  = _parse_date_aeb(line[10:16])
                fecha_valor = _parse_date_aeb(line[16:22])
                signo       = line[27]          # '1'=debe (cargo/-), '2'=haber (abono/+)
                importe_raw = line[28:42]       # 14 dígitos
                importe     = _parse_importe_aeb(importe_raw, signo)
                concepto_raw = line[52:].strip() if len(line) > 52 else ""
            except Exception as e:
                logger.debug(f"Error parsing tipo 22: {e} — line: {line}")
                concepto_raw = line
                fecha_valor = "??"
                signo = "?"
                importe = 0.0
            pending_movement = {
                "fecha_real": fecha_real,
                "fecha_valor": fecha_valor,
                "signo": signo,
                "importe": importe,
                "concepto": concepto_raw,
            }

        # --- Concepto complementario ---
        elif tipo == "23" and len(line) >= 4:
            extra = line[4:].strip()
            if pending_movement and extra:
                # Acumular concepto
                pending_movement["concepto"] = (
                    (pending_movement["concepto"] + " " + extra).strip()
                )

        # --- Totales ---
        elif tipo == "33" and len(line) >= 60:
            flush_movement()
            try:
                saldo_raw = line[27:41]
                signo_sal = line[26]
                saldo = _parse_importe_aeb(saldo_raw, signo_sal)
                sign_str = "+" if signo_sal == "2" else "-"
                result_lines.append("-" * 60)
                result_lines.append(f"SALDO FINAL: {sign_str}{saldo:.2f}")
            except Exception:
                pass

    flush_movement()
    return "\n".join(result_lines) if result_lines else "[No se encontraron movimientos]"


# ---------------------------------------------------------------------------
# Parseo AEB SEPA
# ---------------------------------------------------------------------------

def parse_sepa(content_bytes: bytes) -> str:
    """
    Parsea AEB SEPA (Norma 43 SEPA).
    Estructura idéntica a Norma 43 estándar con divisa explícita.
    Reutilizamos el mismo parser añadiendo la divisa al output.
    """
    text = _decode(content_bytes)
    if not text:
        return "[Error: no se pudo decodificar el fichero]"

    lines_raw = [l.rstrip() for l in text.splitlines() if l.strip()]
    result_lines: list[str] = []
    pending_movement: Optional[dict] = None

    def flush_movement():
        nonlocal pending_movement
        if pending_movement:
            m = pending_movement
            sign_str = "+" if m["signo"] == "2" else "-"
            # Limpiar posible basura inicial en AEB43 SEPA
            concepto_limpio = re.sub(r'^[a-zA-Z0-9]{12,30}(?:\s+\d{5,10})?\s+', '', m['concepto'])
            
            result_lines.append(
                f"{m['fecha_valor']} | {sign_str}{m['importe']:.2f} {m['divisa']} | {concepto_limpio}"
            )
            pending_movement = None

    for line in lines_raw:
        if len(line) < 2:
            continue
        tipo = line[:2]

        if tipo == "11" and len(line) >= 34:
            try:
                fecha_ini = _parse_date_aeb(line[22:28])
                fecha_fin = _parse_date_aeb(line[28:34])
            except Exception:
                fecha_ini = fecha_fin = "?"
            result_lines.append(f"=== Cuenta: {line[2:22]}  |  Período: {fecha_ini} → {fecha_fin} ===")
            result_lines.append("Fecha valor   | Importe          | Concepto")
            result_lines.append("-" * 65)

        elif tipo == "22" and len(line) >= 42:
            flush_movement()
            try:
                fecha_valor = _parse_date_aeb(line[16:22])
                signo       = line[27]
                importe     = _parse_importe_aeb(line[28:42], signo)
                divisa      = line[53:56].strip() if len(line) > 56 else "EUR"
                concepto    = line[52:].strip() if len(line) > 52 else ""
            except Exception:
                fecha_valor, signo, importe, divisa, concepto = "?", "?", 0.0, "EUR", line
            pending_movement = {
                "fecha_valor": fecha_valor,
                "signo": signo,
                "importe": importe,
                "divisa": divisa,
                "concepto": concepto,
            }

        elif tipo == "23":
            extra = line[4:].strip()
            if pending_movement and extra:
                pending_movement["concepto"] = (pending_movement["concepto"] + " " + extra).strip()

        elif tipo == "33":
            flush_movement()

    flush_movement()
    return "\n".join(result_lines) if result_lines else "[No se encontraron movimientos]"


# ---------------------------------------------------------------------------
# Parseo Excel
# ---------------------------------------------------------------------------

def parse_excel(content_bytes: bytes, filename: str = "") -> str:
    """
    Parsea la primera hoja de un fichero Excel y devuelve representación CSV.
    Usa el motor adecuado por extensión:
      - .xlsx/.xlsm/.xltx/.xltm -> openpyxl
      - .xls -> xlrd
    """
    try:
        import pandas as pd

        lower_name = filename.lower()
        engine: Optional[str]
        if lower_name.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
            engine = "openpyxl"
        elif lower_name.endswith(".xls"):
            engine = "xlrd"
        else:
            engine = None

        df = pd.read_excel(io.BytesIO(content_bytes), sheet_name=0, engine=engine)
        # Limitar a 200 filas para no saturar el LLM
        if len(df) > 200:
            df = df.head(200)
        lines = [",".join(str(c) for c in df.columns)]
        for _, row in df.iterrows():
            lines.append(",".join(str(v) for v in row.values))
        return "\n".join(lines)
    except ImportError as e:
        lower_name = filename.lower()
        missing_pkg = "openpyxl"
        if lower_name.endswith(".xls"):
            missing_pkg = "xlrd"

        return (
            f"[Error leyendo Excel: falta la dependencia '{missing_pkg}' ({e}). "
            f"Instala con '{sys.executable} -m pip install {missing_pkg}' "
            "y reinicia la app.]"
        )
    except Exception as e:
        return f"[Error leyendo Excel: {e}]"


# ---------------------------------------------------------------------------
# Función principal de parseo
# ---------------------------------------------------------------------------

def parse_file(filename: str, content_bytes: bytes) -> tuple[FileType, str]:
    """
    Detecta el tipo y convierte el contenido del fichero a texto legible.
    Retorna (FileType, texto_legible).
    """
    ftype = detect_file_type(filename, content_bytes)
    if ftype == FileType.AEB_NORMA43:
        text = parse_aeb43(content_bytes)
    elif ftype == FileType.AEB_SEPA:
        text = parse_sepa(content_bytes)
    elif ftype == FileType.EXCEL:
        text = parse_excel(content_bytes, filename=filename)
    else:
        # Intentar mostrar como texto plano
        decoded = _decode(content_bytes)
        text = decoded if decoded else "[No se puede mostrar el contenido del fichero]"
    return ftype, text
