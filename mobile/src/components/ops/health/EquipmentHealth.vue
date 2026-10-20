<template>
  <div class="space-y-5">
    <p v-if="error" role="alert" class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <div v-if="!h && !error" class="grid gap-4 md:grid-cols-3"><div v-for="i in 3" :key="i" class="h-40 animate-pulse rounded-xl bg-gray-200/70" /></div>

    <template v-if="h">
      <!-- Score and the reasons for it -->
      <div class="card grid gap-6 p-5 md:grid-cols-[13rem_minmax(0,1fr)]">
        <div class="flex flex-col items-center justify-center gap-2 text-center">
          <div class="relative h-36 w-36">
            <svg viewBox="0 0 120 120" class="h-full w-full -rotate-90" aria-hidden="true">
              <circle cx="60" cy="60" r="50" fill="none" class="stroke-gray-200" stroke-width="12" />
              <circle v-if="h.health.score !== null" cx="60" cy="60" r="50" fill="none" :class="GRADE[h.health.grade].ring" stroke-width="12" stroke-linecap="round" :stroke-dasharray="`${(314.16 * h.health.score) / 100} 314.16`" />
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center">
              <span class="text-[36px] font-bold leading-none tabular-nums text-gray-900">{{ h.health.score ?? '–' }}</span>
              <span class="text-[11px] text-gray-500">out of 100</span>
            </div>
          </div>
          <span v-if="h.health.grade" class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold" :class="GRADE[h.health.grade].chip">
            <FeatherIcon :name="GRADE[h.health.grade].icon" class="h-4 w-4" />{{ h.health.grade }}
          </span>
          <p v-if="h.health.down_now" class="text-xs font-semibold text-red-600">Down now</p>
        </div>
        <div>
          <h2 class="card-title">Health</h2>
          <p class="mb-3 text-xs text-gray-500">From the last {{ 90 }} days of readings, services, breakdowns, downtime and open repairs.</p>
          <ul class="space-y-3">
            <li v-for="f in h.health.factors" :key="f.key">
              <div class="flex items-baseline justify-between gap-3 text-sm">
                <span class="font-medium text-gray-900">{{ f.label }}</span>
                <span class="tabular-nums text-gray-600">{{ f.points === null ? 'not measured' : `${num(f.points)} / ${f.max}` }}</span>
              </div>
              <div class="mt-1 h-1.5 rounded-full bg-gray-100"><div v-if="f.points !== null" class="h-1.5 rounded-full" :class="barTone(f.points / f.max)" :style="{ width: `${(100 * f.points) / f.max}%` }" /></div>
              <p class="mt-1 text-xs text-gray-500">{{ f.detail }}</p>
            </li>
          </ul>
        </div>
      </div>

      <!-- Forecasts -->
      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">Forecasts</h2><span class="text-xs text-gray-500">Straight-line projections from recent readings and history</span></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="f in forecastRows" :key="f.text" class="flex items-start gap-3 px-5 py-3 text-sm">
            <span class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" :class="f.box"><FeatherIcon :name="f.icon" class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1">
              <span class="block font-medium text-gray-900">{{ f.text }}</span>
              <span v-if="f.sub" class="block text-xs text-gray-500">{{ f.sub }}</span>
              <span v-if="f.trust" class="mt-1 inline-flex items-center gap-1 rounded px-1.5 text-[11px] font-semibold" :class="TRUST[f.trust.level].chip" :title="f.trust.why">
                <FeatherIcon :name="TRUST[f.trust.level].icon" class="h-3 w-3" />{{ f.trust.level }} confidence
              </span>
              <span v-if="f.trust" class="ml-1.5 text-[11px] text-gray-500">{{ f.trust.why }}</span>
            </span>
            <span v-if="f.when" class="shrink-0 text-right text-xs tabular-nums">
              <span class="block font-semibold" :class="f.trust?.level === 'Low' ? 'text-gray-500' : f.whenTone">{{ f.when }}</span>
              <span v-if="f.range" class="block text-gray-500">{{ f.range }}</span>
            </span>
          </li>
          <li v-if="!forecastRows.length" class="px-5 py-3 text-sm text-gray-500">Record a few meter readings over some weeks to see forecasts.</li>
        </ul>
      </div>

      <!-- How complete the data is: what to fix for better answers -->
      <div class="card overflow-hidden">
        <div class="card-header"><h2 class="card-title">How complete the data is</h2><span class="text-xs text-gray-500">{{ dataGaps.length ? `${dataGaps.length} thing${dataGaps.length === 1 ? '' : 's'} to improve` : 'Nothing missing' }}</span></div>
        <ul class="divide-y divide-gray-100">
          <li v-for="g in dataGaps" :key="g.text" class="flex items-start gap-3 px-5 py-2.5 text-sm">
            <FeatherIcon :name="g.icon" class="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <span class="min-w-0 flex-1"><span class="block text-gray-900">{{ g.text }}</span><span class="block text-xs text-gray-500">{{ g.fix }}</span></span>
          </li>
          <li v-if="!dataGaps.length" class="flex items-center gap-3 px-5 py-2.5 text-sm text-gray-700"><FeatherIcon name="check-circle" class="h-4 w-4 text-green-600" />Readings are recent, repairs are coded and downtime is recorded.</li>
        </ul>
        <p class="border-t border-gray-100 px-5 py-2.5 text-xs text-gray-500">{{ h.data.readings_90 }} readings in the last 90 days across {{ h.data.meters }} meter{{ h.data.meters === 1 ? '' : 's' }} · {{ h.data.repairs }} repair{{ h.data.repairs === 1 ? '' : 's' }} in 12 months<template v-if="h.data.customer"> · {{ h.data.customer.logs }} customer log{{ h.data.customer.logs === 1 ? '' : 's' }} in {{ h.data.customer.days }} days</template></p>
      </div>

      <!-- Readings -->
      <div v-if="h.meters.length" class="grid gap-5 lg:grid-cols-2">
        <div v-for="m in h.meters" :key="m.name" class="card overflow-hidden">
          <div class="card-header flex-wrap gap-2">
            <h3 class="card-title">{{ m.meter_name }}<span v-if="m.stale" class="ml-2 rounded bg-amber-50 px-1.5 text-[11px] font-semibold text-amber-800">Not read for {{ ageDays(m.last_on) }} days</span></h3>
            <span class="flex items-center gap-3">
              <span v-if="m.last !== null" class="text-sm font-semibold tabular-nums text-gray-900">{{ num(m.last) }} <span class="font-normal text-gray-500">{{ m.unit }}</span></span>
              <button class="text-xs font-medium text-brand-600 hover:underline" :aria-pressed="tables[m.name]" @click="tables[m.name] = !tables[m.name]">{{ tables[m.name] ? 'Chart' : 'Table' }}</button>
            </span>
          </div>
          <div class="px-3 pb-3 pt-2">
            <LineChart v-if="!tables[m.name]" :points="m.points" :forecast="m.forecast?.line" :excluded="m.excluded" :limits="m.limits" :target="m.next_due" :unit="m.unit" :label="`${m.meter_name} readings`" />
            <div v-else class="max-h-[180px] overflow-y-auto">
              <table class="w-full text-sm"><tbody class="divide-y divide-gray-100">
                <tr v-for="p in tableRows(m)" :key="p.on"><td class="py-1 text-gray-600">{{ formatDate(p.on) }}</td><td class="py-1 text-right tabular-nums" :class="p.left_out ? 'text-red-600 line-through' : ''" :title="p.left_out ? 'Left out of the trend' : ''">{{ num(p.value) }} {{ m.unit }}</td></tr>
              </tbody></table>
            </div>
            <p class="mt-1 flex flex-wrap gap-x-3 px-2 text-[11px] text-gray-500">
              <span v-if="m.forecast?.line" class="inline-flex items-center gap-1"><span class="inline-block w-4 border-t-2 border-dashed" style="border-color: var(--series-1)" />projection</span>
              <span v-if="m.limits.length" class="inline-flex items-center gap-1"><span class="inline-block w-4 border-t-2 border-dashed border-red-500" />limit</span>
              <span v-if="m.next_due !== null" class="inline-flex items-center gap-1"><span class="inline-block w-4 border-t border-dotted border-gray-400" />next service at {{ num(m.next_due) }} {{ m.unit }}</span>
              <span v-if="m.excluded.length" class="inline-flex items-center gap-1"><span class="inline-block h-2.5 w-2.5 rounded-full border-2 border-red-500" />left out of the trend</span>
            </p>
            <ul v-if="m.excluded.length" class="mt-1.5 space-y-0.5 px-2 text-[11px] text-gray-600">
              <li v-for="e in m.excluded" :key="e.on">{{ num(e.value) }} {{ m.unit }} on {{ formatDate(e.on) }}: {{ e.why.toLowerCase() }}{{ e.why.startsWith('Far') ? ' (a typo, or a one-off?)' : '' }}</li>
            </ul>
          </div>
        </div>
      </div>
      <div v-else class="card px-5 py-4 text-sm text-gray-500">No meters on this machine yet. Add meters (running hours, TDS, pressure…) on the Overview tab to see readings and forecasts here.</div>

      <!-- History by month -->
      <div class="grid gap-5 lg:grid-cols-2">
        <div class="card overflow-hidden">
          <div class="card-header"><h3 class="card-title">Jobs each month</h3><span class="text-xs text-gray-500">Last 12 months</span></div>
          <div class="p-4"><BarChart :categories="labels" :series="jobSeries" label="Jobs opened each month" /></div>
        </div>
        <div class="card overflow-hidden">
          <div class="card-header"><h3 class="card-title">Hours down each month</h3><span class="text-xs text-gray-500">{{ num(totalDown) }} h in 12 months</span></div>
          <div class="p-4"><BarChart :categories="labels" :series="[{ key: 'down', label: 'Hours down', values: h.months.map((x) => x.down_hours) }]" :format="(v) => `${num(v)} h`" label="Hours down each month" /></div>
        </div>
        <div v-if="h.manager" class="card overflow-hidden">
          <div class="card-header"><h3 class="card-title">Cost each month</h3><span class="text-xs text-gray-500">Parts at cost and labour · {{ money(totalCost) }} in 12 months</span></div>
          <div class="p-4"><BarChart :categories="labels" :series="[{ key: 'cost', label: 'Cost', values: h.months.map((x) => x.cost || 0) }]" :format="money" label="Cost each month" /></div>
        </div>
        <div class="card overflow-hidden">
          <div class="card-header"><h3 class="card-title">Most common problems</h3><span class="text-xs text-gray-500">Failure codes, last 12 months</span></div>
          <ul class="space-y-2 p-5">
            <li v-for="f in h.failures" :key="f.code" class="text-sm">
              <div class="flex justify-between gap-2"><span class="truncate">{{ f.title }}</span><span class="tabular-nums text-gray-600">{{ f.jobs }}</span></div>
              <div class="mt-1 h-1.5 rounded-full bg-gray-100"><div class="health-chart h-1.5 rounded-full" :style="{ width: `${(100 * f.jobs) / h.failures[0].jobs}%`, background: 'var(--series-1)' }" /></div>
            </li>
            <li v-if="!h.failures.length" class="text-sm text-gray-500">No failure codes recorded on this machine's jobs.</li>
          </ul>
        </div>
      </div>

      <WhatIfPlanner :planner="h.planner" :manager="h.manager" :money="money" />
      <ROPerformance v-if="h.ro" :ro="h.ro" :equipment="equipment" :manager="h.manager" @reload="load" />
      <ROProcessModel v-if="h.process" :key="h.as_of" :process="h.process" :meters="h.meters" />
    </template>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import LineChart from '@/components/ops/charts/LineChart.vue'
