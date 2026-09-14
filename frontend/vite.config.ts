import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The backend's CORS_ORIGINS default covers this exact origin (5173).
// If Vite ever binds another port, update CORS_ORIGINS in the backend .env too.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
