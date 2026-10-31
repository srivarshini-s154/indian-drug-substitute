/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sage: {
          50: '#f4f7f4',
          100: '#e5ebe5',
          200: '#cbd7cb',
          300: '#a7bda6',
          400: '#7e9e7d',
          500: '#6a8b69', // Primary Sage Green
          600: '#526f51',
          700: '#425841',
          800: '#374736',
          900: '#1e281e',
          950: '#0f140f',
        },
        dark: {
          bg: '#0a0c0a',
          card: '#121612',
          border: '#222c22',
        }
      },
    },
  },
  plugins: [],
}