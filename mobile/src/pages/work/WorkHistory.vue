<template>
  <div class="space-y-5">
    <PageHeader mobile title="History" subtitle="Your checked-in time, as recorded on your timesheets." />

    <div class="grid grid-cols-2 gap-3">
      <div class="card p-4">
        <p class="text-xs font-medium text-gray-500">Today</p>
        <p class="mt-1 text-[26px] font-semibold tracking-tight">{{ hours(totals.today) }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs font-medium text-gray-500">This week</p>
        <p class="mt-1 text-[26px] font-semibold tracking-tight">{{ hours(totals.week) }}</p>
      </div>
    </div>

    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="loading && !rows.length" class="space-y-2">
      <div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-xl bg-gray-200/70" />
    </div>

    <section v-for="day in days" :key="day.date">
      <div class="mb-2 flex items-baseline justify-between px-1">
        <h2 class="text-sm font-semibold text-gray-800">{{ dayLabel(day.date) }}</h2>
        <span class="text-xs font-medium text-gray-500">{{ hours(day.total) }}</span>
      </div>
      <ul class="card divide-y divide-gray-100 overflow-hidden">
        <li v-for="t in day.rows" :key="t.name" class="flex items-start gap-3 px-4 py-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="t.open ? 'bg-accent-50 text-accent-600' : 'bg-brand-50 text-brand-700'">
            <FeatherIcon :name="t.open ? 'play-circle' : 'briefcase'" class="h-4 w-4" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold">{{ t.project_name || 'No project' }}</p>
            <p class="mt-0.5 text-xs text-gray-500">
              {{ formatTime(t.started) }} – {{ t.open ? 'now' : formatTime(t.ended) }}<template v-if="t.task"> · {{ t.task }}</template>
            </p>
          </div>
          <div class="text-right">
            <p v-if="t.open" class="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-0.5 text-xs font-semibold text-accent-600"><span class="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-500" />In progress</p>
            <template v-else>
              <p class="font-semibold">{{ hours(t.total_hours) }}</p>
              <p v-if="t.overtime_hours" class="text-[11px] font-medium text-orange-600">{{ hours(t.overtime_hours) }} overtime</p>
            </template>
          </div>
        </li>
      </ul>
    </section>

    <EmptyState v-if="!loading && !rows.length && !error" icon="clock" title="No time recorded yet" text="Check in from Today when you start work. Your entries will appear here after you check out." />
    <button v-if="hasMore" class="btn btn-secondary w-full" :disabled="loading" @click="load(true)">Load older entries</button>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import { api, formatDate, formatTime, dueIn } from '@/data/ops'

const rows = ref([])
const totals = ref({ today: 0, week: 0 })
const loading = ref(false)
const error = ref('')
const hasMore = ref(false)

const hours = (h) => {
  const minutes = Math.round((Number(h) || 0) * 60)
  if (minutes < 1) return Number(h) > 0 ? "<1m" : "0m"
  return minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`
}
const dayLabel = (d) => ({ 0: 'Today', '-1': 'Yesterday' })[dueIn(d)] || new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'short' }) || formatDate(d)
const days = computed(() => {
  const groups = []
  for (const row of rows.value) {
    let group = groups.find((g) => g.date === row.start_date)
    if (!group) groups.push((group = { date: row.start_date, rows: [], total: 0 }))
    group.rows.push(row)
    if (!row.open) group.total += Number(row.total_hours) || 0
  }
  return groups
})

async function load(append = false) {
  loading.value = true
  error.value = ''
  try {
    const data = await api('projectit.work.history', { start: append ? rows.value.length : 0 })
    rows.value = append ? [...rows.value, ...data.timesheets] : data.timesheets
    totals.value = data.totals
    hasMore.value = data.has_more
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>
