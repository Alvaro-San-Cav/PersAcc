"""
Tests de paridad de la API contra la capa de dominio.

Objetivo: garantizar que los endpoints devuelven exactamente lo que calcula
business_logic sobre la DB real, y que las reglas de inmutabilidad de meses
cerrados se respetan. Es la red de seguridad antes de tocar el frontend.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
for p in (str(ROOT), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import server  # noqa: E402
from src import business_logic as bl  # noqa: E402
from src import database as db  # noqa: E402

client = TestClient(server.app)


def test_health():
    assert client.get("/api/health").json()["ok"] is True


def test_dashboard_kpis_match_domain():
    data = client.get("/api/dashboard").json()
    mes = data["mes_fiscal"]
    expected = bl.calcular_kpis(mes)
    for k, v in expected.items():
        assert data["kpis"][k] == pytest.approx(v), f"KPI {k} difiere"


def test_relevancia_matches_domain():
    data = client.get("/api/dashboard").json()
    mes = data["mes_fiscal"]
    expected = bl.calcular_kpis_relevancia(mes)
    assert data["relevancia"] == pytest.approx(expected)


def test_categories_count_consistency():
    cats = client.get("/api/categories").json()
    counts = db.get_category_counts()
    for c in cats:
        assert c["count"] == counts.get(c["id"], 0)


def test_history_year_matches_domain():
    years = client.get("/api/history/years").json()
    assert years, "La DB de test debe tener años con datos"
    anio = years[0]
    api = client.get(f"/api/history/{anio}").json()
    dom = bl.calcular_kpis_anuales(anio)
    for k in ("total_ingresos", "total_gastos", "total_ahorrado", "pct_ahorro",
              "gastos_NE", "gastos_LI", "gastos_SUP", "gastos_TON"):
        assert api[k] == pytest.approx(dom[k]), f"KPI anual {k} difiere"


def test_closed_month_entry_is_immutable():
    """Editar/borrar una entrada de un mes CERRADO debe devolver 409."""
    cerrados = db.get_all_meses_fiscales_cerrados()
    if not cerrados:
        pytest.skip("No hay meses cerrados en la DB de test")
    mes = cerrados[0].mes_fiscal
    entries = db.get_ledger_by_month(mes)
    if not entries:
        pytest.skip(f"El mes cerrado {mes} no tiene entradas")
    entry_id = entries[0].id
    r = client.put(f"/api/ledger/{entry_id}", json={
        "categoria_id": entries[0].categoria_id, "concepto": "x", "importe": 1.0,
    })
    assert r.status_code == 409
    assert client.delete(f"/api/ledger/{entry_id}").status_code == 409


def test_create_entry_in_closed_month_rejected():
    cerrados = db.get_all_meses_fiscales_cerrados()
    if not cerrados:
        pytest.skip("No hay meses cerrados en la DB de test")
    mes = cerrados[0].mes_fiscal
    cats = db.get_all_categorias()
    r = client.post("/api/ledger", json={
        "fecha_real": f"{mes}-15", "tipo_movimiento": "GASTO",
        "categoria_id": cats[0].id, "concepto": "test", "importe": 1.0,
    })
    assert r.status_code == 409


def test_ai_status_shape():
    """El estado de IA responde sin requerir Ollama arrancado."""
    body = client.get("/api/ai/status").json()
    assert set(body) == {"enabled", "ollama_running", "models"}
    assert isinstance(body["models"], list)


def test_projections_shape():
    body = client.get("/api/projections?months=6").json()
    assert body["months"] == 6
    assert set(body["series"]) == {"gasto", "ingreso", "ahorro"}
    for s in body["series"].values():
        assert "success" in s


def test_import_commit_empty():
    r = client.post("/api/import/commit", json={"entries": []})
    assert r.status_code == 200
    assert r.json() == {"inserted": 0, "skipped": 0}


def test_closing_preview_does_not_mutate():
    """El preview de cierre no debe escribir en la DB."""
    mes = server._primer_mes_abierto()
    before = len(db.get_all_ledger_entries())
    r = client.post("/api/closing/preview", json={
        "mes_fiscal": mes, "saldo_banco_real": 1000.0, "nomina_nueva": 1500.0,
        "pct_retencion_remanente": 0.1, "pct_retencion_salario": 0.2,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mes_siguiente"] != mes
    assert len(db.get_all_ledger_entries()) == before  # sin efectos secundarios
