import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import { VitePWA } from 'vite-plugin-pwa';
// https://vite.dev/config/
export default defineConfig({
    plugins: [
        vue(),
        vueDevTools(),
        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'maskable-icon-*.png', 'android-icon-*.png'],
            workbox: {
                globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2,ttf}'],
                navigateFallback: 'index.html',
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
                manualChunks: {
                    // Split vendor libraries for better caching
                    'vue-vendor': ['vue', 'vue-router'],
                    'chart-vendor': ['chart.js']
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
            overlay: false // Disable error overlay for better development experience
        }
    }
});
