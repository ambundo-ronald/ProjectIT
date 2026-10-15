<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Our assets" subtitle="Company-owned equipment and its maintenance history. Assets are managed in ERPNext." class="hidden md:flex" />
    <EquipmentTabs />
    <div class="flex flex-col gap-2 sm:flex-row">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" placeholder="Search by name, code or item" aria-label="Search assets" class="input pl-9" @input="debounced" />
      </div>
      <div class="flex gap-2">
        <select v-model="location" class="input min-w-0 flex-1 sm:w-56" aria-label="Location" @change="load()">
          <option value="">All locations</option>
          <option v-for="l in locations" :key="l.name" :value="l.name">{{ l.location_name || l.name }}</option>
        </select>
        <ViewToggle v-model="view" />
      </div>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{{ error }}</p>

    <div v-if="busy && !rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 6" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <div v-else-if="rows.length && view === 'list'" class="card overflow-hidden" :class="busy && 'opacity-60'">
      <div class="hidden grid-cols-[minmax(0,1.4fr)_10rem_minmax(0,1fr)_8rem] gap-4 border-b border-gray-100 bg-gray-50/80 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 md:grid">
        <span>Asset</span><span>Code</span><span>Location</span><span>Open work</span>
      </div>
      <ul class="divide-y divide-gray-100">
        <li v-for="a in rows" :key="a.name">
          <router-link :to="{ name: 'OpsAsset', params: { name: a.name } }" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 md:grid md:grid-cols-[minmax(0,1.4fr)_10rem_minmax(0,1fr)_8rem] md:gap-4">
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-900">{{ a.asset_name }}</span>
              <span class="block truncate text-xs text-gray-500 md:hidden">{{ a.name }}<template v-if="a.location"> · {{ a.location }}</template></span>
            </span>
            <span class="hidden truncate font-mono text-xs text-gray-500 md:block">{{ a.name }}</span>
            <span class="hidden truncate text-sm text-gray-600 md:block">{{ a.location || '—' }}</span>
            <span class="shrink-0 text-xs">
              <span v-if="a.open_work_orders" class="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-800">{{ a.open_work_orders }} open</span>
              <span v-else class="text-green-700">None</span>
            </span>
          </router-link>
        </li>
      </ul>
    </div>
    <div v-else-if="rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" :class="busy && 'opacity-60'">
      <router-link v-for="a in rows" :key="a.name" :to="{ name: 'OpsAsset', params: { name: a.name } }" class="card group flex gap-3 p-3.5 transition hover:-translate-y-px hover:border-gray-300 hover:shadow-pop">
        <div class="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gradient-to-br from-gray-50 to-gray-100 ring-1 ring-inset ring-gray-200">
          <img v-if="safeFile(a.image)" :src="a.image" alt="" class="h-full w-full object-cover" loading="lazy" />
          <FeatherIcon v-else name="box" class="h-6 w-6 text-gray-400" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate font-semibold text-gray-900 group-hover:text-brand-700">{{ a.asset_name }}</p>
          <p class="truncate text-xs text-gray-500">{{ a.name }}</p>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span v-if="a.location" class="inline-flex items-center gap-1 text-gray-600"><FeatherIcon name="map-pin" class="h-3.5 w-3.5" />{{ a.location }}</span>
            <span v-if="a.open_work_orders" class="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-800">{{ a.open_work_orders }} open</span>
            <span v-else class="inline-flex items-center gap-1 text-green-700"><FeatherIcon name="check-circle" class="h-3.5 w-3.5" />No open work</span>
          </div>
        </div>
      </router-link>
    </div>
    <EmptyState v-else-if="!error" icon="box" title="No assets found" text="Add assets in ERPNext (Assets › Asset) to track their work orders and maintenance here." />
    <Pager :total="total" :start="start" :page-length="pageLength" :busy="busy" label="Asset pages" @change="load" @update:page-length="(n) => { pageLength = n; load() }" />
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EquipmentTabs from '@/components/ops/EquipmentTabs.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import Pager from '@/components/ops/Pager.vue'
import ViewToggle from '@/components/ops/ViewToggle.vue'
import { api, safeFile } from '@/data/ops'
import { usePageLength, useView } from '@/data/paging'

const rows = ref([])
const locations = ref([])
const search = ref('')
const location = ref('')
const busy = ref(false)
const error = ref('')
const view = useView('assets')
const pageLength = usePageLength()
const start = ref(0)
const total = ref(0)

async function load(from = 0) {
  busy.value = true
  error.value = ''
  try {
    const data = await api('projectit.maintenance.list_assets', { search: search.value, location: location.value, start: from, page_length: pageLength.value })
    rows.value = data.assets
    start.value = data.start
    total.value = data.total
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

let timer = null
function debounced() {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 300)
}

onMounted(async () => {
  load()
  try {
    locations.value = await api('projectit.maintenance.list_locations')
  } catch (e) {
    locations.value = []
  }
})
</script>
