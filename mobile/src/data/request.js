import { isNative, server, apiBase, authHeaders, localize, signedOut } from './native'

/**
 * POST a whitelisted method; throws an Error whose message is the server's user-facing text.
 * When the server cannot be reached the error has `offline: true` (see data/offline.js).
 */
export async function request(method, args = {}) {
  // In the phone app: the company's site and this phone's token (data/native.js).
  const headers = { Accept: 'application/json', 'Content-Type': 'application/json; charset=utf-8', ...authHeaders() }
  if (window.csrf_token && !window.csrf_token.includes('{{')) headers['X-Frappe-CSRF-Token'] = window.csrf_token
  // A manager previewing the customer plant app as one machine's customer (read-only; see data/plant.js).
  if (window.__techyPreview && method.startsWith('projectit.plant.')) headers['X-Techy-Preview'] = window.__techyPreview
  let res
  try {
    res = await fetch(`${apiBase()}/api/method/${method}`, { method: 'POST', headers, body: JSON.stringify(args) })
  } catch (e) {
    const error = new Error("You're offline. Check your connection.")
    error.offline = true
    throw error
  }
  let data = {}
  try {
    data = await res.json()
  } catch (e) {
    /* non-JSON error page */
  }
  if (res.ok && !data.exc) return isNative ? localize(data.message) : data.message
  // The phone was signed out (in Desk, or the user was disabled): forget its token and ask to sign in.
  if (isNative && res.status === 401 && server.token) {
    signedOut()
    window.location.replace('/account/login')
  }
  let messages = []
  try {
    messages = JSON.parse(data._server_messages || '[]').map((m) => {
      try {
        return JSON.parse(m).message
      } catch (e) {
        return m
      }
    })
  } catch (e) {
    /* ignore */
  }
  const text = messages.filter(Boolean).join(' ').replace(/<[^>]*>/g, '')
  const error = new Error(text || data.exception || (res.status === 429 ? 'Too many requests. Try again later.' : `Request failed (${res.status}).`))
  error.status = res.status
  if (res.status === 401) error.exc_type = 'AuthenticationError'
  // A gateway that cannot reach the site (502-504) is as good as offline.
  if ([502, 503, 504].includes(res.status) && !data.exc) error.offline = true
  throw error
}
