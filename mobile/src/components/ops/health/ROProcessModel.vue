<template>
  <div class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <h2 class="card-title">RO process model</h2>
      <button v-if="changed" class="text-xs font-medium text-brand-600 hover:underline" @click="reset">Back to this machine's numbers</button>
    </div>
    <div class="grid gap-6 p-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <!-- Inputs -->
      <div class="space-y-3">
        <div v-for="f in FIELDS" :key="f.key">
          <label class="label flex items-baseline justify-between gap-2" :for="`ro-${f.key}`">
            <span>{{ f.label }}</span>
            <span v-if="source[f.key]" class="truncate text-[11px] font-normal text-brand-600" :title="source[f.key]">from {{ source[f.key] }}</span>
          </label>
          <div class="flex items-center gap-2">
            <input :id="`ro-${f.key}`" v-model.number="input[f.key]" type="number" :min="f.min" :max="f.max" :step="f.step" class="input h-9" />
            <span class="w-14 shrink-0 text-xs text-gray-500">{{ f.unit }}</span>
          </div>
        </div>
      </div>

      <div class="min-w-0 space-y-5">
        <!-- Today -->
        <div>
          <p class="section-label mb-2">The plant today</p>
          <dl class="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <div v-for="s in today" :key="s.label" class="rounded-lg bg-gray-50 px-3 py-2">
              <dt class="text-[11px] text-gray-500">{{ s.label }}</dt>
              <dd class="text-base font-semibold tabular-nums" :class="s.tone || 'text-gray-900'">{{ s.value }}</dd>
            </div>
          </dl>
          <p v-if="calc.ndp <= 0" class="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">The feed pressure is below the osmotic pressure: the plant cannot make water at this recovery. Lower the recovery or raise the pressure.</p>
        </div>

        <!-- Projection -->
        <div>
          <p class="section-label mb-2">The next {{ HORIZON / 12 }} years as the membranes age</p>
          <ul class="mb-3 space-y-1.5 text-sm">
            <li v-for="e in events" :key="e.text" class="flex items-start gap-2"><FeatherIcon :name="e.icon" class="mt-0.5 h-4 w-4 shrink-0" :class="e.tone" /><span>{{ e.text }}</span></li>
          </ul>
          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <p class="mb-1 text-xs font-medium text-gray-600">Permeate TDS (mg/L)</p>
              <LineChart :points="tdsLine" :limits="[{ type: 'Above', value: input.target }]" unit="mg/L" label="Projected permeate TDS" :height="170" />
            </div>
            <div>
              <p class="mb-1 text-xs font-medium text-gray-600">Product flow (L/h)</p>
              <LineChart :points="flowLine" :limits="[{ type: 'Below', value: cleanAt }]" unit="L/h" label="Projected product flow" :height="170" />
            </div>
          </div>
        </div>
        <p class="text-xs leading-relaxed text-gray-500">
          A rule-of-thumb model for planning, not a design tool: osmotic pressure about 0.7 bar per 1,000 mg/L, log-mean concentration along the membranes, a 0.7 bar pressure drop, the standard temperature correction, flow falling by the fouling rate each year and salt passage rising by its rate. Use the membrane maker's projection software for design.
        </p>
      </div>
    </div>
  </div>
