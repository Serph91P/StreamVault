/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_APP_TITLE: string
    // Add other env variables you use
  }
  
  interface ImportMeta {
    readonly env: ImportMetaEnv
  }