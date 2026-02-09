/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}', './projects/**/*.{html,ts}'],
  theme: {
    extend: {},
  },
  daisyui: {
    themes: [
      {
        'aql-light': {
          primary: '#3B82F6',
          'primary-focus': '#013AB8',
          'primary-content': '#FFFFFF',

          secondary: '#00D8C0',
          'secondary-focus': '#00BAA6',
          'secondary-content': '#FFFFFF',

          accent: '#F3C649',
          'accent-focus': '#EEAF00',
          'accent-content': '#111827',

          neutral: '#111827',
          'neutral-content': '#F9FAFB',

          'base-100': '#F8FAFC',
          'base-200': '#F3F4F6',
          'base-300': '#E5E7EB',
          'base-content': '#111827',

          info: '#38BDF8',
          'info-content': '#0f172a',
          success: '#22C55E',
          'success-content': '#052e16',
          warning: '#F59E0B',
          'warning-content': '#1f2937',
          error: '#EF4444',
          'error-content': '#111827',
        },
      },
      {
        'aql-dark': {
          primary: '#3B82F6',
          'primary-focus': '#013AB8',
          'primary-content': '#FFFFFF',

          secondary: '#00D8C0',
          'secondary-focus': '#00BAA6',
          'secondary-content': '#051017',

          accent: '#F3C649',
          'accent-focus': '#EEAF00',
          'accent-content': '#051017',

          neutral: '#111827',
          'neutral-content': '#F9FAFB',

          'base-100': '#020617',
          'base-200': '#020617',
          'base-300': '#020617',
          'base-content': '#F9FAFB',

          info: '#38BDF8',
          'info-content': '#0B1220',
          success: '#22C55E',
          'success-content': '#052e16',
          warning: '#F59E0B',
          'warning-content': '#1f2937',
          error: '#EF4444',
          'error-content': '#111827',
        },
      },
    ],
  },
  plugins: [require('daisyui')],
};
