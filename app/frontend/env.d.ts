/// <reference types="vite/client" />
/// <reference types="vue/ref-macros" />
/// <reference types="vite-plugin-pwa/client" />

declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
    readonly VITE_APP_TITLE: string
    // Add other env variables you use
  }
  
  interface ImportMeta {
    readonly env: ImportMetaEnv
  }