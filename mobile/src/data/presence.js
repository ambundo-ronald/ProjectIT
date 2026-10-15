/** Who is online and their status ("🚐 On site at Bahari"), kept fresh by a once-a-minute heartbeat. */
import { reactive } from 'vue'
import { api, me } from './ops'

/** user -> { online, away, emoji, text, clear_at } */
export const presence = reactive({})
/** The "Set a status" dialog (rendered once in App.vue). */
export const statusDialog = reactive({ open: false })

const watched = new Map() // user -> number of screens showing them
let timer = null
let soon = null

async function beat() {
  if (document.visibilityState !== 'visible') return
  try {
    Object.assign(presence, await api('projectit.presence.heartbeat', { users: [...watched.keys()] }))
  } catch (e) {
    /* offline or signed out: try again next minute */
  }
}

/** Start the heartbeat once per page load (safe to call again). */
export function startPresence() {
  if (timer) return
  beat()
  timer = setInterval(beat, 60000)
  document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && beat())
}

/** Keep these people's presence fresh while a screen shows them; call the returned function to stop. */
export function watchPeople(users) {
  const list = [...new Set((users || []).filter(Boolean))]
  list.forEach((u) => watched.set(u, (watched.get(u) || 0) + 1))
  if (list.some((u) => !(u in presence))) {
    clearTimeout(soon)
    soon = setTimeout(beat, 200)
  }
  return () =>
    list.forEach((u) => {
      const n = (watched.get(u) || 1) - 1
      if (n) watched.set(u, n)
      else watched.delete(u)
    })
}

/** Set or clear my status; returns my new presence. */
export async function setStatus(values) {
  const mine = await api('projectit.presence.set_status', values)
  presence[me.user] = mine
  return mine
}

/** "🚐 On site at Bahari", or ''. */
export const statusLine = (p) => [p?.emoji, p?.text].filter(Boolean).join(' ')
