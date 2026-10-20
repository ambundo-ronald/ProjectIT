/**
 * The customer app (Techy Plant): who is signed in, their machines and the one they are looking at.
 * The chosen machine is remembered on the phone, so someone with several plants picks once.
 */
import { reactive, computed } from 'vue'
import { api, request } from './ops'

const KEY = 'techy_plant_machine'
export const plant = reactive({ me: null, machine: null, error: '' })

function remembered() {
  try {
    return localStorage.getItem(KEY)
  } catch (e) {
    return null
  }
}

let loading = null
export function loadPlant(force = false) {
  if (!loading || force) {
    loading = api('projectit.plant.me')
      .then((me) => {
        plant.me = me
        plant.error = ''
        const names = me.machines.map((m) => m.name)
        plant.machine = names.includes(plant.machine) ? plant.machine : names.includes(remembered()) ? remembered() : names[0] || null
        return me
      })
      .catch((e) => {
        plant.error = e.message
        loading = null
        throw e
      })
  }
  return loading
}

export function chooseMachine(name) {
  plant.machine = name
  try {
    localStorage.setItem(KEY, name)
  } catch (e) {
    /* storage blocked: the first machine is shown next time */
  }
}

export const machine = computed(() => plant.me?.machines.find((m) => m.name === plant.machine) || null)

/* Logs saved without signal ---------------------------------------------------------------------------------------
 * Plant rooms often have no signal. A log saved offline waits on the phone with the time it was taken and an id,
 * and is sent when the phone is back online (the id makes sending it twice harmless). It is not checked for
 * unusual values while waiting: the server saves it with those readings marked, for us to check. */
const QUEUE = 'techy_plant_queue'
function stored() {
  try {
    return JSON.parse(localStorage.getItem(QUEUE) || '[]')
  } catch (e) {
    return []
  }
}
export const waiting = reactive({ items: stored(), sending: false, failed: [] })
function persist() {
  try {
    localStorage.setItem(QUEUE, JSON.stringify(waiting.items))
  } catch (e) {
    /* full or blocked: it stays in memory until sent */
  }
}

export function queueLog(entry) {
  waiting.items.push({ ...entry, client_id: entry.client_id || `${Date.now()}-${Math.random().toString(36).slice(2, 10)}` })
  persist()
}

export async function sendWaiting() {
  if (waiting.sending || !waiting.items.length || !navigator.onLine) return 0
  waiting.sending = true
  let sent = 0
  try {
    while (waiting.items.length) {
      const item = waiting.items[0]
      try {
        await request('projectit.plant.save_log', { ...item, confirm: 2 })
        sent++
      } catch (e) {
        if (e.offline) break
        // Refused (for example a counter lower than its last reading): tell the person, do not retry forever.
        waiting.failed.push({ when: item.taken_on, message: e.message })
      }
      waiting.items.shift()
      persist()
    }
  } finally {
    waiting.sending = false
  }
  return sent
}

if (typeof window !== 'undefined') window.addEventListener('online', () => sendWaiting())
