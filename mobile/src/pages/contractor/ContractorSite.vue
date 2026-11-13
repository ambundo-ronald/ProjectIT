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
      <section class="palette-light relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-800 to-brand-900 p-5 text-white shadow-pop md:p-7" aria-live="polite">
        <div class="pointer-events-none absolute -right-10 -top-10 h-44 w-44 rounded-full bg-accent-400/10" aria-hidden="true" />
        <div class="flex items-center justify-between">
          <span class="inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold" :class="visit ? 'bg-accent-400/20 text-accent-100' : 'bg-white/10 text-brand-100'">
            <span class="relative flex h-2 w-2">
              <span v-if="visit" class="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-400 opacity-75" />
              <span class="relative inline-flex h-2 w-2 rounded-full" :class="visit ? 'bg-accent-400' : 'bg-brand-300'" />
            </span>
            {{ visit ? 'On site' : 'Not on site' }}
          </span>
          <span class="text-xs text-brand-200">{{ dateLabel }}</span>
        </div>
        <p class="mt-4 font-mono text-[44px] font-semibold leading-none tracking-tight md:text-[56px]">{{ visit ? elapsed : clock }}</p>
        <p v-if="visit" class="mt-3 text-[15px] font-semibold">{{ visit.subject || visit.project_name }}</p>
        <p v-if="visit" class="mt-0.5 text-sm text-brand-200">
          Checked in at {{ formatTime(visit.check_in_at) }}<template v-if="visit.pending"> · sends when you have signal</template>
        </p>
        <p v-else class="mt-3 text-sm text-brand-200">Check in when you arrive at the site, and out when you leave.</p>
        <div class="mt-6 flex flex-col gap-2 sm:flex-row">
          <button v-if="visit" class="btn btn-lg w-full bg-panel text-brand-900 hover:bg-brand-50 sm:flex-1" :disabled="!!working" @click="checkOut">
            <FeatherIcon name="log-out" class="h-5 w-5" />Check out
          </button>
          <button v-else class="btn btn-lg w-full bg-accent-400 text-brand-900 hover:bg-accent-500 disabled:bg-white/10 disabled:text-brand-200 disabled:opacity-100 sm:flex-1" :disabled="!!working || !chosen" @click="startCamera">
            <FeatherIcon name="log-in" class="h-5 w-5" />{{ chosen ? `Check in to ${chosen.label}` : 'Choose where you are' }}
          </button>
        </div>
        <p class="mt-3 flex items-center gap-1.5 text-xs text-brand-200"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />Checking in takes a photo and records your location. Checking out records your location.</p>
        <div v-if="working" class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-brand-900/85 backdrop-blur-sm">
          <FeatherIcon name="loader" class="h-8 w-8 animate-spin text-accent-400" />
          <p class="text-sm font-medium">{{ working }}</p>
        </div>
      </section>

      <!-- Where: a job, or a project when there is no single job -->
      <section v-if="!visit">
        <h2 class="section-label mb-2 px-1">Where are you?</h2>
        <div v-if="places.length" class="space-y-2" role="radiogroup" aria-label="Job or project">
          <button v-for="p in places" :key="p.key" role="radio" :aria-checked="choice === p.key" class="card flex w-full items-start gap-3 p-4 text-left transition" :class="choice === p.key ? 'border-brand-500 ring-2 ring-brand-500/20' : 'hover:border-gray-300'" @click="choice = p.key">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2" :class="choice === p.key ? 'border-brand-600 bg-brand-600' : 'border-gray-300'">
              <span v-if="choice === p.key" class="h-2 w-2 rounded-full bg-panel" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-semibold text-gray-900">{{ p.label }}</span>
              <span class="mt-0.5 block text-sm text-gray-500">{{ p.sub }}</span>
            </span>
            <FeatherIcon :name="p.work_order ? 'tool' : 'briefcase'" class="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
          </button>
        </div>
        <EmptyState v-else icon="map-pin" title="Nowhere to check in yet" text="Accept a job, or ask us to give you a project, then check in here when you arrive." />
      </section>

      <section class="card overflow-hidden">
        <div class="card-header">
          <h2 class="card-title">Your visits</h2>
          <button class="btn btn-ghost btn-sm -mr-2" :disabled="!!working" @click="load"><FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" />Refresh</button>
        </div>
        <ul v-if="data.recent.length" class="divide-y divide-gray-100">
          <li v-for="v in data.recent" :key="v.name" class="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span class="w-20 shrink-0 text-gray-600">{{ formatDate(v.check_in_at) }}</span>
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-900">{{ v.subject || v.project_name }}</span>
              <span class="block text-xs text-gray-500">{{ formatTime(v.check_in_at) }}<template v-if="v.check_out_at"> – {{ formatTime(v.check_out_at) }}</template><template v-if="v.far"> · {{ Math.round(v.distance_m) }} m from the site</template></span>
            </span>
            <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium" :class="visitTone(v)">{{ visitLabel(v) }}</span>
          </li>
        </ul>
        <p v-else class="px-4 py-4 text-sm text-gray-500">No visits in the last two weeks.</p>
      </section>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { FeatherIcon, toast } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, formatDate, formatTime, readFile } from '@/data/ops'
