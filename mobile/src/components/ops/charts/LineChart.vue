<template>
  <div ref="root" class="health-chart relative select-none" :style="{ height: `${height}px` }">
    <svg v-if="width" :width="width" :height="height" role="img" :aria-label="label" class="block overflow-visible">
      <!-- grid and y axis -->
      <g v-for="t in yTicks" :key="`y${t}`">
        <line :x1="pad.l" :x2="width - pad.r" :y1="y(t)" :y2="y(t)" class="stroke-gray-200" stroke-width="1" />
        <text :x="pad.l - 6" :y="y(t) + 3.5" text-anchor="end" class="fill-gray-500 text-[10px]">{{ fmt(t) }}</text>
      </g>
      <text v-for="t in xTicks" :key="`x${t.at}`" :x="x(t.at)" :y="height - 4" text-anchor="middle" class="fill-gray-500 text-[10px]">{{ t.label }}</text>
      <!-- limits: a status reference, labelled -->
      <g v-for="l in limits" :key="`${l.type}${l.value}`">
        <line :x1="pad.l" :x2="width - pad.r" :y1="y(l.value)" :y2="y(l.value)" class="stroke-red-500" stroke-width="1.5" stroke-dasharray="5 4" />
        <text :x="width - pad.r" :y="y(l.value) + (l.type === 'Below' ? 12 : -4)" text-anchor="end" class="fill-red-600 text-[10px] font-semibold">{{ l.type === 'Below' ? 'Min' : 'Max' }} {{ fmt(l.value) }}</text>
      </g>
      <line v-if="target !== null && target !== undefined" :x1="pad.l" :x2="width - pad.r" :y1="y(target)" :y2="y(target)" class="stroke-gray-400" stroke-width="1" stroke-dasharray="2 3" />
      <!-- readings left out of the trend -->
      <g v-for="e in excluded" :key="`ex${e.on}`">
        <circle :cx="x(t(e.on))" :cy="edge(e.value)" r="5" fill="var(--chart-surface)" class="stroke-red-500" stroke-width="2" />
        <text v-if="edge(e.value) !== y(Number(e.value))" :x="x(t(e.on)) + 8" :y="edge(e.value) + 4" class="fill-red-600 text-[10px] font-semibold">{{ fmt(e.value) }}</text>
      </g>
      <!-- the readings, then the projection -->
      <path :d="path(points)" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <path v-if="forecast?.length" :d="path(forecast)" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-dasharray="6 5" stroke-linecap="round" opacity="0.8" />
      <circle v-if="forecast?.length" :cx="x(t(forecast[forecast.length - 1].on))" :cy="y(forecast[forecast.length - 1].value)" r="4" fill="var(--chart-surface)" stroke="var(--series-1)" stroke-width="2" />
      <circle v-if="points.length" :cx="x(t(points[points.length - 1].on))" :cy="y(points[points.length - 1].value)" r="4" fill="var(--series-1)" stroke="var(--chart-surface)" stroke-width="2" />
      <!-- hover: a transparent layer over the plot, larger than the marks -->
      <rect :x="pad.l" :y="0" :width="Math.max(0, width - pad.l - pad.r)" :height="height" fill="transparent" @pointermove="hover" @pointerdown="hover" @pointerleave="tip = null" />
      <g v-if="tip" class="pointer-events-none">
        <line :x1="tip.x" :x2="tip.x" :y1="pad.t" :y2="height - pad.b" class="stroke-gray-400" stroke-width="1" />
        <circle :cx="tip.x" :cy="tip.y" r="5" fill="var(--series-1)" stroke="var(--chart-surface)" stroke-width="2" />
      </g>
    </svg>
    <div v-if="tip" class="pointer-events-none absolute z-10 whitespace-nowrap rounded-md border border-gray-200 bg-panel px-2 py-1 text-xs shadow-pop" :style="{ left: `${Math.min(Math.max(tip.x - 60, 0), width - 130)}px`, top: '0px' }">
      <span class="font-semibold tabular-nums text-gray-900">{{ fmt(tip.value) }} {{ unit }}</span><span class="ml-1.5 text-gray-500">{{ tip.when }}</span><span v-if="tip.projected" class="ml-1 text-gray-500">(projected)</span>
    </div>
    <p v-if="!points.length" class="absolute inset-0 flex items-center justify-center text-sm text-gray-400">No readings yet</p>
  </div>
