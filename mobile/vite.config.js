import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { frappeProxy } from './scripts/frappe-proxy.mjs'
import { VitePWA } from 'vite-plugin-pwa'

import pkg from './package.json' with { type: 'json' }

// `vite build --mode native` builds the Play Store app (Capacitor, see README.md): served from the phone at its
// root, no service worker (the app itself is on the phone), and into dist-native for `npx cap sync`.
export default defineConfig(({ command, mode }) => {
  const native = mode === 'native'
  process.env.VITE_APP_VERSION = pkg.nativeVersion || pkg.version
  return {
  base: native ? '/' : command === 'build' ? '/assets/projectit/projectit/' : '/',
  server: { port: 8080, proxy: frappeProxy(__dirname) },
  plugins: [
    vue(),
    !native && VitePWA({
      registerType: 'autoUpdate',
      strategies: 'injectManifest',
      injectRegister: null,
      srcDir: 'public',
      filename: 'sw.js',
      devOptions: { enabled: true },
      // The worker is served from /techy-sw.js (so it can control /techy-app), so precache absolute asset URLs.
      injectManifest: { modifyURLPrefix: { '': '/assets/projectit/projectit/' }, maximumFileSizeToCacheInBytes: 6 * 1024 * 1024, globPatterns: ['**/*.{js,css,svg,png,woff2}'] },
      manifest: {
        display: 'standalone',
        name: 'Techy App',
        short_name: 'Techy App',
        // Preserve the identity of existing home-screen installations.
        id: '/projectit',
        start_url: '/techy-app',
        scope: '/',
        description: 'Techy App - field workforce and project tracking',
        theme_color: '#163B65',
        background_color: '#ffffff',
        // PNGs for phones (drawn from icon-src/); the maskable ones fill the square for Android's shaped crops.
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'icons/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: 'techy-app.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        ],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  build: native
    ? { outDir: path.resolve(__dirname, 'dist-native'), emptyOutDir: true, target: 'es2019' }
    : { outDir: path.resolve(__dirname, '../projectit/public/projectit'), emptyOutDir: true, target: 'es2015' },
  optimizeDeps: {
    include: ['frappe-ui > feather-icons', 'showdown', 'engine.io-client'],
  },
  }
})