import { showCamera, cameraMode, imageFile } from '@/data/camera_context'
import { getLocation, loadContractor } from '@/data/contractor'

const route = useRoute()
const data = ref(null)
const error = ref('')
const working = ref('')
const choice = ref(route.query.job ? `job:${route.query.job}` : '')
const now = ref(Date.now())
const visit = computed(() => data.value?.visit || null)
const places = computed(() => {
  const p = data.value?.places || { jobs: [], projects: [] }
  return [
    ...p.jobs.map((j) => ({ key: `job:${j.name}`, work_order: j.name, label: j.subject, sub: `Job ${j.name}` })),
    ...p.projects.map((pr) => ({ key: `project:${pr.name}`, project: pr.name, label: pr.project_name, sub: 'Project' })),
  ]
})
const chosen = computed(() => places.value.find((p) => p.key === choice.value) || null)
const parse = (v) => new Date(String(v).replace(' ', 'T')).getTime()
const pad = (n) => String(n).padStart(2, '0')
const elapsed = computed(() => {
  const s = Math.max(0, Math.floor((now.value - parse(visit.value.check_in_at)) / 1000))
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
})
const clock = computed(() => new Date(now.value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }))
const dateLabel = computed(() => new Date(now.value).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }))
const visitLabel = (v) => (v.status === 'On site' ? 'On site' : v.status === 'Auto closed' && !v.confirmed ? 'No check-out' : `${Number(v.hours || 0).toFixed(1)} h`)
const visitTone = (v) => (v.status === 'On site' ? 'bg-green-50 text-green-700' : v.status === 'Auto closed' && !v.confirmed ? 'bg-amber-50 text-amber-800' : 'bg-gray-100 text-gray-700')

async function load() {
  try {
    data.value = await api('projectit.site_visits.status')
    if (!choice.value && places.value.length === 1) choice.value = places.value[0].key
  } catch (e) {
    error.value = e.message
  }
}
function startCamera() {
  error.value = ''
  cameraMode.value = 'Check-In'
  showCamera.value = true
}
watch(imageFile, (file) => {
  if (file instanceof Blob && !working.value && cameraMode.value === 'Check-In' && route.name === 'ContractorSite') checkIn(file)
})
async function checkIn(file) {
  working.value = 'Getting your location…'
  try {
    const photo = await readFile(file, 10)
    // Nothing is written on the server until GPS has succeeded.
    const location = await getLocation()
    working.value = 'Checking in…'
    const place = chosen.value
    await api('projectit.site_visits.check_in', { work_order: place.work_order || null, project: place.project || null, ...location, photo })
    await load()
    loadContractor(true).catch(() => {})
    toast({ title: 'Checked in', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    working.value = ''
    imageFile.value = null
  }
}
async function checkOut() {
  error.value = ''
  working.value = 'Getting your location…'
  try {
    const location = await getLocation()
    working.value = 'Checking out…'
    await api('projectit.site_visits.check_out', { visit: visit.value.name, ...location })
    await load()
    loadContractor(true).catch(() => {})
    toast({ title: 'Checked out', text: 'Your time on site is recorded.', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
  } catch (e) {
    error.value = e.message
  } finally {
    working.value = ''
  }
}

let timer = null
onMounted(() => {
  load()
  timer = setInterval(() => (now.value = Date.now()), 1000)
  window.addEventListener('techy-synced', load)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  window.removeEventListener('techy-synced', load)
})
</script>
