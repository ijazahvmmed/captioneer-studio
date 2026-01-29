/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'studio': {
          bg: '#0a0a0f',
          panel: '#12121a',
          border: '#1e1e2e',
          accent: '#6366f1',
          text: '#e5e7eb',
          muted: '#6b7280',
        }
      }
    },
  },
  plugins: [],
}
