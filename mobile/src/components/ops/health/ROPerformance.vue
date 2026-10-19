<template>
  <div class="card overflow-hidden">
    <div class="card-header flex-wrap gap-2">
      <h2 class="card-title">RO performance (normalised)</h2>
      <span class="text-xs text-gray-500">Corrected for temperature and pressure, against the baseline log</span>
    </div>

    <!-- Not set up yet -->
    <div v-if="ro.missing.length" class="space-y-3 px-5 py-4 text-sm">
      <p class="text-gray-700">To follow the membranes properly, this machine needs these readings at every visit: <b>{{ ro.missing.join(', ') }}</b>.</p>
      <div v-if="manager" class="flex flex-wrap items-center gap-2">
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="setup"><FeatherIcon name="plus" class="h-4 w-4" />{{ busy ? 'Setting up…' : 'Set up RO logging' }}</button>
        <span class="text-xs text-gray-500">Adds the missing meters and the <b>RO log sheet</b> procedure. Attach the procedure to this machine's service visits.</span>
      </div>
      <p v-else class="text-xs text-gray-500">A manager can set up RO logging for this machine.</p>
    </div>

    <p v-if="!ro.points.length" class="px-5 py-4 text-sm text-gray-500">{{ ro.problem || 'Record a full RO log (the RO log sheet on a visit) to see normalised performance.' }}</p>

    <template v-else>
      <!-- The call: clean or not -->
      <div class="flex flex-wrap items-start gap-3 px-5 py-3" :class="ro.breaches.length ? 'bg-red-50' : 'bg-green-50'" role="status">
        <FeatherIcon :name="ro.breaches.length ? 'alert-triangle' : 'check-circle'" class="mt-0.5 h-5 w-5 shrink-0" :class="ro.breaches.length ? 'text-red-600' : 'text-green-600'" />
        <div class="min-w-0 flex-1 text-sm">
          <p class="font-semibold" :class="ro.breaches.length ? 'text-red-800' : 'text-green-800'">{{ ro.breaches.length ? 'Clean the membranes (CIP)' : 'Within the cleaning limits' }}</p>
          <p class="text-gray-700">
            <template v-if="ro.breaches.length">The latest log ({{ formatDate(ro.latest.on) }}): {{ ro.breaches.join('; ') }}.</template>
            <template v-else>Latest log {{ formatDate(ro.latest.on) }}: flow {{ signed(ro.latest.flow) }}, salt passage {{ ro.latest.salt === null ? '–' : signed(ro.latest.salt) }}, pressure drop {{ ro.latest.dp === null ? '–' : signed(ro.latest.dp) }}.</template>
          </p>
        </div>
        <router-link v-if="ro.cip_job" :to="{ name: 'OpsWorkOrder', params: { name: ro.cip_job.name } }" class="btn btn-secondary btn-sm shrink-0"><FeatherIcon name="tool" class="h-4 w-4" />Cleaning job</router-link>
      </div>

      <div class="grid gap-4 p-4 md:grid-cols-3">
        <div v-for="c in charts" :key="c.key">
          <p class="mb-1 flex items-baseline justify-between text-xs"><span class="font-medium text-gray-700">{{ c.label }}</span><span class="tabular-nums font-semibold" :class="c.tone">{{ c.now }}</span></p>
          <LineChart :points="c.points" :limits="c.limits" unit="%" :label="`${c.label}, % change from the baseline`" :height="150" />
          <p class="mt-1 text-[11px] text-gray-500">{{ c.help }}</p>
        </div>
      </div>

      <div class="space-y-2 border-t border-gray-100 px-5 py-3 text-xs text-gray-600">
        <p class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>Compared with the log of <b>{{ formatDate(ro.baseline.on) }}</b>{{ ro.baseline.chosen ? ' (chosen by a manager)' : ' (the first full log)' }}.</span>
          <button v-if="manager" class="font-medium text-brand-600 hover:underline" :disabled="busy" @click="rebase">Use the latest log as the baseline</button>
        </p>
        <p v-if="ro.assumed.length" class="text-amber-800"><FeatherIcon name="info" class="mr-1 inline h-3.5 w-3.5" />Not recorded, so assumed: {{ ro.assumed.map(describe).join(', ') }}. Record them for a reliable result.</p>
        <p class="text-gray-500">Each log is the readings taken on one job (or one day). Cleaning limits: flow down {{ ro.rules.cip_flow_drop }}%, salt passage up {{ ro.rules.cip_salt_rise }}%, pressure drop up {{ ro.rules.cip_dp_rise }}% (Techy Ops Settings). Breaking one raises a cleaning job.</p>
      </div>
    </template>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import LineChart from '@/components/ops/charts/LineChart.vue'
import { api, formatDate } from '@/data/ops'

const props = defineProps({ ro: { type: Object, required: true }, equipment: { type: String, required: true }, manager: Boolean })
const emit = defineEmits(['reload'])
const busy = ref(false)
const signed = (v) => `${v > 0 ? '+' : ''}${Number(v).toFixed(1)}%`
const describe = (a) => ({ temperature: 'water temperature (25 °C)', 'concentrate pressure': 'concentrate pressure (feed minus 0.7 bar)', 'concentrate flow': 'concentrate flow (75% recovery)' })[a] || a
const series = (key) => props.ro.points.filter((p) => p[key] !== null && p[key] !== undefined).map((p) => ({ on: p.on, value: p[key] }))
const charts = computed(() => {
  const r = props.ro.rules
  const l = props.ro.latest
  return [
    { key: 'flow', label: 'Permeate flow', points: series('flow'), limits: [{ type: 'Below', value: -r.cip_flow_drop }], now: signed(l.flow), tone: l.flow <= -r.cip_flow_drop ? 'text-red-600' : 'text-gray-900', help: 'Falls as the membranes foul or scale.' },
    { key: 'salt', label: 'Salt passage', points: series('salt'), limits: [{ type: 'Above', value: r.cip_salt_rise }], now: l.salt === null ? '–' : signed(l.salt), tone: l.salt >= r.cip_salt_rise ? 'text-red-600' : 'text-gray-900', help: 'Rises with scaling, damage or worn membranes.' },
    { key: 'dp', label: 'Pressure drop', points: series('dp'), limits: [{ type: 'Above', value: r.cip_dp_rise }], now: l.dp === null ? '–' : signed(l.dp), tone: l.dp >= r.cip_dp_rise ? 'text-red-600' : 'text-gray-900', help: 'Rises as the feed channels clog.' },
  ]
})

async function setup() {
  busy.value = true
  try {
    const r = await api('projectit.ro.setup', { equipment: props.equipment })
    toast({ title: r.added.length ? `Added: ${r.added.join(', ')}` : 'RO logging is set up', icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    emit('reload')
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  } finally {
    busy.value = false
  }
}
async function rebase() {
  if (!window.confirm('Compare from the latest log from now on? Do this after new membranes are fitted.')) return
  busy.value = true
  try {
    await api('projectit.ro.set_baseline', { equipment: props.equipment })
    emit('reload')
  } catch (e) {
    toast({ title: e.message, icon: 'alert-circle', iconClasses: 'text-red-600', position: 'top-center' })
  } finally {
    busy.value = false
  }
}
</script>
