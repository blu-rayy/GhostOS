/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "false" to call the real backend instead of fixtures. */
  readonly VITE_USE_FIXTURES?: string
  /** Defaults to http://127.0.0.1:8000 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
