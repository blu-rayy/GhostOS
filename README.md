# GhostOS

**Your paperwork never leaves your laptop, and nothing moves without your say-so.**

GhostOS is a desktop workspace that organizes messy folders of receipts, invoices, and notes into tidy dated folders — and drafts your expense report along the way. A small AI model running **entirely on your own computer** reads each file, tells you what it found, and flags anything it's unsure about. You review, you approve, and only then does anything move. Changed your mind? One click puts everything back.

Built for the **AppBuildersPH Hackathon 2026**.

## Why it exists

Freelancers, small businesses, and anyone drowning in PDFs share one miserable chore: turning a pile of receipts into organized records and expense totals. Cloud tools can do it — by uploading your financial life to someone else's server. GhostOS does it **offline, on-device**, so bank statements, IDs, and medical papers are never sent anywhere.

## How it works

1. **Pick a folder** — a messy mix of PDFs, text files, and CSVs (up to 100 files).
2. **GhostOS reads everything locally.** An on-device model (Ollama) classifies each file — receipt, invoice, statement, ID, or "not sure" — and pulls out shop, date, amount, and currency, with the exact quote it read them from.
3. **It's honest about doubt.** Conflicting totals, missing dates, unreadable scans, and even sneaky text inside files trying to give it orders get *flagged for you* instead of guessed. A birth certificate is never forced into an expense row.
4. **You check its work.** Confirm, fix, or set aside each flagged file. Set-aside files are never counted and never move early.
5. **You preview the plan.** Exact destination for every file (`Receipts/2026-09/`, …) plus expense totals — before anything happens.
6. **You approve.** One "Move" press reorganizes the folders and writes the expense CSV.
7. **You can undo.** Everything goes back to where it was.

## Safety design (the part we're proud of)

- **Local-first:** inference at `127.0.0.1:11434`, backend at `127.0.0.1:8000`, zero external requests. Works with Wi-Fi off.
- **The model never decides anything destructive:** destinations come from a fixed backend map, never from model output; money is handled as exact decimals, never floats.
- **Evidence or it didn't happen:** every extracted amount must appear verbatim in the source text; conflicting or unsupported amounts are rejected, never counted.
- **No silent failures:** symlinks, oversized, and unreadable files are skipped with reasons; collisions get numeric suffixes, never overwrites; every move is recorded in an undo manifest.

## Run it

You need **Python 3.11+**, **Node.js 20.19+**, and (for real inference) **Ollama** with the model pre-pulled.

```powershell
# 1. Local AI (one-time)
ollama pull qwen3:4b-instruct
ollama serve

# 2. Backend (from backend/)
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Frontend (from frontend/)
npm install
npm run dev:browser        # http://127.0.0.1:5173
```

By default the UI runs on **built-in demo data** (look for the demo badge) so you can click through the whole flow with no setup. To use the live backend, create `frontend/.env.local`:

```
VITE_USE_FIXTURES=false
VITE_API_BASE=http://127.0.0.1:8000
```

A 20-file sample folder with edge cases (duplicates, collisions, conflicts, statements, prompt injection) lives in `tests/fixtures/sample_folder/`.

## Verify it

```powershell
# Backend (from backend/, venv activated)
python -m pytest          # full suite

# Frontend (from frontend/)
npm run typecheck
npm run lint
npm test
npm run build
```

## Project layout

| Path | What |
|---|---|
| `backend/app/` | FastAPI service: scanning, extraction, local-AI classification, validation, plan preview, approval, undo |
| `backend/tests/` | Contract, validation, and session tests |
| `frontend/src/` | React + TypeScript UI (browser + Electron): Check → Totals → Done flow, paper design system |
| `frontend/src/api/` | `GhostApi` interface, HTTP client, and the fixture mock used for demos |
| `tests/fixtures/sample_folder/` | 20-file demo dataset covering the edge cases |
| `tests/reports/` | QA evidence: acceptance logs, retest reports, model evaluations |
| `docs/` | Product plan, API handoff, design screens, QA strategy |
| `context.md` | Working reference: mission, phases, and team ownership |

## Team

| Developer | Ownership |
|---|---|
| John Janiel Obmerga | Backend foundation, API contracts, scanning, safe paths, commit/undo |
| Kurt Laurence Tendero | Ollama/local model, classification, validation, offline verification |
| Kristian David Bautista | Frontend/desktop UI, evidence and approval experience, pitch and submission |
| Jhon Vincent Libatique | Test dataset, fixtures, QA, integration, demo support |
