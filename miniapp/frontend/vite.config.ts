import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // Для деплоя измените на путь к вашему приложению
  server: {
    port: 5173,
    host: true,
    // Разрешаем все хосты (для ngrok, localtunnel и т.д.)
    allowedHosts: 'all',
    // Прокси для API в режиме разработки
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'esbuild',
  },
})
