/**
 * Light or dark (navy) appearance, chosen per device: Light, Dark, or Match phone (the system setting).
 * index.html applies the saved choice before the app loads, so a dark phone never flashes white.
 * The colours themselves are in theme.cjs.
 */
import { reactive } from 'vue'

const KEY = 'techy_theme'
const BAR = { light: '#163B65', dark: '#0E2440' } // the phone's status bar colour
const media = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null

function saved() {
  try {
    const v = localStorage.getItem(KEY)
    return ['light', 'dark', 'system'].includes(v) ? v : 'light'
  } catch (e) {
    return 'light'
  }
}

export const theme = reactive({ choice: saved(), dark: false })

function apply() {
  theme.dark = theme.choice === 'dark' || (theme.choice === 'system' && !!media?.matches)
  document.documentElement.classList.toggle('techy-dark', theme.dark)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.dark ? BAR.dark : BAR.light)
}

export function setTheme(choice) {
  theme.choice = choice
  try {
    localStorage.setItem(KEY, choice)
  } catch (e) {
    /* storage blocked: the choice lasts until the page is closed */
  }
  apply()
}

if (typeof document !== 'undefined') {
  apply()
  media?.addEventListener?.('change', () => theme.choice === 'system' && apply())
}
