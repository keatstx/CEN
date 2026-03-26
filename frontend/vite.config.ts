import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/ready': 'http://localhost:8000',
      '/execute': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/update-aop': 'http://localhost:8000',
      '/tlm': 'http://localhost:8000',
      '/modules': 'http://localhost:8000',
    },
  },
})
