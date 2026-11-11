<template>
  <div class="space-y-5">
    <PageHeader mobile title="Projects" subtitle="Crews, site instructions and who is on site right now.">
      <button class="btn btn-ghost btn-icon" aria-label="Refresh" :disabled="loading" @click="load"><FeatherIcon name="refresh-cw" class="h-4 w-4" :class="loading ? 'animate-spin' : ''" /></button>
    </PageHeader>

    <div class="grid grid-cols-3 gap-3">
      <div class="card p-4">
        <p class="flex items-center gap-1.5 text-xs font-medium text-gray-500"><span class="h-2 w-2 rounded-full bg-green-500" />On site now</p>
        <p class="mt-1 text-[26px] font-semibold tracking-tight text-green-700">{{ data?.totals.on_site ?? '–' }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-gray-500">People allocated</p>
        <p class="mt-1 text-[26px] font-semibold tracking-tight">{{ data?.totals.crew ?? '–' }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-gray-500">Open projects</p>
        <p class="mt-1 text-[26px] font-semibold tracking-tight">{{ data?.totals.projects ?? '–' }}</p>
      </div>
    </div>

    <div class="flex gap-2">
      <div class="relative min-w-0 flex-1">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input v-model="search" type="search" class="input pl-9" placeholder="Search projects or people" aria-label="Search projects or people" />
      </div>
      <ViewToggle v-model="view" />
    </div>
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <div v-if="!data && !error" class="grid gap-3 md:grid-cols-2"><div v-for="i in 4" :key="i" class="h-36 animate-pulse rounded-xl bg-gray-200/70" /></div>
    <div v-else-if="visible.length && view === 'list'" class="card overflow-hidden">
      <div class="hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1.4fr)_7rem_7rem] gap-4 border-b border-gray-100 bg-gray-50/80 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 md:grid">
        <span>Project</span><span>Site instructions</span><span>Crew</span><span>On site</span>
      </div>
      <ul class="divide-y divide-gray-100">
        <li v-for="p in paged" :key="p.name">
          <router-link :to="{ name: 'ManageProject', params: { project: p.name } }" class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 md:grid md:grid-cols-[minmax(0,1.4fr)_minmax(0,1.4fr)_7rem_7rem] md:gap-4">
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium text-gray-900">{{ p.project_name }}</span>
              <span class="block truncate text-xs text-gray-500">{{ p.name }}<template v-if="p.expected_end_date"> · due {{ formatDate(p.expected_end_date) }}</template><span class="md:hidden"> · {{ p.crew.length }} crew</span></span>
            </span>
            <span class="hidden truncate text-sm md:block" :class="p.work_instruction ? 'text-gray-600' : 'italic text-gray-400'">{{ p.work_instruction || 'None yet' }}</span>
            <span class="hidden text-sm md:block" :class="p.crew.length ? 'text-gray-600' : 'font-medium text-amber-700'">{{ p.crew.length ? `${p.crew.length} ${p.crew.length === 1 ? 'person' : 'people'}` : 'No crew' }}</span>
            <span class="shrink-0 text-xs">
              <span v-if="onSite(p)" class="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2 py-0.5 font-semibold text-green-700"><span class="h-1.5 w-1.5 rounded-full bg-green-500" />{{ onSite(p) }}</span>
              <span v-else class="text-gray-400">—</span>
            </span>
          </router-link>
        </li>
      </ul>
    </div>
    <div v-else-if="visible.length" class="grid gap-3 md:grid-cols-2">
      <router-link v-for="p in paged" :key="p.name" :to="{ name: 'ManageProject', params: { project: p.name } }" class="card group flex flex-col p-4 transition hover:-translate-y-px hover:border-gray-300 hover:shadow-pop">
        <div class="flex items-start gap-3">
          <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon name="briefcase" class="h-5 w-5" /></span>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold text-gray-900 group-hover:text-brand-700">{{ p.project_name }}</p>
            <p class="text-xs text-gray-500">{{ p.name }}<template v-if="p.expected_end_date"> · due {{ formatDate(p.expected_end_date) }}</template></p>
          </div>
          <span v-if="onSite(p)" class="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700"><span class="h-1.5 w-1.5 rounded-full bg-green-500" />{{ onSite(p) }} on site</span>
        </div>
        <p class="mt-3 line-clamp-2 text-sm" :class="p.work_instruction ? 'text-gray-600' : 'italic text-gray-400'">{{ p.work_instruction || 'No site instructions yet' }}</p>
        <div class="mt-auto flex items-center justify-between pt-4">
          <div v-if="p.crew.length" class="flex items-center gap-2">
            <div class="flex -space-x-1.5">
              <span v-for="m in p.crew.slice(0, 5)" :key="m.employee" class="relative rounded-full ring-2 ring-panel">
                <UserAvatar :name="m.name" :image="m.image" size="sm" />
                <span v-if="m.on_site" class="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-green-500 ring-2 ring-panel" />
              </span>
            </div>
            <span class="text-xs text-gray-500">{{ p.crew.length }} {{ p.crew.length === 1 ? 'person' : 'people' }}</span>
          </div>
          <span v-else class="inline-flex items-center gap-1 text-xs font-medium text-amber-700"><FeatherIcon name="user-plus" class="h-3.5 w-3.5" />No crew yet</span>
          <FeatherIcon name="chevron-right" class="h-4 w-4 text-gray-300 group-hover:text-brand-600" />
        </div>
      </router-link>
    </div>
    <EmptyState v-else-if="data" icon="briefcase" :title="search ? 'No matches' : 'No open projects'" :text="search ? 'Try a different project or person name.' : 'Create a Project in ERPNext and it will appear here, ready for a crew.'" />
    <Pager :total="total" :start="start" :page-length="pageLength" label="Project pages" @change="(s) => (start = s)" @update:page-length="(n) => (pageLength = n)" />
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import UserAvatar from '@/components/ops/UserAvatar.vue'
import Pager from '@/components/ops/Pager.vue'
import ViewToggle from '@/components/ops/ViewToggle.vue'
import { api, formatDate } from '@/data/ops'
import { usePaged, useView } from '@/data/paging'

const data = ref(null)
const error = ref('')
const loading = ref(false)
const search = ref('')
const onSite = (p) => p.crew.filter((m) => m.on_site).length
const visible = computed(() => {
  const q = search.value.trim().toLowerCase()
  const rows = data.value?.projects || []
  return q ? rows.filter((p) => p.project_name.toLowerCase().includes(q) || p.name.toLowerCase().includes(q) || p.crew.some((m) => m.name.toLowerCase().includes(q))) : rows
})

const view = useView('manage_projects')
const { start, pageLength, total, paged } = usePaged(visible, [search])

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api('projectit.manage.overview')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
