<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <div>
        <h2 class="card-title">Meters</h2>
        <p v-if="alerts" class="mt-0.5 text-xs font-semibold text-red-600">{{ alerts }} past {{ alerts === 1 ? 'its' : 'their' }} limit</p>
      </div>
      <span v-if="manager" class="flex gap-2">
        <button v-if="missing.length && equipment" class="btn btn-secondary btn-sm" :disabled="busy === 'standard'" :title="missing.join(', ')" @click="addStandard"><FeatherIcon name="download" class="h-4 w-4" />Add standard meters ({{ missing.length }})</button>
        <button class="btn btn-secondary btn-sm" @click="edit(null)"><FeatherIcon name="plus" class="h-4 w-4" />Add meter</button>
      </span>
    </div>
    <p v-if="problem" role="alert" class="mx-5 mt-3 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700"><span class="flex-1">{{ problem }}</span><button class="text-red-500" aria-label="Dismiss" @click="problem = ''"><FeatherIcon name="x" class="h-4 w-4" /></button></p>
    <ul v-if="meters.length" class="divide-y divide-gray-100">
      <li v-for="m in meters" :key="m.name" class="px-5 py-4" :class="[!m.active && 'opacity-60', m.alert && 'bg-red-50/40']">
        <div class="flex items-start gap-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="m.alert ? 'bg-red-100 text-red-700' : 'bg-brand-50 text-brand-700'"><FeatherIcon :name="m.meter_type === 'Counter' ? 'clock' : 'activity'" class="h-4 w-4" /></span>
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-3">
              <button class="min-w-0 text-left" :aria-label="`${m.meter_name} history`" @click="openHistory(m)">
                <span class="block truncate text-[15px] font-medium hover:text-brand-700">{{ m.meter_name }}<span v-if="!m.active" class="ml-1.5 text-xs font-normal text-gray-500">(not in use)</span></span>
                <span class="mt-0.5 block text-xs text-gray-500">
                  <template v-if="m.last_reading !== null"><b class="text-[15px] font-semibold tabular-nums" :class="m.alert ? 'text-red-700' : 'text-gray-900'">{{ num(m.last_reading) }}</b> {{ m.unit }} · {{ fromNow(m.last_reading_on) }}<template v-if="m.last_reading_by"> by {{ m.last_reading_by }}</template></template>
                  <template v-else>No readings yet</template>
                </span>
              </button>
              <svg v-if="m.trend.length > 1" viewBox="0 0 100 32" preserveAspectRatio="none" class="h-8 w-20 shrink-0 sm:w-28" aria-hidden="true">
                <polyline :points="spark(m.trend)" fill="none" :stroke="m.alert ? '#dc2626' : '#2563eb'" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" />
              </svg>
              <button v-if="manager" class="btn btn-ghost btn-icon btn-sm -mr-2 shrink-0 text-gray-400" :aria-label="`Edit ${m.meter_name}`" @click="edit(m)"><FeatherIcon name="settings" class="h-4 w-4" /></button>
            </div>
            <ul v-if="m.triggers.length" class="mt-2 flex flex-wrap gap-1.5 text-xs">
              <li v-for="t in m.triggers" :key="t.name" class="inline-flex flex-wrap items-center gap-1 rounded-md px-2 py-1" :class="t.open_job && t.trigger_type !== 'Every' ? 'bg-red-50 text-red-800' : 'bg-gray-100 text-gray-700'">
                <FeatherIcon :name="t.trigger_type === 'Every' ? 'repeat' : 'alert-triangle'" class="h-3 w-3" />{{ t.label }}
                <span v-if="t.trigger_type === 'Every' && t.next_due !== null" class="text-gray-500">· next at {{ num(t.next_due) }}<template v-if="t.due_on"> (~{{ formatDate(t.due_on) }})</template></span>
                <router-link v-if="t.open_job" :to="{ name: 'OpsWorkOrder', params: { name: t.open_job.name } }" class="font-semibold underline">job open</router-link>
              </li>
            </ul>
            <form v-if="m.active && canRecord" class="mt-3 flex items-center gap-2" @submit.prevent="record(m)">
              <label class="sr-only" :for="`reading-${m.name}`">New {{ m.meter_name }} reading</label>
              <div class="relative w-36">
                <input :id="`reading-${m.name}`" v-model="values[m.name]" type="number" step="any" inputmode="decimal" class="input h-9 pr-12 tabular-nums" :placeholder="m.last_reading !== null ? num(m.last_reading) : 'Reading'" :disabled="busy === m.name" />
                <span class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-gray-500">{{ m.unit }}</span>
              </div>
              <button class="btn btn-secondary btn-sm" :disabled="busy === m.name || values[m.name] === '' || values[m.name] === undefined || values[m.name] === null">Record</button>
            </form>
          </div>
        </div>
      </li>
    </ul>
    <p v-else class="px-5 py-4 text-sm text-gray-500">{{ manager ? 'Add meters such as running hours, water produced or TDS. Readings can raise service jobs automatically.' : 'No meters on this machine.' }}</p>

    <Modal v-model="historyOpen" :title="history?.meter.meter_name || 'Meter'" :subtitle="history ? `${history.meter.meter_type === 'Counter' ? 'Counter' : 'Gauge'} · ${history.meter.unit}` : ''" size="lg">
      <div v-if="!history" class="h-40 animate-pulse rounded-xl bg-gray-100" />
      <template v-else>
        <svg v-if="chart.points" viewBox="0 0 300 120" class="h-40 w-full" role="img" :aria-label="`${history.readings.length} readings from ${num(chart.min)} to ${num(chart.max)} ${history.meter.unit}`">
          <line v-for="l in chart.limits" :key="l.y" x1="0" x2="300" :y1="l.y" :y2="l.y" stroke="#f87171" stroke-dasharray="4 3" stroke-width="1" />
          <polyline :points="chart.points" fill="none" stroke="#2563eb" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
          <text x="2" y="10" class="fill-gray-400 text-[9px]">{{ num(chart.max) }}</text>
          <text x="2" y="118" class="fill-gray-400 text-[9px]">{{ num(chart.min) }}</text>
        </svg>
        <ul class="mt-3 divide-y divide-gray-100 text-sm">
          <li v-for="r in history.readings" :key="r.name" class="flex items-start gap-3 py-2.5">
            <span class="w-24 shrink-0 font-semibold tabular-nums">{{ num(r.value) }} <span class="text-xs font-normal text-gray-500">{{ history.meter.unit }}</span></span>
            <span class="min-w-0 flex-1 text-xs text-gray-500">
              {{ formatDate(r.reading_on) }} · {{ r.recorded_by_name }}
              <span v-if="r.reset" class="ml-1 rounded bg-amber-50 px-1 font-semibold text-amber-800">meter replaced</span>
              <router-link v-if="r.work_order" :to="{ name: 'OpsWorkOrder', params: { name: r.work_order } }" class="ml-1 link" @click="historyOpen = false">on {{ r.work_order }}</router-link>
              <router-link v-if="r.triggered_job" :to="{ name: 'OpsWorkOrder', params: { name: r.triggered_job } }" class="ml-1 font-semibold text-red-700 underline" @click="historyOpen = false">raised {{ r.triggered_job }}</router-link>
              <span v-if="r.note" class="block text-gray-600">{{ r.note }}</span>
            </span>
            <button v-if="history.manager" class="btn btn-ghost btn-icon btn-sm -mr-2 text-gray-400 hover:text-red-600" :aria-label="`Delete reading ${num(r.value)}`" :disabled="!!busy" @click="removeReading(r)"><FeatherIcon name="trash-2" class="h-4 w-4" /></button>
          </li>
          <li v-if="!history.readings.length" class="py-3 text-gray-500">No readings yet.</li>
        </ul>
      </template>
    </Modal>
    <MeterForm v-model="formOpen" :meter="editing" :equipment="equipment" :asset="asset" @saved="saved" />
  </div>
