# GhostOS frontend

React + TypeScript + Vite UI for GhostOS.

```sh
npm install
npm run dev        # http://localhost:5173, runs on JSON fixtures by default
npm run build      # type-check and production build
npm run lint
```

## Fixtures vs. real backend

By default the app uses an in-memory mock ([src/api/mock.ts](src/api/mock.ts)) fed by
[src/fixtures/](src/fixtures/). To use the FastAPI service instead, create `.env.local`:

```
VITE_USE_FIXTURES=false
VITE_API_BASE=http://127.0.0.1:8000
```

The status bar shows a **Fixture data** badge whenever the mock is active.

## Layout

| Path | What |
|---|---|
| `src/types/api.ts` | Shared API shapes (proposed contract; Developer 1 owns the canonical schema) |
| `src/api/` | `GhostApi` interface, HTTP client, fixture mock |
| `src/fixtures/` | `scan.json` (18 documents and 5 skipped files covering edge cases), `status.json` |
| `src/components/` | Stepper, FolderSelect, ReviewView + DocumentCard, PlanView, StatusBar |
| `src/lib/money.ts` | Decimal-string arithmetic (BigInt cents, so no float rounding) |

See [../docs/frontend-api-handoff.md](../docs/frontend-api-handoff.md) for the field list and open questions.
