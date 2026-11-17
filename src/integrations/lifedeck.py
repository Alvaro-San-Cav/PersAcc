"""
Cliente de la bandeja de LifeDeck (PWA) — sustituto de Notion como origen de apuntes rápidos.

LifeDeck expone /api/finance (token Bearer de ámbito 'finance', generado en LifeDeck › Finanzas):
  GET  ?op=ping        → {ok: true}
  GET  ?op=pending     → {entries: [{id, date, kind, amount, concept, category, relevance}]}
  POST ?op=ack         {ids: [uuid], status: 'imported'|'discarded'} → {updated}
  POST ?op=categories  {categories: [{kind, name}]} → {count}
  POST ?op=snapshot    {month: 'YYYY-MM', data: {...}} → {ok: true}

Misma interfaz que NotionClient (is_configured, test_connection, get_all_entries, delete_entry)
para que las rutas y el diálogo de revisión funcionen igual con cualquiera de los dos orígenes.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.config import load_config

logger = logging.getLogger(__name__)

SOURCE_NAME = "LifeDeck"
TIMEOUT = 15
ACK_BATCH = 200  # el servidor acepta hasta 500 ids por petición

# kind de LifeDeck → texto de tipo que entiende notion_parser.map_tipo_movimiento
_KIND_TO_TIPO = {
    "GASTO": "Gasto",
    "INGRESO": "Ingreso",
    "INVERSION_AHORRO": "Inversión",
    "TRASPASO_ENTRADA": "Traspaso entrada",
    "TRASPASO_SALIDA": "Traspaso salida",
}

_ERRORS = {
    "unauthorized": "Token no válido. Genera uno nuevo en LifeDeck › Finanzas › Conexión con PersAcc.",
    "server_not_configured": "El servidor de LifeDeck no está configurado (faltan variables en Vercel).",
}


class LifeDeckError(Exception):
    """Error de comunicación con LifeDeck."""


class LifeDeckClient:
    source_name = SOURCE_NAME

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        conf = cfg if cfg is not None else load_config().get("lifedeck", {})
        conf = conf if isinstance(conf, dict) else {}
        self.enabled = bool(conf.get("enabled", False))
        self.url = str(conf.get("url") or "").strip().rstrip("/")
        self.token = str(conf.get("token") or "").strip()

    # ── interfaz común con NotionClient ─────────────────────────────────────
    def is_available(self) -> bool:
        return True

    def is_configured(self) -> bool:
        """URL y token presentes (no mira `enabled`: eso lo decide el selector de bandeja)."""
        return bool(self.url and self.token)

    def test_connection(self) -> Tuple[bool, str]:
        if not self.url:
            return False, "Falta la URL de LifeDeck."
        if not self.token:
            return False, "Falta el token de LifeDeck."
        try:
            self._request("GET", "ping")
            pending = self._request("GET", "pending").get("entries", [])
            n = len(pending)
            return True, f"Conectado a LifeDeck. {n} apunte{'s' if n != 1 else ''} pendiente{'s' if n != 1 else ''}."
        except LifeDeckError as exc:
            return False, str(exc)

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Apuntes pendientes con el mismo formato que NotionClient.get_all_entries()."""
        if not self.is_configured():
            return []
        data = self._request("GET", "pending")
        out: List[Dict[str, Any]] = []
        for e in data.get("entries", []) or []:
            try:
                fecha = date.fromisoformat(str(e.get("date", ""))[:10])
            except ValueError:
                fecha = date.today()
            try:
                importe = abs(float(e.get("amount", 0)))
            except (TypeError, ValueError):
                continue
            out.append({
                "id": str(e.get("id", "")),
                "concepto": str(e.get("concept") or ""),
                "importe": importe,
                "tipo": _KIND_TO_TIPO.get(str(e.get("kind", "")), "Gasto"),
                "categoria": str(e.get("category") or ""),
                "relevancia": str(e.get("relevance") or ""),
                "fecha": fecha,
            })
        return out

    def delete_entry(self, entry_id: str) -> bool:
        """Equivalente a 'archivar' de Notion: la marca como importada en LifeDeck."""
        return self.ack([entry_id], "imported") > 0

    # ── específico de LifeDeck ──────────────────────────────────────────────
    def ack(self, ids: List[str], status: str = "imported") -> int:
        """Marca apuntes como 'imported' o 'discarded' (por lotes). Devuelve cuántos cambiaron."""
        if status not in ("imported", "discarded"):
            raise ValueError("status debe ser 'imported' o 'discarded'")
        clean = [i for i in dict.fromkeys(ids) if i]
        total = 0
        for start in range(0, len(clean), ACK_BATCH):
            chunk = clean[start:start + ACK_BATCH]
            try:
                res = self._request("POST", "ack", {"ids": chunk, "status": status})
                total += int(res.get("updated", 0))
            except LifeDeckError as exc:
                logger.warning("LifeDeck ack falló: %s", exc)
        return total

    def discard(self, ids: List[str]) -> int:
        return self.ack(ids, "discarded")

    def push_categories(self) -> int:
        """Sube el catálogo de categorías activas de PersAcc. Devuelve cuántas subió."""
        from src import database as db

        cats = [
            {"kind": c.tipo_movimiento.value, "name": c.nombre.strip()[:100]}
            for c in db.get_all_categorias()
            if c.es_activo and c.nombre and c.nombre.strip()
        ][:500]
        res = self._request("POST", "categories", {"categories": cats})
        return int(res.get("count", len(cats)))

    def push_snapshot(self, mes_fiscal: Optional[str] = None) -> str:
        """Calcula el resumen del mes a partir del ledger y lo sube. Devuelve el mes subido."""
        mes = mes_fiscal or _current_month()
        data = build_snapshot(mes)
        self._request("POST", "snapshot", {"month": mes, "data": data})
        return mes

    def push_hints(self) -> int:
        """Sube las pistas concepto → categoría/relevancia aprendidas del ledger. Devuelve cuántas."""
        hints = build_hints()
        res = self._request("POST", "hints", {"hints": hints})
        return int(res.get("count", len(hints)))

    # ── HTTP ────────────────────────────────────────────────────────────────
    def _request(self, method: str, op: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            raise LifeDeckError("LifeDeck no está configurado.")
        url = f"{self.url}/api/finance"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        try:
            resp = requests.request(method, url, params={"op": op}, json=body, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise LifeDeckError(f"No se pudo conectar con LifeDeck: {exc}") from exc
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code != 200:
            code = payload.get("error") if isinstance(payload, dict) else None
            msg = _ERRORS.get(str(code), f"LifeDeck respondió {resp.status_code}" + (f" ({code})" if code else ""))
            raise LifeDeckError(msg)
        return payload if isinstance(payload, dict) else {}


def _current_month() -> str:
    from src import business_logic as bl

    return bl.calcular_mes_fiscal(date.today())


def build_snapshot(mes_fiscal: str) -> Dict[str, Any]:
    """Resumen del mes con la forma que pinta LifeDeck (ver web/api/_lib/finance.ts)."""
    from src import business_logic as bl
    from src import database as db
    from src.models import TipoMovimiento

    kpis = bl.calcular_kpis(mes_fiscal)
    relevancia = bl.calcular_kpis_relevancia(mes_fiscal)
    cat_name = {c.id: c.nombre for c in db.get_all_categorias()}
    por_cat: Dict[str, float] = {}
    ledger = db.get_ledger_by_month(mes_fiscal)
    for e in ledger:
        if e.tipo_movimiento == TipoMovimiento.GASTO:
            nombre = cat_name.get(e.categoria_id, "Otros")
            por_cat[nombre] = por_cat.get(nombre, 0.0) + float(e.importe)
    top = sorted(por_cat.items(), key=lambda kv: kv[1], reverse=True)[:12]

    return {
        "ingresos": round(float(kpis.get("total_ingresos", 0.0)), 2),
        "gastos": round(float(kpis.get("total_gastos", 0.0)), 2),
        "inversion": round(float(kpis.get("total_inversion", 0.0)), 2),
        "ahorro": round(float(kpis.get("balance_mes", 0.0)), 2),
        "tasa_ahorro": round(float(kpis.get("pct_salary_retention", 0.0)), 4),
        "por_categoria": [{"nombre": n[:100], "importe": round(v, 2)} for n, v in top],
        "por_relevancia": {k: round(float(relevancia.get(k, 0.0)), 2) for k in ("NE", "LI", "SUP", "TON")},
        "estado": "CERRADO" if db.is_mes_cerrado(mes_fiscal) else "ABIERTO",
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "movimientos": build_movements(ledger, cat_name),
    }


MAX_MOVEMENTS = 400
#: Presupuesto para la lista dentro del snapshot (LifeDeck acepta 48 KB en total).
MAX_MOVEMENTS_BYTES = 40 * 1024


def build_movements(entries: List[Any], cat_name: Dict[int, str]) -> List[Dict[str, Any]]:
    """
    Movimientos ya confirmados del mes, compactos y del más reciente al más antiguo:
    {f: fecha real, t: tipo, c: concepto, i: importe, cat: categoría}. Si no caben, se quitan los más antiguos.
    """
    import json

    rows = sorted(entries, key=lambda e: (str(e.fecha_real), e.id or 0), reverse=True)[:MAX_MOVEMENTS]
    out: List[Dict[str, Any]] = []
    size = 2
    for e in rows:
        kind = e.tipo_movimiento.value if hasattr(e.tipo_movimiento, "value") else str(e.tipo_movimiento)
        fecha = e.fecha_real.isoformat() if hasattr(e.fecha_real, "isoformat") else str(e.fecha_real)
        m = {"f": fecha[:10], "t": kind, "c": (e.concepto or "").strip()[:60], "i": round(float(e.importe), 2), "cat": cat_name.get(e.categoria_id, "")[:40]}
        size += len(json.dumps(m, ensure_ascii=False).encode("utf-8")) + 1
        if size > MAX_MOVEMENTS_BYTES:
            break
        out.append(m)
    return out


MAX_HINTS = 1500


def norm_concept(text: str) -> str:
    """Igual que normConcept de LifeDeck: minúsculas, sin acentos, solo letras y espacios."""
    import re
    import unicodedata

    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def build_hints(entries: Optional[List[Any]] = None, categorias: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """
    Del ledger: para cada (tipo, concepto normalizado) la categoría y relevancia más usadas y cuántas
    veces aparece. Las más usadas (y recientes) primero, hasta MAX_HINTS. Ignora categorías inactivas.
    """
    from collections import Counter, defaultdict

    from src import database as db

    entries = db.get_all_ledger_entries() if entries is None else entries
    categorias = db.get_all_categorias() if categorias is None else categorias
    cat_name = {c.id: c.nombre.strip() for c in categorias if c.es_activo and c.nombre and c.nombre.strip()}

    groups: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"cats": Counter(), "rels": Counter(), "n": 0, "last": ""})
    for e in entries:
        name = cat_name.get(e.categoria_id)
        concept = norm_concept(e.concepto)[:80].strip()
        if not name or not concept:
            continue
        kind = e.tipo_movimiento.value if hasattr(e.tipo_movimiento, "value") else str(e.tipo_movimiento)
        g = groups[(kind, concept)]
        g["cats"][name] += 1
        if e.relevancia_code is not None:
            rel = e.relevancia_code.value if hasattr(e.relevancia_code, "value") else str(e.relevancia_code)
            g["rels"][rel] += 1
        g["n"] += 1
        fecha = e.fecha_real.isoformat() if hasattr(e.fecha_real, "isoformat") else str(e.fecha_real)
        g["last"] = max(g["last"], fecha)

    ranked = sorted(groups.items(), key=lambda kv: (kv[1]["n"], kv[1]["last"]), reverse=True)[:MAX_HINTS]
    out: List[Dict[str, Any]] = []
    for (kind, concept), g in ranked:
        rel = g["rels"].most_common(1)[0][0] if (kind == "GASTO" and g["rels"]) else None
        out.append({"c": concept, "k": kind, "cat": g["cats"].most_common(1)[0][0][:100], "r": rel, "n": g["n"]})
    return out


def get_lifedeck_client() -> LifeDeckClient:
    return LifeDeckClient()


def sync_summary(mes_fiscal: Optional[str] = None) -> Dict[str, Any]:
    """Sube categorías + resumen del mes. Lanza LifeDeckError si falla algo."""
    client = get_lifedeck_client()
    categories = client.push_categories()
    month = client.push_snapshot(mes_fiscal)
    try:
        hints = client.push_hints()
    except LifeDeckError as exc:  # LifeDeck antiguo sin op=hints: no rompe el resto
        logger.info("Pistas de categoría no subidas: %s", exc)
        hints = 0
    return {"categories": categories, "month": month, "hints": hints}


def sync_summary_background() -> None:
    """Best-effort en un hilo aparte: nunca bloquea ni rompe la importación."""
    import threading

    def _run() -> None:
        try:
            if _lifedeck_active():
                sync_summary()
        except Exception as exc:  # noqa: BLE001
            logger.info("Sincronización con LifeDeck omitida: %s", exc)

    threading.Thread(target=_run, name="lifedeck-sync", daemon=True).start()


_soon_timer: Optional[Any] = None


def sync_summary_soon(delay: float = 8.0) -> None:
    """
    Tras añadir/editar/borrar en el ledger: sube el resumen pasados `delay` s. Varias ediciones seguidas
    se agrupan en una sola subida. Best-effort, nunca bloquea la petición.
    """
    import threading

    global _soon_timer
    if _soon_timer is not None:
        _soon_timer.cancel()
    _soon_timer = threading.Timer(delay, sync_summary_background)
    _soon_timer.daemon = True
    _soon_timer.start()


def _lifedeck_active() -> bool:
    c = get_lifedeck_client()
    return c.enabled and c.is_configured()