import BarChart from '@/components/ops/charts/BarChart.vue'
import WhatIfPlanner from './WhatIfPlanner.vue'
import ROProcessModel from './ROProcessModel.vue'
import ROPerformance from './ROPerformance.vue'
import { api, formatDate } from '@/data/ops'

const props = defineProps({ equipment: { type: String, required: true } })
const h = ref(null)
const error = ref('')
const tables = reactive({})
const GRADE = {
  Good: { chip: 'bg-green-50 text-green-700', ring: 'stroke-green-500', icon: 'check-circle' },
  Watch: { chip: 'bg-amber-50 text-amber-800', ring: 'stroke-amber-500', icon: 'eye' },
  'At risk': { chip: 'bg-red-50 text-red-700', ring: 'stroke-red-500', icon: 'alert-triangle' },
}
const TRUST = {
  High: { chip: 'bg-green-50 text-green-700', icon: 'check' },
  Medium: { chip: 'bg-amber-50 text-amber-800', icon: 'minus' },
  Low: { chip: 'bg-gray-100 text-gray-600', icon: 'help-circle' },
}
const ageDays = (on) => Math.max(0, Math.round((new Date() - new Date(String(on).replace(' ', 'T'))) / 86400000))
// Every reading, newest first; the ones left out of the trend are struck through.
const tableRows = (m) => [...m.points, ...m.excluded.map((e) => ({ ...e, left_out: true }))]
  .sort((a, b) => new Date(String(b.on).replace(' ', 'T')) - new Date(String(a.on).replace(' ', 'T')))
