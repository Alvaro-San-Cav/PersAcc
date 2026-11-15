"""
PersAcc — FastAPI backend.

Reutiliza la capa de dominio existente (src/): database, business_logic, config,
models. No duplica lógica. La base de datos (data/finanzas.db) no se toca.

Ejecutar:
    python backend/server.py
    uvicorn backend.server:app --reload --port 8001
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

# ── Hacer importable el paquete src del proyecto ────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# UTF-8 en consola Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Silenciar el warning "No runtime found" de st.cache_data: la capa de dominio
# usa el caché de Streamlit si la librería está instalada, pero aquí corremos sin
# runtime (el caché en disco basado en mtime cubre la persistencia).
import logging
logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from src import database as db
from src import business_logic as bl
from src import config as cfg
from src.models import (
    TipoMovimiento, RelevanciaCode, Categoria, LedgerEntry, EstadoCierre,
)

from api_models import (
    CategoriaOut, CategoriaCreate, CategoriaUpdate,
    LedgerEntryOut, LedgerEntryCreate, LedgerEntryUpdate,
    Kpis, DashboardResponse, SaldoInicioRequest,
    ClosingStatus, ClosingPreviewRequest, ClosingPreview, ClosingExecuteResponse,
    ConsequenceBreakdown,
    AnnualKpis, MesBalance,
    MonthDetailResponse, CategoriaImporte, RetencionesBreakdown,
    YearAnalysisResponse, WordCount, TopEntry, Curiosities,
    NotesUpdate, OkResponse, IdResponse, ConfigResponse,
)

app = FastAPI(title="PersAcc API", version="4.0.0-dev")

from ai_import_routes import router as ai_import_router
app.include_router(ai_import_router)

# CORS para el frontend en dev (Vite). En producción se sirve estático desde aquí.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _cat_map() -> dict[int, str]:
    return {c.id: c.nombre for c in db.get_all_categorias()}


def _entry_to_out(e: LedgerEntry, cat_names: dict[int, str]) -> LedgerEntryOut:
    return LedgerEntryOut(
        id=e.id,
        fecha_real=e.fecha_real,
        fecha_contable=e.fecha_contable,
        mes_fiscal=e.mes_fiscal,
        tipo_movimiento=e.tipo_movimiento.value,
        categoria_id=e.categoria_id,
        categoria_nombre=cat_names.get(e.categoria_id),
        concepto=e.concepto,
        importe=e.importe,
        relevancia_code=e.relevancia_code.value if e.relevancia_code else None,
        flag_liquidez=e.flag_liquidez,
    )


def _kpis_model(mes_fiscal: str) -> Kpis:
    return Kpis(**bl.calcular_kpis(mes_fiscal))


def _mes_siguiente(mes_fiscal: str) -> str:
    y, m = map(int, mes_fiscal.split("-"))
    return f"{y+1}-01" if m == 12 else f"{y}-{m+1:02d}"


def _primer_mes_abierto() -> str:
    """Mes activo por defecto: el siguiente al último cerrado, o el mes actual."""
    cerrados = db.get_all_meses_fiscales_cerrados()
    if cerrados:
        ultimo = sorted(c.mes_fiscal for c in cerrados)[-1]
        return _mes_siguiente(ultimo)
    hoy = date.today()
    return hoy.strftime("%Y-%m")


def _available_months() -> List[str]:
    """Meses con datos o con registro de cierre, ordenados desc."""
    meses: set[str] = set()
    for y in db.get_available_years():
        for e in db.get_ledger_by_year(y):
            meses.add(e.mes_fiscal)
    meses.add(_primer_mes_abierto())
    return sorted(meses, reverse=True)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=OkResponse)
def health() -> OkResponse:
    return OkResponse(detail="PersAcc API up")


# ── Config ──────────────────────────────────────────────────────────────────
@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    return ConfigResponse(config=cfg.load_config(), currency_symbol=cfg.get_currency_symbol())


@app.put("/api/config", response_model=ConfigResponse)
def put_config(new_config: dict) -> ConfigResponse:
    # Merge superficial contra defaults lo hace load_config; aquí persistimos tal cual.
    cfg.save_config(new_config)
    return ConfigResponse(config=cfg.load_config(), currency_symbol=cfg.get_currency_symbol())


# ── Categorías ──────────────────────────────────────────────────────────────
@app.get("/api/categories", response_model=List[CategoriaOut])
def list_categories(tipo: Optional[str] = None) -> List[CategoriaOut]:
    counts = db.get_category_counts()
    if tipo:
        cats = db.get_categorias_by_tipo(TipoMovimiento(tipo))
    else:
        cats = db.get_all_categorias()
    return [
        CategoriaOut(
            id=c.id, nombre=c.nombre, tipo_movimiento=c.tipo_movimiento.value,
            es_activo=c.es_activo, descripcion_ia=c.descripcion_ia,
            count=counts.get(c.id, 0),
        )
        for c in cats
    ]


@app.get("/api/categories/usage-stats", response_model=dict)
def category_usage_stats(
    tipo: str = Query(..., description="Tipo de movimiento"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Mes 1-12"),
    year: Optional[int] = Query(None, description="Año de referencia"),
) -> dict:
    """Estadísticas de uso por categoría para orden inteligente en QuickAdd.

    Devuelve {cat_id (str): {"history": int, "curr_year": int}}: uso en el mismo
    mes de años anteriores + uso acumulado del año actual. Espeja
    `db.get_category_usage_stats` (misma función que usaba el sidebar legacy).
    """
    hoy = date.today()
    stats = db.get_category_usage_stats(
        TipoMovimiento(tipo), month or hoy.month, year or hoy.year
    )
    return {str(k): v for k, v in stats.items()}


@app.post("/api/categories", response_model=IdResponse, status_code=201)
def create_category(payload: CategoriaCreate) -> IdResponse:
    new_id = db.insert_categoria(Categoria(
        id=None, nombre=payload.nombre,
        tipo_movimiento=TipoMovimiento(payload.tipo_movimiento),
        es_activo=True, descripcion_ia=payload.descripcion_ia,
    ))
    return IdResponse(id=new_id)


@app.put("/api/categories/{cat_id}", response_model=OkResponse)
def update_category(cat_id: int, payload: CategoriaUpdate) -> OkResponse:
    db.update_categoria(
        cat_id, payload.nombre,
        TipoMovimiento(payload.tipo_movimiento) if payload.tipo_movimiento else None,
        payload.descripcion_ia,
    )
    return OkResponse()


@app.delete("/api/categories/{cat_id}", response_model=OkResponse)
def delete_category(cat_id: int) -> OkResponse:
    """Borra si no tiene historial; si falla por FK, desactiva (soft delete)."""
    try:
        db.delete_categoria(cat_id)
        return OkResponse(detail="deleted")
    except Exception:
        db.deactivate_categoria(cat_id)
        return OkResponse(detail="deactivated")


# ── Ledger ──────────────────────────────────────────────────────────────────
@app.get("/api/ledger", response_model=List[LedgerEntryOut])
def list_ledger(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    year: Optional[int] = None,
) -> List[LedgerEntryOut]:
    cat_names = _cat_map()
    if month:
        entries = db.get_ledger_by_month(month)
    elif year:
        entries = db.get_ledger_by_year(year)
    else:
        entries = db.get_all_ledger_entries()
    return [_entry_to_out(e, cat_names) for e in entries]


@app.post("/api/ledger", response_model=IdResponse, status_code=201)
def create_ledger(payload: LedgerEntryCreate) -> IdResponse:
    mes_fiscal = bl.calcular_mes_fiscal(payload.fecha_real)
    if db.is_mes_cerrado(mes_fiscal):
        raise HTTPException(409, f"El mes {mes_fiscal} está cerrado; no admite nuevas entradas.")

    tipo = TipoMovimiento(payload.tipo_movimiento)
    rel = RelevanciaCode(payload.relevancia_code) if (payload.relevancia_code and tipo == TipoMovimiento.GASTO) else None
    fecha_contable = bl.calcular_fecha_contable(payload.fecha_real, tipo, payload.flag_liquidez, payload.concepto or "")

    new_id = db.insert_ledger_entry(LedgerEntry(
        id=None, fecha_real=payload.fecha_real, fecha_contable=fecha_contable,
        mes_fiscal=mes_fiscal, tipo_movimiento=tipo, categoria_id=payload.categoria_id,
        concepto=payload.concepto, importe=payload.importe, relevancia_code=rel,
        flag_liquidez=payload.flag_liquidez,
    ))
    return IdResponse(id=new_id)


@app.put("/api/ledger/{entry_id}", response_model=OkResponse)
def update_ledger(entry_id: int, payload: LedgerEntryUpdate) -> OkResponse:
    _assert_entry_editable(entry_id)
    db.update_ledger_entry(
        entry_id, payload.categoria_id, payload.concepto or "",
        payload.importe, payload.relevancia_code,
    )
    return OkResponse()


@app.delete("/api/ledger/{entry_id}", response_model=OkResponse)
def delete_ledger(entry_id: int) -> OkResponse:
    _assert_entry_editable(entry_id)
    db.delete_ledger_entry(entry_id)
    return OkResponse()


def _assert_entry_editable(entry_id: int) -> None:
    """Bloquea edición/borrado si la entrada pertenece a un mes cerrado."""
    entry = db.get_ledger_entry(entry_id)
    if entry is None:
        raise HTTPException(404, f"No existe entrada id={entry_id}")
    if db.is_mes_cerrado(entry.mes_fiscal):
        raise HTTPException(409, f"El mes {entry.mes_fiscal} está cerrado; la entrada es inmutable.")


# ── Dashboard ───────────────────────────────────────────────────────────────
@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(month: Optional[str] = Query(None, description="YYYY-MM")) -> DashboardResponse:
    mes = month or _primer_mes_abierto()
    cat_names = _cat_map()
    entries = db.get_ledger_by_month(mes)
    kpis = _kpis_model(mes)
    cierre = db.get_cierre_mes(mes)
    saldo_inicio = cierre.saldo_inicio if cierre else 0.0
    # Estimación del efectivo disponible: saldo de arranque + flujo neto del mes,
    # descontando toda la inversión (dinero que ya salió del banco, no está en cuenta).
    saldo_cuenta = saldo_inicio + kpis.balance_mes - kpis.total_inversion
    return DashboardResponse(
        mes_fiscal=mes,
        is_cerrado=db.is_mes_cerrado(mes),
        saldo_inicio=saldo_inicio,
        saldo_cuenta=saldo_cuenta,
        kpis=kpis,
        relevancia=bl.calcular_kpis_relevancia(mes),
        entries=[_entry_to_out(e, cat_names) for e in entries],
        available_months=_available_months(),
    )


@app.put("/api/dashboard/saldo-inicio", response_model=OkResponse)
def set_saldo_inicio(payload: SaldoInicioRequest, month: str = Query(..., description="YYYY-MM")) -> OkResponse:
    """Fija manualmente el saldo inicial de un mes abierto (onboarding / primer saldo)."""
    if db.is_mes_cerrado(month):
        raise HTTPException(409, f"El mes {month} está cerrado; no admite cambiar el saldo inicial.")
    db.abrir_mes(month, payload.saldo_inicio)
    return OkResponse(detail="saldo inicial actualizado")


# ── Cierre ──────────────────────────────────────────────────────────────────
@app.get("/api/closing/status", response_model=ClosingStatus)
def closing_status() -> ClosingStatus:
    mes = _primer_mes_abierto()
    cierre = db.get_cierre_mes(mes)
    return ClosingStatus(
        mes_a_cerrar=mes,
        is_cerrado=db.is_mes_cerrado(mes),
        saldo_inicio=cierre.saldo_inicio if cierre else 0.0,
    )


@app.post("/api/closing/preview", response_model=ClosingPreview)
def closing_preview(req: ClosingPreviewRequest) -> ClosingPreview:
    if db.is_mes_cerrado(req.mes_fiscal):
        raise HTTPException(409, f"El mes {req.mes_fiscal} ya está cerrado.")

    kpis = bl.calcular_kpis(req.mes_fiscal)

    consequences = {"total": 0.0, "breakdown": []}
    if req.aplicar_consecuencias:
        rules = cfg.get_config_value("consequences_rules", []) or []
        consequences = bl.calculate_consequences(req.mes_fiscal, rules)

    saldo_base = req.saldo_banco_real - req.nomina_nueva if req.salario_ya_incluido else req.saldo_banco_real
    retencion_remanente = saldo_base * req.pct_retencion_remanente
    retencion_salario = req.nomina_nueva * req.pct_retencion_salario
    retencion_total = bl.calcular_inversion_cierre(
        retenciones_manuales=kpis["inversion_manual"],
        saldo_banco_real=saldo_base,
        nomina_nueva=req.nomina_nueva,
        pct_retencion_remanente=req.pct_retencion_remanente,
        pct_retencion_salario=req.pct_retencion_salario,
        consequences_amount=consequences["total"],
    )
    saldo_fin = saldo_base - retencion_remanente
    # Desviación = saldo esperado del banco vs. saldo real ajustado (sin la nómina nueva,
    # que pertenece al mes siguiente). balance_mes ya incluye los traspasos de entrada.
    cierre_actual = db.get_cierre_mes(req.mes_fiscal)
    saldo_inicio = cierre_actual.saldo_inicio if cierre_actual else 0.0
    balance_esperado = saldo_inicio + kpis["balance_mes"] - kpis["total_inversion"]
    desviacion = balance_esperado - saldo_base if req.saldo_banco_real else None

    return ClosingPreview(
        mes_fiscal=req.mes_fiscal,
        mes_siguiente=_mes_siguiente(req.mes_fiscal),
        kpis=Kpis(**kpis),
        retencion_remanente=retencion_remanente,
        retencion_salario=retencion_salario,
        consequences_total=consequences["total"],
        consequences_breakdown=[ConsequenceBreakdown(**b) for b in consequences["breakdown"]],
        retencion_total=retencion_total,
        saldo_fin=saldo_fin,
        desviacion=desviacion,
    )


@app.post("/api/closing/execute", response_model=ClosingExecuteResponse)
def closing_execute(req: ClosingPreviewRequest) -> ClosingExecuteResponse:
    consequences_amount = 0.0
    if req.aplicar_consecuencias:
        rules = cfg.get_config_value("consequences_rules", []) or []
        consequences_amount = bl.calculate_consequences(req.mes_fiscal, rules)["total"]

    try:
        snapshot = bl.ejecutar_cierre_mes(
            mes_fiscal=req.mes_fiscal,
            saldo_banco_real=req.saldo_banco_real,
            nomina_nueva=req.nomina_nueva,
            pct_retencion_remanente=req.pct_retencion_remanente,
            pct_retencion_salario=req.pct_retencion_salario,
            consequences_amount=consequences_amount,
            salario_ya_incluido=req.salario_ya_incluido,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))

    return ClosingExecuteResponse(
        mes_cerrado=snapshot.mes_cierre,
        mes_siguiente=_mes_siguiente(req.mes_fiscal),
        saldo_inicial_nuevo=snapshot.saldo_inicial_nuevo,
        retencion_ejecutada=snapshot.retencion_ejecutada or 0.0,
        desviacion=snapshot.desviacion_registrada,
    )


# ── Histórico ───────────────────────────────────────────────────────────────
@app.get("/api/history/years", response_model=List[int])
def history_years() -> List[int]:
    return db.get_available_years()


@app.get("/api/history/{anio}/analysis", response_model=YearAnalysisResponse)
def history_analysis(anio: int, tipo: str = Query("GASTO")) -> YearAnalysisResponse:
    """Análisis textual del año: frecuencia de palabras, top movimientos, curiosidades."""
    t = TipoMovimiento(tipo)
    entries = db.get_ledger_by_year(anio)
    cat_names = _cat_map()

    wc = bl.get_word_counts(entries, filter_type=t, limit=15)  # dict {word: count}
    word_counts = [WordCount(word=w, count=c) for w, c in wc.items()]

    top = bl.get_top_entries(entries, filter_type=t, limit=10)
    top_entries = [
        TopEntry(
            fecha=e.fecha_real.isoformat(),
            categoria=cat_names.get(e.categoria_id, ""),
            concepto=e.concepto or "",
            importe=e.importe,
        )
        for e in top
    ]

    cur = bl.calculate_curious_metrics(entries, filter_type=t)
    curiosities = Curiosities(**cur) if cur else Curiosities()

    return YearAnalysisResponse(
        tipo=tipo, word_counts=word_counts, top_entries=top_entries, curiosities=curiosities,
    )


@app.get("/api/history/{anio}/{mes}", response_model=MonthDetailResponse)
def history_month(anio: int, mes: int) -> MonthDetailResponse:
    """Detalle de un mes: KPIs, calidad del gasto, gastos por categoría, retenciones."""
    mes_fiscal = f"{anio}-{mes:02d}"
    cat_names = _cat_map()
    entries = db.get_ledger_by_month(mes_fiscal)

    gastos: dict[str, float] = {}
    for e in entries:
        if e.tipo_movimiento == TipoMovimiento.GASTO:
            name = cat_names.get(e.categoria_id, f"Cat {e.categoria_id}")
            gastos[name] = gastos.get(name, 0.0) + e.importe
    gastos_list = [
        CategoriaImporte(categoria=k, importe=v)
        for k, v in sorted(gastos.items(), key=lambda x: x[1], reverse=True)
    ]

    ret = RetencionesBreakdown()
    for e in entries:
        if e.tipo_movimiento != TipoMovimiento.INVERSION:
            continue
        concepto = (e.concepto or "").lower()
        if "retención salario" in concepto:
            ret.salario += e.importe
        elif "retención remanente" in concepto:
            ret.remanente += e.importe
        elif "consecuencias" in concepto:
            ret.consecuencias += e.importe
        else:
            ret.manual += e.importe
    ret.total = ret.salario + ret.remanente + ret.consecuencias + ret.manual

    return MonthDetailResponse(
        mes_fiscal=mes_fiscal,
        is_cerrado=db.is_mes_cerrado(mes_fiscal),
        kpis=_kpis_model(mes_fiscal),
        relevancia=bl.calcular_kpis_relevancia(mes_fiscal),
        gastos_por_categoria=gastos_list,
        retenciones=ret,
        entries=[_entry_to_out(e, cat_names) for e in entries],
    )


@app.get("/api/history/{anio}", response_model=AnnualKpis)
def history_year(anio: int) -> AnnualKpis:
    k = bl.calcular_kpis_anuales(anio)
    meses = [
        MesBalance(mes_fiscal=m, ingresos=d["ingresos"], gastos=d["gastos"], balance=d["balance"])
        for m, d in sorted(k.get("meses_data", {}).items())
    ]
    return AnnualKpis(
        anio=k["anio"], total_ingresos=k["total_ingresos"], total_gastos=k["total_gastos"],
        total_ahorrado=k["total_ahorrado"], total_inversion=k.get("total_inversion", 0.0),
        pct_ahorro=k["pct_ahorro"], gastos_NE=k["gastos_NE"], gastos_LI=k["gastos_LI"],
        gastos_SUP=k["gastos_SUP"], gastos_TON=k["gastos_TON"],
        mejor_mes=k["mejor_mes"], peor_mes=k["peor_mes"],
        categoria_mas_gasto=k["categoria_mas_gasto"], meses=meses,
    )


# ── Notas ───────────────────────────────────────────────────────────────────
@app.get("/api/notes/{period_type}/{period_id}", response_model=str)
def get_notes(period_type: str, period_id: str) -> str:
    return db.get_period_notes(period_type, period_id) or ""


@app.put("/api/notes/{period_type}/{period_id}", response_model=OkResponse)
def put_notes(period_type: str, period_id: str, payload: NotesUpdate) -> OkResponse:
    db.save_period_notes(period_type, period_id, payload.note_text)
    return OkResponse()


# ── Export ──────────────────────────────────────────────────────────────────
@app.get("/api/export/csv", response_class=PlainTextResponse)
def export_csv() -> str:
    import csv
    import io
    cat_names = _cat_map()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "fecha_real", "fecha_contable", "mes_fiscal", "tipo_movimiento",
                "categoria", "concepto", "importe", "relevancia_code", "flag_liquidez"])
    for e in db.get_all_ledger_entries():
        w.writerow([
            e.id, e.fecha_real.isoformat(), e.fecha_contable.isoformat(), e.mes_fiscal,
            e.tipo_movimiento.value, cat_names.get(e.categoria_id, ""), e.concepto or "",
            e.importe, e.relevancia_code.value if e.relevancia_code else "",
            int(e.flag_liquidez),
        ])
    return buf.getvalue()


# ── Estático (frontend build) en producción ─────────────────────────────────
_DIST = ROOT / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # No servir el SPA para rutas de API no encontradas: devolver 404 real para
        # que el cliente no cachee index.html (200) en lugar de la respuesta JSON.
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8001, reload=True)
