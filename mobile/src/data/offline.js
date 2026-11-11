/**
 * Offline mode for technicians.
 *
 * Reads: every answer to the read methods below is kept on the phone (IndexedDB). Without a connection the saved
 * answer is shown instead. The jobs assigned to me are fetched in the background so they are there when needed.
 *
 * Changes: the job actions below are queued on the phone when there is no connection, and the job is updated on
 * screen straight away. The queue is sent, oldest first, as soon as the connection is back. A change the server
 * refuses (the job was closed meanwhile, say) is kept and shown so the person can try again or discard it.
 * Timer starts and stops, check-ins and check-outs, site photos and On my way carry the time they happened on the
 * phone. A check-out queued after an offline check-in is sent with the timesheet the check-in created.
 */
import { reactive } from 'vue'
import { request } from './request'

const READS = new Set([
  'projectit.ops.bootstrap',
  'projectit.api.my_apps',
  'projectit.api.get_header_info',
  'projectit.api.get_modules_for_router',
  'projectit.work_orders.list_work_orders',
  'projectit.work_orders.get_work_order',
  'projectit.work_orders.summary',
  'projectit.work_orders.options',
  'projectit.failures.options',
  'projectit.ops.search_users',
  'projectit.chat.list_channels',
  'projectit.chat.get_channel',
  'projectit.chat.get_messages',
  'projectit.reminders.my_reminders',
  // Techy Work (check-in) and what a technician opens from a job.
  'projectit.work.today',
  'projectit.tasks.work_tasks',
  'projectit.procedures.list_procedures',
  'projectit.equipment.get_equipment',
  'projectit.meters.get_meter',
])
// Lists whose screen filters what it gets, so any saved copy is better than none.
const ANY_ARGS = new Set(['projectit.work_orders.list_work_orders', 'projectit.work_orders.summary', 'projectit.ops.search_users'])

const DETAIL = 'projectit.work_orders.get_work_order'
const BOOT = 'projectit.ops.bootstrap'
const TODAY = 'projectit.work.today'

export const offline = reactive({ online: typeof navigator === 'undefined' || navigator.onLine, pending: 0, failed: [], syncing: false })

