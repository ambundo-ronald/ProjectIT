<template>
  <div class="space-y-4">
    <div v-if="!d && !error" class="space-y-3" aria-busy="true">
      <div class="h-28 animate-pulse rounded-2xl bg-gray-200/70" />
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4"><div v-for="i in 4" :key="i" class="h-24 animate-pulse rounded-2xl bg-gray-200/70" /></div>
      <div class="h-56 animate-pulse rounded-2xl bg-gray-200/70" />
    </div>
    <EmptyState v-else-if="error" icon="alert-circle" title="Your plant could not be loaded" :text="error" />

    <template v-else>
      <!-- How the plant is doing, in plain words -->
      <section class="card overflow-hidden" :aria-label="`Plant status: ${STATUS[d.status.level].label}`">
        <div class="flex items-start gap-4 p-5" :class="STATUS[d.status.level].band">
          <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full" :class="STATUS[d.status.level].badge"><FeatherIcon :name="STATUS[d.status.level].icon" class="h-6 w-6" /></span>
          <div class="min-w-0 flex-1">
            <p class="text-xs font-medium text-gray-600">{{ d.machine.equipment_name }}</p>
            <h1 class="text-[22px] font-semibold tracking-tight text-gray-900">{{ STATUS[d.status.level].label }}</h1>
            <ul v-if="d.status.reasons.length" class="mt-1 space-y-0.5 text-sm text-gray-700">
              <li v-for="r in d.status.reasons" :key="r" class="flex gap-2"><span aria-hidden="true">·</span><span>{{ r }}</span></li>
            </ul>
            <p v-else class="mt-1 text-sm text-gray-700">The latest readings look normal.</p>
            <p v-if="d.status.level !== 'good'" class="mt-2 text-xs text-gray-600">{{ d.membranes?.cleaning_planned ? 'We have planned a membrane clean.' : 'We follow these readings too, and will contact you about anything that needs a visit.' }}</p>
          </div>
        </div>
        <router-link v-if="d.logging.today.due" :to="{ name: 'PlantLog' }" class="flex items-center gap-3 border-t border-gray-100 px-5 py-3 text-sm font-medium text-brand-700 hover:bg-gray-50">
          <FeatherIcon name="edit-3" class="h-4 w-4" /><span class="flex-1">{{ d.logging.today.schedule === 'Weekly' ? "This week's log is due" : "Today's log is due" }}: log the readings now</span><FeatherIcon name="arrow-right" class="h-4 w-4" />
        </router-link>
      </section>

      <AdviceCard :items="d.advice" title="Readings out of range: what to do" :phone="plant.me?.support_phone" />

      <!-- Key numbers -->
      <section v-if="d.numbers.length" aria-label="Key numbers" class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div v-for="n in d.numbers" :key="n.key" class="card p-4" :title="n.help || undefined">
          <p class="truncate text-xs font-medium text-gray-500">{{ n.label }}</p>
          <p class="mt-1 text-[22px] font-semibold tabular-nums tracking-tight text-gray-900">{{ num(n.value) }}<span class="ml-1 text-sm font-normal text-gray-500">{{ n.unit }}</span></p>
          <p class="mt-0.5 flex items-center gap-1 text-xs text-gray-500">
            <template v-if="n.week && n.week.change !== 0"><FeatherIcon :name="n.week.change > 0 ? 'arrow-up-right' : 'arrow-down-right'" class="h-3.5 w-3.5" />{{ num(Math.abs(n.week.change)) }} {{ n.unit }} {{ n.week.change > 0 ? 'more' : 'less' }} than last week</template>
            <template v-else-if="n.week">Same as last week</template>
            <template v-else>{{ n.on ? `Read ${fromNow(n.on)}` : 'Not read yet' }}</template>
          </p>
        </div>
      </section>

      <!-- Charts -->
      <section v-if="d.charts.length || d.membranes" class="space-y-4" aria-label="Charts">
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-[15px] font-semibold text-gray-900">Trends</h2>
          <span class="segmented" role="group" aria-label="Period">
            <button v-for="p in [30, 90]" :key="p" type="button" :aria-pressed="days === p" @click="setDays(p)">{{ p }} days</button>
          </span>
        </div>

        <div v-if="d.membranes" class="card overflow-hidden">
          <div class="card-header flex-wrap gap-2">
            <div class="min-w-0">
              <h3 class="card-title">Membrane condition</h3>
              <p class="text-xs text-gray-500">Compared with {{ formatDate(d.membranes.since) }}, corrected for water temperature and pressure</p>
            </div>
            <button class="text-xs font-medium text-brand-600 hover:underline" :aria-pressed="!!tables.membranes" @click="tables.membranes = !tables.membranes">{{ tables.membranes ? 'Chart' : 'Table' }}</button>
          </div>
          <div class="grid gap-4 p-4 md:grid-cols-2">
            <div v-for="c in membraneCharts" :key="c.key">
              <p class="mb-1 flex items-baseline justify-between gap-2 text-xs"><span class="font-medium text-gray-700">{{ c.label }}</span><span class="tabular-nums font-semibold text-gray-900">{{ c.now }}</span></p>
              <LineChart v-if="!tables.membranes" :points="c.points" :limits="c.limits" unit="%" :label="`${c.label}, % change`" :height="150" />
              <DataTable v-else :rows="c.points" unit="%" :signed="true" />
              <p class="mt-1 text-[11px] text-gray-500">{{ c.help }}</p>
            </div>
          </div>
          <p class="border-t border-gray-100 px-5 py-2.5 text-xs text-gray-600">
            <span class="mr-1 inline-block w-4 border-t-2 border-dashed border-red-500 align-middle" aria-hidden="true" />The red line is where the membranes need cleaning.
            {{ d.membranes.needs_cleaning ? (d.membranes.cleaning_planned ? 'A clean is planned.' : 'They have passed it: we will contact you.') : '' }}
          </p>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <div v-for="c in d.charts" :key="c.key" class="card overflow-hidden">
            <div class="card-header">
              <div class="min-w-0"><h3 class="card-title">{{ c.label }}</h3><p v-if="c.meter !== c.label" class="text-xs text-gray-500">{{ c.meter }}</p></div>
              <button class="text-xs font-medium text-brand-600 hover:underline" :aria-pressed="!!tables[c.key]" @click="tables[c.key] = !tables[c.key]">{{ tables[c.key] ? 'Chart' : 'Table' }}</button>
            </div>
            <div class="p-4">
              <p v-if="!c.points.length" class="py-8 text-center text-sm text-gray-500">No readings in the last {{ days }} days.</p>
              <LineChart v-else-if="!tables[c.key]" :points="c.points" :limits="c.limits" :unit="c.unit" :label="`${c.label} readings`" :height="160" />
              <DataTable v-else :rows="c.points" :unit="c.unit" />
            </div>
          </div>
        </div>
      </section>

      <div class="grid gap-4 md:grid-cols-2">
        <!-- What's next -->
        <section class="card overflow-hidden" aria-labelledby="next-title">
          <div class="card-header"><h2 id="next-title" class="card-title">What's next</h2></div>
          <ul v-if="d.next.length" class="divide-y divide-gray-100">
            <li v-for="n in d.next" :key="n.kind" class="flex items-start gap-3 px-5 py-3 text-sm">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><FeatherIcon :name="NEXT_ICON[n.kind] || 'calendar'" class="h-4 w-4" /></span>
              <span class="min-w-0 flex-1">
                <span class="block font-medium text-gray-900">{{ n.label }}<span v-if="n.due" class="ml-2 rounded bg-red-50 px-1.5 text-[11px] font-semibold text-red-700">Due now</span></span>
                <span v-if="n.estimate" class="block text-xs text-gray-500">Estimated from its daily running hours</span>
              </span>
              <span class="shrink-0 text-right text-xs tabular-nums" :class="n.past ? 'text-gray-500' : 'text-gray-700'">
                <template v-if="n.kind === 'onway'">
                  <span class="block font-semibold">{{ n.minutes ? `About ${n.minutes} min` : 'Soon' }}</span>
                  <span class="block text-gray-500">Left {{ fromNow(n.on) }}</span>
                </template>
                <template v-else>
                  <span class="block font-semibold">{{ n.estimate ? 'About ' : '' }}{{ formatDate(n.on) }}</span>
                  <span class="block text-gray-500">{{ n.past ? 'Ended' : until(n.on) }}</span>
                </template>
              </span>
            </li>
          </ul>
          <p v-else class="px-5 py-4 text-sm text-gray-500">Nothing planned yet.</p>
        </section>

        <!-- Logging -->
        <section class="card p-5" aria-labelledby="logging-title">
          <h2 id="logging-title" class="card-title">Your logs</h2>
          <template v-if="d.logging.expected">
            <p class="mt-2 text-sm text-gray-700"><span class="text-[22px] font-semibold tabular-nums text-gray-900">{{ d.logging.done }}</span> of the last {{ d.logging.expected }} {{ d.logging.schedule === 'Weekly' ? 'weeks' : 'days' }} logged</p>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-gray-100" role="meter" :aria-valuenow="d.logging.done" aria-valuemin="0" :aria-valuemax="d.logging.expected" :aria-label="`${d.logging.done} of ${d.logging.expected} logged`">
              <div class="h-full rounded-full bg-brand-600" :style="{ width: `${Math.min(100, (100 * d.logging.done) / d.logging.expected)}%` }" />
            </div>
            <p class="mt-2 text-xs text-gray-500">{{ d.logging.done >= d.logging.expected ? 'Every day logged. Thank you!' : 'Logging every day lets us spot problems before they stop the plant.' }}</p>
          </template>
          <p v-else class="mt-2 text-sm text-gray-500">No regular log is needed for this machine.</p>
          <router-link :to="{ name: 'PlantLog' }" class="btn btn-secondary btn-sm mt-3"><FeatherIcon name="edit-3" class="h-4 w-4" />{{ d.logging.today.due ? 'Log now' : 'See your logs' }}</router-link>
        </section>
      </div>
      <p class="text-center text-[11px] text-gray-500">Updated {{ fromNow(d.as_of) }}</p>
    </template>
  </div>
