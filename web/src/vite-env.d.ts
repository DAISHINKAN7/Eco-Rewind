/// <reference types="vite/client" />
interface ImportMetaEnv {
  /** Optional absolute URL of the data folder (results.json, maps.json, layers/, pixels/, lab/), with CORS enabled. */
  readonly VITE_DATA_BASE?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv }
