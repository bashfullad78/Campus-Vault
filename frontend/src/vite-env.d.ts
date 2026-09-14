/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public origin of the FastAPI backend, e.g. https://your-api.onrender.com */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
