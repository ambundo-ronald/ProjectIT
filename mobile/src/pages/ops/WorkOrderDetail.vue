<template>
  <section class="mx-auto max-w-6xl p-4 md:p-8" :class="actionBar ? 'pb-40 md:pb-8' : ''">
    <nav class="mb-4 hidden items-center gap-1.5 text-sm text-gray-500 md:flex" aria-label="Breadcrumb">
      <router-link :to="{ name: 'OpsWorkOrders' }" class="hover:text-gray-800">Work orders</router-link>
      <FeatherIcon name="chevron-right" class="h-4 w-4" />
      <span class="text-gray-800">#{{ route.params.name }}</span>
    </nav>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="!data && !error" class="space-y-4" aria-live="polite" aria-label="Loading">
      <div class="h-40 animate-pulse rounded-xl bg-gray-200/70" />
      <div class="h-56 animate-pulse rounded-xl bg-gray-200/70" />
    </div>

    <div v-if="data" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div class="min-w-0 space-y-5">
        <!-- Header -->
        <div class="card p-5">
          <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span class="font-mono">#{{ wo.name }}</span>
            <span v-if="wo.custom_work_category" class="rounded-md bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">{{ wo.custom_work_category }}</span>
            <span v-if="data.pm_log" class="inline-flex items-center gap-1 rounded-md bg-accent-50 px-1.5 py-0.5 font-medium text-accent-600"><FeatherIcon name="repeat" class="h-3 w-3" />Preventive maintenance</span>
          </div>
          <h1 class="mt-2 text-[20px] font-semibold leading-snug tracking-tight md:text-[24px]">{{ wo.subject }}</h1>
          <div class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <StatusPill :status="overdue ? 'Overdue' : wo.status" />
            <PriorityFlag :priority="wo.priority" />
            <span v-if="wo.exp_end_date" class="inline-flex items-center gap-1 text-[13px]" :class="overdue ? 'font-semibold text-red-600' : 'text-gray-600'"><FeatherIcon name="calendar" class="h-3.5 w-3.5" />Due {{ formatDate(wo.exp_end_date) }}</span>
            <router-link v-if="data.asset" :to="{ name: 'OpsAsset', params: { name: data.asset.name } }" class="inline-flex items-center gap-1 text-[13px] text-gray-600 hover:text-brand-700"><FeatherIcon name="box" class="h-3.5 w-3.5" />{{ data.asset.asset_name }}</router-link>
            <router-link v-if="data.equipment" :to="{ name: 'OpsEquipmentDetail', params: { name: data.equipment.name } }" class="inline-flex items-center gap-1 text-[13px] text-gray-600 hover:text-brand-700"><FeatherIcon name="droplet" class="h-3.5 w-3.5" />{{ data.equipment.equipment_name }}</router-link>
            <CoverageBadge v-if="data.equipment" :kind="data.equipment.coverage.kind" :until="data.equipment.coverage.until" />
          </div>

          <!-- Status stepper -->
          <ol v-if="wo.status !== 'Cancelled'" class="mt-5 grid grid-cols-4 gap-1.5" aria-label="Status">
            <li v-for="(step, i) in steps" :key="step.status">
              <button
                type="button"
                class="group w-full text-left disabled:cursor-default"
                :disabled="!canAct || step.status === current || busy"
                :aria-current="step.status === current ? 'step' : undefined"
                :title="canAct && step.status !== current ? `Move to ${step.label}` : step.label"
                @click="setStatus(step.status)"
              >
                <span class="block h-1.5 rounded-full transition-colors" :class="i <= stepIndex ? step.bar : 'bg-gray-200 group-enabled:group-hover:bg-gray-300'" />
                <span class="mt-1.5 block truncate text-[11px] font-medium sm:text-xs" :class="step.status === current ? 'text-gray-900' : 'text-gray-400'">{{ step.label }}</span>
              </button>
            </li>
          </ol>
          <p v-else class="mt-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">This work order was cancelled.</p>

          <div v-if="data.workflow" class="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Tasks on this site use an ERPNext Workflow. <a :href="deskLink" target="_blank" rel="noopener" class="font-medium underline">Open in ERPNext</a> to change status.
          </div>
          <!-- Desktop actions -->
          <div v-else-if="canAct" class="mt-5 hidden flex-wrap gap-2 md:flex">
            <button v-for="a in actions" :key="a.status" class="btn" :class="a.style" :disabled="busy" @click="setStatus(a.status)"><FeatherIcon :name="a.icon" class="h-4 w-4" />{{ a.label }}</button>
            <button v-if="data.manager && !closed" class="btn btn-ghost ml-auto text-gray-500" :disabled="busy" @click="cancel">Cancel work order</button>
          </div>
        </div>

        <TimerCard v-if="data.timer && (data.timer.entries.length || data.timer.can_start)" :timer="data.timer" :work-order="wo.name" :status="wo.status" :assignees="data.assignees" @updated="timed" @error="warn" />
        <CustomerSiteCard v-if="data.equipment" :equipment="data.equipment" class="lg:hidden" />

        <!-- Description -->
        <div v-if="data.description" class="card p-5">
          <h2 class="section-label">Description</h2>
          <p class="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800">{{ data.description }}</p>
        </div>

        <!-- Procedure (typed steps from the library) -->
        <div v-if="data.procedure" id="procedure" class="card overflow-hidden">
          <div class="flex items-start justify-between gap-3 px-5 pb-2 pt-4">
            <div class="min-w-0">
              <p class="section-label">Procedure</p>
              <h2 class="mt-0.5 text-[16px] font-semibold leading-snug">{{ data.procedure.title }}</h2>
            </div>
            <button v-if="data.can_write && !closed" class="btn btn-ghost btn-sm shrink-0 text-gray-500" :disabled="busy" @click="detachProcedure">Remove</button>
          </div>
          <ProcedureRun :steps="data.procedure.steps" :locked="!data.can_write || closed" :saving="saving" :highlight="highlight" @answer="answer" @error="warn" />
        </div>
        <div v-else-if="data.can_write && !closed" class="card flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
          <div class="min-w-0 flex-1">
            <h2 class="card-title">Add a procedure</h2>
            <p class="mt-0.5 text-sm text-gray-500">Readings, pass/fail checks, photos and sign-off from the procedure library.</p>
          </div>
          <div class="flex gap-2 sm:w-80">
            <ProcedureSelect v-model="picked" placeholder="Choose a procedure" class="min-w-0 flex-1" />
            <button class="btn btn-primary" :disabled="!picked || busy" @click="attachProcedure">Add</button>
          </div>
        </div>

        <FailureCard v-if="data.failure && (data.failure.has_machine || data.failure.problem || data.failure.required || ['Corrective', 'Inspection', 'Safety'].includes(wo.custom_work_category))" :failure="data.failure" :work-order="wo.name" @updated="set" @error="warn" />
        <PartsCard v-if="data.parts && (data.parts.rows.length || data.parts.can_edit)" :parts="data.parts" :work-order="wo.name" @updated="set" @error="warn" @reload="load" />
        <LabourCard v-if="data.billing?.customer" :billing="data.billing" :logged="data.timer?.total || 0" :work-order="wo.name" @updated="set" @error="warn" />
        <ServiceReportCard v-if="data.report" :report="data.report" :work-order="wo.name" @updated="set" @error="warn" />
        <MetersCard v-if="data.meters?.length" :meters="data.meters" :work-order="wo.name" :can-record="data.can_write && !closed" @reload="load" />

        <!-- Quick checklist (child Tasks) -->
        <div v-if="data.steps.length" class="card overflow-hidden">
          <div class="card-header">
            <h2 class="card-title">Checklist</h2>
            <span class="text-sm font-medium" :class="doneSteps === data.steps.length ? 'text-green-600' : 'text-gray-500'">{{ doneSteps }} of {{ data.steps.length }} done</span>
          </div>
          <div class="h-1 bg-gray-100"><div class="h-1 bg-green-500 transition-all" :style="{ width: `${(doneSteps / data.steps.length) * 100}%` }" /></div>
          <ul class="divide-y divide-gray-100">
            <li v-for="(step, i) in data.steps" :key="step.name">
              <label class="flex min-h-[3.25rem] cursor-pointer items-center gap-3 px-5 py-2 hover:bg-gray-50" :class="!data.can_write || closed ? 'cursor-default hover:bg-transparent' : ''">
                <input type="checkbox" class="h-5 w-5 rounded-md border-gray-300 text-green-600 focus:ring-green-500" :checked="step.status === 'Completed'" :disabled="busy || !data.can_write || closed" @change="toggle(step, $event.target.checked)" />
                <span class="w-5 text-xs font-semibold text-gray-400">{{ i + 1 }}</span>
                <span class="text-[15px]" :class="step.status === 'Completed' ? 'text-gray-400' : 'text-gray-800'">{{ step.subject }}</span>
              </label>
            </li>
          </ul>
        </div>

        <!-- Photos -->
        <div class="card p-5">
          <div class="flex items-center justify-between">
            <h2 class="card-title">Photos & files</h2>
            <span class="text-xs text-gray-500">{{ files.length }}</span>
          </div>
          <div class="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
            <a v-for="file in files" :key="file.name" :href="file.file_url" target="_blank" rel="noopener" class="group relative block aspect-square overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
              <img v-if="/\.(jpe?g|png|gif|webp)$/i.test(file.file_url)" :src="file.file_url" :alt="file.file_name" class="h-full w-full object-cover transition group-hover:scale-105" loading="lazy" />
              <span v-else class="flex h-full flex-col items-center justify-center gap-1 p-2 text-center text-[11px] text-gray-600"><FeatherIcon name="file" class="h-5 w-5" />{{ file.file_name }}</span>
            </a>
            <PhotoButtons v-if="data.can_write" variant="tiles" multiple :busy="uploading" :disabled="busy" @photos="upload" @error="warn" />
          </div>
        </div>

        <!-- Activity -->
        <div class="card p-5">
          <h2 class="card-title">Activity</h2>
          <ol v-if="data.comments.length" class="mt-4 space-y-4">
            <li v-for="c in data.comments" :key="c.name" class="flex gap-3">
              <UserAvatar v-if="c.comment_type === 'Comment'" :name="c.comment_by" size="md" />
              <span v-else class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500"><FeatherIcon name="activity" class="h-4 w-4" /></span>
              <div class="min-w-0 flex-1">
                <p class="text-xs text-gray-500"><span class="text-[13px] font-semibold text-gray-900">{{ c.comment_type === 'Comment' ? c.comment_by : 'System' }}</span> · {{ c.pending ? 'saved on this phone, waiting to send' : fromNow(c.creation) }}</p>
                <RichText :text="c.content" :names="names" class="mt-0.5 text-[14px] leading-relaxed" :class="c.comment_type === 'Info' ? 'text-gray-500' : 'text-gray-800'" />
              </div>
            </li>
          </ol>
          <p v-else class="mt-2 text-sm text-gray-500">No updates yet. Post progress or questions, and @mention a teammate to loop them in.</p>
          <Composer v-if="data.can_write" class="mt-5" placeholder="Add an update…" :people="mentionable" :submit="comment" />
        </div>
      </div>

      <!-- Details -->
      <aside class="space-y-4 lg:sticky lg:top-8 lg:self-start">
        <CustomerSiteCard v-if="data.equipment" :equipment="data.equipment" class="hidden lg:block" />
        <div class="card divide-y divide-gray-100 text-sm">
          <div class="p-4">
            <div class="flex items-center justify-between">
              <h3 class="section-label">Assigned to</h3>
              <button v-if="data.manager && !closed" class="text-xs font-medium text-brand-600 hover:underline" @click="editing = !editing">{{ editing ? 'Done' : 'Edit' }}</button>
            </div>
            <ul class="mt-2 space-y-2">
              <li v-for="p in data.assignees" :key="p.user" class="flex items-center gap-2"><UserAvatar :name="p.full_name" :image="p.image" size="sm" />{{ p.full_name }}</li>
              <li v-if="!data.assignees.length" class="text-gray-400">Nobody yet</li>
            </ul>
            <div v-if="editing" class="mt-3 space-y-2">
              <PeoplePicker v-model="assignees" :initial="data.assignees" />
              <button class="btn btn-primary btn-sm w-full" :disabled="busy" @click="saveAssignees">Save assignees</button>
            </div>
          </div>
          <dl class="space-y-3 p-4">
            <div class="flex items-center justify-between gap-3">
              <dt class="text-gray-500">Due date</dt>
              <dd v-if="data.manager && !closed"><input type="date" :value="wo.exp_end_date || ''" class="input h-8 w-36 px-2 text-[13px]" aria-label="Due date" @change="update({ due_date: $event.target.value })" /></dd>
              <dd v-else :class="overdue ? 'font-semibold text-red-600' : ''">{{ wo.exp_end_date ? formatDate(wo.exp_end_date) : '—' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-gray-500">Priority</dt>
              <dd v-if="data.manager && !closed">
                <select :value="wo.priority" class="input h-8 w-36 px-2 text-[13px]" aria-label="Priority" @change="update({ priority: $event.target.value })">
                  <option v-for="p in ['Low', 'Medium', 'High', 'Urgent']" :key="p">{{ p }}</option>
                </select>
              </dd>
              <dd v-else><PriorityFlag :priority="wo.priority" /></dd>
            </div>
            <div v-if="data.asset" class="flex justify-between gap-3">
              <dt class="text-gray-500">Asset</dt>
              <dd class="min-w-0 truncate text-right"><router-link :to="{ name: 'OpsAsset', params: { name: data.asset.name } }" class="link">{{ data.asset.asset_name }}</router-link></dd>
            </div>
            <div v-if="wo.custom_location" class="flex justify-between gap-3">
              <dt class="text-gray-500">Location</dt>
              <dd class="text-right">{{ wo.custom_location }}</dd>
            </div>
            <div v-if="wo.project" class="flex justify-between gap-3">
              <dt class="text-gray-500">Project</dt>
              <dd class="truncate text-right">{{ wo.project }}</dd>
            </div>
            <div v-if="data.request" class="flex justify-between gap-3">
              <dt class="text-gray-500">Request</dt>
              <dd class="min-w-0 truncate text-right"><router-link :to="{ name: 'OpsRequests', query: { open: data.request.name } }" class="link">{{ data.request.subject }}</router-link></dd>
            </div>
            <div class="flex justify-between gap-3">
              <dt class="text-gray-500">Created</dt>
              <dd class="text-right">{{ formatDate(wo.creation) }}</dd>
            </div>
          </dl>
          <div class="p-4">
            <a :href="deskLink" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-brand-700"><FeatherIcon name="external-link" class="h-3.5 w-3.5" />Open in ERPNext</a>
          </div>
        </div>
      </aside>
    </div>

    <!-- Mobile action bar -->
    <div v-if="actionBar" class="fixed inset-x-0 bottom-16 z-30 flex gap-2 border-t border-gray-200 bg-white/95 p-3 backdrop-blur md:hidden">
      <button v-for="a in actions" :key="a.status" class="btn btn-lg flex-1" :class="a.style" :disabled="busy" @click="setStatus(a.status)"><FeatherIcon :name="a.icon" class="h-5 w-5" />{{ a.short || a.label }}</button>
    </div>
  </section>
</template>
<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import StatusPill from '@/components/ops/StatusPill.vue'
import PriorityFlag from '@/components/ops/PriorityFlag.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import Composer from '@/components/ops/Composer.vue'
import RichText from '@/components/ops/RichText.vue'
import PeoplePicker from '@/components/ops/PeoplePicker.vue'
import ProcedureRun from '@/components/ops/ProcedureRun.vue'
import CoverageBadge from '@/components/ops/CoverageBadge.vue'
import CustomerSiteCard from '@/components/ops/CustomerSiteCard.vue'
import PartsCard from '@/components/ops/PartsCard.vue'
import LabourCard from '@/components/ops/LabourCard.vue'
import MetersCard from '@/components/ops/MetersCard.vue'
import ServiceReportCard from '@/components/ops/ServiceReportCard.vue'
import TimerCard from '@/components/ops/TimerCard.vue'
import FailureCard from '@/components/ops/FailureCard.vue'
import PhotoButtons from '@/components/ops/PhotoButtons.vue'
import ProcedureSelect from '@/components/ops/ProcedureSelect.vue'
import { ui } from '@/data/apps'
import { api, loadMe, onRealtime, formatDate, fromNow, isOverdue, safeFile } from '@/data/ops'

const route = useRoute()
const data = ref(null)
const error = ref('')
const busy = ref(false)
const uploading = ref(false)
const editing = ref(false)
const assignees = ref([])
const mentionable = ref([])
const picked = ref('')
const saving = reactive({})
const highlight = ref('')

const steps = [
  { status: 'Open', label: 'Open', bar: 'bg-blue-500' },
  { status: 'Working', label: 'In progress', bar: 'bg-amber-500' },
  { status: 'Pending Review', label: 'On hold', bar: 'bg-violet-500' },
  { status: 'Completed', label: 'Done', bar: 'bg-green-500' },
]
const wo = computed(() => data.value.work_order)
const current = computed(() => (wo.value.status === 'Overdue' ? 'Open' : wo.value.status))
const stepIndex = computed(() => steps.findIndex((s) => s.status === current.value))
const closed = computed(() => ['Completed', 'Cancelled'].includes(wo.value.status))
const overdue = computed(() => !closed.value && (wo.value.status === 'Overdue' || isOverdue(wo.value)))
const canAct = computed(() => data.value?.can_write && !data.value?.workflow)
const doneSteps = computed(() => data.value.steps.filter((s) => s.status === 'Completed').length)
const files = computed(() => data.value.files.filter((f) => f.pending || safeFile(f.file_url)))
const deskLink = computed(() => `/desk/task/${encodeURIComponent(route.params.name)}`)
const names = computed(() => Object.fromEntries(mentionable.value.map((p) => [p.user, p.full_name])))

const START = { status: 'Working', label: 'Start work', short: 'Start', icon: 'play', style: 'btn-warning' }
const HOLD = { status: 'Pending Review', label: 'Put on hold', short: 'Hold', icon: 'pause', style: 'btn-secondary' }
const COMPLETE = { status: 'Completed', label: 'Mark complete', short: 'Complete', icon: 'check-circle', style: 'btn-success' }
const actions = computed(() => {
  if (!data.value) return []
  const s = wo.value.status
  if (s === 'Completed' || s === 'Cancelled') return [{ status: 'Open', label: 'Reopen', icon: 'rotate-ccw', style: 'btn-secondary' }]
  if (s === 'Working') return [HOLD, COMPLETE]
  if (s === 'Pending Review') return [{ ...START, label: 'Resume work', short: 'Resume' }, COMPLETE]
  return [START, COMPLETE]
})
const actionBar = computed(() => !!data.value && canAct.value && wo.value.status !== 'Cancelled')
watch(actionBar, (on) => (ui.dockLift = on ? 76 : 0), { immediate: true })

function set(result) {
  data.value = result
  assignees.value = result.assignees.map((p) => p.user)
}

async function run(work) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
  } catch (e) {
    error.value = e.message
    throw e
  } finally {
    busy.value = false
  }
}

