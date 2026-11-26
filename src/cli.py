from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cadence import CadenceEngine
from .server import run_studio_server


def main() -> None:
    parser = argparse.ArgumentParser(description="B2B Outbound Cadence Engine")
    parser.add_argument("--demo", action="store_true", help="Executa simulação CLI de cadência D+1 / D+3")
    parser.add_argument("--serve", action="store_true", help="Inicia o painel web Kanban & Cadence Studio")
    parser.add_argument("--port", type=int, default=8016, help="Porta HTTP do painel web (padrão: 8016)")
    args = parser.parse_args()

    if args.serve:
        engine = CadenceEngine(Path("data/cadence_studio.db"), daily_invite_quota=15)
        run_studio_server(engine, port=args.port)
        return

    if not args.demo:
        print("Use --demo para simular no terminal ou --serve para abrir o Kanban Web Studio.")
        return

    now = datetime.now(timezone.utc)
    engine = CadenceEngine(Path("data/cadence_demo.db"), daily_invite_quota=2)
    engine.add_prospect("P-1", "sdr_ana", "Carlos Mendes", "Diretor de Operações", "Acme Cloud Brasil", "NEW", now)
    engine.add_prospect("P-2", "sdr_ana", "Fernanda Lima", "Head de Produto", "Vortex Logistica S.A.", "NEW", now)
    engine.add_prospect("P-3", "sdr_ana", "Rafael Gomes", "Gerente de TI", "Nova Pay", "NEW", now)
    engine.add_prospect("P-4", "sdr_ana", "Juliana Rocha", "VP Comercial", "Acme Tech", "ACCEPTED", now - timedelta(days=2))
    engine.add_prospect("P-5", "sdr_ana", "Pedro Costa", "CTO", "Vortex Transportes", "SENT_D1", now - timedelta(days=4))

    stats = engine.run_daily_cycle("sdr_ana", now=now)
    print(
        f"Ciclo concluído -> Convites: {stats.invitations_queued} | Bloqueados pela cota: {stats.quota_skipped} | "
        f"Rascunhos D+1: {stats.d1_drafts_generated} | Follow-ups D+3: {stats.d3_followups_generated}"
    )
    for d in engine.list_drafts_for_review("sdr_ana"):
        print(f"  [{d['stage']}] {d['full_name']} ({d['canonical_company']}): {d['draft_message']}")


if __name__ == "__main__":
    main()
