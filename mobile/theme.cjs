/**
 * Light and dark themes for the Techy App.
 *
 * Every colour the app uses is a CSS variable, so one class on <html> switches the whole app:
 *   - light: exactly the colours the app always had (frappe-ui's palette plus the Techy brand);
 *   - dark (html.techy-dark): built on the logo's navy (#163B65) rather than black. Cards are the logo navy, the
 *     page behind them a deeper navy, greys are navy-tinted, and colours are lifted so they read on navy.
 *
 * Backgrounds, borders and rings use `colors`; text uses `textColor`, which is mapped separately in dark mode
 * because a colour that works as a tinted background (red-50) is not the one that works as text (red-700 must
 * become light on navy). `panel` is the card and input surface (white in light mode) and `canvas` the page.
 * Anything under `.palette-light` keeps the light colours in dark mode (the navy sidebar, signature pads).
 */
const preset = require('frappe-ui/src/utils/tailwind.config')
const twColors = require('tailwindcss/colors')

const base = preset.theme.colors({ colors: twColors })
const BRAND = {
  50: '#EEF4FB', 100: '#DCE8F6', 200: '#B6CEEC', 300: '#86AEDD', 400: '#5288C9',
  500: '#2F6DB5', 600: '#245A9C', 700: '#1C4A82', 800: '#163B65', 900: '#0F2A4A',
}
const ACCENT = { 50: '#ECFBF8', 100: '#CFF5EF', 400: '#40D6C4', 500: '#22BBA9', 600: '#169687' }
const SHADES = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900']
const HUES = ['red', 'green', 'amber', 'blue', 'violet', 'orange', 'teal', 'cyan', 'pink', 'yellow']

// The navy dark theme.
const NAVY = {
  canvas: '#0E2440', // the page, behind the cards
  panel: '#163B65', // cards, inputs and sheets: the logo colour
  gray: { 50: '#1B4472', 100: '#204B7B', 200: '#2B5786', 300: '#3A6696', 400: '#5A80AB', 500: '#7F9CBF', 600: '#A3B9D3', 700: '#C1D1E4', 800: '#DCE6F1', 900: '#EEF3F9' },
  grayText: { 50: '#1B4472', 100: '#2B5786', 200: '#3A6696', 300: '#62849F', 400: '#8BA5C4', 500: '#A3B9D3', 600: '#B9CADF', 700: '#D0DCEA', 800: '#E3EBF4', 900: '#F4F7FB' },
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
const rgb = (h) => hex(h).join(' ')
const mix = (a, b, t) => { // t of colour a over b
  const [x, y] = [hex(a), hex(b)]
  return '#' + x.map((v, i) => Math.round(v * t + y[i] * (1 - t)).toString(16).padStart(2, '0')).join('')
}

/** Dark versions of a colour scale: tinted navy for the light shades, the colour itself for the mid ones. */
function darkFills(scale) {
  const mid = scale['500'] || scale['400']
  return {
    50: mix(mid, NAVY.panel, 0.16), 100: mix(mid, NAVY.panel, 0.26), 200: mix(mid, NAVY.panel, 0.38),
    // Solid shades (buttons with white text, badges) keep their light-mode colour so white text stays readable.
    300: mix(mid, NAVY.panel, 0.55), 400: scale['400'] || mid, 500: mid, 600: scale['600'] || mid,
    700: scale['700'] || mid, 800: scale['800'] || mid, 900: scale['900'] || mid,
  }
}
/** Dark text: the deeper shades (used for text on light backgrounds) become the light ones. */
function darkText(scale) {
  const pick = (...keys) => keys.map((k) => scale[k]).find(Boolean)
  return {
    50: pick('50'), 100: pick('100', '50'), 200: pick('200', '100'), 300: pick('300', '200', '100'), 400: pick('300', '400'),
    500: pick('300', '400'), 600: pick('300', '400'), 700: pick('200', '100'), 800: pick('200', '100'), 900: pick('100', '50'),
  }
}

const scales = { gray: base.gray, brand: BRAND, accent: ACCENT }
for (const h of HUES) scales[h] = base[h]

const light = {}
const dark = {}
for (const [name, scale] of Object.entries(scales)) {
  const fills = name === 'gray' ? NAVY.gray : darkFills(scale)
  const texts = name === 'gray' ? NAVY.grayText : darkText(scale)
  for (const s of SHADES) {
    if (!scale[s]) continue
    light[`--c-${name}-${s}`] = light[`--t-${name}-${s}`] = rgb(scale[s])
    dark[`--c-${name}-${s}`] = rgb(fills[s])
    dark[`--t-${name}-${s}`] = rgb(texts[s])
  }
}
// The brand blue is the primary button and link colour: brighter on navy so buttons stand off the cards.
Object.assign(dark, {
  '--c-brand-600': rgb('#3A7FD0'), '--c-brand-700': rgb('#2F6DB5'), '--c-brand-800': rgb('#0B1E36'), '--c-brand-900': rgb('#081729'),
  '--t-brand-500': rgb('#9EC2EE'), '--t-brand-600': rgb('#9EC2EE'), '--t-brand-700': rgb('#B9D3F3'), '--t-brand-800': rgb('#D3E3F7'),
})
light['--c-panel'] = light['--t-panel'] = rgb('#FFFFFF')
light['--c-canvas'] = rgb(base.gray['50'])
dark['--c-panel'] = dark['--t-panel'] = rgb(NAVY.panel)
dark['--c-canvas'] = rgb(NAVY.canvas)

const variable = (prefix, name, s) => `rgb(var(--${prefix}-${name}-${s}) / <alpha-value>)`
function palette(prefix) {
  const out = {}
  for (const [name, scale] of Object.entries(scales)) {
    out[name] = {}
    for (const s of SHADES) if (scale[s]) out[name][s] = variable(prefix, name, s)
  }
  out.panel = `rgb(var(--${prefix === 't' ? 't' : 'c'}-panel) / <alpha-value>)`
  if (prefix === 'c') out.canvas = 'rgb(var(--c-canvas) / <alpha-value>)'
  return out
}

module.exports = {
  colors: palette('c'),
  textColor: palette('t'),
  themes: { light, dark },
  /** Tailwind plugin: the variables, the dark switch, the light islands and light printing. */
  plugin: ({ addBase }) => addBase({
    ':root': light,
    'html.techy-dark': { ...dark, colorScheme: 'dark' },
    'html.techy-dark .palette-light': { ...light, colorScheme: 'light' },
    '@media print': { 'html.techy-dark': { ...light, colorScheme: 'light' } },
  }),
  NAVY,
}