const load = () => run(async () => set(await api('projectit.work_orders.get_work_order', { name: route.params.name }))).catch(() => {})
const update = (changes) => run(async () => set(await api('projectit.work_orders.update_work_order', { name: wo.value.name, modified: wo.value.modified, ...changes }))).catch(() => {})
function setStatus(status) {
  const procedure = data.value.procedure
  if (status === 'Completed' && procedure?.missing) {
    // Same rule the server enforces; point at the first unanswered required step.
    const first = procedure.steps.find((s) => s.required && !s.value && s.field_type !== 'Heading')
    warn(`Finish the procedure first: ${procedure.missing} required step${procedure.missing === 1 ? '' : 's'} still need${procedure.missing === 1 ? 's' : ''} an answer.`)
    highlight.value = first?.name || ''
    document.getElementById(`step-${first?.name}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  if (status === 'Completed' && data.value.failure?.missing?.length) {
    warn(`Choose the ${data.value.failure.missing.map((k) => k.toLowerCase()).join(' and ')} code before completing this repair.`)
    document.getElementById('failure')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  update({ status })
}
const cancel = () => window.confirm('Cancel this work order?') && setStatus('Cancelled')
const saveAssignees = () => update({ assignees: assignees.value }).then(() => (editing.value = false))
const toggle = (step, done) => run(async () => set(await api('projectit.work_orders.toggle_step', { name: wo.value.name, step: step.name, done: done ? 1 : 0 }))).catch(() => load())
const attachProcedure = () => run(async () => set(await api('projectit.procedures.attach', { work_order: wo.value.name, procedure: picked.value }))).then(() => (picked.value = '')).catch(() => {})
const detachProcedure = () => window.confirm('Remove this procedure from the work order?') && run(async () => set(await api('projectit.procedures.detach', { work_order: wo.value.name }))).catch(() => {})

// Starting or stopping the timer also changes the running-timer banner in the app shell.
function timed(result) {
  set(result)
  loadMe(true).catch(() => {})
}
const warn = (title) => toast({ title, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })

// Answers save one at a time, in order, and show instantly while saving.
let queue = Promise.resolve()
function answer(step, payload) {
  const row = data.value.procedure.steps.find((s) => s.name === step.name)
  if (row && !payload.photo) row.value = payload.value
  if (highlight.value === step.name) highlight.value = ''
  saving[step.name] = true
  queue = queue.then(async () => {
    try {
      set(await api('projectit.procedures.answer', { work_order: wo.value.name, step: step.name, ...payload }))
    } catch (e) {
      warn(e.message)
      await load()
    } finally {
      delete saving[step.name]
    }
  })
}
const comment = (content) => run(async () => set(await api('projectit.work_orders.add_comment', { name: wo.value.name, content })))

async function upload(photos) {
  uploading.value = true
  await run(async () => {
    for (const p of photos) set(await api('projectit.work_orders.attach_photo', { name: wo.value.name, content: p.content }))
  }).catch(() => {})
  photos.forEach((p) => URL.revokeObjectURL(p.preview))
  uploading.value = false
}

const synced = (e) => e.detail.includes(route.params.name) && load()
window.addEventListener('techy-synced', synced)
onBeforeUnmount(() => window.removeEventListener('techy-synced', synced))
const stop = onRealtime('techy_work_order', (msg) => {
  if (msg.name === route.params.name && !busy.value && !Object.keys(saving).length) load()
})
onMounted(async () => {
  await load()
  try {
    mentionable.value = await api('projectit.ops.search_users', { txt: '' })
  } catch (e) {
    mentionable.value = []
  }
})
onBeforeUnmount(() => {
  stop()
  ui.dockLift = 0
})
</script>
