<template>
  <div class="space-y-5">
    <p v-if="error" role="alert" class="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <FeatherIcon name="alert-circle" class="mt-0.5 h-4 w-4 shrink-0" /><span class="flex-1">{{ error }}</span>
      <button class="text-red-500 hover:text-red-800" aria-label="Dismiss" @click="error = ''"><FeatherIcon name="x" class="h-4 w-4" /></button>
    </p>

    <div v-if="!data" class="space-y-4" aria-label="Loading">
      <div class="h-56 animate-pulse rounded-2xl bg-gray-200/70" />
      <div class="h-28 animate-pulse rounded-xl bg-gray-200/70" />
    </div>

    <template v-else>
      <!-- Clock card -->
      <section class="palette-light relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-800 to-brand-900 p-5 text-white shadow-pop md:p-7" aria-live="polite">
        <div class="pointer-events-none absolute -right-10 -top-10 h-44 w-44 rounded-full bg-accent-400/10" aria-hidden="true" />
        <div class="flex items-center justify-between">
          <span class="inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold" :class="session ? 'bg-accent-400/20 text-accent-100' : 'bg-white/10 text-brand-100'">
            <span class="relative flex h-2 w-2">
              <span v-if="session" class="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-400 opacity-75" />
              <span class="relative inline-flex h-2 w-2 rounded-full" :class="session ? 'bg-accent-400' : 'bg-brand-300'" />
            </span>
            {{ session ? 'On the clock' : 'Off the clock' }}
          </span>
          <span class="text-xs text-brand-200">{{ dateLabel }}</span>
        </div>

        <p class="mt-4 font-mono text-[44px] font-semibold leading-none tracking-tight md:text-[56px]">{{ session ? elapsed : clock }}</p>
        <p v-if="session" class="mt-3 text-[15px] font-semibold">{{ session.project_name }}</p>
        <p v-if="session" class="mt-0.5 text-sm text-brand-200">
          Checked in at {{ formatTime(session.from_time) }}<template v-if="activeTask"> · {{ activeTask }}</template>
        </p>
        <p v-else class="mt-3 text-sm text-brand-200">
          {{ greeting }}, {{ firstName }}.<template v-if="data.hours.start"> Regular hours {{ hhmm(data.hours.start) }}–{{ hhmm(data.hours.end) }}.</template>
        </p>

        <div class="mt-6 flex flex-col gap-2 sm:flex-row">
          <template v-if="session">
            <button class="btn btn-lg w-full sm:w-auto sm:flex-1 bg-panel text-brand-900 hover:bg-brand-50" :disabled="!!working" @click="startCamera('Check-Out')">
              <FeatherIcon name="log-out" class="h-5 w-5" />Check out
            </button>
            <button class="btn btn-lg w-full sm:w-auto sm:flex-1 bg-white/10 text-white hover:bg-white/20" :disabled="!!working" @click="updating = true">
              <FeatherIcon name="camera" class="h-5 w-5" />Photo update
            </button>
          </template>
          <button v-else class="btn btn-lg w-full sm:w-auto sm:flex-1 bg-accent-400 text-brand-900 hover:bg-accent-500 disabled:bg-white/10 disabled:text-brand-200 disabled:opacity-100" :disabled="!!working || !selected" @click="startCamera('Check-In')">
            <FeatherIcon name="log-in" class="h-5 w-5" />{{ selected ? `Check in to ${selected.project_name}` : 'Choose a project to check in' }}
          </button>
        </div>
        <p class="mt-3 flex items-center gap-1.5 text-xs text-brand-200"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />{{ session ? 'Checking out' : 'Checking in' }} takes a photo and records your location.</p>

        <div v-if="working" class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-brand-900/85 backdrop-blur-sm">
          <FeatherIcon name="loader" class="h-8 w-8 animate-spin text-accent-400" />
          <p class="text-sm font-medium">{{ working }}</p>
        </div>
      </section>

      <!-- Project picker -->
      <section v-if="!session">
        <h2 class="section-label mb-2 px-1">Where are you working?</h2>
        <div v-if="data.projects.length" class="space-y-2" role="radiogroup" aria-label="Project">
          <button
            v-for="p in data.projects"
            :key="p.project"
            role="radio"
            :aria-checked="selectedId === p.project"
            class="card flex w-full items-start gap-3 p-4 text-left transition"
            :class="selectedId === p.project ? 'border-brand-500 ring-2 ring-brand-500/20' : 'hover:border-gray-300'"
            @click="select(p.project)"
          >
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2" :class="selectedId === p.project ? 'border-brand-600 bg-brand-600' : 'border-gray-300'">
              <span v-if="selectedId === p.project" class="h-2 w-2 rounded-full bg-panel" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-semibold text-gray-900">{{ p.project_name }}</span>
              <span v-if="p.my_instructions || p.work_instruction" class="mt-0.5 line-clamp-2 block text-sm text-gray-500">{{ p.my_instructions || p.work_instruction }}</span>
              <span class="mt-2 flex items-center gap-2 text-xs text-gray-500">
                <AvatarStack :people="p.team.map((m) => ({ user: m.name, full_name: m.name, image: m.image }))" :max="4" />
                <span v-if="onSite(p)" class="inline-flex items-center gap-1 font-medium text-green-700"><span class="h-1.5 w-1.5 rounded-full bg-green-500" />{{ onSite(p) }} on site</span>
              </span>
            </span>
          </button>
        </div>
        <EmptyState v-else icon="briefcase" title="No projects allocated" text="Ask your manager to allocate you to a project in Techy Manage before you check in." />

        <div v-if="selected && (tasks.length || loadingTasks)" class="mt-3">
          <label class="label" for="work-task">Task <span class="font-normal text-gray-400">(optional)</span></label>
          <select id="work-task" v-model="taskId" class="input" :disabled="loadingTasks">
            <option value="">Project time only</option>
            <option v-for="t in tasks" :key="t.name" :value="t.name">{{ t.subject }}</option>
          </select>
          <p class="hint">Time is logged against this task at check-out.</p>
        </div>
      </section>

      <!-- Project details -->
      <template v-if="focus">
        <section class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Instructions</h2><span class="truncate text-xs text-gray-500">{{ focus.project_name }}</span></div>
          <div class="space-y-4 p-4">
            <div v-if="focus.my_instructions" class="rounded-lg border border-accent-100 bg-accent-50 p-3">
              <p class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-accent-600"><FeatherIcon name="user" class="h-3.5 w-3.5" />For you</p>
              <p class="mt-1 whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800">{{ focus.my_instructions }}</p>
            </div>
            <div>
              <p class="section-label">Project</p>
              <p class="mt-1 whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800">{{ focus.work_instruction || 'No project instructions yet.' }}</p>
            </div>
          </div>
        </section>

        <section class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title">Team</h2><span class="text-xs text-gray-500">{{ onSite(focus) }} of {{ focus.team.length }} on site</span></div>
          <ul class="divide-y divide-gray-100">
            <li v-for="m in focus.team" :key="m.name" class="flex items-center gap-3 px-4 py-2.5">
              <UserAvatar :name="m.name" :image="m.image" size="md" />
              <span class="flex-1 text-sm font-medium">{{ m.name }}<span v-if="m.me" class="ml-1 font-normal text-gray-400">(you)</span></span>
              <span class="inline-flex items-center gap-1.5 text-xs" :class="m.on_site ? 'font-medium text-green-700' : 'text-gray-400'"><span class="h-2 w-2 rounded-full" :class="m.on_site ? 'bg-green-500' : 'bg-gray-300'" />{{ m.on_site ? 'On site' : 'Not checked in' }}</span>
            </li>
          </ul>
        </section>
      </template>

      <!-- Attendance -->
      <section class="card overflow-hidden">
        <div class="card-header">
          <h2 class="card-title">Attendance</h2>
          <button class="btn btn-ghost btn-sm -mr-2" :disabled="!!working" @click="load"><FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" />Refresh</button>
        </div>
        <p class="flex items-start gap-2 px-4 pt-3 text-sm text-gray-600"><FeatherIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />{{ data.attendance.message }}</p>
        <ul v-if="data.attendance.records.length" class="mt-2 divide-y divide-gray-100">
          <li v-for="r in data.attendance.records.slice(0, 7)" :key="r.name" class="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span class="w-24 text-gray-600">{{ formatDate(r.attendance_date) }}</span>
            <span class="flex-1 text-xs text-gray-500">{{ r.shift || '' }}<template v-if="r.working_hours"> · {{ Number(r.working_hours).toFixed(1) }}h</template></span>
            <span class="rounded-full px-2 py-0.5 text-xs font-medium" :class="attendanceTone(r)">{{ r.docstatus === 0 ? `${r.status} (draft)` : r.status }}</span>
          </li>
        </ul>
        <div v-else class="pb-3" />
      </section>
    </template>

    <Modal v-model="updating" title="Photo update" subtitle="Share progress from site. The photo and note are added to today's timesheet.">
      <label class="label" for="update-caption">Note</label>
      <textarea id="update-caption" v-model="caption" rows="3" maxlength="2000" class="input" placeholder="e.g. Panel isolated, starting rewiring" />
      <template #footer>
        <button class="btn btn-secondary" @click="updating = false">Cancel</button>
        <button class="btn btn-primary" @click="updating = false; startCamera('Upload')"><FeatherIcon name="camera" class="h-4 w-4" />Take photo</button>
      </template>
    </Modal>
  </div>