</template>
<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import Modal from '@/components/ops/Modal.vue'
import MeterForm from '@/components/ops/MeterForm.vue'
import { api, formatDate, fromNow } from '@/data/ops'

const props = defineProps({
  meters: { type: Array, default: () => [] },
  equipment: String,
  asset: String,
  workOrder: String,
  manager: Boolean,
  canRecord: { type: Boolean, default: true },
  missing: { type: Array, default: () => [] },
})
const emit = defineEmits(['reload'])
const problem = ref('')
const meters = ref([...props.meters])
watch(() => props.meters, (v) => (meters.value = [...v]))
const values = reactive({})
const busy = ref('')
const historyOpen = ref(false)
const history = ref(null)
const formOpen = ref(false)
const editing = ref(null)
const alerts = computed(() => meters.value.filter((m) => m.alert).length)
const num = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })

function spark(trend) {
  const vals = trend.map((t) => Number(t.value))
  const min = Math.min(...vals)
  const span = Math.max(...vals) - min || 1
  return vals.map((v, i) => `${(100 * i) / (vals.length - 1)},${30 - (28 * (v - min)) / span}`).join(' ')
}
const chart = computed(() => {
  const rows = [...(history.value?.readings || [])].reverse()
  if (rows.length < 2) return {}
  const limits = (history.value.meter.triggers || []).filter((t) => t.trigger_type !== 'Every').map((t) => Number(t.value))
  const vals = rows.map((r) => Number(r.value))
  const min = Math.min(...vals, ...limits)
  const max = Math.max(...vals, ...limits)
  const span = max - min || 1
  const y = (v) => 112 - (100 * (v - min)) / span
  return { min, max, points: vals.map((v, i) => `${(300 * i) / (vals.length - 1)},${y(v)}`).join(' '), limits: limits.map((l) => ({ y: y(l) })) }
})

