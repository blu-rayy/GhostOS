# GhostOS frontend

One React + TypeScript + Vite UI that runs in the browser (Chrome/Edge, with HMR) and inside Electron.
It talks to the local FastAPI backend through `src/api`, or to an in-memory fixture mock by default.

## Requirements

- Node.js 20.19+ or 22.12+ (Vite 8), npm 10+

## Commands (run from `frontend/`)

```powershell
npm install
npm run dev:browser    # Vite at http://127.0.0.1:5173 (browser-first development, HMR)
npm run dev:electron   # Electron window against an already-running Vite server
npm run dev            # both of the above together
npm run build          # type-check + production build to dist/
npm run lint           # oxlint
npm run electron:preview   # build, then open dist/ in Electron
```

## Fixtures vs. real backend

By default the app uses the in-memory mock ([src/api/mock.ts](src/api/mock.ts)) fed by
[src/fixtures/](src/fixtures/). The UI shows a **Fixture data** badge whenever the mock is active.
To call FastAPI instead, create `.env.local`:

```
VITE_USE_FIXTURES=false
VITE_API_BASE=http://127.0.0.1:8000
```

In fixture mode, Settings → *Demo scenarios* can make the mock fail a scan halfway or report an undo conflict.
Both are off by default.

## Layout

| Path | What |
|---|---|
| `src/types/api.ts` | Shared API shapes (proposed contract; Developer 1 owns the canonical schema) |
| `src/api/` | `GhostApi` interface, HTTP client, fixture mock |
| `src/fixtures/` | `scan.json` (18 documents, 5 skipped files covering edge cases), `status.json` |
| `src/platform/` | Browser and Electron adapters (folder picker, capabilities). The only way the UI reaches desktop features |
| `src/state/` | Session state and actions; every backend call goes through `api` |
| `src/lib/viewModel.ts` | Maps contract types to table rows and plan rows (pure functions) |
| `src/lib/money.ts` | Decimal-string arithmetic (BigInt cents, so no float rounding) |
| `src/components/`, `src/pages/` | Design-system components and the ten screens |
| `src/index.css` | Design tokens (Tailwind v4 `@theme`) |
| `electron/` | Main process and preload. `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` |

The preload exposes exactly `window.ghostos = { platform, version, capabilities, selectFolder }`
(typed as `ElectronBridge` in `src/platform/types.ts`). `selectFolder` returns a path string only;
the renderer has no filesystem access.

See [../docs/frontend-api-handoff.md](../docs/frontend-api-handoff.md) for the field list and open questions.
