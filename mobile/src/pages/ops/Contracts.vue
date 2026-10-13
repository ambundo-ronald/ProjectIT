<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Service contracts" subtitle="What each customer's contract covers, its machines and visits. Billing runs on ERPNext Subscriptions.">
      <button v-if="manager" class="btn btn-secondary" :disabled="running" @click="runVisits"><FeatherIcon name="zap" class="h-4 w-4" /><span class="hidden sm:inline">Create due visits</span><span class="sm:hidden">Due visits</span></button>
      <router-link v-if="manager" :to="{ name: 'OpsContract', params: { name: 'new' } }" class="btn btn-primary"><FeatherIcon name="plus" class="h-4 w-4" /><span class="hidden sm:inline">New contract</span><span class="sm:hidden">New</span></router-link>
    </PageHeader>
    <EquipmentTabs />

    <div class="relative">
      <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      <input v-model="search" type="search" placeholder="Search customer, contract or subscription" aria-label="Search contracts" class="input pl-9" @input="debounced" />
    </div>
    <div class="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0" role="group" aria-label="Show">
      <button v-for="v in views" :key="v.key" class="chip" :aria-pressed="view === v.key" @click="view = v.key; load()">{{ v.label }}</button>
    </div>
    <p v-if="notice" role="status" class="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800"><FeatherIcon name="check-circle" class="h-4 w-4" />{{ notice }}</p>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="busy && !rows.length" class="space-y-3"><div v-for="i in 4" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" /></div>
    <ul v-else-if="rows.length" class="card divide-y divide-gray-100 overflow-hidden">
      <li v-for="c in rows" :key="c.name">
        <router-link :to="{ name: 'OpsContract', params: { name: c.name } }" class="flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="file-text" class="h-5 w-5" /></span>
          <span class="min-w-0 flex-1">
            <span class="block truncate font-semibold">{{ c.customer_name }}</span>
            <span class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
              <span>{{ c.machines }} machine{{ c.machines === 1 ? '' : 's' }}</span>
              <span>{{ c.visit_frequency }} visits</span>
              <span v-if="c.next_visit && c.state === 'Active'" class="inline-flex items-center gap-1"><FeatherIcon name="calendar" class="h-3.5 w-3.5" />Next {{ formatDate(c.next_visit) }}</span>
              <span v-if="c.payment_warning" class="inline-flex items-center gap-1 font-semibold text-red-600"><FeatherIcon name="alert-circle" class="h-3.5 w-3.5" />Subscription {{ c.subscription_status.toLowerCase() }}</span>
              <span v-else-if="!c.subscription" class="text-amber-700">No subscription linked</span>
            </span>
          </span>
          <span class="flex shrink-0 flex-col items-end gap-1">
            <span class="rounded-md px-2 py-0.5 text-xs font-semibold" :class="tone(c).chip">{{ tone(c).text }}</span>
            <span class="text-[11px] text-gray-500">{{ c.state === 'Expired' ? 'Ended' : 'Ends' }} {{ formatDate(c.end_date) }}</span>
          </span>
        </router-link>
      </li>
    </ul>
    <EmptyState v-else-if="!busy && !error" icon="file-text" :title="search ? 'No contracts match' : view === 'Expiring' ? 'Nothing expiring in the next 60 days' : 'No contracts here'" text="A contract lists the customer's machines, how often you visit, and what's included. Link its ERPNext Subscription for billing.">
      <router-link v-if="manager && view === 'Active'" :to="{ name: 'OpsContract', params: { name: 'new' } }" class="btn btn-primary"><FeatherIcon name="plus" class="h-4 w-4" />New contract</router-link>
    </EmptyState>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import EquipmentTabs from '@/components/ops/EquipmentTabs.vue'
import { api, dueIn, formatDate } from '@/data/ops'

const rows = ref([])
const view = ref('Active')
const search = ref('')
const manager = ref(false)
const busy = ref(false)
const running = ref(false)
const error = ref('')
const notice = ref('')
const views = [
  { key: 'Active', label: 'Active' },
  { key: 'Expiring', label: 'Expiring in 60 days' },
  { key: 'Expired', label: 'Expired' },
  { key: 'Cancelled', label: 'Cancelled' },
  { key: 'All', label: 'All' },
]

function tone(c) {
  if (c.state === 'Cancelled') return { text: 'Cancelled', chip: 'bg-gray-100 text-gray-500' }
  if (c.state === 'Expired') return { text: 'Expired', chip: 'bg-red-50 text-red-700' }
  if (c.state === 'Upcoming') return { text: 'Starts soon', chip: 'bg-violet-50 text-violet-700' }
  const d = dueIn(c.end_date)
  if (d !== null && d <= 60) return { text: `${d}d left`, chip: 'bg-amber-50 text-amber-800' }
  return { text: 'Active', chip: 'bg-green-50 text-green-700' }
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    const r = await api('projectit.contracts.list_contracts', { view: view.value, search: search.value || null })
    rows.value = r.contracts
    manager.value = r.manager
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
let timer = null
const debounced = () => {
  clearTimeout(timer)
  timer = setTimeout(load, 250)
}

async function runVisits() {
  running.value = true
  notice.value = ''
  try {
    const { created } = await api('projectit.contracts.run_due_visits')
    notice.value = created.length ? `Created ${created.length} service visit job${created.length === 1 ? '' : 's'}.` : 'No visits are due yet.'
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    running.value = false
  }
}
onMounted(load)
</script>
