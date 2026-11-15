"""
Selector de la bandeja de apuntes rápidos: LifeDeck si está activado y configurado; si no, Notion.

Ambos clientes comparten interfaz: is_configured(), test_connection(), get_all_entries(),
delete_entry(id). LifeDeck además tiene ack(ids, status) / discard(ids).
"""
from __future__ import annotations

from typing import Any, List


def get_inbox_client() -> Any:
    from src.integrations.lifedeck import LifeDeckClient

    lifedeck = LifeDeckClient()
    if lifedeck.enabled and lifedeck.is_configured():
        return lifedeck
    from src.integrations.notion import get_notion_client

    return get_notion_client()


def source_name(client: Any) -> str:
    return getattr(client, "source_name", "Notion")


def is_lifedeck(client: Any) -> bool:
    return source_name(client) == "LifeDeck"


def mark_imported(ids: List[str]) -> int:
    """Tras importar al ledger: LifeDeck → 'imported'; Notion → archivar página. Nunca lanza."""
    return _apply(ids, "imported")


def mark_discarded(ids: List[str]) -> int:
    """Descartar sin importar: LifeDeck → 'discarded'; Notion → archivar página. Nunca lanza."""
    return _apply(ids, "discarded")


def _apply(ids: List[str], status: str) -> int:
    ids = [i for i in ids if i]
    if not ids:
        return 0
    try:
        client = get_inbox_client()
        if not client.is_configured():
            return 0
        if hasattr(client, "ack"):
            return client.ack(ids, status)
        return sum(1 for pid in ids if client.delete_entry(pid))
    except Exception:
        return 0
