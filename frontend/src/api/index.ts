import type { GhostApi } from './client'
import { httpApi } from './http'
import { mockApi } from './mock'

// Fixtures are the default until the backend is ready.
// Run `VITE_USE_FIXTURES=false npm run dev` (or set it in .env.local) to hit FastAPI.
export const USING_FIXTURES = import.meta.env.VITE_USE_FIXTURES !== 'false'

export const api: GhostApi = USING_FIXTURES ? mockApi : httpApi
