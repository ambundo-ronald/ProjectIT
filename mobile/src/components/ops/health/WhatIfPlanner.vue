<template>
  <div class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <h2 class="card-title">What-if planner</h2>
      <button v-if="changed" class="text-xs font-medium text-brand-600 hover:underline" @click="reset">Back to today's numbers</button>
    </div>
    <p v-if="!ready" class="px-5 py-4 text-sm text-gray-500">The planner needs at least 30 days of history on this machine, with a running-hours meter or service jobs, to start from.</p>
    <div v-else class="grid gap-6 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div class="space-y-5">
        <div v-if="p.meter">
          <label class="label flex justify-between" for="wi-usage"><span>Use per day</span><span class="tabular-nums text-gray-900">{{ num(usage) }} {{ p.meter.unit }}</span></label>
          <input id="wi-usage" v-model.number="usage" type="range" :min="round(p.meter.per_day * 0.25)" :max="round(Math.max(p.meter.per_day * 2, 24))" :step="step(p.meter.per_day)" class="w-full accent-brand-600" />
          <p class="hint">Today: {{ num(p.meter.per_day) }} {{ p.meter.unit }} a day ({{ p.meter.name }})</p>
        </div>
        <div v-if="p.meter && p.meter.every">
          <label class="label flex justify-between" for="wi-interval"><span>Service every</span><span class="tabular-nums text-gray-900">{{ num(interval) }} {{ p.meter.unit }}</span></label>
          <input id="wi-interval" v-model.number="interval" type="range" :min="round(p.meter.every * 0.5)" :max="round(p.meter.every * 2)" :step="step(p.meter.every / 10)" class="w-full accent-brand-600" />
          <p class="hint">Today: every {{ num(p.meter.every) }} {{ p.meter.unit }}</p>
        </div>
        <div v-else>
          <label class="label flex justify-between" for="wi-visits"><span>Services a year</span><span class="tabular-nums text-gray-900">{{ visits }}</span></label>
          <input id="wi-visits" v-model.number="visits" type="range" min="1" max="24" step="1" class="w-full accent-brand-600" />
          <p class="hint">Today: {{ num(p.services_per_year || 0) }} a year</p>
        </div>
        <p class="rounded-lg bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-600">
          How it estimates: breakdowns rise and fall with how much the machine runs, and with the time between services (servicing half as often gives about 1.7 times the breakdowns). Each breakdown keeps the machine down for its average repair time ({{ num(p.mttr_hours) }} h). Nothing here is saved.
        </p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-xs text-gray-500"><tr><th class="pb-2 font-medium">Per year</th><th class="pb-2 text-right font-medium">Today</th><th class="pb-2 text-right font-medium">Your plan</th></tr></thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="r in rows" :key="r.label">
              <td class="py-2 text-gray-700">{{ r.label }}</td>
              <td class="py-2 text-right tabular-nums text-gray-600">{{ r.fmt(r.now) }}</td>
              <td class="py-2 text-right tabular-nums font-semibold" :class="tone(r)">{{ r.fmt(r.plan) }}<span v-if="delta(r)" class="ml-1 text-[11px] font-medium">{{ delta(r) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="!manager" class="mt-3 text-xs text-gray-500">Managers also see the yearly cost.</p>
        <p v-else-if="p.cost_per_service === null || p.cost_per_breakdown === null" class="mt-3 text-xs text-gray-500">Costs show once this machine has completed both service and repair jobs.</p>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ planner: { type: Object, required: true }, manager: Boolean, money: { type: Function, required: true } })
const p = computed(() => props.planner)
const ready = computed(() => p.value.breakdowns_per_year !== null && (p.value.meter || p.value.services_per_year))
const round = (v) => Math.max(1, Math.round(v))
const step = (v) => (v >= 200 ? 10 : v >= 20 ? 1 : 0.5)
const num = (v) => (v === null || v === undefined ? '–' : Number(v) >= 100 ? Math.round(v).toLocaleString() : Number(v).toFixed(1).replace(/\.0$/, ''))

const usage = ref(p.value.meter ? Number(p.value.meter.per_day.toFixed(1)) : 0)
const interval = ref(p.value.meter?.every || 0)
const visits = ref(Math.max(1, Math.round(p.value.services_per_year || 4)))
const changed = computed(() => (p.value.meter ? usage.value !== Number(p.value.meter.per_day.toFixed(1)) || interval.value !== (p.value.meter.every || 0) : visits.value !== Math.max(1, Math.round(p.value.services_per_year || 4))))
function reset() {
  usage.value = p.value.meter ? Number(p.value.meter.per_day.toFixed(1)) : 0
  interval.value = p.value.meter?.every || 0
  visits.value = Math.max(1, Math.round(p.value.services_per_year || 4))
}

// Breakdowns scale with use, and with the time between services to the power 0.8.
const K = 0.8
function model(useDay, every, perYearVisits) {
  const base = p.value
  let services
  let breakdowns
  if (base.meter && base.meter.every) {
    services = (useDay * 365) / every
    breakdowns = base.breakdowns_per_year * (useDay / base.meter.per_day) * (every / base.meter.every) ** K
  } else if (base.meter) {
    services = base.services_per_year || 0
    breakdowns = base.breakdowns_per_year * (useDay / base.meter.per_day)
  } else {
    services = perYearVisits
    const now = base.services_per_year || perYearVisits
    breakdowns = base.breakdowns_per_year * (now / perYearVisits) ** K
  }
  const down = breakdowns * (base.mttr_hours || 0)
  const cost = base.cost_per_service !== null && base.cost_per_breakdown !== null && base.cost_per_service !== undefined
    ? services * base.cost_per_service + breakdowns * base.cost_per_breakdown : null
  return { services, breakdowns, down, cost }
}
const now = computed(() => model(p.value.meter?.per_day || 0, p.value.meter?.every || 0, p.value.services_per_year || 1))
const plan = computed(() => model(usage.value || 0.01, interval.value || 1, visits.value))
const one = (v) => (v === null ? '–' : Number(v).toFixed(1).replace(/\.0$/, ''))
const rows = computed(() => [
  { label: 'Services', now: now.value.services, plan: plan.value.services, fmt: one, better: 'neutral' },
  { label: 'Breakdowns (expected)', now: now.value.breakdowns, plan: plan.value.breakdowns, fmt: one, better: 'lower' },
  { label: 'Hours down (expected)', now: now.value.down, plan: plan.value.down, fmt: (v) => `${one(v)} h`, better: 'lower' },
  ...(props.manager && now.value.cost !== null ? [{ label: 'Cost (parts and labour)', now: now.value.cost, plan: plan.value.cost, fmt: (v) => props.money(v), better: 'lower' }] : []),
])
const delta = (r) => {
  if (!r.now || Math.abs(r.plan - r.now) / r.now < 0.01) return ''
  const pct = Math.round((100 * (r.plan - r.now)) / r.now)
  return `${pct > 0 ? '▲' : '▼'}${Math.abs(pct)}%`
}
const tone = (r) => (r.better === 'neutral' || !delta(r) ? 'text-gray-900' : (r.plan < r.now) === (r.better === 'lower') ? 'text-green-700' : 'text-red-600')
</script>
