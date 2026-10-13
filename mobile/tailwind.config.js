module.exports = {
  presets: [require('frappe-ui/src/utils/tailwind.config')],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // From the Techy App mark: navy tile (#163B65) and teal chevron (#40D6C4).
        brand: {
          50: '#EEF4FB',
          100: '#DCE8F6',
          200: '#B6CEEC',
          300: '#86AEDD',
          400: '#5288C9',
          500: '#2F6DB5',
          600: '#245A9C',
          700: '#1C4A82',
          800: '#163B65',
          900: '#0F2A4A',
        },
        accent: {
          50: '#ECFBF8',
          100: '#CFF5EF',
          400: '#40D6C4',
          500: '#22BBA9',
          600: '#169687',
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.06), 0 1px 3px rgba(16, 24, 40, 0.04)',
        pop: '0 12px 32px -8px rgba(16, 24, 40, 0.18), 0 4px 8px -4px rgba(16, 24, 40, 0.08)',
      },
    },
  },
  plugins: [],
}
