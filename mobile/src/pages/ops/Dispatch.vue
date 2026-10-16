<template>
  <section class="space-y-4 p-4 md:p-6">
    <PageHeader title="Dispatch" subtitle="Plan who does which job on which day. Drag a job onto a technician and day, or tap it to plan it.">
      <div class="segmented" role="group" aria-label="Days shown">
        <button v-for="s in SPANS" :key="s.days" :aria-pressed="span === s.days" @click="span = s.days; load_()">{{ s.label }}</button>
      </div>
    </PageHeader>
    <div class="flex flex-wrap items-center gap-2">
      <button class="btn btn-secondary btn-icon" aria-label="Earlier" @click="move(-1)"><FeatherIcon name="chevron-left" class="h-4 w-4" /></button>
      <button class="btn btn-secondary btn-sm" @click="start = ''; load_()">Today</button>
      <button class="btn btn-secondary btn-icon" aria-label="Later" @click="move(1)"><FeatherIcon name="chevron-right" class="h-4 w-4" /></button>
      <h2 v-if="b" class="ml-1 text-sm font-semibold text-gray-800">{{ rangeLabel }}</h2>
      <span v-if="busy" class="text-xs text-gray-400">Saving…</span>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!b" class="h-96 animate-pulse rounded-xl bg-gray-200/70" aria-label="Loading" />

    <div v-else class="flex flex-col gap-4 2xl:flex-row 2xl:items-start">
      <!-- Jobs to plan: one row of jobs above the calendar, a column beside it on very wide screens, so the
           calendar stays near the top and a whole week fits while dragging. -->
      <aside class="card shrink-0 overflow-hidden 2xl:sticky 2xl:top-4 2xl:w-72" :class="over === 'backlog' ? 'ring-2 ring-brand-300' : ''" aria-label="Jobs to plan" @dragover.prevent="over = 'backlog'" @dragleave="over === 'backlog' && (over = '')" @drop.prevent="drop(null, null)">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-gray-100 px-4 py-2.5 2xl:block 2xl:space-y-2 2xl:px-3 2xl:py-3">
          <h2 class="card-title">To plan <span class="ml-1 text-xs font-normal text-gray-500">{{ b.backlog.length + b.late.length }}</span></h2>
          <input v-model="filter" type="search" class="input h-8 w-full text-sm sm:w-56 2xl:w-full" placeholder="Filter jobs" aria-label="Filter jobs to plan" />
          <p class="text-[11px] text-gray-400 2xl:hidden">Drag a job onto a day. Drop one here to take it off the plan.</p>
        </div>
        <div class="flex gap-3 overflow-x-auto p-3 2xl:block 2xl:max-h-[60vh] 2xl:space-y-3 2xl:overflow-y-auto">
          <div v-if="late.length" class="shrink-0">
            <p class="section-label mb-1.5 text-red-600">Planned earlier, not done</p>
            <ul class="flex gap-1.5 2xl:block 2xl:space-y-1.5"><li v-for="j in late" :key="j.name" class="w-52 shrink-0 2xl:w-auto"><JobChip :job="j" :from="j.assignees[0] || null" show-day /></li></ul>
          </div>
          <div class="shrink-0">
            <p v-if="late.length" class="section-label mb-1.5">Not planned</p>
            <ul class="flex gap-1.5 2xl:block 2xl:space-y-1.5"><li v-for="j in backlog" :key="j.name" class="w-52 shrink-0 2xl:w-auto"><JobChip :job="j" :from="j.assignees[0] || null" /></li></ul>
            <p v-if="!backlog.length && !late.length" class="py-3 text-sm text-gray-500">Every open job is planned.</p>
          </div>
        </div>
        <p class="hidden border-t border-gray-100 px-4 py-2 text-[11px] text-gray-400 2xl:block">Drop a job here to take it off the plan.</p>
      </aside>

      <!-- Technicians × days -->
      <div class="card min-w-0 flex-1 overflow-x-auto">
        <table class="w-full table-fixed border-collapse text-left" :style="{ minWidth: `${11 + b.days.length * (span === 1 ? 24 : 8)}rem` }">
          <caption class="sr-only">Jobs planned for each technician and day</caption>
          <thead>
            <tr class="border-b border-gray-200">
              <th scope="col" class="sticky left-0 z-10 w-44 bg-white px-3 py-2 text-xs font-semibold text-gray-500">Technician</th>
              <th v-for="d in b.days" :key="d" scope="col" class="px-2 py-2 text-xs font-semibold" :class="d === b.today ? 'text-brand-700' : isWeekend(d) ? 'text-gray-400' : 'text-gray-600'">
                {{ dayName(d) }} <span class="font-normal">{{ dayNum(d) }}</span><span v-if="d === b.today" class="ml-1 rounded bg-brand-600 px-1 text-[10px] text-white">Today</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in rows" :key="p.user || 'none'" class="border-b border-gray-100 align-top last:border-0">
              <th scope="row" class="sticky left-0 z-10 bg-white px-3 py-2.5">
                <span class="flex items-center gap-2">
                  <UserAvatar v-if="p.user" :name="p.full_name" :image="p.image" size="sm" />
                  <FeatherIcon v-else name="user-x" class="h-4 w-4 text-gray-400" />
                  <span class="min-w-0"><span class="block truncate text-sm font-medium text-gray-900">{{ p.full_name }}</span><span class="block text-[11px] font-normal text-gray-500">{{ jobCount(p.user) }} job{{ jobCount(p.user) === 1 ? '' : 's' }}</span></span>
                </span>
              </th>
              <td
                v-for="d in b.days"
                :key="d"
                :data-cell="key(p.user, d)"
                class="h-24 px-1.5 py-1.5 transition-colors"
                :class="[over === key(p.user, d) ? 'bg-brand-50 ring-2 ring-inset ring-brand-300' : d === b.today ? 'bg-brand-50/30' : isWeekend(d) ? 'bg-gray-50' : '']"
                :aria-label="`${p.full_name}, ${dayName(d)} ${dayNum(d)}: ${cell(p.user, d).length} job${cell(p.user, d).length === 1 ? '' : 's'}`"
                @dragover.prevent="over = key(p.user, d)"
                @dragleave="over === key(p.user, d) && (over = '')"
                @drop.prevent="drop(p.user, d)"
              >
                <ul class="space-y-1">
                  <li v-for="j in cell(p.user, d)" :key="j.name"><JobChip :job="j" :from="p.user" compact /></li>
                </ul>
                <p v-if="cell(p.user, d).length > 4" class="mt-1 text-[10px] font-semibold text-amber-700">Busy day</p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Plan one job (tap a job; the keyboard and phone alternative to dragging) -->
    <Modal v-model="planning" title="Plan job" :subtitle="plan.job?.subject">
      <form id="plan-form" class="space-y-4" @submit.prevent="savePlan">
        <div>
          <label class="label" for="plan-day">Day</label>
          <input id="plan-day" v-model="plan.date" type="date" class="input" />
          <p v-if="plan.job?.exp_end_date" class="hint">Due {{ formatDate(plan.job.exp_end_date) }}</p>
        </div>
        <div>
          <label class="label" for="plan-user">Technician</label>
          <select id="plan-user" v-model="plan.user" class="input">
            <option value="">{{ plan.job?.assignees.length ? 'Keep the current technicians' : 'Nobody yet' }}</option>
            <option v-for="p in b?.people || []" :key="p.user" :value="p.user">{{ p.full_name }}</option>
          </select>
          <p v-if="plan.from && plan.user && plan.user !== plan.from" class="hint">Moves the job from {{ nameOf(plan.from) }}.</p>
        </div>
      </form>
      <template #footer>
        <router-link :to="{ name: 'OpsWorkOrder', params: { name: plan.job?.name || 'x' } }" class="btn btn-ghost mr-auto">Open job</router-link>
        <button v-if="plan.job?.exp_start_date" type="button" class="btn btn-secondary" :disabled="busy" @click="unplan">Take off the plan</button>
        <button form="plan-form" class="btn btn-primary" :disabled="busy || !plan.date">Save</button>
      </template>
    </Modal>
  </section>