</template>
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import AvatarStack from '@/components/ops/AvatarStack.vue'
import { api, formatDate, formatTime, readFile } from '@/data/ops'
import { showCamera, cameraMode, imageFile } from '@/data/camera_context'

const data = ref(null)
const error = ref('')
const working = ref('')
const selectedId = ref('')
const taskId = ref('')
const tasks = ref([])
const loadingTasks = ref(false)
const updating = ref(false)
const caption = ref('')
const now = ref(Date.now())
let offset = 0 // server clock minus device clock, so the timer is right even if the phone clock is off

const session = computed(() => data.value?.session || null)
const selected = computed(() => data.value?.projects.find((p) => p.project === selectedId.value) || null)
const focus = computed(() => (session.value ? data.value.projects.find((p) => p.project === session.value.project) : selected.value) || null)
const activeTask = computed(() => tasks.value.find((t) => t.name === session.value?.task)?.subject || '')
const onSite = (p) => p.team.filter((m) => m.on_site).length

const parse = (v) => new Date(String(v).replace(' ', 'T')).getTime()
const pad = (n) => String(n).padStart(2, '0')
const elapsed = computed(() => {
  const s = Math.max(0, Math.floor((now.value + offset - parse(session.value.from_time)) / 1000))
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
})
const clock = computed(() => new Date(now.value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
const dateLabel = computed(() => new Date(now.value).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }))
const hhmm = (t) => String(t).slice(0, 5)
const hour = new Date().getHours()
const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
const firstName = computed(() => (data.value?.employee_name || '').split(' ')[0] || 'there')
const attendanceTone = (r) => ({ Present: 'bg-green-50 text-green-700', 'Half Day': 'bg-amber-50 text-amber-800', Absent: 'bg-red-50 text-red-700', 'On Leave': 'bg-blue-50 text-blue-700' })[r.status] || 'bg-gray-100 text-gray-600'

