<template>
  <section class="mx-auto max-w-[1400px] space-y-5 p-4 md:p-8">
    <PageHeader title="Work orders" class="hidden md:flex">
      <template #subtitle>
        {{ counts.active }} active<template v-if="counts.overdue"> · <span class="font-medium text-red-600">{{ counts.overdue }} overdue</span></template>
      </template>
      <div class="segmented" role="group" aria-label="View">
        <button v-for="v in views" :key="v.value" :aria-pressed="view === v.value" :title="v.label" @click="setView(v.value)"><FeatherIcon :name="v.icon" class="h-4 w-4" />{{ v.label }}</button>
      </div>
      <button class="btn btn-primary" @click="openNew()"><FeatherIcon name="plus" class="h-4 w-4" />New work order</button>
    </PageHeader>

    <!-- Toolbar -->
    <div class="space-y-3">
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative w-full min-w-0 sm:w-auto sm:flex-1 md:max-w-sm">
          <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input v-model="search" type="search" placeholder="Search work orders" aria-label="Search work orders" class="input pl-9" @input="debouncedLoad" />
        </div>
        <div v-if="me.manager" class="segmented shrink-0" role="group" aria-label="Whose work">
          <button v-for="s in scopes" :key="s.value" :aria-pressed="scope === s.value" @click="scope = s.value; load()">{{ s.label }}</button>
        </div>
        <button class="btn btn-ghost btn-icon shrink-0" aria-label="Refresh" :disabled="busy" @click="load()"><FeatherIcon name="refresh-cw" class="h-4 w-4" :class="busy ? 'animate-spin' : ''" /></button>
      </div>
      <div class="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:px-0" role="group" aria-label="Filter">
        <button v-for="f in filters" :key="f.key" class="chip" :aria-pressed="filter === f.key" @click="filter = f.key">
          <FeatherIcon v-if="f.icon" :name="f.icon" class="h-3.5 w-3.5" :class="filter === f.key ? '' : f.tone" />{{ f.label }}<span class="count">{{ f.count }}</span>
        </button>
      </div>
    </div>

    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

    <!-- Loading skeleton -->
    <div v-if="busy && !loaded" class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <div v-for="i in 4" :key="i" class="h-32 animate-pulse rounded-xl bg-gray-200/70" />
    </div>

    <!-- Board -->
    <div v-else-if="view === 'board'" class="grid items-start gap-4 lg:grid-cols-4">
      <div v-for="col in columns" :key="col.key" class="flex flex-col rounded-2xl bg-gray-100/80 p-2">
        <h2 class="flex items-center gap-2 px-2 pb-2 pt-1 text-[13px] font-semibold text-gray-700">
          <span class="h-2 w-2 rounded-full" :class="col.dot" />{{ col.label }}
          <span class="ml-auto rounded-full bg-white px-2 text-xs font-semibold text-gray-600 shadow-sm">{{ col.rows.length }}</span>
        </h2>
        <div class="space-y-2">
          <WorkOrderCard v-for="wo in col.rows" :key="wo.name" :wo="wo" />
          <p v-if="!col.rows.length" class="rounded-xl border border-dashed border-gray-300 px-3 py-6 text-center text-xs text-gray-400">{{ col.empty }}</p>
        </div>
      </div>
    </div>

    <!-- List -->
    <template v-else>
      <div v-if="visible.length" class="overflow-hidden md:rounded-xl md:border md:border-gray-200 md:bg-white md:shadow-card">
        <div class="hidden grid-cols-[minmax(0,1fr)_8rem_7rem_10rem_7rem_6rem] gap-4 border-b border-gray-100 bg-gray-50/80 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 md:grid">
          <span>Work order</span><span>Status</span><span>Priority</span><span>Asset / location</span><span>Due</span><span>Assigned</span>
        </div>
        <ul class="space-y-2 md:space-y-0 md:divide-y md:divide-gray-100">
          <li v-for="wo in visible" :key="wo.name">
            <WorkOrderCard :wo="wo" show-status class="md:hidden" />
            <router-link :to="{ name: 'OpsWorkOrder', params: { name: wo.name } }" class="hidden grid-cols-[minmax(0,1fr)_8rem_7rem_10rem_7rem_6rem] items-center gap-4 px-4 py-3 hover:bg-gray-50 md:grid">
              <span class="min-w-0">
                <span class="block truncate font-medium text-gray-900">{{ wo.subject }}</span>
                <span class="text-xs text-gray-400">#{{ wo.name }}<template v-if="wo.custom_work_category"> · {{ wo.custom_work_category }}</template></span>
              </span>
              <span><StatusPill :status="wo.status !== 'Completed' && isOverdue(wo) ? 'Overdue' : wo.status" /></span>
              <PriorityFlag :priority="wo.priority" />
              <span class="truncate text-[13px] text-gray-600">{{ wo.asset_name || wo.custom_location || '—' }}</span>
              <span class="text-[13px]" :class="isOverdue(wo) ? 'font-semibold text-red-600' : 'text-gray-600'">{{ wo.exp_end_date ? formatDate(wo.exp_end_date) : '—' }}</span>
              <AvatarStack :people="wo.assignees || []" />
            </router-link>
          </li>
        </ul>
      </div>
      <EmptyState v-else icon="check-circle" :title="filter === 'active' ? 'No active work orders' : 'Nothing matches this filter'" :text="filter === 'active' ? 'New work, approved requests and due preventive maintenance will show up here.' : 'Try another filter or clear the search.'">
        <button v-if="filter === 'active'" class="btn btn-primary btn-sm" @click="openNew()"><FeatherIcon name="plus" class="h-4 w-4" />New work order</button>
      </EmptyState>
      <button v-if="hasMore" class="btn btn-secondary w-full" :disabled="busy" @click="load(true)">Load more</button>
    </template>

    <!-- Mobile create button -->
    <button class="fixed bottom-20 right-4 z-30 flex h-14 items-center gap-2 rounded-full bg-brand-600 pl-4 pr-5 font-semibold text-white shadow-pop md:hidden" aria-label="New work order" @click="openNew()">
      <FeatherIcon name="plus" class="h-5 w-5" />New
    </button>
  </section>
