<template>
  <div>
    <ul v-if="series.length > 1" class="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600" aria-label="Legend">
      <li v-for="(s, i) in series" :key="s.key" class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm" :style="{ background: `var(--series-${i + 1})` }" />{{ s.label }}</li>
    </ul>
    <div ref="root" class="health-bars relative select-none" :style="{ height: `${height}px` }">
      <svg v-if="width" :width="width" :height="height" role="img" :aria-label="label" class="block" @pointerleave="tip = null">
        <g v-for="v in ticks" :key="v">
          <line :x1="pad.l" :x2="width - pad.r" :y1="y(v)" :y2="y(v)" class="stroke-gray-200" stroke-width="1" />
          <text :x="pad.l - 6" :y="y(v) + 3.5" text-anchor="end" class="fill-gray-500 text-[10px]">{{ short(v) }}</text>
        </g>
        <g v-for="(c, i) in categories" :key="c">
          <!-- stacked segments with a 2px surface gap; the top one has rounded data-end -->
          <template v-for="seg in stack(i)" :key="seg.key">
            <rect :x="bx(i)" :y="seg.y" :width="bw" :height="Math.max(0, seg.h)" :rx="seg.top ? 3 : 0" :fill="`var(--series-${seg.n})`" />
          </template>
          <text :x="bx(i) + bw / 2" :y="height - 4" text-anchor="middle" class="fill-gray-500 text-[10px]">{{ c }}</text>
          <rect :x="bx(i) - gap / 2" :y="pad.t" :width="bw + gap" :height="height - pad.t - pad.b" fill="transparent" @pointerenter="tip = i" @pointerdown="tip = i" />
        </g>
      </svg>
      <div v-if="tip !== null" class="pointer-events-none absolute top-0 z-10 whitespace-nowrap rounded-md border border-gray-200 bg-panel px-2 py-1 text-xs shadow-pop" :style="{ left: `${Math.min(Math.max(bx(tip) - 50, 0), width - 140)}px` }">
        <p class="font-semibold text-gray-900">{{ categories[tip] }}</p>
        <p v-for="s in series" :key="s.key" class="tabular-nums text-gray-700">{{ s.label }}: <b>{{ format(s.values[tip]) }}</b></p>
      </div>
    </div>
  </div>
</template>
<script setup>
// Bars per category (months), one series or stacked series, with hover readout and a legend for 2+ series.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  categories: { type: Array, required: true },
  series: { type: Array, required: true }, // [{ key, label, values: [] }], in fixed colour order
  format: { type: Function, default: (v) => v },
  label: { type: String, default: 'Chart' },
  height: { type: Number, default: 160 },
})
const root = ref(null)
const width = ref(0)
const tip = ref(null)
const pad = { l: 40, r: 6, t: 8, b: 18 }
let observer = null
onMounted(() => {
  observer = new ResizeObserver(([e]) => (width.value = Math.floor(e.contentRect.width)))
  observer.observe(root.value)
})
onBeforeUnmount(() => observer?.disconnect())

const totals = computed(() => props.categories.map((_c, i) => props.series.reduce((s, x) => s + (Number(x.values[i]) || 0), 0)))
const max = computed(() => {
  const m = Math.max(1, ...totals.value)
  const mag = 10 ** Math.floor(Math.log10(m))
  return [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= m)
})
const ticks = computed(() => [0, max.value / 2, max.value])
const slot = computed(() => (width.value - pad.l - pad.r) / props.categories.length)
const gap = computed(() => Math.max(2, slot.value * 0.3))
const bw = computed(() => Math.max(2, slot.value - gap.value))
const bx = (i) => pad.l + i * slot.value + gap.value / 2
const y = (v) => pad.t + (1 - v / max.value) * (props.height - pad.t - pad.b)
function stack(i) {
  let base = 0
  const segs = props.series.map((s, n) => ({ key: s.key, n: n + 1, value: Number(s.values[i]) || 0 })).filter((s) => s.value > 0)
  return segs.map((s, k) => {
    const top = y(base + s.value)
    const h = y(base) - top - (k > 0 ? 2 : 0)
    base += s.value
    return { ...s, y: top, h, top: k === segs.length - 1 }
  })
}
const short = (v) => (v >= 10000 ? `${Math.round(v / 1000)}k` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : Number(v.toFixed(1)))
</script>
