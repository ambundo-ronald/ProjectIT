import { reactive, ref } from 'vue'
import { io } from 'socket.io-client'

/** Call a whitelisted method (see data/request.js); works offline for the reads and job changes in data/offline.js. */
import { api } from './offline'
import { request } from './request'

export { api, request }

/** Session details for the Ops shell. */
export const me = reactive({ loaded: false, user: '', full_name: '', image: '', manager: false, unread: 0 })

let booting = null
export function loadMe(force = false) {
  if (!booting || force) {
    booting = api('projectit.ops.bootstrap').then((data) => {
      Object.assign(me, data, { loaded: true })
      connect(data)
      return me
    })
    booting.catch(() => (booting = null))
  }
  return booting
}

/* Realtime -------------------------------------------------------------------------------------------- */
const handlers = {}
let socket = null
export const online = ref(false)

function connect({ sitename, socketio_port }) {
  if (socket) return
  // Same rule as Frappe Desk: a custom port means socket.io runs on its own port; otherwise it is proxied.
  const url = window.location.port
    ? `${window.location.protocol}//${window.location.hostname}:${socketio_port}/${sitename}`
    : `${window.location.origin}/${sitename}`
  try {
    socket = io(url, { withCredentials: true, reconnectionAttempts: 10 })
    socket.on('connect', () => (online.value = true))
    socket.on('disconnect', () => (online.value = false))
    for (const event of Object.keys(handlers)) bind(event)
  } catch (e) {
    socket = null
  }
}

function bind(event) {
  socket.on(event, (data) => handlers[event].forEach((fn) => fn(data)))
}

/** Subscribe to a realtime event; returns an unsubscribe function. */
export function onRealtime(event, fn) {
  if (!handlers[event]) {
    handlers[event] = new Set()
    if (socket) bind(event)
  }
  handlers[event].add(fn)
  return () => handlers[event].delete(fn)
}

/* Formatting ------------------------------------------------------------------------------------------ */
export const STATUS_LABEL = {
  Open: 'Open',
  Overdue: 'Overdue',
  Working: 'In progress',
  'Pending Review': 'On hold / review',
  Completed: 'Done',
  Cancelled: 'Cancelled',
}

export const STATUS_STYLE = {
  Open: 'bg-blue-100 text-blue-800',
  Overdue: 'bg-red-100 text-red-800',
  Working: 'bg-amber-100 text-amber-800',
  'Pending Review': 'bg-violet-100 text-violet-800',
  Completed: 'bg-green-100 text-green-800',
  Cancelled: 'bg-gray-200 text-gray-700',
}

export const PRIORITY_STYLE = {
  Low: 'text-gray-600',
  Medium: 'text-blue-700',
  High: 'text-orange-700',
  Urgent: 'text-red-700 font-semibold',
}

export const REQUEST_STYLE = {
  Pending: 'bg-amber-100 text-amber-800',
  Approved: 'bg-blue-100 text-blue-800',
  Declined: 'bg-gray-200 text-gray-700',
  Done: 'bg-green-100 text-green-800',
}

function toDate(value) {
  if (!value) return null
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value))
  // Date-only values are local calendar days, not UTC midnight.
  return day ? new Date(+day[1], +day[2] - 1, +day[3]) : new Date(String(value).replace(' ', 'T'))
}

export function formatDate(value) {
  const d = toDate(value)
  return d ? d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : ''
}

export function formatTime(value) {
  const d = toDate(value)
  return d ? d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : ''
}

export function fromNow(value) {
  const d = toDate(value)
  if (!d) return ''
  const minutes = Math.round((Date.now() - d.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 1440) return `${Math.round(minutes / 60)}h ago`
  return formatDate(value)
}

/** Whole days from today until a date (negative when past), or null. */
export function dueIn(value) {
  const d = toDate(value)
  if (!d) return null
  const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  return Math.round((start(d) - start(new Date())) / 86400000)
}

export function isOverdue(row) {
  if (!row?.exp_end_date || ['Completed', 'Cancelled'].includes(row.status)) return false
  return toDate(row.exp_end_date) < new Date(new Date().toDateString())
}

export function readFile(file, maxMb = 10) {
  return new Promise((resolve, reject) => {
    if (file.size > maxMb * 1024 * 1024) return reject(new Error(`Choose a photo smaller than ${maxMb} MB.`))
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error('Could not read the photo.'))
    reader.readAsDataURL(file)
  })
}

export const safeFile = (url) => typeof url === 'string' && /^\/(private\/)?files\//.test(url)

/** Split message text into plain, @mention and link parts ([[kind:name]], or an older #TASK-… work order) for safe rendering. */
export function tokens(text, names = {}) {
  const parts = []
  const pattern = /(@[\w.+-]+@[\w-]+(?:\.[\w-]+)+)|#(TASK-[\w-]+)|\[\[(task|work-order|project|asset|equipment|request):([^[\]\n]{1,140})\]\]/g
  let last = 0
  let match
  while ((match = pattern.exec(text || ''))) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index) })
    if (match[1]) {
      const user = match[1].slice(1)
      parts.push({ mention: user, text: `@${names[user] || user}` })
    } else if (match[2]) {
      parts.push({ link: { kind: 'work-order', name: match[2] }, text: match[2] }) // older #TASK-… references
    } else {
      parts.push({ link: { kind: match[3], name: match[4] }, text: match[4] })
    }
    last = pattern.lastIndex
  }
  if (last < (text || '').length) parts.push({ text: text.slice(last) })
  return parts
}

/* Job timer ------------------------------------------------------------------------------------------- */
/** 1:05:09 for a running clock. */
export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const pad = (n) => String(n).padStart(2, '0')
  return `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
}

/** "2 h 15 min" for hours worked. */
export function duration(hours) {
  const minutes = Math.round((hours || 0) * 60)
  if (minutes < 60) return `${minutes} min`
  return minutes % 60 ? `${Math.floor(minutes / 60)} h ${minutes % 60} min` : `${minutes / 60} h`
}

/** A clock that ticks every second while any timer is shown; components read `now.value`. */
export const now = ref(Date.now())
let ticking = 0
let tickTimer = null
export function useTick() {
  ticking += 1
  if (!tickTimer) tickTimer = setInterval(() => (now.value = Date.now()), 1000)
  return () => {
    ticking -= 1
    if (!ticking) {
      clearInterval(tickTimer)
      tickTimer = null
    }
  }
}