</template>
<script setup>
import { ref, reactive, computed, h, onMounted, onBeforeUnmount } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import Modal from '@/components/ops/Modal.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import { api, formatDate, onRealtime } from '@/data/ops'

const SPANS = [{ days: 1, label: 'Day' }, { days: 7, label: 'Week' }, { days: 14, label: '2 weeks' }]
const PRIORITY = { Urgent: 'bg-red-500', High: 'bg-orange-400', Medium: 'bg-brand-500', Low: 'bg-gray-300' }
const span = ref(7)
const start = ref('')
const b = ref(null)
const busy = ref(false)
const error = ref('')
const filter = ref('')
const over = ref('')
let dragging = null // { job, from }

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const asDate = (s) => new Date(`${s}T00:00:00`)
const dayName = (s) => asDate(s).toLocaleDateString(undefined, { weekday: 'short' })
const dayNum = (s) => asDate(s).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
const isWeekend = (s) => [0, 6].includes(asDate(s).getDay())
const rangeLabel = computed(() => (b.value.days.length === 1 ? formatDate(b.value.start) : `${formatDate(b.value.start)} – ${formatDate(b.value.end)}`))
const key = (user, day) => `${user || 'none'}|${day}`
const matches = (j) => !filter.value.trim() || `${j.subject} ${j.machine || ''} ${j.where || ''} ${j.name}`.toLowerCase().includes(filter.value.trim().toLowerCase())
const backlog = computed(() => b.value.backlog.filter(matches))
const late = computed(() => b.value.late.filter(matches))
const rows = computed(() => [...b.value.people, { user: null, full_name: 'Not assigned' }])
const nameOf = (user) => b.value?.people.find((p) => p.user === user)?.full_name || user
const cell = (user, day) => b.value.jobs.filter((j) => j.exp_start_date === day && (user ? j.assignees.includes(user) : !j.assignees.length))
const jobCount = (user) => b.value.jobs.filter((j) => (user ? j.assignees.includes(user) : !j.assignees.length) && j.status !== 'Cancelled').length

