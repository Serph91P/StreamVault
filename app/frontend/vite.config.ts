import { fileURLToPath, URL } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

function retryableSettingsPanelHost(): Plugin {
  const publicPath = '/assets/settings-panel-host.js'

  return {
    name: 'streamvault-retryable-settings-panel-host',
    configureServer(server) {
      server.middlewares.use(publicPath, (_request, response) => {
        response.statusCode = 200
        response.setHeader('Content-Type', 'application/javascript')
        response.setHeader('Cache-Control', 'no-store')
        response.end('export default true')
      })
    },
    generateBundle() {
      // The tiny availability facade receives a unique query on every retry.
      // The actual panel chunk remains a normal Vite lazy dependency and is
      // requested only after this retryable boundary succeeds.
      this.emitFile({
        type: 'asset',
        fileName: publicPath.slice(1),
        source: 'export default true',
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