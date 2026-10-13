<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Customer equipment" subtitle="Machines installed at customer sites, with warranty and contract cover.">
      <button v-if="manager" class="btn btn-primary" @click="registering = true"><FeatherIcon name="plus" class="h-4 w-4" /><span class="hidden sm:inline">Register equipment</span><span class="sm:hidden">Register</span></button>
    </PageHeader>
    <EquipmentTabs />

    <div class="flex flex-col gap-2 sm:flex-row">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" placeholder="Search customer, site, model or tag" aria-label="Search equipment" class="input pl-9" @input="debounced" />
      </div>
    </div>
    <div class="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0" role="group" aria-label="Filter">
      <button v-for="f in filters" :key="f.key" class="chip" :aria-pressed="filter === f.key" @click="filter = f.key; load()">
        <FeatherIcon v-if="f.icon" :name="f.icon" class="h-3.5 w-3.5" />{{ f.label }}
      </button>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="busy && !rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 6" :key="i" class="h-28 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <div v-else-if="rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <router-link v-for="e in rows" :key="e.name" :to="{ name: 'OpsEquipmentDetail', params: { name: e.name } }" class="card group flex flex-col p-4 transition hover:-translate-y-px hover:border-gray-300 hover:shadow-pop">
        <div class="flex items-start gap-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600"><FeatherIcon name="droplet" class="h-5 w-5" /></span>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold text-gray-900 group-hover:text-brand-700">{{ e.customer_name }}</p>
            <p class="truncate text-sm text-gray-600">{{ e.equipment_name }}</p>
          </div>
          <CoverageBadge :kind="e.coverage.kind" short />
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-gray-500">
          <span v-if="e.site" class="inline-flex min-w-0 items-center gap-1"><FeatherIcon name="map-pin" class="h-3.5 w-3.5 shrink-0" /><span class="truncate">{{ e.site }}</span></span>
          <span class="font-mono">{{ e.tag || e.name }}</span>
          <span v-if="e.status !== 'Active'" class="rounded-md px-1.5 py-0.5 font-semibold" :class="EQUIPMENT_STATUS[e.status]">{{ e.status }}</span>
          <span v-if="e.open_work_orders" class="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-800">{{ e.open_work_orders }} open job{{ e.open_work_orders === 1 ? '' : 's' }}</span>
        </div>
      </router-link>
    </div>
    <EmptyState v-else-if="!busy && !error" icon="droplet" :title="search || filter !== 'all' ? 'No equipment matches' : 'No customer equipment yet'" text="Tick “Track Installs in Techy Ops” on items like your RO systems in ERPNext. Each unit on a submitted Delivery Note appears here with an installation job. Register machines installed earlier by hand.">
      <button v-if="manager" class="btn btn-primary" @click="registering = true"><FeatherIcon name="plus" class="h-4 w-4" />Register equipment</button>
    </EmptyState>
    <p v-if="hasMore" class="text-center text-xs text-gray-500">Showing the first 100. Search to narrow down.</p>
    <EquipmentForm v-model="registering" @saved="(r) => router.push({ name: 'OpsEquipmentDetail', params: { name: r.equipment.name } })" />
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import EquipmentTabs from '@/components/ops/EquipmentTabs.vue'
import EquipmentForm from '@/components/ops/EquipmentForm.vue'
import CoverageBadge from '@/components/ops/CoverageBadge.vue'
import { api } from '@/data/ops'
import { EQUIPMENT_STATUS } from '@/data/equipment'

const router = useRouter()
const rows = ref([])
const search = ref('')
const filter = ref('all')
const manager = ref(false)
const hasMore = ref(false)
const busy = ref(false)
const error = ref('')
const registering = ref(false)
const filters = [
  { key: 'all', label: 'All' },
  { key: 'Awaiting installation', label: 'To install', icon: 'truck' },
  { key: 'Warranty', label: 'Warranty', icon: 'shield' },
  { key: 'Contract', label: 'Contract', icon: 'file-text' },
  { key: 'Chargeable', label: 'Chargeable', icon: 'credit-card' },
  { key: 'Out of service', label: 'Out of service', icon: 'alert-octagon' },
]

async function load() {
  busy.value = true
  error.value = ''
  const status = ['Awaiting installation', 'Out of service'].includes(filter.value) ? filter.value : null
  const cover = ['Warranty', 'Contract', 'Chargeable'].includes(filter.value) ? filter.value : null
  try {
    const r = await api('projectit.equipment.list_equipment', { search: search.value || null, status, cover })
    rows.value = r.equipment
    manager.value = r.manager
    hasMore.value = r.has_more
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
onMounted(load)
</script>
