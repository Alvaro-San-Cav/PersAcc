"""Tests del cliente de la bandeja de LifeDeck (sin red: requests.request simulado)."""
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integrations import lifedeck  # noqa: E402
from src.integrations import notion_parser as np  # noqa: E402
from src.models import TipoMovimiento  # noqa: E402


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def calls(monkeypatch):
    log = []
    responses = {}

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        log.append({"method": method, "url": url, "op": params["op"], "json": json, "auth": headers["Authorization"]})
        return responses.get(params["op"], FakeResp(200, {}))

    monkeypatch.setattr(lifedeck.requests, "request", fake_request)
    return log, responses


def client():
    return lifedeck.LifeDeckClient({"enabled": True, "url": "https://ld.example/", "token": "t" * 43})


def test_get_all_entries_maps_to_notion_shape(calls):
    log, responses = calls
    responses["pending"] = FakeResp(200, {"entries": [
        {"id": "a", "date": "2026-11-02", "kind": "INVERSION_AHORRO", "amount": 50, "concept": "Fondo",
         "category": None, "relevance": None},
        {"id": "b", "date": "2026-11-03", "kind": "GASTO", "amount": "12.5", "concept": "Café",
         "category": "Comida", "relevance": "LI"},
    ]})
    out = client().get_all_entries()
    assert log[0]["url"] == "https://ld.example/api/finance"
    assert log[0]["auth"] == "Bearer " + "t" * 43
    assert out[1] == {"id": "b", "concepto": "Café", "importe": 12.5, "tipo": "Gasto", "categoria": "Comida",
                      "relevancia": "LI", "fecha": date(2026, 11, 3)}
    assert np.map_tipo_movimiento(out[0]["tipo"]) == TipoMovimiento.INVERSION


def test_ack_batches_and_discard(calls, monkeypatch):
    log, responses = calls
    monkeypatch.setattr(lifedeck, "ACK_BATCH", 2)
    responses["ack"] = FakeResp(200, {"updated": 2})
    assert client().discard(["1", "2", "2", "3"]) == 4
    assert [c["json"] for c in log] == [
        {"ids": ["1", "2"], "status": "discarded"},
        {"ids": ["3"], "status": "discarded"},
    ]


def test_test_connection_reports_bad_token(calls):
    _, responses = calls
    responses["ping"] = FakeResp(401, {"error": "unauthorized"})
    ok, detail = client().test_connection()
    assert ok is False and "Token no válido" in detail


def test_not_configured_is_noop():
    c = lifedeck.LifeDeckClient({"enabled": True, "url": "", "token": ""})
    assert c.is_configured() is False
    assert c.get_all_entries() == []