async function load() {
  try {
    const result = await api('projectit.work.today')
    offset = parse(result.server_time) - Date.now()
    data.value = result
    if (result.session) {
      selectedId.value = result.session.project
      await loadTasks(result.session.project)
    } else if (!selectedId.value && result.projects.length === 1) {
      select(result.projects[0].project)
    }
  } catch (e) {
    error.value = e.message
  }
}

async function loadTasks(project) {
  loadingTasks.value = true
  try {
    tasks.value = await api('projectit.tasks.work_tasks', { project })
  } catch (e) {
    tasks.value = []
  } finally {
    loadingTasks.value = false
  }
}

function select(project) {
  if (selectedId.value === project) return
  selectedId.value = project
  taskId.value = ''
  tasks.value = []
  loadTasks(project)
}

function startCamera(mode) {
  error.value = ''
  cameraMode.value = mode
  showCamera.value = true
}

function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('This device cannot share its location, which is required to check in and out.'))
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ latitude: coords.latitude, longitude: coords.longitude }),
      (e) =>
        reject(
          new Error(
            e.code === 1
              ? 'Allow location access for this site, then try again. Your location is recorded with each check-in and check-out.'
              : e.code === 3
                ? 'Getting your location took too long. Move to an open area and try again.'
                : 'Your location could not be determined. Check that location services are on and try again.',
          ),
        ),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    )
  })
}

watch(imageFile, (file) => {
  if (file instanceof Blob && !working.value) submitPhoto(file)
})

async function submitPhoto(file) {
  const mode = cameraMode.value
  working.value = mode === 'Upload' ? 'Uploading photo…' : 'Getting your location…'
  try {
    const photo = await readFile(file, 10)
    if (mode === 'Upload') {
      await api('projectit.attendance.add_photo', { timesheet: session.value.name, photo, caption: caption.value })
      caption.value = ''
    } else {
      // Nothing is written on the server until GPS has succeeded.
      const location = await getLocation()
      working.value = mode === 'Check-In' ? 'Checking in…' : 'Checking out…'
      if (mode === 'Check-In') await api('projectit.attendance.check_in', { project: selectedId.value, task: taskId.value || null, ...location, photo })
      else await api('projectit.attendance.check_out', { timesheet: session.value.name, ...location, photo })
    }
    await load()
    toast({ title: { Upload: 'Photo update saved', 'Check-In': 'Checked in', 'Check-Out': 'Checked out' }[mode], text: mode === 'Check-Out' ? 'Your time is logged. Attendance follows your HR shift rules.' : '', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    working.value = ''
    imageFile.value = null
  }
}

let timer = null
onMounted(() => {
  load()
  timer = setInterval(() => (now.value = Date.now()), 1000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
