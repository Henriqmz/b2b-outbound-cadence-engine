# B2B Outbound Cadence Engine (Prospecção & Follow-up D+1 / D+3)

Motor em Python + SQLite para gestão segura de cadências de prospecção B2B outbound: aplica **resolução/normalização de empresa-alvo**, **teto diário por conta** (rate limit para evitar bloqueios), controle de estágios (`NEW` → `INVITED` → `ACCEPTED` → `DRAFT_D1` → `FOLLOWUP_D3`), geração de rascunhos personalizados para **revisão humana** (Human-in-the-Loop) e relatório consolidado de fechamento diário.

## Recursos

- **Resolução de Empresa-Alvo:** agrupa variações de nomes/subsidiárias em um catálogo canônico (`company_resolver.py`).
- **Rate Limiting Diário:** impede ultrapassar a cota diária de abordagens por perfil/conta.
- **Cadência D+1 e D+3:** promove automaticamente contatos aceitos há ≥ 1 dia para rascunho de abordagem inicial e contatos sem resposta há ≥ 3 dias para follow-up.
- **Revisão Humana Obrigatória:** mensagens nunca são disparadas sem aprovação; o motor prepara rascunhos prontos em fila.

## Como Executar

```bash
python -m src.cli --demo
pytest -v
```