// A likely range for a date; nothing when it is the same day (a very steady trend).
const range = (a, b) => (!a || (b && formatDate(a) === formatDate(b)) ? '' : `between ${formatDate(a)} and ${b ? formatDate(b) : 'later than a year'}`)
const barTone = (share) => (share >= 0.8 ? 'bg-green-500' : share >= 0.5 ? 'bg-amber-400' : 'bg-red-500')
const num = (v) => (v === null || v === undefined ? '–' : Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : Number(Number(v).toFixed(1)).toString())
const money = (n) => {
  const currency = h.value?.currency || 'KES'
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency, maximumFractionDigits: 0 })
  } catch (e) {
    return `${currency} ${Math.round(n || 0).toLocaleString()}`
  }
}
const daysTo = (on) => Math.round((new Date(String(on).replace(' ', 'T')) - new Date()) / 86400000)
const when = (on) => {
  const d = daysTo(on)
  return d <= 0 ? 'now' : d === 1 ? 'tomorrow' : d < 60 ? `in ${d} days` : `in ${Math.round(d / 30)} months`
}

const labels = computed(() => h.value.months.map((m) => m.label))
const jobSeries = computed(() => [
  { key: 'repairs', label: 'Repairs', values: h.value.months.map((m) => m.repairs) },
  { key: 'services', label: 'Services and inspections', values: h.value.months.map((m) => m.services) },
  { key: 'other', label: 'Other', values: h.value.months.map((m) => m.other) },
])
const totalDown = computed(() => h.value.months.reduce((s, m) => s + m.down_hours, 0))
const totalCost = computed(() => h.value.months.reduce((s, m) => s + (m.cost || 0), 0))
const forecastRows = computed(() => {
  const f = h.value.forecasts
  const rows = f.meters.map((m) => {
    const soon = daysTo(m.on) <= 30
    if (m.kind === 'service') {
      return { icon: 'tool', box: 'bg-brand-50 text-brand-700', text: `${m.meter} reaches its next service at ${num(m.target)} ${m.unit}`,
        sub: `About ${num(m.rate_per_day)} ${m.unit} a day`, when: `${formatDate(m.on)} · ${when(m.on)}`, whenTone: soon ? 'text-amber-700' : 'text-gray-700',
        trust: m.confidence, range: range(m.earliest, m.latest) }
    }
    return { icon: 'alert-triangle', box: 'bg-amber-50 text-amber-700', text: `${m.meter} crosses its ${m.limit === 'Below' ? 'minimum' : 'maximum'} of ${num(m.target)} ${m.unit}`,
      sub: `${m.rate_per_day > 0 ? 'Rising' : 'Falling'} about ${num(Math.abs(m.rate_per_day * 30))} ${m.unit} a month`, when: `${formatDate(m.on)} · ${when(m.on)}`, whenTone: soon ? 'text-red-600' : 'text-amber-700',
      trust: m.confidence, range: range(m.earliest, m.latest) }
  })
  if (!f.enough_history) {
    rows.push({ icon: 'clock', box: 'bg-gray-100 text-gray-500', text: 'Breakdown and cost forecasts start after 30 days of history', sub: `This machine has ${f.history_days} day${f.history_days === 1 ? '' : 's'} so far.` })
  } else if (f.next_breakdown) {
    rows.push({ icon: 'zap', box: 'bg-red-50 text-red-600', text: 'Next breakdown is likely around', sub: `It has run about ${num(f.mtbf_days)} days between breakdowns (${num(f.breakdowns_per_year)} a year)${f.mttr_hours ? `, each taking about ${num(f.mttr_hours)} h to fix` : ''}.`, when: `${formatDate(f.next_breakdown)} · ${when(f.next_breakdown)}`, whenTone: 'text-gray-700',
      trust: f.breakdown_confidence, range: f.breakdown_range ? range(f.breakdown_range[0], f.breakdown_range[1]) : '' })
  } else {
    rows.push({ icon: 'check-circle', box: 'bg-green-50 text-green-600', text: 'No breakdowns in the last 12 months', sub: 'Nothing to project from.' })
  }
  if (h.value.manager && f.cost_next_year !== null && f.cost_next_year !== undefined) {
    rows.push({ icon: 'dollar-sign', box: 'bg-gray-100 text-gray-600', text: `About ${money(f.cost_next_year)} to keep running over the next 12 months`, sub: 'Parts and labour, at the pace of the last 12 months.' })
  }
  return rows
})

