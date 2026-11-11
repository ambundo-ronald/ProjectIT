/**
 * The Techy phone app (Play Store, built with Capacitor; see mobile/README.md).
 *
 * In a browser the app is served by the company's own site and uses its session cookie: nothing here applies.
 * In the phone app the same code runs from the phone itself, and talks to whichever site the person typed in:
 *
 * - `server.url` is that site, chosen on the sign-in screen and checked with projectit.device_auth.hello.
 * - Sign-in returns a token for this phone (projectit.device_auth.sign_in); every request sends it in a header.
 *   Requests go through the phone's own HTTP (CapacitorHttp, see capacitor.config.json), so no CORS is needed.
 * - Server paths in answers ("/files/x.jpg", "/private/files/y.jpg") are made absolute, and private ones signed,
 *   so they open in <img> and the phone's browser (see `localize`).
 * - Taps on links to the server (PDFs, Excel, Desk) open in the phone's browser, signed where needed.
 */
import { reactive } from 'vue'

export const isNative = typeof window !== 'undefined' && !!window.Capacitor?.isNativePlatform?.()

const KEY = 'techy_native'
function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch (e) {
    return {}
  }
}
/** url: the company's site; token/device/user/full_name: this phone's sign-in; company/logo: from hello. */
export const server = reactive({ url: '', token: '', device: '', user: '', full_name: '', company: '', logo: '', ...load() })
function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(server))
  } catch (e) {
    /* storage blocked: the person signs in again next time */
  }
}

export const APP_VERSION = import.meta.env.VITE_APP_VERSION || ''

/** "ops.example.com", "https://ops.example.com/", "ops.example.com/app" → "https://ops.example.com". */
export function normalizeUrl(text) {
  let value = String(text || '').trim()
  if (!value) return ''
  if (!/^https?:\/\//i.test(value)) value = `https://${value}`
  try {
    const u = new URL(value)
    return `${u.protocol}//${u.host}`
  } catch (e) {
    return ''
  }
}

/** Absolute address on the company's site ('' prefix in a browser). */
export const apiBase = () => (isNative ? server.url : '')
export const authHeaders = () => (isNative && server.token ? { 'X-Techy-Device': server.token } : {})

async function call(method, args = {}, withToken = true) {
  const res = await fetch(`${server.url}/api/method/${method}`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json; charset=utf-8', ...(withToken ? authHeaders() : {}) },
    body: JSON.stringify(args),
  })
  let data = {}
  try {
    data = await res.json()
  } catch (e) {
    /* not JSON */
  }
  if (res.ok && !data.exc) return data.message
  let text = ''
  try {
    text = JSON.parse(data._server_messages || '[]').map((m) => JSON.parse(m).message).join(' ').replace(/<[^>]*>/g, '')
  } catch (e) {
    /* none */
  }
  const error = new Error(text || (res.status === 429 ? 'Too many tries. Wait a few minutes and try again.' : `The site answered ${res.status}.`))
  error.status = res.status
  throw error
}

