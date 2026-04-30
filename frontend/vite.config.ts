import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/ready': 'http://localhost:8000',
      '/execute': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/cases': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/artifacts': 'http://localhost:8000',
      '/faqs': 'http://localhost:8000',
      '/concierge': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/update-aop': 'http://localhost:8000',
      '/tlm': 'http://localhost:8000',
      '/modules': 'http://localhost:8000',
      '/sop': 'http://localhost:8000',
    },
  },
})
