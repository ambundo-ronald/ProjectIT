<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 md:p-8">
    <PageHeader title="Procedures" subtitle="Reusable checklists with readings, pass/fail checks, photos and sign-off.">
      <router-link v-if="manager" :to="{ name: 'OpsProcedure', params: { name: 'new' } }" class="btn btn-primary"><FeatherIcon name="plus" class="h-4 w-4" />New procedure</router-link>
    </PageHeader>

    <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" placeholder="Search procedures" aria-label="Search procedures" class="input pl-9" @input="debounced" />
      </div>
      <div v-if="manager" class="segmented self-start" role="group" aria-label="Show">
        <button :aria-pressed="!archived" @click="archived = false; load()">Active</button>
        <button :aria-pressed="archived" @click="archived = true; load()">Archived</button>
      </div>
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="busy && !rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="i in 6" :key="i" class="h-32 animate-pulse rounded-xl bg-gray-200/70" />
    </div>
    <div v-else-if="rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <router-link v-for="p in rows" :key="p.name" :to="{ name: 'OpsProcedure', params: { name: p.name } }" class="card group flex flex-col p-4 transition hover:-translate-y-px hover:border-gray-300 hover:shadow-pop">
        <div class="flex items-start gap-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg" :class="tone(p.category)"><FeatherIcon :name="icon(p.category)" class="h-5 w-5" /></span>
          <div class="min-w-0 flex-1">
            <p class="font-semibold leading-snug text-gray-900 group-hover:text-brand-700">{{ p.title }}</p>
            <p class="mt-0.5 text-xs text-gray-500">{{ p.category || 'Uncategorised' }} · <span class="font-mono">{{ p.name }}</span></p>
          </div>
        </div>
        <p v-if="p.description" class="mt-3 line-clamp-2 text-sm text-gray-600">{{ p.description }}</p>
        <div class="mt-auto flex items-center gap-4 pt-3 text-xs text-gray-500">
          <span class="inline-flex items-center gap-1"><FeatherIcon name="list" class="h-3.5 w-3.5" />{{ p.steps }} step{{ p.steps === 1 ? '' : 's' }}</span>
          <span class="inline-flex items-center gap-1"><FeatherIcon name="tool" class="h-3.5 w-3.5" />Used on {{ p.used }} work order{{ p.used === 1 ? '' : 's' }}</span>
        </div>
      </router-link>
    </div>
    <EmptyState v-else-if="!busy && !error" icon="clipboard" :title="search ? 'No procedures match' : archived ? 'Nothing archived' : 'No procedures yet'" :text="manager ? 'Build checklists once and attach them to any work order or preventive maintenance plan.' : 'Your managers have not published any procedures yet.'">
      <div v-if="manager && !search && !archived" class="flex flex-wrap justify-center gap-2">
        <router-link :to="{ name: 'OpsProcedure', params: { name: 'new' } }" class="btn btn-primary"><FeatherIcon name="plus" class="h-4 w-4" />Start blank</router-link>
        <router-link v-for="s in STARTERS" :key="s.key" :to="{ name: 'OpsProcedure', params: { name: 'new' }, query: { starter: s.key } }" class="btn btn-secondary">{{ s.title }}</router-link>
      </div>
    </EmptyState>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api } from '@/data/ops'
import { STARTERS } from '@/data/procedures'

const rows = ref([])
const search = ref('')
const archived = ref(false)
const manager = ref(false)
const busy = ref(false)
const error = ref('')

const ICONS = { Corrective: 'tool', Preventive: 'repeat', Inspection: 'search', Safety: 'shield', Other: 'clipboard' }
const TONES = { Corrective: 'bg-orange-50 text-orange-600', Preventive: 'bg-accent-50 text-accent-600', Inspection: 'bg-brand-50 text-brand-700', Safety: 'bg-red-50 text-red-600' }
const icon = (c) => ICONS[c] || 'clipboard'
const tone = (c) => TONES[c] || 'bg-gray-100 text-gray-600'

async function load() {
  busy.value = true
  error.value = ''
  try {
    const r = await api('projectit.procedures.list_procedures', { search: search.value || null, archived: archived.value ? 1 : 0 })
    rows.value = r.procedures
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
onMounted(load)
</script>