/* IndexedDB --------------------------------------------------------------------------------------------- */
let dbp = null
function db() {
  if (!dbp) {
    dbp = new Promise((resolve, reject) => {
      const req = indexedDB.open('techy-offline', 1)
      req.onupgradeneeded = () => {
        req.result.createObjectStore('cache', { keyPath: 'key' })
        req.result.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true })
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  }
  return dbp
}
async function tx(store, mode, work) {
  const conn = await db()
  return new Promise((resolve, reject) => {
    const t = conn.transaction(store, mode)
    const result = work(t.objectStore(store))
    t.oncomplete = () => resolve(result instanceof IDBRequest ? result.result : result)
    t.onerror = () => reject(t.error)
  })
}
const get = (store, key) => tx(store, 'readonly', (s) => s.get(key))
const put = (store, value) => tx(store, 'readwrite', (s) => s.put(value))
const del = (store, key) => tx(store, 'readwrite', (s) => s.delete(key))
const all = (store) => tx(store, 'readonly', (s) => s.getAll())

/** The same arguments always give the same key, whatever order they were written in. */
function keyOf(method, args) {
  const clean = Object.fromEntries(Object.entries(args || {}).filter(([, v]) => v !== undefined && v !== null && v !== '').sort(([a], [b]) => a.localeCompare(b)))
  return `${method} ${JSON.stringify(clean)}`
}
async function remember(method, args, value) {
  try {
    await put('cache', { key: keyOf(method, args), value, at: Date.now() })
    if (ANY_ARGS.has(method)) await put('cache', { key: `${method} *`, value, at: Date.now() })
  } catch (e) {
    /* private mode or storage full: offline copies are a bonus */
  }
}
async function recall(method, args) {
  let row = await get('cache', keyOf(method, args)).catch(() => null)
  if (!row && ANY_ARGS.has(method)) row = await get('cache', `${method} *`).catch(() => null)
  if (!row) {
    const error = new Error("You're offline, and this wasn't saved on this phone yet. Open it once while online.")
    error.offline = true
    throw error
  }
  return catchUp(method, row)
}
/** Running clocks saved earlier have kept running since. */
function catchUp(method, row) {
  const value = typeof structuredClone === 'function' ? structuredClone(row.value) : JSON.parse(JSON.stringify(row.value))
  const seconds = Math.max(0, (Date.now() - row.at) / 1000)
  if (method === DETAIL && value?.timer) for (const r of value.timer.running || []) r.elapsed = (r.elapsed || 0) + seconds
  if (method === BOOT && value?.timer) value.timer.elapsed = (value.timer.elapsed || 0) + seconds
  // A saved Today is shown against the phone's clock, not the server time from when it was saved.
  if (method === TODAY && value) value.server_time = localNow()
  return value
}

/* Changes made offline ------------------------------------------------------------------------------- */
const pad = (n) => String(n).padStart(2, '0')
function localNow() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** For each queued method: the job it changes, and how the job looks once it is done. */
const WRITES = {
  'projectit.work_orders.update_work_order': {
    job: (a) => a.name,
    apply(d, a) {
      if (a.status) {
        d.work_order.status = a.status
        d.work_order.custom_review_requested = a.status === 'Pending Review' && Number(a.review) ? 1 : 0
      }
    },
    label: (a) => (a.status ? `Status: ${a.status === 'Working' ? 'In progress' : a.status === 'Pending Review' ? (Number(a.review) ? 'Sent for review' : 'On hold') : a.status}` : 'Job update'),
  },
  'projectit.work_orders.add_comment': {
    job: (a) => a.name,
    apply(d, a, ctx) {
      d.comments.push({ name: `pending-${ctx.id}`, content: a.content, comment_type: 'Comment', comment_by: ctx.me.full_name, comment_email: ctx.me.user, creation: ctx.now, pending: true })
    },
    label: () => 'Update posted',
  },
  'projectit.work_orders.toggle_step': {
    job: (a) => a.name,
    apply(d, a) {
      const step = d.steps.find((s) => s.name === a.step)
      if (step) step.status = Number(a.done) ? 'Completed' : 'Open'
      if (Number(a.done) && ['Open', 'Overdue'].includes(d.work_order.status)) d.work_order.status = 'Working'
    },
    label: () => 'Checklist step',
  },
  'projectit.work_orders.attach_photo': {
    job: (a) => a.name,
    apply(d, a, ctx) {
      d.files.unshift({ name: `pending-${ctx.id}`, file_name: 'Photo waiting to upload', file_url: `data:image/jpeg;base64,${a.content}`, creation: ctx.now, pending: true })
    },
    label: () => 'Photo',
  },
  'projectit.procedures.answer': {
    job: (a) => a.work_order,
    apply(d, a, ctx) {
      const step = d.procedure?.steps.find((s) => s.name === a.step)
      if (!step) return
      step.value = a.photo ? `data:image/jpeg;base64,${a.photo}` : a.value ?? ''
      Object.assign(step, { answered_by: ctx.me.full_name, answered_on: ctx.now, pending: true })
      const answerable = d.procedure.steps.filter((s) => s.field_type !== 'Heading')
      d.procedure.answered = answerable.filter((s) => s.value).length
      d.procedure.missing = answerable.filter((s) => s.required && !s.value).length
    },
    label: () => 'Procedure answer',
  },
  'projectit.timer.start': {
    job: (a) => a.work_order,
    apply(d, a, ctx) {
      if (!d.timer || d.timer.mine) return
      const mine = { name: `pending-${ctx.id}`, user: ctx.me.user, full_name: ctx.me.full_name, started_at: a.at, ended_at: null, elapsed: 0, hours: 0, source: 'Timer', can_edit: false, pending: true }
      d.timer.mine = mine
      d.timer.running = [mine, ...d.timer.running]
      d.timer.entries = [mine, ...d.timer.entries]
      if (['Open', 'Overdue', 'Pending Review'].includes(d.work_order.status)) d.work_order.status = 'Working'
    },
    boot: (b, a, d) => (b.timer = { work_order: a.work_order, subject: d.work_order.subject, elapsed: 0 }),
    stamp: true,
    label: () => 'Timer started',
  },
  'projectit.timer.stop': {
    job: (a) => a.work_order,
    apply(d) {
      const mine = d.timer?.mine
      if (!mine) return
      Object.assign(mine, { ended_at: localNow(), hours: Math.round(((mine.elapsed || 0) / 3600) * 100) / 100, elapsed: null })
      d.timer.total = Math.round((d.timer.total + mine.hours) * 100) / 100
      d.timer.running = d.timer.running.filter((r) => r.name !== mine.name)
      d.timer.mine = null
    },
    boot: (b) => (b.timer = null),
    stamp: true,
    label: () => 'Timer stopped',
  },
  'projectit.failures.set_failure': {
    job: (a) => a.work_order,
    apply(d, a) {
      const f = d.failure
      if (!f) return
      for (const k of ['problem', 'cause', 'remedy']) if (a[k] !== undefined) f[k] = a[k] ? { code: a[k], title: a[k] } : null
      if (a.machine_down !== undefined) f.machine_down = !!Number(a.machine_down)
      if (a.down_from !== undefined) f.down_from = a.down_from
      if (a.down_to !== undefined) f.down_to = a.down_to || null
      f.missing = f.required ? ['Problem', 'Cause'].filter((k) => !f[k.toLowerCase()]) : []
    },
    label: () => 'Failure and downtime',
  },
  'projectit.service_report.set_summary': {
    job: (a) => a.name,
    apply(d, a) {
      if (d.report) d.report.work_summary = a.summary
    },
    label: () => 'Work done',
  },
  'projectit.work_orders.on_my_way': {
    job: (a) => a.name,
    apply(d, a, ctx) {
      d.on_way = { ...(d.on_way || {}), at: a.at, by: ctx.me.full_name, minutes: a.minutes || null, can_go: false, pending: true }
    },
    stamp: true,
    label: () => 'On my way',
  },
  'projectit.meters.record_reading': {
    // No saved screen to update: the meter card shows the value itself (see MetersCard).
    result: (a) => ({ meter: null, raised: [], queued: true, value: a.value }),
    // An unusual reading cannot be confirmed later; the person saw the number when they typed it.
    send: (a) => ({ ...a, confirm: 1 }),
    label: () => 'Meter reading',
  },
  // Techy Work: check in and out of a project with no signal at the site.
  'projectit.attendance.check_in': {
    target: () => [TODAY, {}],
    apply(t, a, ctx) {
      const project = (t.projects || []).find((p) => p.project === a.project)
      t.session = { name: `pending-${ctx.id}`, project: a.project, project_name: project?.project_name || a.project, from_time: a.at, task: a.task || null, note: '', docstatus: 0, pending: true }
      const me = project?.team.find((m) => m.me)
      if (me) me.on_site = true
    },
    stamp: true,
    label: () => 'Check-in',
  },
  'projectit.attendance.check_out': {
    target: () => [TODAY, {}],
    apply(t) {
      for (const p of t.projects || []) for (const m of p.team) if (m.me) m.on_site = false
      t.session = null
    },
    stamp: true,
    label: () => 'Check-out',
  },
  'projectit.attendance.add_photo': {
    target: () => [TODAY, {}],
    apply() {},
    stamp: true,
    label: () => 'Site photo',
  },
}

/** Where a queued change shows on screen: the saved copy it updates. */
const targetOf = (spec, args) => (spec.target ? spec.target(args) : spec.job ? [DETAIL, { name: spec.job(args) }] : null)

async function queue(method, args) {
  const spec = WRITES[method]
  const job = spec.job ? spec.job(args) : null
  const target = targetOf(spec, args)
  const row = target ? await get('cache', keyOf(...target)).catch(() => null) : null
  if (target && !row) {
    const error = new Error(target[0] === DETAIL
      ? "You're offline, and this job wasn't saved on this phone. Open it once while online."
      : "You're offline, and this screen wasn't saved on this phone yet. Open it once while online.")
    error.offline = true
    throw error
  }
  const queued = spec.stamp ? { ...args, at: localNow() } : args
  const id = await put('outbox', { method, args: queued, job, target, label: spec.label(args), created: Date.now() })
  const boot = await get('cache', keyOf(BOOT, {})).catch(() => null)
  const ctx = { id, now: localNow(), me: { user: boot?.value?.user, full_name: boot?.value?.full_name || 'You' } }
  let value = null
  if (row) {
    value = catchUp(target[0], row)
    spec.apply(value, queued, ctx)
    await remember(target[0], target[1], value)
  }
  if (spec.boot && boot) {
    const b = catchUp(BOOT, boot)
    spec.boot(b, queued, value)
    await remember(BOOT, {}, b)
  }
  await counts()
  return spec.result ? spec.result(queued, value) : value
}

export async function counts() {
  try {
    const rows = await all('outbox')
    offline.pending = rows.filter((r) => !r.failed).length
    offline.failed = rows.filter((r) => r.failed)
  } catch (e) {
    /* no storage */
  }
}

/** Send what was queued, oldest first. */
export async function sync() {
  if (offline.syncing) return
  offline.syncing = true
  const touched = new Set()
  const screens = new Map()
  const created = await realNames()
  try {
    const rows = (await all('outbox')).filter((r) => !r.failed).sort((a, b) => a.id - b.id)
    for (const item of rows) {
      const spec = WRITES[item.method] || {}
      let args = spec.send ? spec.send({ ...item.args }) : { ...item.args }
      // A check-out or photo for a check-in made offline: use the timesheet that check-in created.
      if (typeof args.timesheet === 'string' && args.timesheet.startsWith('pending-')) {
        const real = created[args.timesheet]
        if (!real) {
          await put('outbox', { ...item, failed: true, error: 'Its check-in was not sent. Retry or discard the check-in first.' })
          continue
        }
        args.timesheet = real
      }
      try {
        if (item.method === 'projectit.procedures.answer' && !args.confirm) args.confirm = 2 // nobody to ask any more
        if (item.method === 'projectit.work_orders.update_work_order') {
          // The job may have changed since; the change made on the phone wins.
          args.modified = (await request(DETAIL, { name: args.name })).work_order.modified
        }
        const result = await request(item.method, args)
        if (item.method === 'projectit.attendance.check_in' && result?.name) {
          created[`pending-${item.id}`] = result.name
          await put('cache', { key: 'techy-offline-timesheets', value: created, at: Date.now() })
        }
        await del('outbox', item.id)
      } catch (e) {
        if (e.offline) {
          offline.online = false
          break
        }
        await put('outbox', { ...item, failed: true, error: e.message })
      }
      if (item.job) touched.add(item.job)
      if (item.target && item.target[0] !== DETAIL) screens.set(keyOf(...item.target), item.target)
      offline.online = true
    }
    for (const job of touched) {
      try {
        await remember(DETAIL, { name: job }, await request(DETAIL, { name: job }))
      } catch (e) {
        /* the next read refreshes it */
      }
    }
    for (const [method, args] of screens.values()) {
      try {
        await remember(method, args, await request(method, args))
      } catch (e) {
        /* the next read refreshes it */
      }
    }
  } finally {
    offline.syncing = false
    await counts()
    if (touched.size || screens.size) window.dispatchEvent(new CustomEvent('techy-synced', { detail: [...touched] }))
  }
}

/** Timesheets created by check-ins sent from the outbox, by the placeholder the phone gave them. */
async function realNames() {
  const row = await get('cache', 'techy-offline-timesheets').catch(() => null)
  return row?.value || {}
}

/** Everything waiting to be sent, oldest first, for the "Waiting to send" list. */
export async function outbox() {
  try {
    return (await all('outbox')).sort((a, b) => a.id - b.id)
  } catch (e) {
    return []
  }
}

export async function retry(item) {
  const { failed, error, ...rest } = item
  await put('outbox', rest)
  await counts()
  return sync()
}
export async function discard(item) {
  await del('outbox', item.id)
  await counts()
  // Show the job (or screen) as it really is again.
  const target = item.target || (item.job ? [DETAIL, { name: item.job }] : null)
  if (target) {
    try {
      await remember(target[0], target[1], await request(target[0], target[1]))
    } catch (e) {
      /* offline: it refreshes later */
    }
  }
  window.dispatchEvent(new CustomEvent('techy-synced', { detail: item.job ? [item.job] : [] }))
}

/** The offline-aware api(): see the top of this file. */
export async function api(method, args = {}) {
  const read = READS.has(method)
  const write = method in WRITES
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    offline.online = false
    if (read) return recall(method, args)
    if (write) return queue(method, args)
  }
  try {
    const result = await request(method, args)
    if (!offline.online) {
      offline.online = true
      sync()
    }
    if (read) remember(method, args, result)
    // Changes answer with the job as it now is: keep the saved copy current.
    if (result?.work_order?.name && Array.isArray(result.steps)) remember(DETAIL, { name: result.work_order.name }, result)
    return result
  } catch (e) {
    if (!e.offline) throw e
    offline.online = false
    if (read) return recall(method, args)
    if (write) return queue(method, args)
    throw new Error("You're offline. This needs a connection.")
  }
}