// A job on the board: drag it, or tap it to plan it.
const JobChip = (props) => {
  const j = props.job
  const done = ['Completed', 'Cancelled'].includes(j.status)
  return h('button', {
    type: 'button',
    draggable: !done,
    class: ['group flex w-full items-start gap-1.5 rounded-lg border px-2 py-1.5 text-left text-xs transition', done ? 'border-gray-100 bg-gray-50 text-gray-400 line-through' : 'border-gray-200 bg-white shadow-sm hover:border-brand-300 cursor-grab active:cursor-grabbing'],
    title: `${j.subject}${j.machine ? ` · ${j.machine}` : ''}${j.where ? ` · ${j.where}` : ''}`,
    'aria-label': `${j.subject}${j.where ? `, ${j.where}` : ''}, ${j.priority} priority${done ? `, ${j.status.toLowerCase()}` : ''}. Plan this job`,
    onDragstart: (e) => {
      dragging = { job: j, from: props.from }
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', j.name)
    },
    onDragend: () => (over.value = ''),
    onClick: () => !done && openPlan(j, props.from),
  }, [
    h('span', { class: ['mt-1 h-2 w-2 shrink-0 rounded-full', PRIORITY[j.priority] || 'bg-gray-300'] }),
    h('span', { class: 'min-w-0 flex-1' }, [
      h('span', { class: ['block font-medium text-gray-900', props.compact ? 'line-clamp-2' : 'truncate', done ? 'text-gray-400' : ''] }, j.subject),
      j.where || j.machine ? h('span', { class: 'block truncate text-[11px] text-gray-500' }, j.where || j.machine) : null,
      props.showDay && j.exp_start_date ? h('span', { class: 'block text-[11px] text-red-600' }, `Planned ${formatDate(j.exp_start_date)}`) : null,
      j.status === 'Working' ? h('span', { class: 'mt-0.5 inline-block rounded bg-amber-100 px-1 text-[10px] text-amber-800' }, 'In progress') : null,
    ]),
  ])
}
JobChip.props = ['job', 'from', 'compact', 'showDay']

async function load_() {
  error.value = ''
  try {
    b.value = await api('projectit.dispatch.board', { start: start.value || undefined, days: span.value })
    start.value = b.value.start
  } catch (e) {
    error.value = e.message
  }
}
function move(dir) {
  const d = asDate(b.value.start)
  d.setDate(d.getDate() + dir * span.value)
  start.value = iso(d)
  load_()
}

async function schedule(job, values) {
  busy.value = true
  error.value = ''
  try {
    let result = await api('projectit.dispatch.schedule', { name: job.name, ...values })
    if (result.needs_due_move) {
      if (!window.confirm(`${job.subject} is due ${formatDate(result.needs_due_move)}. Move the due date to ${formatDate(values.date)} too?`)) return false
      result = await api('projectit.dispatch.schedule', { name: job.name, ...values, move_due: 1 })
    }
    await load_()
    return true
  } catch (e) {
    error.value = e.message
    return false
  } finally {
    busy.value = false
  }
}
function drop(user, day) {
  over.value = ''
  const d = dragging
  dragging = null
  if (!d) return
  const { job, from } = d
  if (!day) {
    if (job.exp_start_date) schedule(job, { date: null })
    return
  }
  if (job.exp_start_date === day && (from || null) === (user || null)) return
  // Dropped on "Not assigned": keep the plan's day and leave the technicians as they are.
  schedule(job, { date: day, user: user || null, from_user: user ? from || null : null })
}

const planning = ref(false)
const plan = reactive({ job: null, from: null, date: '', user: '' })
function openPlan(job, from) {
  Object.assign(plan, { job, from: from || null, date: job.exp_start_date || b.value.today, user: '' })
  planning.value = true
}
async function savePlan() {
  if (await schedule(plan.job, { date: plan.date, user: plan.user || null, from_user: plan.user ? plan.from : null })) planning.value = false
}
async function unplan() {
  if (await schedule(plan.job, { date: null })) planning.value = false
}

let timer = null
const stop = onRealtime('techy_work_order', () => {
  clearTimeout(timer)
  timer = setTimeout(() => !busy.value && load_(), 1500)
})
onMounted(load_)
onBeforeUnmount(stop)
</script>
