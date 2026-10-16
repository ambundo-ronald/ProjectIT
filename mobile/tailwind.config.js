const theme = require('./theme.cjs')

module.exports = {
  presets: [require('frappe-ui/src/utils/tailwind.config')],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // Every colour is a CSS variable with a light and a navy dark value (see theme.cjs). The brand comes from the
      // Techy App mark: navy tile (#163B65) and teal chevron (#40D6C4).
      colors: theme.colors,
      textColor: theme.textColor,
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.06), 0 1px 3px rgba(16, 24, 40, 0.04)',
        pop: '0 12px 32px -8px rgba(16, 24, 40, 0.18), 0 4px 8px -4px rgba(16, 24, 40, 0.08)',
      },
    },
  },
  plugins: [theme.plugin],
}
