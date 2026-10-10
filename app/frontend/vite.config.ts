import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

function retryableSettingsPanelHost(): Plugin {
  const publicPath = '/assets/settings-panel-host-loader.js'
  const panelHostModule = fileURLToPath(new URL('./src/components/settings/SettingsPanelHost.vue', import.meta.url))

  return {
    name: 'streamvault-retryable-settings-panel-host',
    configureServer(server) {
      server.middlewares.use(publicPath, (_request, response) => {
        response.statusCode = 200
        response.setHeader('Content-Type', 'application/javascript')
        response.setHeader('Cache-Control', 'no-store')
        response.end(
          'export const loadSettingsPanelHost = (attempt) => ' +
          'import(`/src/components/settings/SettingsPanelHost.vue?retry=${encodeURIComponent(attempt)}`)'
        )
      })
    },
    generateBundle(_options, bundle) {
      const panelHostOutput = Object.values(bundle).find(
        output => output.type === 'chunk' && panelHostModule in output.modules,
      )
      if (!panelHostOutput || panelHostOutput.type !== 'chunk') {
        this.error('SettingsPanelHost output chunk was not generated')
      }
      const panelHostChunk = panelHostOutput.fileName
      const relativePanelHostChunk = panelHostChunk.replace(/^assets\//, './')
      const panelHostCss = [...(
        panelHostOutput as typeof panelHostOutput & {
          viteMetadata?: { importedCss?: Set<string> }
        }
      ).viteMetadata?.importedCss ?? []]
      if (panelHostCss.length === 0) {
        this.error('SettingsPanelHost CSS output was not generated')
      }
      const relativePanelHostCss = panelHostCss.map(fileName => fileName.replace(/^assets\//, './'))

      // The loader itself is stable and cacheable. Every call imports the real
      // compiled panel chunk at a unique URL, so a rejected browser module-map
      // entry cannot poison a later user retry. Because this generated import
      // bypasses Vite's normal preload wrapper, restore the chunk's extracted
      // CSS dependency explicitly and resolve only after it has loaded.
      this.emitFile({
        type: 'asset',
        fileName: publicPath.slice(1),
        source: `const panelUrl=${JSON.stringify(relativePanelHostChunk)},panelCssUrls=${JSON.stringify(relativePanelHostCss)};
const loadCss=(path,attempt)=>{const url=new URL(path,import.meta.url);if([...document.styleSheets].some(({href})=>href&&new URL(href).pathname===url.pathname))return;return new Promise((resolve,reject)=>{const link=document.createElement('link');link.rel='stylesheet';link.href=url.href+'?retry='+encodeURIComponent(attempt);link.onload=()=>resolve();link.onerror=()=>{link.remove();reject(new Error('Settings panel stylesheet could not be loaded'))};document.head.append(link)})};
export const loadSettingsPanelHost=async attempt=>{const[,panelModule]=await Promise.all([Promise.all(panelCssUrls.map(url=>loadCss(url,attempt))),import(panelUrl+'?retry='+encodeURIComponent(attempt))]);return panelModule};
`,
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    retryableSettingsPanelHost(),
    VitePWA({
      registerType: 'autoUpdate',
      // Workbox globs already enumerate these public static assets. Keep the
      // manifest metadata, but do not register a second copy in precache.
      includeAssets: [],
      includeManifestIcons: false,
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2,ttf}'],
        navigateFallback: 'index.html',
        // The backend appends its canonical /pwa/push-sw.js import when it
        // serves /sw.js. Do not generate a root-relative helper import: that
        // route is intentionally not a public static asset in production.
        // Prevent service worker from intercepting API, auth, and WebSocket paths
        navigateFallbackDenylist: [/^\/api\//, /^\/auth\//, /^\/ws/, /^\/eventsub/, /^\/health/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365 // 1 year
              }
            }
          }
        ]
      },
      manifest: {
        name: 'StreamVault',
        short_name: 'StreamVault',
        description: 'Manage and monitor your Twitch streamers',
        theme_color: '#2a2c33',
        background_color: '#1a1b20',
        start_url: '/?source=pwa',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait-primary',
        icons: [
          {
            src: '/android-icon-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          },
          {
            src: '/maskable-icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable'
          },
          {
            src: '/maskable-icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable'
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    // PERFORMANCE OPTIMIZATION
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Split vendor libraries for better caching
          if (id.includes('node_modules/vue/') || id.includes('node_modules/vue-router/')) {
            return 'vue-vendor'
          }
        }
      }
    },
    // Default minification is esbuild, which is faster for development
    minify: true,
    // Force empty output directory to prevent build errors
    emptyOutDir: true,
    // More robust output directory handling
    outDir: 'dist'
  },
  // Development optimization
  server: {
    hmr: {
      overlay: false  // Disable error overlay for better development experience
    }
  }
})