</template>
<script setup>
import { reactive, computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import LineChart from '@/components/ops/charts/LineChart.vue'

const props = defineProps({ process: { type: Object, required: true }, meters: { type: Array, default: () => [] } })
const HORIZON = 36 // months
const OSMOTIC = 0.0007 // bar per mg/L, NaCl-like water
const DP = 0.7 // pressure drop along the vessels, bar
const FIELDS = [
  { key: 'capacity', label: 'Product flow', unit: 'L/h', min: 10, max: 100000, step: 10 },
  { key: 'recovery', label: 'Recovery', unit: '%', min: 20, max: 90, step: 1 },
  { key: 'feedTds', label: 'Feed TDS', unit: 'mg/L', min: 50, max: 45000, step: 10 },
  { key: 'pressure', label: 'Feed pressure', unit: 'bar', min: 1, max: 80, step: 0.1 },
  { key: 'temperature', label: 'Water temperature', unit: '°C', min: 5, max: 45, step: 0.5 },
  { key: 'rejection', label: 'Salt rejection', unit: '%', min: 80, max: 99.9, step: 0.1 },
  { key: 'fouling', label: 'Flow lost to fouling', unit: '% a year', min: 0, max: 60, step: 1 },
  { key: 'passage', label: 'Salt passage rise', unit: '% a year', min: 0, max: 100, step: 1 },
  { key: 'target', label: 'Permeate TDS target', unit: 'mg/L', min: 1, max: 1000, step: 1 },
  { key: 'clean', label: 'Clean when flow drops', unit: '%', min: 5, max: 40, step: 1 },
]

const lmcf = (r) => Math.log(1 / (1 - r)) / r // log-mean concentration factor along the membranes
const tcf = (t) => Math.exp(2640 * (1 / 298.15 - 1 / (273.15 + t)))

// Start from the machine's own readings and trends where it has them.
function start() {
  const r = props.process.readings || {}
  const v = { capacity: props.process.capacity_lph, recovery: 75, feedTds: 800, pressure: 12, temperature: 25, rejection: 97.5, fouling: 8, passage: 12, target: 50, clean: 15 }
  const source = {}
  const use = (key, value, from) => {
    v[key] = value
    source[key] = from
  }
  if (r.permeate_flow) use('capacity', r.permeate_flow.value, r.permeate_flow.meter)
  else if (props.process.from_name) source.capacity = 'the machine name'
  if (r.recovery) use('recovery', r.recovery.value, r.recovery.meter)
  if (r.feed_tds) use('feedTds', r.feed_tds.value, r.feed_tds.meter)
  if (r.pressure) use('pressure', r.pressure.value, r.pressure.meter)
  if (r.temperature) use('temperature', r.temperature.value, r.temperature.meter)
  if (r.feed_tds && r.permeate_tds) {
    // Salt rejection the plant actually achieves, from its own feed and permeate readings.
    const rejection = 100 * (1 - r.permeate_tds.value / (r.feed_tds.value * lmcf(v.recovery / 100)))
    if (rejection > 80 && rejection < 99.95) use('rejection', Number(rejection.toFixed(1)), `${r.permeate_tds.meter} vs ${r.feed_tds.meter}`)
  }
  const meter = (re) => props.meters.find((m) => re.test(m.meter_name) && m.forecast && m.last)
  const flow = meter(/product|permeate.*flow|flow/i)
  if (flow && flow.forecast.rate_per_day < 0) {
    const perYear = (-flow.forecast.rate_per_day * 365 * 100) / flow.last
    if (perYear > 0 && perYear < 60) use('fouling', Math.round(perYear), `${flow.meter_name} trend`)
  }
  const tds = meter(/permeate.*tds|product.*tds/i)
  if (tds) {
    const limit = tds.limits?.find((l) => l.type === 'Above')
    if (limit) use('target', limit.value, `${tds.meter_name} limit`)
    if (tds.forecast.rate_per_day > 0) {
      const perYear = (tds.forecast.rate_per_day * 365 * 100) / tds.last
      if (perYear > 0 && perYear < 100) use('passage', Math.round(perYear), `${tds.meter_name} trend`)
    }
  }
  return { v, source }
}
const first = start()
const input = reactive({ ...first.v })
const source = reactive({ ...first.source })
const changed = computed(() => Object.keys(first.v).some((k) => input[k] !== first.v[k]))
const reset = () => Object.assign(input, first.v)

const calc = computed(() => {
  const r = Math.min(Math.max(input.recovery, 1), 95) / 100
  const qp = input.capacity
  const qf = qp / r
  const cf = lmcf(r)
  const cp = input.feedTds * cf * (1 - input.rejection / 100)
  const cc = (input.feedTds - r * cp) / (1 - r)
  const piFeed = OSMOTIC * input.feedTds * cf
  const ndp = input.pressure - DP / 2 - piFeed + OSMOTIC * cp
  return { r, qp, qf, qc: qf - qp, cp, cc, piFeed, ndp }
})
const n0 = (v) => Math.round(v).toLocaleString()
const today = computed(() => [
  { label: 'Feed flow', value: `${n0(calc.value.qf)} L/h` },
  { label: 'Concentrate (reject)', value: `${n0(calc.value.qc)} L/h` },
  { label: 'Permeate TDS', value: `${calc.value.cp.toFixed(1)} mg/L`, tone: calc.value.cp > input.target ? 'text-red-600' : 'text-green-700' },
  { label: 'Concentrate TDS', value: `${n0(calc.value.cc)} mg/L` },
  { label: 'Osmotic pressure (avg)', value: `${calc.value.piFeed.toFixed(1)} bar` },
  { label: 'Net driving pressure', value: `${calc.value.ndp.toFixed(1)} bar`, tone: calc.value.ndp <= 1 ? 'text-red-600' : '' },
])

// Month by month: flow falls with fouling; salt passage rises, and less flow carries the same salt (higher TDS).
const projection = computed(() => {
  const out = []
  const now = new Date()
  for (let m = 0; m <= HORIZON; m++) {
    const flowFactor = (1 - input.fouling / 100) ** (m / 12)
    const passage = (1 - input.rejection / 100) * (1 + input.passage / 100) ** (m / 12)
    const on = new Date(now.getFullYear(), now.getMonth() + m, now.getDate())
    out.push({ on: on.toISOString().slice(0, 10), flow: input.capacity * flowFactor, tds: input.feedTds * lmcf(calc.value.r) * passage / flowFactor })
  }
  return out
})
const tdsLine = computed(() => projection.value.map((p) => ({ on: p.on, value: Number(p.tds.toFixed(1)) })))
const flowLine = computed(() => projection.value.map((p) => ({ on: p.on, value: Math.round(p.flow) })))
const cleanAt = computed(() => Math.round(input.capacity * (1 - input.clean / 100)))
const months = (pred) => projection.value.findIndex(pred)
const events = computed(() => {
  const list = []
  const clean = months((p) => p.flow < cleanAt.value)
  const over = months((p) => p.tds > input.target)
  const when = (m) => (m === 0 ? 'now' : m < 12 ? `in about ${m} month${m === 1 ? '' : 's'}` : `in about ${(m / 12).toFixed(1).replace(/\.0$/, '')} years`)
  list.push(clean >= 0 ? { icon: 'droplet', tone: 'text-amber-600', text: `Clean the membranes (CIP) ${when(clean)}, when product flow falls ${input.clean}% to ${n0(cleanAt.value)} L/h.` }
    : { icon: 'check-circle', tone: 'text-green-600', text: `Product flow stays within ${input.clean}% for the next ${HORIZON / 12} years.` })
  list.push(over >= 0 ? { icon: 'alert-triangle', tone: 'text-red-600', text: `Permeate TDS passes the ${input.target} mg/L target ${when(over)}. If cleaning does not bring it back, plan new membranes.` }
    : { icon: 'check-circle', tone: 'text-green-600', text: `Permeate stays under ${input.target} mg/L for the next ${HORIZON / 12} years.` })
  return list
})
</script>
