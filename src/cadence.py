from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .company_resolver import resolve_canonical_company


@dataclass
class CadenceRunStats:
    invitations_queued: int = 0
    quota_skipped: int = 0
    d1_drafts_generated: int = 0
    d3_followups_generated: int = 0


class CadenceEngine:
    """SQLite-backed outbound cadence manager enforcing daily quotas and D+1/D+3 follow-up rules."""

    def __init__(self, db_path: Path, daily_invite_quota: int = 15) -> None:
        self.db_path = db_path
        self.daily_invite_quota = daily_invite_quota
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prospects (
                    prospect_id TEXT PRIMARY KEY,
                    account_owner TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role_title TEXT NOT NULL,
                    canonical_company TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    draft_message TEXT,
                    stage_updated_at TEXT NOT NULL
                )
                """
            )

    def add_prospect(
        self,
        prospect_id: str,
        account_owner: str,
        full_name: str,
        role_title: str,
        raw_company: str,
        stage: str = "NEW",
        stage_updated_at: datetime | None = None,
        draft_message: str | None = None,
    ) -> None:
        ts = (stage_updated_at or datetime.now(timezone.utc)).isoformat()
        canonical = resolve_canonical_company(raw_company)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prospects
                (prospect_id, account_owner, full_name, role_title, canonical_company, stage, draft_message, stage_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (prospect_id, account_owner, full_name, role_title, canonical, stage, draft_message, ts),
            )

    def run_daily_cycle(self, account_owner: str, now: datetime | None = None) -> CadenceRunStats:
        now_dt = now or datetime.now(timezone.utc)
        today_prefix = now_dt.strftime("%Y-%m-%d")
        stats = CadenceRunStats()

        with self._connect() as conn:
            invited_today = conn.execute(
                """
                SELECT COUNT(*) FROM prospects
                WHERE account_owner = ? AND stage = 'INVITED' AND stage_updated_at LIKE ?
                """,
                (account_owner, f"{today_prefix}%"),
            ).fetchone()[0]

            remaining_quota = max(0, self.daily_invite_quota - int(invited_today))
            new_rows = conn.execute(
                "SELECT * FROM prospects WHERE account_owner = ? AND stage = 'NEW' ORDER BY prospect_id ASC",
                (account_owner,),
            ).fetchall()

            for row in new_rows:
                if remaining_quota > 0:
                    conn.execute(
                        "UPDATE prospects SET stage = 'INVITED', stage_updated_at = ? WHERE prospect_id = ?",
                        (now_dt.isoformat(), row["prospect_id"]),
                    )
                    remaining_quota -= 1
                    stats.invitations_queued += 1
                else:
                    stats.quota_skipped += 1

            # Generate D+1 human-review drafts for prospects accepted >= 24h ago
            d1_cutoff = (now_dt - timedelta(days=1)).isoformat()
            accepted = conn.execute(
                """
                SELECT * FROM prospects
                WHERE account_owner = ? AND stage = 'ACCEPTED' AND stage_updated_at <= ?
                """,
                (account_owner, d1_cutoff),
            ).fetchall()
            for row in accepted:
                first_name = row["full_name"].split()[0]
                draft = (
                    f"Olá {first_name}, obrigado pela conexão! Vi sua atuação como {row['role_title']} "
                    f"na {row['canonical_company']} e gostaria de compartilhar um benchmark rápido do setor."
                )
                conn.execute(
                    "UPDATE prospects SET stage = 'DRAFT_D1', draft_message = ?, stage_updated_at = ? WHERE prospect_id = ?",
                    (draft, now_dt.isoformat(), row["prospect_id"]),
                )
                stats.d1_drafts_generated += 1

            # Generate D+3 follow-up drafts for D1 messages sent >= 3 days ago without reply
            d3_cutoff = (now_dt - timedelta(days=3)).isoformat()
            sent_d1 = conn.execute(
                """
                SELECT * FROM prospects
                WHERE account_owner = ? AND stage = 'SENT_D1' AND stage_updated_at <= ?
                """,
                (account_owner, d3_cutoff),
            ).fetchall()
            for row in sent_d1:
                first_name = row["full_name"].split()[0]
                draft = f"Olá {first_name}, retomando rapidamente minha mensagem anterior — faz sentido conversarmos 10 min esta semana?"
                conn.execute(
                    "UPDATE prospects SET stage = 'FOLLOWUP_D3', draft_message = ?, stage_updated_at = ? WHERE prospect_id = ?",
                    (draft, now_dt.isoformat(), row["prospect_id"]),
                )
                stats.d3_followups_generated += 1

        return stats

    def list_drafts_for_review(self, account_owner: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT prospect_id, full_name, canonical_company, stage, draft_message
                FROM prospects
                WHERE account_owner = ? AND stage IN ('DRAFT_D1', 'FOLLOWUP_D3')
                ORDER BY prospect_id ASC
                """,
                (account_owner,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_prospects(
        self,
        account_owner: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if account_owner and account_owner != "all":
            clauses.append("account_owner = ?")
            params.append(account_owner)
        if start_date:
            clauses.append("substr(stage_updated_at, 1, 10) >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("substr(stage_updated_at, 1, 10) <= ?")
            params.append(end_date)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM prospects {where_sql} ORDER BY stage_updated_at DESC, prospect_id ASC",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_quota_summary(self, account_owner: str, now: datetime | None = None) -> dict[str, Any]:
        now_dt = now or datetime.now(timezone.utc)
        today_prefix = now_dt.strftime("%Y-%m-%d")
        week_cutoff = (now_dt - timedelta(days=7)).isoformat()
        with self._connect() as conn:
            if account_owner == "all":
                daily_used = conn.execute(
                    "SELECT COUNT(*) FROM prospects WHERE stage = 'INVITED' AND stage_updated_at LIKE ?",
                    (f"{today_prefix}%",),
                ).fetchone()[0]
                weekly_used = conn.execute(
                    "SELECT COUNT(*) FROM prospects WHERE stage != 'NEW' AND stage_updated_at >= ?",
                    (week_cutoff,),
                ).fetchone()[0]
                daily_limit = self.daily_invite_quota * 2
                weekly_limit = 400
            else:
                daily_used = conn.execute(
                    "SELECT COUNT(*) FROM prospects WHERE account_owner = ? AND stage = 'INVITED' AND stage_updated_at LIKE ?",
                    (account_owner, f"{today_prefix}%"),
                ).fetchone()[0]
                weekly_used = conn.execute(
                    "SELECT COUNT(*) FROM prospects WHERE account_owner = ? AND stage != 'NEW' AND stage_updated_at >= ?",
                    (account_owner, week_cutoff),
                ).fetchone()[0]
                daily_limit = self.daily_invite_quota
                weekly_limit = 200
        return {
            "account_owner": account_owner,
            "daily_used": int(daily_used),
            "daily_limit": daily_limit,
            "weekly_used": int(weekly_used),
            "weekly_limit": weekly_limit,
        }

    def approve_draft(self, prospect_id: str, edited_message: str | None = None) -> dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prospects WHERE prospect_id = ?", (prospect_id,)).fetchone()
            if not row:
                raise KeyError(prospect_id)
            next_stage = "SENT_D1" if row["stage"] == "DRAFT_D1" else "SENT_D3"
            msg = edited_message.strip() if edited_message is not None else (row["draft_message"] or "")
            conn.execute(
                "UPDATE prospects SET stage = ?, draft_message = ?, stage_updated_at = ? WHERE prospect_id = ?",
                (next_stage, msg, now_iso, prospect_id),
            )
            return dict(conn.execute("SELECT * FROM prospects WHERE prospect_id = ?", (prospect_id,)).fetchone())

    def promote_to_crm(self, prospect_id: str) -> dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM prospects WHERE prospect_id = ?", (prospect_id,)).fetchone()
            if not row:
                raise KeyError(prospect_id)
            conn.execute(
                "UPDATE prospects SET stage = 'CRM_SYNCED', stage_updated_at = ? WHERE prospect_id = ?",
                (now_iso, prospect_id),
            )
            return dict(conn.execute("SELECT * FROM prospects WHERE prospect_id = ?", (prospect_id,)).fetchone())

    def seed_demo_if_empty(self) -> None:
        if self.list_prospects():
            return
        now = datetime.now(timezone.utc)
        samples = [
            ("P-101", "sdr_ana", "Carlos Mendes", "Diretor de Operações", "Acme Cloud Brasil Ltda", "NEW", now, None),
            ("P-102", "sdr_ana", "Fernanda Lima", "Head de Produto", "Vortex Logistica S.A.", "INVITED", now - timedelta(hours=3), None),
            ("P-103", "sdr_ana", "Juliana Rocha", "VP Comercial", "Acme Sistemas", "DRAFT_D1", now - timedelta(days=1), "Olá Juliana, obrigado pela conexão! Vi sua atuação como VP Comercial na Acme Cloud e gostaria de compartilhar um benchmark rápido do setor."),
            ("P-104", "sdr_ana", "Pedro Costa", "CTO", "Vortex Transportes", "FOLLOWUP_D3", now - timedelta(days=3), "Olá Pedro, retomando rapidamente minha mensagem anterior — faz sentido conversarmos 10 min esta semana?"),
            ("P-105", "sdr_ana", "Beatriz Nogueira", "Diretora Financeira", "Horizonte Varejo", "ACCEPTED", now - timedelta(days=2), None),
            ("P-201", "sdr_lucas", "Rafael Gomes", "Gerente de Engenharia", "Nova Pay S.A.", "NEW", now, None),
            ("P-202", "sdr_lucas", "Camila Duarte", "COO", "Vortex Logistica", "SENT_D1", now - timedelta(days=4), "Olá Camila, obrigado pela conexão!"),
            ("P-203", "sdr_lucas", "Thiago Barros", "Head de Dados", "Acme Cloud Brasil", "CRM_SYNCED", now - timedelta(days=1), "Reunião agendada para quinta-feira às 15h."),
        ]
        for pid, owner, name, role, comp, stg, ts, draft in samples:
            self.add_prospect(pid, owner, name, role, comp, stg, ts, draft_message=draft)
