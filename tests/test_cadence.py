from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.cadence import CadenceEngine
from src.company_resolver import resolve_canonical_company


def test_company_resolver_normalizes_aliases():
    assert resolve_canonical_company("Acme Cloud Brasil Ltda") == "Acme Cloud"
    assert resolve_canonical_company("VORTEX LOGISTICA") == "Vortex Logistics"
    assert resolve_canonical_company("Empresa Independente") == "Empresa Independente"


def test_cadence_engine_quota_and_followups(tmp_path: Path):
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    engine = CadenceEngine(tmp_path / "cadence.db", daily_invite_quota=1)
    engine.add_prospect("P1", "sdr1", "Alice Silva", "CTO", "Acme Sistemas", "NEW", now)
    engine.add_prospect("P2", "sdr1", "Bruno Reis", "COO", "Nova Fintech", "NEW", now)
    engine.add_prospect("P3", "sdr1", "Carla Dias", "VP", "Vortex Transportes", "ACCEPTED", now - timedelta(days=2))
    engine.add_prospect("P4", "sdr1", "Daniel Melo", "Head", "Acme Tech", "SENT_D1", now - timedelta(days=4))

    stats = engine.run_daily_cycle("sdr1", now=now)
    assert stats.invitations_queued == 1
    assert stats.quota_skipped == 1
    assert stats.d1_drafts_generated == 1
    assert stats.d3_followups_generated == 1

    drafts = engine.list_drafts_for_review("sdr1")
    assert len(drafts) == 2
    assert drafts[0]["canonical_company"] == "Vortex Logistics"