const fail = (message) => (problem.value = message)
async function record(m, reset = false) {
  problem.value = ''
  const value = Number(values[m.name])
  if (!reset && m.meter_type === 'Counter' && m.last_reading !== null && value < m.last_reading) {
    if (!props.manager) return fail(`${m.meter_name} only goes up: the last reading was ${num(m.last_reading)} ${m.unit}. If the meter was replaced, ask a manager to record it.`)
    if (!window.confirm(`${num(value)} is lower than the last reading (${num(m.last_reading)}). Record it as a replaced or reset meter?`)) return
    reset = true
  }
  busy.value = m.name
  try {
    const args = { meter: m.name, value, work_order: props.workOrder || null, reset: reset ? 1 : 0 }
    let r = await api('projectit.meters.record_reading', args)
    if (r.needs_confirm) {
      // An unusual reading: check with the person before it is saved.
      if (!window.confirm(`${r.warning}\n\nSave it anyway?`)) return
      r = await api('projectit.meters.record_reading', { ...args, confirm: 1 })
    }
    meters.value = meters.value.map((x) => (x.name === m.name ? r.meter : x))
    values[m.name] = ''
    if (r.raised.length) {
      toast({ title: `Job raised: ${r.raised[0].subject}`, icon: 'alert-triangle', iconClasses: 'text-amber-600', position: 'top-center' })
      emit('reload')
    } else {
      toast({ title: `${m.meter_name} recorded`, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    }
  } catch (e) {
    fail(e.message)
  } finally {
    busy.value = ''
  }
}
async function openHistory(m) {
  history.value = null
  historyOpen.value = true
  try {
    history.value = await api('projectit.meters.get_meter', { name: m.name })
  } catch (e) {
    historyOpen.value = false
    fail(e.message)
  }
}
async function removeReading(r) {
  if (!window.confirm(`Delete the reading ${num(r.value)} ${history.value.meter.unit}? Jobs it raised stay open.`)) return
  busy.value = r.name
  try {
    history.value = await api('projectit.meters.delete_reading', { name: r.name })
    meters.value = meters.value.map((x) => (x.name === history.value.meter.name ? history.value.meter : x))
  } catch (e) {
    fail(e.message)
  } finally {
    busy.value = ''
  }
}
async function addStandard() {
  busy.value = 'standard'
  problem.value = ''
  try {
    meters.value = (await api('projectit.meters.add_standard_meters', { equipment: props.equipment })).meters
    emit('reload')
  } catch (e) {
    fail(e.message)
  } finally {
    busy.value = ''
  }
}
function edit(m) {
  editing.value = m
  formOpen.value = true
}
function saved(m) {
  const i = meters.value.findIndex((x) => x.name === m.name)
  if (i >= 0) meters.value.splice(i, 1, m)
  else meters.value.push(m)
}
</script>
