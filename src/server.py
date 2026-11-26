"""Zero-dependency Web Kanban & Human-in-the-Loop Cadence Studio."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .cadence import CadenceEngine

STUDIO_HTML = """<!doctype html>
<html lang="pt-BR" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>B2B Outbound Cadence Studio — Kanban &amp; Follow-up</title>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root, [data-theme="dark"] {
      --bg: #050a0f;
      --surface: #0b1219;
      --surface-2: #111b24;
      --surface-hover: #172430;
      --text: #f0f7fc;
      --muted: #9ab3c8;
      --accent: #d4f1ff;
      --accent-ink: #050a0f;
      --accent-soft: rgba(212, 241, 255, 0.11);
      --accent-border: rgba(212, 241, 255, 0.34);
      --border: rgba(212, 241, 255, 0.14);
      --ok-bg: rgba(52, 211, 153, 0.15);
      --ok-text: #6ee7b7;
      --warn-bg: rgba(251, 191, 36, 0.15);
      --warn-text: #fcd34d;
    }
    [data-theme="light"] {
      --bg: #f0f7fc;
      --surface: #ffffff;
      --surface-2: #e3eef6;
      --surface-hover: #d5e5f1;
      --text: #050a0f;
      --muted: #395064;
      --accent: #050a0f;
      --accent-ink: #f0f7fc;
      --accent-soft: rgba(5, 10, 15, 0.08);
      --accent-border: rgba(5, 10, 15, 0.3);
      --border: rgba(5, 10, 15, 0.14);
      --ok-bg: #ecfdf5;
      --ok-text: #047857;
      --warn-bg: #fffbeb;
      --warn-text: #b45309;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      transition: background-color 0.25s ease, color 0.25s ease;
    }
    .shell-header {
      padding: 16px max(24px, calc((100% - 1320px) / 2));
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem;
    }
    .brand { display: flex; align-items: center; gap: 0.85rem; }
    .logo-mark {
      width: 38px; height: 38px; border-radius: 10px;
      background: var(--accent); color: var(--accent-ink);
      display: grid; place-items: center; font-weight: 900; font-size: 0.85rem;
    }
    .brand-title { font-weight: 800; font-size: 1.06rem; }
    .brand-sub { font-size: 0.76rem; color: var(--muted); }
    .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; }
    select, input[type="date"] {
      padding: 0.48rem 0.75rem; border-radius: 9px; border: 1px solid var(--border);
      background: var(--surface-2); color: var(--text); font: inherit; font-size: 0.82rem; font-weight: 600;
    }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
      padding: 0.5rem 0.9rem; border-radius: 9px; border: 1px solid var(--border);
      background: var(--surface-2); color: var(--text); font: inherit; font-size: 0.82rem;
      font-weight: 700; cursor: pointer;
    }
    .btn:hover { background: var(--surface-hover); border-color: var(--accent-border); }
    .btn-primary { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
    .btn-sm { padding: 0.34rem 0.65rem; font-size: 0.74rem; border-radius: 7px; }
    .quota-pill {
      font-family: "JetBrains Mono", monospace; font-size: 0.75rem; padding: 0.42rem 0.8rem;
      border-radius: 999px; background: var(--accent-soft); border: 1px solid var(--accent-border); color: var(--accent);
    }

    .shell-body {
      width: min(1320px, calc(100% - 40px));
      margin: 0 auto;
      padding: 22px 0 44px;
    }
    .filter-strip {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.8rem;
      padding: 12px 16px; border-radius: 12px; background: var(--surface-2); border: 1px solid var(--border);
      margin-bottom: 18px; font-size: 0.82rem;
    }
    .kanban {
      display: grid;
      grid-template-columns: repeat(5, minmax(235px, 1fr));
      gap: 14px;
      overflow-x: auto;
      padding-bottom: 8px;
    }
    .col {
      background: var(--surface-2); border: 1px solid var(--border); border-radius: 14px;
      padding: 12px; min-height: 440px; display: flex; flex-direction: column; gap: 10px;
    }
    .col-head {
      display: flex; align-items: center; justify-content: space-between;
      padding-bottom: 8px; border-bottom: 1px solid var(--border); font-size: 0.8rem; font-weight: 800;
    }
    .count {
      font-family: "JetBrains Mono", monospace; font-size: 0.72rem; padding: 2px 7px;
      border-radius: 999px; background: var(--surface); border: 1px solid var(--border); color: var(--accent);
    }
    .p-card {
      background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent);
      border-radius: 10px; padding: 11px; display: flex; flex-direction: column; gap: 5px;
    }
    .p-name { font-weight: 700; font-size: 0.88rem; }
    .p-role { font-size: 0.77rem; color: var(--muted); }
    .mono { font-family: "JetBrains Mono", monospace; font-size: 0.71rem; color: var(--muted); }
    .draft-preview {
      font-size: 0.76rem; padding: 7px 8px; border-radius: 7px;
      background: var(--warn-bg); color: var(--warn-text); line-height: 1.4; margin-top: 3px;
    }
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: none;
      place-items: center; padding: 20px; z-index: 50;
    }
    .modal-backdrop.open { display: grid; }
    .modal {
      width: min(520px, 100%); background: var(--surface-2); border: 1px solid var(--accent-border);
      border-radius: 16px; padding: 1.4rem;
    }
    textarea {
      width: 100%; min-height: 120px; padding: 10px; border-radius: 9px;
      border: 1px solid var(--border); background: var(--bg); color: var(--text); font: inherit; font-size: 0.86rem;
    }
    .toast {
      position: fixed; right: 24px; bottom: 24px; padding: 0.75rem 1.1rem; border-radius: 10px;
      background: var(--accent); color: var(--accent-ink); font-weight: 700; font-size: 0.83rem;
      opacity: 0; pointer-events: none; transition: opacity 0.2s ease;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <header class="shell-header">
    <div class="brand">
      <span class="logo-mark">B2B</span>
      <div>
        <div class="brand-title">B2B Outbound Cadence Engine</div>
        <div class="brand-sub">Multi-Conta · Cota Diária/Semanal · Revisão Humana D+1 / D+3 · Sync CRM</div>
      </div>
    </div>
    <div class="controls">
      <select id="accountSelect">
        <option value="all">Todas as Contas</option>
        <option value="sdr_ana" selected>Conta: sdr_ana</option>
        <option value="sdr_lucas">Conta: sdr_lucas</option>
      </select>
      <span id="quotaBadge" class="quota-pill">--/200 convites na semana</span>
      <button id="runCycleBtn" type="button" class="btn btn-primary">⚡ Rodar Ciclo Diário</button>
      <button id="themeToggle" type="button" class="btn" style="border-radius:999px">
        <span id="themeIcon">☀</span> <span id="themeLabel">Modo Claro</span>
      </button>
    </div>
  </header>

  <main class="shell-body">
    <div class="filter-strip">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.55rem">
        <strong>Filtro de Atividade (Data / Período):</strong>
        <label>De <input type="date" id="startDate" /></label>
        <label>Até <input type="date" id="endDate" /></label>
        <button id="clearDatesBtn" type="button" class="btn btn-sm">Limpar Período</button>
      </div>
      <span class="mono" id="summaryText">Carregando pipeline...</span>
    </div>

    <section class="kanban" id="kanbanBoard"></section>
  </main>

  <div id="draftModal" class="modal-backdrop">
    <div class="modal">
      <div class="mono" id="mMeta">Revisão Human-in-the-Loop</div>
      <h3 id="mTitle" style="margin:4px 0 10px">Revisar Rascunho</h3>
      <textarea id="mDraft"></textarea>
      <div style="display:flex;justify-content:flex-end;gap:0.5rem;margin-top:0.9rem">
        <button type="button" class="btn" onclick="closeModal()">Cancelar</button>
        <button type="button" class="btn btn-primary" id="mApproveBtn">Aprovar e Disparar</button>
      </div>
    </div>
  </div>

  <div id="toast" class="toast"></div>

  <script>
    const COLUMNS = [
      { key: "NEW_INVITED", title: "Fila & Convites", stages: ["NEW", "INVITED"] },
      { key: "ACCEPTED", title: "Aceitos (Aguard. D+1)", stages: ["ACCEPTED"] },
      { key: "REVIEW", title: "Revisão Humana (D+1/D+3)", stages: ["DRAFT_D1", "FOLLOWUP_D3"] },
      { key: "SENT", title: "Em Cadência Ativa", stages: ["SENT_D1", "SENT_D3"] },
      { key: "CRM", title: "Exportados ao CRM", stages: ["CRM_SYNCED"] },
    ];

    const root = document.documentElement;
    function applyTheme(t) {
      root.setAttribute("data-theme", t);
      localStorage.setItem("b2b-theme", t);
      document.getElementById("themeIcon").textContent = t === "light" ? "☾" : "☀";
      document.getElementById("themeLabel").textContent = t === "light" ? "Modo Escuro" : "Modo Claro";
    }
    applyTheme(localStorage.getItem("b2b-theme") || "dark");
    document.getElementById("themeToggle").addEventListener("click", () => {
      applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });

    function toast(msg) {
      const el = document.getElementById("toast");
      el.textContent = msg;
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 2500);
    }

    let prospects = [];
    let editingId = null;

    async function loadBoard() {
      const owner = document.getElementById("accountSelect").value;
      const s = document.getElementById("startDate").value;
      const e = document.getElementById("endDate").value;
      const qs = new URLSearchParams({ account: owner });
      if (s) qs.set("start_date", s);
      if (e) qs.set("end_date", e || s);

      const [listResp, quotaResp] = await Promise.all([
        fetch(`/api/prospects?${qs}`),
        fetch(`/api/quota?account=${encodeURIComponent(owner)}`),
      ]);
      prospects = await listResp.json();
      const quota = await quotaResp.json();
      document.getElementById("quotaBadge").textContent =
        `${quota.weekly_used}/${quota.weekly_limit} sem · ${quota.daily_used}/${quota.daily_limit} hoje`;
      document.getElementById("summaryText").textContent =
        `${prospects.length} lead(s) exibidos · empresa canônica normalizada`;

      const board = document.getElementById("kanbanBoard");
      board.innerHTML = "";
      COLUMNS.forEach(col => {
        const items = prospects.filter(p => col.stages.includes(p.stage));
        const colEl = document.createElement("div");
        colEl.className = "col";
        colEl.innerHTML = `<div class="col-head"><span>${col.title}</span><span class="count">${items.length}</span></div>`;
        items.forEach(p => {
          const card = document.createElement("div");
          card.className = "p-card";
          const draftHtml = p.draft_message && ["DRAFT_D1", "FOLLOWUP_D3"].includes(p.stage)
            ? `<div class="draft-preview">${p.draft_message}</div>`
            : "";
          let btns = "";
          if (["DRAFT_D1", "FOLLOWUP_D3"].includes(p.stage)) {
            btns = `<button class="btn btn-sm btn-primary" onclick="openReview('${p.prospect_id}')">Revisar &amp; Enviar</button>`;
          } else if (p.stage !== "CRM_SYNCED") {
            btns = `<button class="btn btn-sm" onclick="syncCrm('${p.prospect_id}')">Exportar CRM</button>`;
          }
          card.innerHTML = `
            <div class="mono">${p.stage} · ${p.account_owner} · ${p.stage_updated_at.slice(0, 10)}</div>
            <div class="p-name">${p.full_name}</div>
            <div class="p-role">${p.role_title} · <strong>${p.canonical_company}</strong></div>
            ${draftHtml}
            ${btns ? `<div style="margin-top:6px">${btns}</div>` : ""}
          `;
          colEl.appendChild(card);
        });
        board.appendChild(colEl);
      });
    }

    window.openReview = (id) => {
      const p = prospects.find(x => x.prospect_id === id);
      if (!p) return;
      editingId = id;
      document.getElementById("mMeta").textContent = `${p.stage} · ${p.canonical_company}`;
      document.getElementById("mTitle").textContent = `Rascunho para ${p.full_name}`;
      document.getElementById("mDraft").value = p.draft_message || "";
      document.getElementById("draftModal").classList.add("open");
    };

    window.closeModal = () => {
      document.getElementById("draftModal").classList.remove("open");
      editingId = null;
    };

    document.getElementById("mApproveBtn").addEventListener("click", async () => {
      if (!editingId) return;
      await fetch(`/api/prospects/${editingId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft_message: document.getElementById("mDraft").value }),
      });
      closeModal();
      toast("Mensagem aprovada e disparada na cadência!");
      loadBoard();
    });

    window.syncCrm = async (id) => {
      await fetch(`/api/prospects/${id}/crm`, { method: "POST" });
      toast(`Lead ${id} sincronizado com o CRM!`);
      loadBoard();
    };

    document.getElementById("runCycleBtn").addEventListener("click", async () => {
      const owner = document.getElementById("accountSelect").value === "all" ? "sdr_ana" : document.getElementById("accountSelect").value;
      const res = await (await fetch("/api/run-cycle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_owner: owner }),
      })).json();
      toast(`Ciclo ${owner}: +${res.invitations_queued} convites, +${res.d1_drafts_generated} D+1, +${res.d3_followups_generated} D+3`);
      loadBoard();
    });

    ["accountSelect", "startDate", "endDate"].forEach(id => {
      document.getElementById(id).addEventListener("change", loadBoard);
    });
    document.getElementById("clearDatesBtn").addEventListener("click", () => {
      document.getElementById("startDate").value = "";
      document.getElementById("endDate").value = "";
      loadBoard();
    });

    loadBoard();
  </script>
</body>
</html>
"""


def run_studio_server(engine: CadenceEngine, host: str = "127.0.0.1", port: int = 8016) -> None:
    engine.seed_demo_if_empty()

    class StudioHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: object, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/api/prospects":
                account = (qs.get("account") or ["all"])[0]
                start_d = (qs.get("start_date") or [None])[0]
                end_d = (qs.get("end_date") or [None])[0]
                self._send_json(engine.list_prospects(account, start_d, end_d))
                return
            if parsed.path == "/api/quota":
                account = (qs.get("account") or ["sdr_ana"])[0]
                self._send_json(engine.get_quota_summary(account))
                return
            body = STUDIO_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/run-cycle":
                data = self._read_json()
                owner = data.get("account_owner", "sdr_ana")
                st = engine.run_daily_cycle(owner)
                self._send_json(
                    {
                        "invitations_queued": st.invitations_queued,
                        "quota_skipped": st.quota_skipped,
                        "d1_drafts_generated": st.d1_drafts_generated,
                        "d3_followups_generated": st.d3_followups_generated,
                    }
                )
                return
            if parsed.path.startswith("/api/prospects/") and parsed.path.endswith("/approve"):
                pid = parsed.path.split("/")[3]
                data = self._read_json()
                self._send_json(engine.approve_draft(pid, data.get("draft_message")))
                return
            if parsed.path.startswith("/api/prospects/") and parsed.path.endswith("/crm"):
                pid = parsed.path.split("/")[3]
                self._send_json(engine.promote_to_crm(pid))
                return
            self.send_error(404)

    httpd = HTTPServer((host, port), StudioHandler)
    print(f"B2B Outbound Cadence Studio rodando em http://{host}:{port}")
    httpd.serve_forever()
