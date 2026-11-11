/**
 * Phone notifications (Web Push): subscribe this browser so the site can alert it while the app is closed.
 * The service worker (public/sw.js) shows what is new when a push arrives. See projectit/push.py.
 */
import { reactive } from 'vue'
import { api } from './ops'

export const push = reactive({
  supported: typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window,
  subscribed: false,
})

function keyBytes(key) {
  const raw = atob((key + '='.repeat((4 - (key.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

async function registration() {
  // The worker is registered by the built app only (not by the Vite dev server).
  const reg = await navigator.serviceWorker.getRegistration('/techy-app/')
  return reg ? navigator.serviceWorker.ready : null
}

function device() {
  const ua = navigator.userAgent
  const os = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iPhone' : /Windows/.test(ua) ? 'Windows' : /Mac OS/.test(ua) ? 'Mac' : 'Other'
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'Browser'
  return `${browser} on ${os}`
}

/** Subscribe (or refresh) this browser. Returns whether it is subscribed. */
export async function enablePush() {
  if (!push.supported) return false
  try {
    const reg = await registration()
    if (!reg) return false
    const { key } = await api('projectit.push.public_key')
    let sub = await reg.pushManager.getSubscription()
    // A subscription made with another key (the site's key was replaced) cannot be used.
    const current = sub?.options?.applicationServerKey
    if (sub && current && btoa(String.fromCharCode(...new Uint8Array(current))) !== btoa(String.fromCharCode(...keyBytes(key)))) {
      await sub.unsubscribe()
      sub = null
    }
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) })
    await api('projectit.push.subscribe', { subscription: JSON.stringify(sub.toJSON()), device: device() })
    push.subscribed = true
  } catch (e) {
    push.subscribed = false
  }
  return push.subscribed
}

export async function disablePush() {
  if (!push.supported) return
  try {
    const reg = await registration()
    const sub = reg && (await reg.pushManager.getSubscription())
    if (sub) {
      await api('projectit.push.unsubscribe', { endpoint: sub.endpoint }).catch(() => {})
      await sub.unsubscribe()
    }
  } finally {
    push.subscribed = false
  }
}

export const testPush = () => api('projectit.push.test')

/** Whether this browser is already subscribed, and whether notifications are blocked (for settings screens). */
export async function checkPush() {
  push.permission = typeof Notification !== 'undefined' ? Notification.permission : 'default'
  if (!push.supported) return false
  try {
    const reg = await registration()
    push.subscribed = !!(reg && (await reg.pushManager.getSubscription()))
  } catch (e) {
    push.subscribed = false
  }
  return push.subscribed
}