</template>
<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PageHeader from '@/components/ops/PageHeader.vue'
import EmptyState from '@/components/ops/EmptyState.vue'
import WorkOrderCard from '@/components/ops/WorkOrderCard.vue'
import StatusPill from '@/components/ops/StatusPill.vue'
import PriorityFlag from '@/components/ops/PriorityFlag.vue'
import AvatarStack from '@/components/ops/AvatarStack.vue'
import { api, me, onRealtime, formatDate, isOverdue, dueIn } from '@/data/ops'
import { ui } from '@/data/apps'

const openNew = inject('openNewWorkOrder')
const rows = ref([])
const busy = ref(false)
const loaded = ref(false)
const error = ref('')
const hasMore = ref(false)
const scope = ref(me.manager ? 'all' : 'mine')
const filter = ref('active')
const search = ref('')
const views = [
  { value: 'board', label: 'Board', icon: 'columns' },
  { value: 'list', label: 'List', icon: 'list' },
]
const scopes = [
  { value: 'mine', label: 'Mine' },
  { value: 'all', label: 'Everyone' },
]
const storedView = (() => {
  try {
    return localStorage.getItem('techy_ops_view')
  } catch (e) {
    return null
  }
})()
const view = ref(window.innerWidth >= 1024 ? storedView || 'board' : 'list')

function setView(v) {
  view.value = v
  try {
    localStorage.setItem('techy_ops_view', v)
  } catch (e) {
    /* storage unavailable */
  }
}

const isDone = (r) => ['Completed', 'Cancelled'].includes(r.status)
const late = (r) => r.status === 'Overdue' || isOverdue(r)
const predicates = {
  active: (r) => !isDone(r),
  overdue: (r) => !isDone(r) && late(r),
  today: (r) => !isDone(r) && dueIn(r.exp_end_date) === 0,
  high: (r) => !isDone(r) && ['High', 'Urgent'].includes(r.priority),
  unassigned: (r) => !isDone(r) && !r.assignees?.length,
  done: (r) => r.status === 'Completed',
}
const counts = computed(() => Object.fromEntries(Object.entries(predicates).map(([k, fn]) => [k, rows.value.filter(fn).length])))
const filters = computed(() => [
  { key: 'active', label: 'Active', count: counts.value.active },
  { key: 'overdue', label: 'Overdue', icon: 'alert-circle', tone: 'text-red-500', count: counts.value.overdue },
  { key: 'today', label: 'Due today', icon: 'clock', tone: 'text-amber-500', count: counts.value.today },
  { key: 'high', label: 'High priority', icon: 'flag', tone: 'text-orange-500', count: counts.value.high },
  { key: 'unassigned', label: 'Unassigned', icon: 'user-x', tone: 'text-gray-500', count: counts.value.unassigned },
  { key: 'done', label: 'Done', icon: 'check', tone: 'text-green-600', count: counts.value.done },
])
const visible = computed(() => rows.value.filter(predicates[filter.value]))

const columns = computed(() => {
  // On the board, a filter narrows every column; "Done" shows recent completions.
  const base = filter.value === 'active' || filter.value === 'done' ? rows.value : visible.value
  return [
    { key: 'open', label: 'Open', dot: 'bg-blue-500', empty: 'No open work', rows: base.filter((r) => ['Open', 'Overdue'].includes(r.status)) },
    { key: 'working', label: 'In progress', dot: 'bg-amber-500', empty: 'Nothing in progress', rows: base.filter((r) => r.status === 'Working') },
    { key: 'review', label: 'On hold / review', dot: 'bg-violet-500', empty: 'Nothing on hold', rows: base.filter((r) => r.status === 'Pending Review') },
    { key: 'done', label: 'Done', dot: 'bg-green-500', empty: 'Completed work appears here', rows: base.filter((r) => r.status === 'Completed').slice(0, 8) },
  ]
})

async function load(append = false) {
  busy.value = true
  error.value = ''
  try {
    const data = await api('projectit.work_orders.list_work_orders', { scope: scope.value, status: '', search: search.value, start: append ? rows.value.length : 0 })
    rows.value = append ? [...rows.value, ...data.work_orders] : data.work_orders
    hasMore.value = data.has_more
    loaded.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

let timer = null
function debouncedLoad() {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 300)
}

let refresh = null
const stop = onRealtime('techy_work_order', () => {
  clearTimeout(refresh)
  refresh = setTimeout(() => load(), 800)
})
onMounted(() => {
  load()
  ui.dockLift = 72 // sit above the "New" button
})
onBeforeUnmount(() => {
  stop()
  ui.dockLift = 0
})
</script>
