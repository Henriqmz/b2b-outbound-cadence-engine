from __future__ import annotations

import re

CANONICAL_ALIASES: dict[str, list[str]] = {
    "Acme Cloud": ["acme", "acme tech", "acme cloud brasil", "acme sistemas"],
    "Vortex Logistics": ["vortex", "vortex logistica", "vortex transportes"],
    "Nova FinTech": ["nova pay", "nova fintech", "nova pagamentos"],
}


def resolve_canonical_company(raw_company: str) -> str:
    """Normalizes company aliases and subsidiaries into a canonical target name."""
    cleaned = re.sub(r"\s+", " ", (raw_company or "").strip().lower())
    if not cleaned:
        return "Empresa Não Informada"
    for canonical, aliases in CANONICAL_ALIASES.items():
        if any(alias in cleaned for alias in aliases):
            return canonical
    return raw_company.strip()