/** Save my open jobs on the phone, so they can be opened without a connection. */
export async function prefetch() {
  // Staff work orders only; the customer app (/plant) keeps its own logs (data/plant.js).
  if (!navigator.onLine || location.pathname.includes('/plant')) return
  try {
    const list = await api('projectit.work_orders.list_work_orders', { scope: 'mine', status: 'Active', page_length: 100 })
    for (const row of list.work_orders.slice(0, 40)) await api(DETAIL, { name: row.name })
    await api('projectit.failures.options')
    await api('projectit.procedures.list_procedures').catch(() => {})
  } catch (e) {
    /* best effort */
  }
  // Techy Work: today's projects, so a technician can check in at a site with no signal.
  try {
    const today = await api(TODAY)
    for (const p of (today.projects || []).slice(0, 10)) await api('projectit.tasks.work_tasks', { project: p.project }).catch(() => {})
  } catch (e) {
    /* not a Techy Work user */
  }
}

let started = false
/** Watch the connection, register the service worker and send anything left from last time. */
export function startOffline() {
  if (started || typeof window === 'undefined') return
  started = true
  window.addEventListener('online', () => {
    offline.online = true
    sync()
    prefetch()
  })
  window.addEventListener('offline', () => (offline.online = false))
  counts().then(() => navigator.onLine && offline.pending && sync())
  if ('serviceWorker' in navigator && location.pathname.startsWith('/techy-app') && !import.meta.env.DEV) {
    navigator.serviceWorker.register('/techy-sw.js', { scope: '/techy-app/' }).catch(() => {})
  }
}