</template>
<script setup>
import { ref, reactive, computed, watch, onMounted, h } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import EmptyState from '@/components/ops/EmptyState.vue'
import LineChart from '@/components/ops/charts/LineChart.vue'
import AdviceCard from '@/components/plant/AdviceCard.vue'
import { api, formatDate, fromNow, dueIn } from '@/data/ops'
import { plant } from '@/data/plant'

// Status: an icon and a word, never colour alone.
const STATUS = {
  good: { label: 'Running well', icon: 'check-circle', band: 'bg-green-50', badge: 'bg-green-100 text-green-700' },
  watch: { label: 'Needs attention', icon: 'alert-circle', band: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700' },
  action: { label: 'Action needed', icon: 'alert-triangle', band: 'bg-red-50', badge: 'bg-red-100 text-red-700' },
}
const NEXT_ICON = { supply: 'filter', onway: 'navigation', visit: 'truck', service: 'tool', warranty_until: 'shield', contract_until: 'file-text' }
const d = ref(null)
const error = ref('')
const days = ref(90)
const tables = reactive({})

// How far away a date is, in words.
function until(on) {
  const n = dueIn(on)
  if (n === null) return ''
  if (n === 0) return 'today'
  if (n === 1) return 'tomorrow'
  if (n < 0) return `${-n} days ago`
  if (n < 60) return `in ${n} days`
  return `in ${Math.round(n / 30)} months`
}
const num = (v) => (v === null || v === undefined ? '–' : Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : Number(Number(v).toFixed(1)).toLocaleString())
const signed = (v) => (v === null || v === undefined ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%`)
const membraneCharts = computed(() => {
  const m = d.value?.membranes
  if (!m) return []
  return [
    { key: 'flow', label: 'Water output', points: m.flow, limits: [{ type: 'Below', value: m.clean_at.flow }], now: signed(m.latest.flow), help: 'Falls as dirt and scale build up on the membranes.' },
    { key: 'salt', label: 'Salt let through', points: m.salt, limits: [{ type: 'Above', value: m.clean_at.salt }], now: signed(m.latest.salt), help: 'Rises with scale, or as the membranes wear.' },
  ]
})

async function load() {
  if (!plant.machine) return
  error.value = ''
  try {
    d.value = await api('projectit.plant.dashboard', { equipment: plant.machine, days: days.value })
  } catch (e) {
    if (!d.value) error.value = e.message
  }
}
function setDays(p) {
  days.value = p
  load()
}
watch(() => plant.machine, () => {
  d.value = null
  load()
})
onMounted(load)

// The numbers behind a chart, newest first (for screen readers, and anyone who prefers a table).
const DataTable = (p) =>
  h('div', { class: 'max-h-48 overflow-y-auto' }, [
    h('table', { class: 'w-full text-xs' }, [
      h('thead', h('tr', { class: 'text-left text-gray-500' }, [h('th', { class: 'py-1 font-medium' }, 'Date'), h('th', { class: 'py-1 text-right font-medium' }, 'Value')])),
      h('tbody', [...p.rows].reverse().map((r) => h('tr', { key: r.on, class: 'border-t border-gray-100' }, [
        h('td', { class: 'py-1 text-gray-600' }, formatDate(r.on)),
        h('td', { class: 'py-1 text-right tabular-nums text-gray-900' }, p.signed ? signed(r.value) : `${num(r.value)} ${p.unit}`),
      ]))),
    ]),
  ])
DataTable.props = ['rows', 'unit', 'signed']
</script>
