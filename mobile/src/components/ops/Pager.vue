<template>
  <nav v-if="total > sizes[0] || start > 0" class="flex flex-wrap items-center justify-between gap-3 text-sm" :aria-label="label">
    <p class="text-gray-600" aria-live="polite">
      Showing <b class="font-semibold tabular-nums text-gray-900">{{ from }}–{{ to }}</b> of <b class="font-semibold tabular-nums text-gray-900">{{ total.toLocaleString() }}</b>
    </p>
    <div class="flex flex-wrap items-center gap-2">
      <label class="flex items-center gap-1.5 text-xs text-gray-500">
        <span class="hidden sm:inline">Per page</span>
        <select :value="pageLength" class="input h-8 w-auto py-0 pl-2 pr-7 text-xs" aria-label="Rows per page" :disabled="busy" @change="emit('update:pageLength', Number($event.target.value))">
          <option v-for="n in sizes" :key="n" :value="n">{{ n }}</option>
        </select>
      </label>
      <div class="flex items-center gap-1">
        <button class="btn btn-secondary btn-sm btn-icon" aria-label="Previous page" :disabled="busy || page <= 1" @click="go(page - 1)"><FeatherIcon name="chevron-left" class="h-4 w-4" /></button>
        <template v-for="(p, i) in pages" :key="i">
          <span v-if="p === '…'" class="px-1 text-gray-400" aria-hidden="true">…</span>
          <button v-else class="btn btn-sm min-w-[2rem] px-2 tabular-nums" :class="p === page ? 'btn-primary' : 'btn-ghost'" :aria-current="p === page ? 'page' : undefined" :aria-label="`Page ${p}`" :disabled="busy" @click="go(p)">{{ p }}</button>
        </template>
        <button class="btn btn-secondary btn-sm btn-icon" aria-label="Next page" :disabled="busy || page >= last" @click="go(page + 1)"><FeatherIcon name="chevron-right" class="h-4 w-4" /></button>
      </div>
    </div>
  </nav>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({
  total: { type: Number, default: 0 },
  start: { type: Number, default: 0 },
  pageLength: { type: Number, default: 25 },
  busy: Boolean,
  label: { type: String, default: 'Pages' },
  sizes: { type: Array, default: () => [25, 50, 100] },
})
const emit = defineEmits(['change', 'update:pageLength'])
const page = computed(() => Math.floor(props.start / props.pageLength) + 1)
const last = computed(() => Math.max(1, Math.ceil(props.total / props.pageLength)))
const from = computed(() => (props.total ? props.start + 1 : 0))
const to = computed(() => Math.min(props.total, props.start + props.pageLength))
// First, last and the pages around the current one; gaps become "…".
const pages = computed(() => {
  const keep = new Set([1, last.value, page.value - 1, page.value, page.value + 1].filter((p) => p >= 1 && p <= last.value))
  const out = []
  for (const p of [...keep].sort((a, b) => a - b)) {
    if (out.length && p - out[out.length - 1] > 1) out.push('…')
    out.push(p)
  }
  return out
})
function go(p) {
  emit('change', (Math.min(Math.max(p, 1), last.value) - 1) * props.pageLength)
}
</script>