const dataGaps = computed(() => {
  const d = h.value.data
  const gaps = []
  if (!d.meters) gaps.push({ icon: 'activity', text: 'No meters on this machine', fix: 'Add meters (running hours, pressure, TDS, flow) so its condition can be followed.' })
  if (d.stale.length) gaps.push({ icon: 'clock', text: `Not read recently: ${d.stale.join(', ')}`, fix: 'Record readings at every visit; readings older than 45 days are not used for the score.' })
  if (d.left_out) gaps.push({ icon: 'alert-circle', text: `${d.left_out} reading${d.left_out === 1 ? '' : 's'} left out of the trends`, fix: 'Check them on the charts below: correct typos, or confirm them if they were right.' })
  if (d.uncoded) gaps.push({ icon: 'tag', text: `${d.uncoded} of ${d.repairs} repairs have no problem code`, fix: 'Turn on "Require failure codes and downtime on repairs" in Techy Ops Settings.' })
  if (d.downtime_unknown) gaps.push({ icon: 'power', text: `${d.downtime_unknown} completed repair${d.downtime_unknown === 1 ? '' : 's'} without a downtime answer`, fix: 'Availability may look better than it is. The same setting makes technicians say whether the machine was down.' })
  const c = d.customer
  if (c && c.expected && c.done < c.expected) gaps.push({ icon: 'edit-3', text: `The customer logged ${c.done} of the expected ${c.expected} ${c.schedule === 'Weekly' ? 'weeks' : 'days'} in the last ${c.days} days`, fix: 'Their operators log in the plant app. Remind them, or change the plant app log schedule (Edit on the Overview tab).' })
  if (h.value.manager && d.labour_rate_set === false) gaps.push({ icon: 'dollar-sign', text: 'Labour cost per hour is not set', fix: 'Costs leave out labour until it is set in Techy Ops Settings.' })
  if (h.value.manager && d.untimed) gaps.push({ icon: 'watch', text: `${d.untimed} completed job${d.untimed === 1 ? '' : 's'} without any hours`, fix: 'Use the job timer, or add the time, so labour cost is counted.' })
  return gaps
})

async function load() {
  try {
    h.value = await api('projectit.health.machine_health', { equipment: props.equipment })
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)
</script>
