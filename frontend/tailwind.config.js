/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#dde8ff',
          200: '#b3ccff',
          300: '#7aa8ff',
          400: '#4a80f8',
          500: '#2b5ce6',
          600: '#1e44c7',
          700: '#1934a0',
          800: '#1a2d7d',
          900: '#1a2962',
        },
      },
    },
  },
  plugins: [],
}
