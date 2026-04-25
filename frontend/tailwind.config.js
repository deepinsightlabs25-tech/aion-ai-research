/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        ink: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          500: '#4f46e5',
          600: '#4338ca',
          700: '#3730a3',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-up': 'fadeUp 0.6s ease forwards',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        }
      },
      typography: (theme) => ({
        invert: {
          css: {
            '--tw-prose-body': theme('colors.ink[200]'),
            '--tw-prose-headings': theme('colors.ink[50]'),
            '--tw-prose-lead': theme('colors.ink[300]'),
            '--tw-prose-links': theme('colors.amber[400]'),
            '--tw-prose-bold': theme('colors.ink[100]'),
            '--tw-prose-counters': theme('colors.ink[400]'),
            '--tw-prose-bullets': theme('colors.ink[500]'),
            '--tw-prose-hr': theme('colors.ink[700]'),
            '--tw-prose-quotes': theme('colors.ink[100]'),
            '--tw-prose-quote-borders': theme('colors.amber[500]'),
            '--tw-prose-code': theme('colors.amber[400]'),
            '--tw-prose-pre-code': theme('colors.ink[200]'),
            '--tw-prose-pre-bg': theme('colors.ink[950]'),
            '--tw-prose-th-borders': theme('colors.ink[600]'),
            '--tw-prose-td-borders': theme('colors.ink[700]'),
          },
        },
      }),
    },
  },
  plugins: [],
}
