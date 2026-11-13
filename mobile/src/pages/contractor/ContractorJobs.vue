<template>
  <div class="space-y-4">
    <div class="segmented w-full" role="tablist" aria-label="Jobs">
      <button v-for="v in views" :key="v.key" type="button" role="tab" class="flex-1" :aria-selected="view === v.key" :aria-pressed="view === v.key" @click="setView(v.key)">
        {{ v.label }}<span v-if="v.count" class="ml-1 rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white">{{ v.count }}</span>
      </button>
    </div>

    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="loading && !rows.length" class="space-y-3" aria-busy="true">
      <div v-for="i in 3" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-200/70" />
    </div>

    <template v-else>
      <p v-if="view === 'offered' && rows.length" class="text-sm text-gray-600">Accept a job to start it. Declining tells us why, so we can give it to someone else.</p>
      <ul v-if="rows.length" class="space-y-2.5">
        <li v-for="j in rows" :key="j.name">
          <router-link :to="{ name: 'ContractorJob', params: { name: j.name } }" class="card block p-4 transition hover:border-gray-300">
            <div class="flex items-start gap-3">
              <span class="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="tone(j)"><FeatherIcon :name="icon(j)" class="h-5 w-5" /></span>
              <span class="min-w-0 flex-1">
                <span class="block font-semibold leading-snug text-gray-900">{{ j.subject }}</span>
                <span class="mt-0.5 block truncate text-sm text-gray-500">{{ [j.customer_name, j.equipment?.equipment_name, j.project_name].filter(Boolean).join(' · ') || j.name }}</span>
                <span class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <StatusPill v-if="j.custom_contractor_state === 'Accepted'" :status="displayStatus(j)" />
                  <span v-else-if="j.custom_contractor_state === 'Declined'" class="rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-600">Declined</span>
                  <span v-else class="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">Waiting for your answer</span>
                  <span v-if="j.exp_end_date" class="inline-flex items-center gap-1" :class="late(j) ? 'font-semibold text-red-600' : 'text-gray-500'"><FeatherIcon name="calendar" class="h-3 w-3" />Due {{ formatDate(j.exp_end_date) }}</span>
                  <span v-if="j.pay != null" class="inline-flex items-center gap-1 font-medium text-gray-700"><FeatherIcon name="credit-card" class="h-3 w-3" />{{ money(j.pay) }}</span>
                  <AvatarStack v-if="j.assignees.length" :people="j.assignees" :max="3" />
                </span>
              </span>
              <FeatherIcon name="chevron-right" class="mt-3 h-4 w-4 shrink-0 text-gray-400" />
            </div>
          </router-link>
        </li>
      </ul>
      <EmptyState v-else :icon="view === 'done' ? 'check-circle' : 'tool'" :title="emptyTitle" :text="emptyText" />
    </template>

    <!-- Projects given to the contractor, with the site instructions -->
    <section v-if="projects.length && view === 'active'" class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Projects</h2><span class="text-xs text-gray-500">{{ projects.length }}</span></div>
      <ul class="divide-y divide-gray-100">
        <li v-for="p in projects" :key="p.name" class="px-5 py-3">
          <p class="font-medium text-gray-900">{{ p.project_name }}</p>
          <p class="text-xs text-gray-500">{{ [p.customer_name, p.expected_end_date ? `Due ${formatDate(p.expected_end_date)}` : ''].filter(Boolean).join(' · ') }}</p>
          <p v-if="p.instructions" class="mt-2 whitespace-pre-wrap rounded-lg border border-accent-100 bg-accent-50 p-2.5 text-sm text-gray-800">{{ p.instructions }}</p>
          <p v-if="p.work_instruction" class="mt-2 whitespace-pre-wrap text-sm text-gray-600">{{ p.work_instruction }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import StatusPill from '@/components/ops/StatusPill.vue'
import AvatarStack from '@/components/ops/AvatarStack.vue'
import { api, formatDate, displayStatus } from '@/data/ops'
import { contractor, loadContractor, money as fmt } from '@/data/contractor'

const route = useRoute()
const router = useRouter()
const view = ref(['offered', 'active', 'done'].includes(route.query.view) ? route.query.view : 'active')
const rows = ref([])
const projects = ref([])
const loading = ref(false)
const error = ref('')
const money = (v) => fmt(v)
const views = computed(() => [
  ...(contractor.me?.runs_jobs ? [{ key: 'offered', label: 'Offered', count: contractor.me.counts.offered }] : []),
  { key: 'active', label: 'Active' },
  { key: 'done', label: 'Done' },
])
const today = new Date().toISOString().slice(0, 10)
const late = (j) => j.exp_end_date && j.exp_end_date < today && !['Completed', 'Cancelled'].includes(j.status)
const tone = (j) => (j.custom_contractor_state === 'Offered' ? 'bg-amber-50 text-amber-700' : j.status === 'Completed' ? 'bg-green-50 text-green-700' : 'bg-brand-50 text-brand-700')
const icon = (j) => (j.custom_contractor_state === 'Offered' ? 'inbox' : j.status === 'Completed' ? 'check' : 'tool')
const emptyTitle = computed(() => ({ offered: 'No jobs waiting for an answer', active: 'No active jobs', done: 'Nothing done yet' })[view.value])
const emptyText = computed(() => ({
  offered: 'When we offer you a job it shows here.',
  active: contractor.me?.runs_jobs ? 'Accepted jobs show here. Choose who on your team does each one.' : 'Jobs your team gives you show here.',
  done: 'Completed and declined jobs show here.',
})[view.value])

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = (await api('projectit.contractors.jobs', { view: view.value })).jobs
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function setView(key) {
  view.value = key
  router.replace({ query: { ...route.query, view: key } })
  load()
}
const refresh = () => {
  load()
  loadContractor(true).catch(() => {})
}
onMounted(async () => {
  await loadContractor().catch(() => {})
  if (view.value === 'active' && contractor.me?.runs_jobs && contractor.me.counts.offered && !route.query.view) view.value = 'offered'
  load()
  api('projectit.contractors.my_projects').then((p) => (projects.value = p)).catch(() => {})
  window.addEventListener('techy-synced', refresh)
})
onBeforeUnmount(() => window.removeEventListener('techy-synced', refresh))
</script>
