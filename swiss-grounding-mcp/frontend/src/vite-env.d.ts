/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AGENT_BACKEND_URL: string;
  readonly VITE_AGENT_BACKEND_API_KEY: string;
  readonly VITE_MAPBOX_TOKEN: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