</template>
<script setup>
// A single series over time (readings), with an optional dashed projection, limit lines and hover readout.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  points: { type: Array, default: () => [] }, // [{ on, value }]
  forecast: { type: Array, default: null }, // [{ on, value }], drawn dashed
  excluded: { type: Array, default: () => [] }, // [{ on, value }]: readings left out of the trend, drawn as rings
  limits: { type: Array, default: () => [] }, // [{ type: 'Above' | 'Below', value }]
  target: { type: Number, default: null }, // a quiet reference line (e.g. next service)
  unit: { type: String, default: '' },
  label: { type: String, default: 'Chart' },
  height: { type: Number, default: 180 },
})
const root = ref(null)
const width = ref(0)
const tip = ref(null)
const pad = { l: 44, r: 10, t: 12, b: 20 }
let observer = null
onMounted(() => {
  observer = new ResizeObserver(([e]) => (width.value = Math.floor(e.contentRect.width)))
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const t = (on) => new Date(String(on).replace(' ', 'T')).getTime()
const all = computed(() => [...props.points, ...(props.forecast || [])])
const xDomain = computed(() => {
  const ts = all.value.map((p) => t(p.on))
  const lo = Math.min(...ts)
  const hi = Math.max(...ts)
  return ts.length ? [lo, hi > lo ? hi : lo + 86400000] : [0, 1]
})
const yDomain = computed(() => {
  // Readings left out of the trend do not stretch the scale: a typo of 410 must not flatten readings around 40.
  const vs = [...all.value.map((p) => Number(p.value)), ...props.limits.map((l) => Number(l.value))]
  if (props.target !== null && props.target !== undefined) vs.push(Number(props.target))
  if (!vs.length) return [0, 1]
  let lo = Math.min(...vs)
  let hi = Math.max(...vs)
  if (hi === lo) [lo, hi] = [lo - 1, hi + 1]
  const room = (hi - lo) * 0.12
  return [lo - room, hi + room]
})
const x = (ms) => pad.l + ((ms - xDomain.value[0]) / (xDomain.value[1] - xDomain.value[0])) * (width.value - pad.l - pad.r)
const y = (v) => pad.t + (1 - (v - yDomain.value[0]) / (yDomain.value[1] - yDomain.value[0])) * (props.height - pad.t - pad.b)
// A left-out reading beyond the scale sits on the plot's edge, with its value written beside it.
const edge = (v) => Math.min(Math.max(y(Number(v)), pad.t), props.height - pad.b)
const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(t(p.on)).toFixed(1)},${y(Number(p.value)).toFixed(1)}`).join(' ')

function niceStep(span, count) {
  const raw = span / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw
}
const yTicks = computed(() => {
  const [lo, hi] = yDomain.value
  const step = niceStep(hi - lo, 4)
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(Number(v.toFixed(6)))
  return out
})
const xTicks = computed(() => {
  const [lo, hi] = xDomain.value
  const days = (hi - lo) / 86400000
  const out = []
  const d = new Date(lo)
  if (days > 75) {
    // Month starts, at most six of them.
    d.setDate(1)
    d.setMonth(d.getMonth() + 1)
    const every = Math.max(1, Math.ceil(days / 30 / 6))
    for (let i = 0; d.getTime() <= hi; i++, d.setMonth(d.getMonth() + 1)) {
      if (i % every === 0) out.push({ at: d.getTime(), label: d.toLocaleDateString(undefined, { month: 'short' }) })
    }
  } else {
    const every = Math.max(1, Math.ceil(days / 6))
    for (let at = lo; at <= hi; at += every * 86400000) out.push({ at, label: new Date(at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) })
  }
  return out
})
const fmt = (v) => {
  const n = Number(v)
  const a = Math.abs(n)
  return a >= 10000 ? `${(n / 1000).toFixed(a >= 100000 ? 0 : 1)}k` : a >= 100 ? n.toFixed(0) : a >= 10 ? n.toFixed(1).replace(/\.0$/, '') : n.toFixed(2).replace(/0$/, '').replace(/\.0$/, '')
}

function hover(e) {
  const rect = root.value.getBoundingClientRect()
  const px = e.clientX - rect.left
  const pts = [...props.points.map((p) => ({ ...p, projected: false })), ...(props.forecast || []).slice(1).map((p) => ({ ...p, projected: true }))]
  if (!pts.length) return
  const near = pts.reduce((best, p) => (Math.abs(x(t(p.on)) - px) < Math.abs(x(t(best.on)) - px) ? p : best))
  tip.value = { x: x(t(near.on)), y: y(Number(near.value)), value: near.value, projected: near.projected,
    when: new Date(t(near.on)).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) }
}
</script>
<style>
/* Chart colours (validated for both surfaces; see the data-viz palette). */
.health-chart, .health-bars { --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --chart-surface: #ffffff; }
html.techy-dark .health-chart, html.techy-dark .health-bars { --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --chart-surface: #163b65; }
@media print { html.techy-dark .health-chart, html.techy-dark .health-bars { --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --chart-surface: #ffffff; } }
</style>
