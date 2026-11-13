<template>
  <section class="mx-auto max-w-5xl p-4 md:p-8">
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="min-w-0 flex-1">
        <h1 class="text-[22px] font-semibold tracking-tight md:text-[26px]">On site</h1>
        <p class="mt-0.5 text-sm text-gray-500">Staff and contractors checked in with the Techy App right now.</p>
      </div>
      <button class="btn btn-secondary" :disabled="loading" @click="load"><FeatherIcon name="refresh-cw" class="h-4 w-4" :class="loading ? 'animate-spin' : ''" />Refresh</button>
    </div>
    <p v-if="error" role="alert" class="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="now" class="mb-6">
      <div class="mb-3 flex gap-2 text-sm">
        <span class="chip" aria-pressed="false">Staff <span class="count">{{ now.staff }}</span></span>
        <span class="chip" aria-pressed="false">Contractors <span class="count">{{ now.contractors }}</span></span>
      </div>
      <div v-if="groups.length" class="space-y-3">
        <div v-for="g in groups" :key="g.key" class="card overflow-hidden">
          <div class="card-header"><h2 class="card-title truncate">{{ g.title }}</h2><span class="text-xs text-gray-500">{{ g.people.length }} on site</span></div>
          <ul class="divide-y divide-gray-100">
            <li v-for="p in g.people" :key="p.user + p.since" class="flex items-center gap-3 px-4 py-2.5">
              <UserAvatar :name="p.full_name" size="md" />
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium text-gray-900">{{ p.full_name }}</span>
                <span class="block truncate text-xs text-gray-500">{{ p.kind === 'Contractor' ? p.contractor_name : 'Staff' }} · since {{ formatTime(p.since) }}</span>
              </span>
              <span v-if="p.far" class="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">{{ Math.round(p.distance_m) }} m away</span>
              <router-link v-if="p.work_order" :to="{ name: 'OpsWorkOrder', params: { name: p.work_order } }" class="btn btn-ghost btn-sm">Job</router-link>
            </li>
          </ul>
        </div>
      </div>
      <EmptyState v-else icon="map-pin" title="Nobody is checked in right now" text="Staff check in from Techy Work, contractors from the Site tab of their app." />
    </div>

    <!-- Contractors' visits to look at: far from the site, or a forgotten check-out -->
    <div class="card overflow-hidden">
      <div class="card-header">
        <h2 class="card-title">Contractor visits</h2>
        <label class="flex items-center gap-2 text-xs text-gray-600"><input v-model="review" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-brand-600" @change="loadVisits" />Only to check</label>
      </div>
      <ul v-if="visits?.visits.length" class="divide-y divide-gray-100">
        <li v-for="v in visits.visits" :key="v.name" class="px-4 py-3">
          <div class="flex items-start gap-3">
            <a v-if="v.photos?.[0]" :href="v.photos[0]" target="_blank" rel="noopener" class="h-11 w-11 shrink-0 overflow-hidden rounded-lg border border-gray-200"><img :src="v.photos[0]" alt="Check-in photo" class="h-full w-full object-cover" /></a>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-gray-900">{{ v.full_name }} <span class="font-normal text-gray-500">· {{ v.contractor_name }}</span></p>
              <p class="truncate text-xs text-gray-500">{{ v.subject || v.project }} · {{ formatDate(v.check_in_at) }} {{ formatTime(v.check_in_at) }}<template v-if="v.check_out_at"> – {{ formatTime(v.check_out_at) }}</template></p>
              <p class="mt-1 flex flex-wrap gap-1.5 text-xs">
                <span v-if="v.far" class="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">{{ Math.round(v.distance_m) }} m from the site</span>
                <span v-if="v.status === 'Auto closed' && !v.confirmed" class="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">Forgot to check out</span>
                <span v-if="v.offline" class="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">Recorded offline</span>
                <span v-if="v.status !== 'On site'" class="rounded-full bg-gray-100 px-2 py-0.5 text-gray-700">{{ Number(v.hours || 0).toFixed(2) }} h{{ v.confirmed ? '' : ' (not confirmed)' }}</span>
              </p>
              <p v-if="v.manager_note" class="mt-1 whitespace-pre-wrap text-xs text-gray-500">{{ v.manager_note }}</p>
            </div>
            <Dropdown>
              <template #trigger="{ open, toggle }"><button class="btn btn-ghost btn-icon" :aria-expanded="open" aria-haspopup="menu" :aria-label="`Actions for ${v.full_name}'s visit`" @click="toggle"><FeatherIcon name="more-vertical" class="h-4 w-4" /></button></template>
              <template #default="{ close }">
                <button v-if="v.status !== 'On site'" class="menu-item" role="menuitem" @click="close(); confirmHours(v)"><FeatherIcon name="clock" class="h-4 w-4" />{{ v.confirmed ? 'Correct the hours' : 'Confirm the hours' }}</button>
                <button v-if="v.far" class="menu-item" role="menuitem" @click="close(); setLocation(v)"><FeatherIcon name="map-pin" class="h-4 w-4" />This is the site's location</button>
                <a :href="`https://maps.google.com/?q=${v.in_latitude},${v.in_longitude}`" target="_blank" rel="noopener" class="menu-item" role="menuitem"><FeatherIcon name="map" class="h-4 w-4" />Show on a map</a>
              </template>
            </Dropdown>
          </div>
        </li>
      </ul>
      <p v-else class="px-4 py-4 text-sm text-gray-500">{{ review ? 'Nothing to check in the last two weeks.' : 'No contractor visits in the last two weeks.' }}</p>
    </div>
  </section>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import Dropdown from '@/components/ops/Dropdown.vue'
import { api, formatDate, formatTime } from '@/data/ops'

const now = ref(null)
const visits = ref(null)
const review = ref(true)
const loading = ref(false)
const error = ref('')
const groups = computed(() => {
  const map = new Map()
  for (const p of now.value?.people || []) {
    const key = p.project || p.work_order || 'none'
    if (!map.has(key)) map.set(key, { key, title: p.project_name || p.subject || 'No project', people: [] })
    map.get(key).people.push(p)
  }
  return [...map.values()]
})
async function load() {
  loading.value = true
  try {
    now.value = await api('projectit.site_visits.on_site')
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
  loadVisits()
}
async function loadVisits() {
  try {
    visits.value = await api('projectit.site_visits.visits', { review: review.value ? 1 : 0 })
  } catch (e) {
    error.value = e.message
  }
}
async function confirmHours(v) {
  const value = window.prompt(`Hours ${v.full_name} worked on this visit:`, Number(v.hours || 0).toFixed(2))
  if (value === null) return
  const note = window.prompt('Note (optional):') || ''
  try {
    await api('projectit.site_visits.confirm', { name: v.name, hours: value, note })
    loadVisits()
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}
async function setLocation(v) {
  if (!window.confirm('Use where they checked in as the site location? Later check-ins are measured from here.')) return
  try {
    const r = await api('projectit.site_visits.set_site_location', { visit: v.name })
    toast({ title: `Location saved for ${r.where}`, icon: 'map-pin', position: 'top-center' })
    loadVisits()
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  }
}
onMounted(load)
</script>
