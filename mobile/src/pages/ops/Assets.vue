<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Our assets" subtitle="Company-owned equipment and its maintenance history. Assets are managed in ERPNext." class="hidden md:flex" />
    <EquipmentTabs />
    <div class="flex flex-col gap-2 sm:flex-row">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" placeholder="Search by name, code or item" aria-label="Search assets" class="input pl-9" @input="debounced" />
      </div>
      <select v-model="location" class="input sm:w-56" aria-label="Location" @change="load()">
        <option value="">All locations</option>
        <option v-for="l in locations" :key="l.name" :value="l.name">{{ l.location_name || l.name }}</option>
      </select>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{{ error }}</p>

    <div v-if="busy && !rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 6" :key="i" class="h-24 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <div v-else-if="rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
    <button v-if="hasMore" class="btn btn-secondary w-full" :disabled="busy" @click="load(true)">Load more</button>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EquipmentTabs from '@/components/ops/EquipmentTabs.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, safeFile } from '@/data/ops'

const rows = ref([])
const locations = ref([])
const search = ref('')
const location = ref('')
const busy = ref(false)
const error = ref('')
const hasMore = ref(false)

async function load(append = false) {
  busy.value = true
  error.value = ''
  try {
    const data = await api('projectit.maintenance.list_assets', { search: search.value, location: location.value, start: append ? rows.value.length : 0 })
    rows.value = append ? [...rows.value, ...data.assets] : data.assets
    hasMore.value = data.has_more
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