/** Check the address is a Techy site and remember it. */
export async function chooseServer(text) {
  const url = normalizeUrl(text)
  if (!url) throw new Error('Type your company’s Techy address, for example ops.yourcompany.com.')
  const previous = server.url
  server.url = url
  try {
    const hello = await call('projectit.device_auth.hello', {}, false)
    if (hello?.app !== 'techy') throw new Error('not techy')
    Object.assign(server, { company: hello.company || url.replace(/^https?:\/\//, ''), logo: hello.logo || '' })
    if (previous !== url) Object.assign(server, { token: '', device: '', user: '', full_name: '' })
    save()
    return hello
  } catch (e) {
    server.url = previous
    if (e.status === 404 || e.message === 'not techy') throw new Error(`${url.replace(/^https?:\/\//, '')} is not a Techy site. Check the address with your manager.`)
    throw new Error(`Could not reach ${url.replace(/^https?:\/\//, '')}. Check the address and your connection.`)
  }
}

export function forgetServer() {
  Object.assign(server, { url: '', token: '', device: '', user: '', full_name: '', company: '', logo: '' })
  save()
}

function deviceName() {
  const m = navigator.userAgent.match(/Android [\d.]+; ([^;)]+)/)
  return m ? m[1].replace(/ Build\/.*/, '').trim() : 'Android phone'
}

export async function signIn(usr, pwd) {
  const r = await call('projectit.device_auth.sign_in', { usr, pwd, device_name: deviceName(), platform: 'android', app_version: APP_VERSION }, false)
  Object.assign(server, { token: r.token, device: r.device, user: r.user, full_name: r.full_name })
  save()
  return r
}

export async function signOut() {
  try {
    await call('projectit.device_auth.sign_out')
  } catch (e) {
    /* offline or already signed out: forget it here anyway */
  }
  signedOut()
}

/** The site refused this phone's token (signed out in Desk, user disabled): forget it. */
export function signedOut() {
  Object.assign(server, { token: '', device: '', user: '', full_name: '' })
  save()
}

/* Signed links ---------------------------------------------------------------------------------------------- */
const enc = new TextEncoder()
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
let hmacKey = null
let keyFor = ''
async function key() {
  if (!hmacKey || keyFor !== server.token) {
    // The server stores sha256(token) and signs with it; so do we (see projectit/device_auth.py).
    const secret = hex(await crypto.subtle.digest('SHA-256', enc.encode(server.token)))
    hmacKey = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
    keyFor = server.token
  }
  return hmacKey
}
const signed = new Map()

/** "/private/files/x.jpg" or "/api/method/…download?…" → an absolute link that works for a day. */
export async function signUrl(path) {
  // Rounded to the hour, so the same photo keeps the same address (and the WebView's image cache) for an hour.
  const expires = Math.floor(Date.now() / 3600000) * 3600 + 23 * 3600
  const id = `${path}|${expires}`
  if (signed.has(id)) return signed.get(id)
  const [rawPath, query = ''] = path.split('?')
  let decoded = rawPath
  try {
    decoded = decodeURI(rawPath)
  } catch (e) {
    /* already plain */
  }
  const base = decoded + (query ? `?${query}` : '')
  const signature = hex(await crypto.subtle.sign('HMAC', await key(), enc.encode(`${base}|${expires}`)))
  const url = `${server.url}${encodeURI(decoded)}${query ? `?${query}&` : '?'}_td=${encodeURIComponent(server.device)}&_te=${expires}&_ts=${signature}`
  signed.set(id, url)
  return url
}

const FILE_RE = /(^|["'(\s=])(\/(?:private\/)?files\/[^"'()\s<>]+)/g

/** Make server paths in an answer usable from the phone (see the top of this file). */
export async function localize(value) {
  if (!isNative || !server.url || value === null || typeof value !== 'object') return value
  const privates = new Set()
  const scan = (v) => {
    if (typeof v === 'string') {
      if (v.includes('/private/files/')) for (const m of v.matchAll(FILE_RE)) if (m[2].startsWith('/private/')) privates.add(m[2])
    } else if (v && typeof v === 'object') for (const k in v) scan(v[k])
  }
  scan(value)
  const urls = {}
  for (const p of privates) urls[p] = await signUrl(p)
  const fix = (s) => (s.includes('/files/') ? s.replace(FILE_RE, (all, lead, p) => lead + (urls[p] || `${server.url}${p}`)) : s)
  const walk = (v) => {
    if (typeof v === 'string') return fix(v)
    if (Array.isArray(v)) return v.map(walk)
    if (v && typeof v === 'object') {
      for (const k in v) v[k] = walk(v[k])
      return v
    }
    return v
  }
  return walk(value)
}

/* Links ------------------------------------------------------------------------------------------------------ */
export async function openExternal(url) {
  const { Browser } = await import('@capacitor/browser')
  await Browser.open({ url })
}

/** Links that point at the company's site rather than a screen in the app. */
const SERVER_LINK = /^(https?:\/\/|\/api\/method\/|\/private\/files\/|\/files\/|\/desk|\/app\/|\/update-password)/i

/** Where a link inside the app really points, on the company's site. */
function target(href) {
  if (/^https?:\/\//i.test(href)) return Promise.resolve(href)
  if (href.startsWith('/api/method/') || href.startsWith('/private/files/')) return signUrl(href)
  return Promise.resolve(`${server.url}${href}`)
}

/** The address of a page of the app on the company's site, for QR codes and links people share. */
export const publicUrl = (path) => `${server.url}/techy-app${path}`

let started = false
export function startNative() {
  if (!isNative || started) return
  started = true
  document.documentElement.classList.add('native-app')
  // Links to the server open in the phone's browser; the app's own links (router-link) are left alone.
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented || e.button !== 0) return
    const a = e.target.closest?.('a[href]')
    const href = a?.getAttribute('href')
    if (!href || !SERVER_LINK.test(href)) return
    e.preventDefault()
    target(href).then(openExternal).catch(() => {})
  })
  // Status bar icons follow the app's own light or dark theme (data/theme.js), not the phone's.
  import('@capacitor/core').then(({ SystemBars }) => {
    const apply = () => SystemBars?.setStyle({ style: document.documentElement.classList.contains('techy-dark') ? 'DARK' : 'LIGHT' }).catch(() => {})
    apply()
    new MutationObserver(apply).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  }).catch(() => {})
  // The phone's Back button goes back in the app, and closes it from the first screen.
  import('@capacitor/app').then(({ App }) => {
    App.addListener('backButton', ({ canGoBack }) => (canGoBack ? window.history.back() : App.exitApp()))
  }).catch(() => {})
}
