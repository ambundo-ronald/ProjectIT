<template>
  <Modal :model-value="modelValue" title="Add a part" subtitle="Your list goes to a manager or stock manager for approval." size="md" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="!item" class="space-y-3">
      <div class="relative">
        <FeatherIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input ref="searchBox" v-model="query" type="search" class="input pl-9" placeholder="Search parts by name or code" aria-label="Search parts" autocomplete="off" @input="search" />
      </div>
      <ul class="max-h-80 divide-y divide-gray-100 overflow-y-auto rounded-lg border border-gray-200" aria-label="Parts">
        <li v-if="busy && !results.length" class="space-y-2 p-3"><div v-for="i in 3" :key="i" class="h-8 animate-pulse rounded bg-gray-100" /></li>
        <li v-else-if="!results.length" class="p-4 text-center text-sm text-gray-500">{{ query ? 'No stock items match.' : 'Type to search.' }}</li>
        <li v-for="r in results" :key="r.name">
          <button type="button" class="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-50" @click="pick(r)">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500"><FeatherIcon name="package" class="h-4 w-4" /></span>
            <span class="min-w-0 flex-1"><span class="block truncate text-sm font-medium">{{ r.item_name }}</span><span class="block truncate font-mono text-[11px] text-gray-500">{{ r.name }}</span></span>
            <span class="shrink-0 text-xs font-medium" :class="r.in_stock ? 'text-green-700' : 'text-gray-400'">{{ r.in_stock ? `${fmt(r.in_stock)} ${r.stock_uom} in stock` : 'Out of stock' }}</span>
          </button>
        </li>
      </ul>
    </div>

    <form v-else id="part-form" class="space-y-4" @submit.prevent="add">
      <div class="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-gray-500 ring-1 ring-gray-200"><FeatherIcon name="package" class="h-4 w-4" /></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-semibold">{{ item.item_name }}</span><span class="font-mono text-xs text-gray-500">{{ item.name }}</span></span>
        <button type="button" class="btn btn-ghost btn-sm" @click="item = null">Change</button>
      </div>
      <fieldset>
        <legend class="label">Taken from</legend>
        <div class="space-y-2">
          <label v-for="w in warehouses" :key="w.warehouse" class="flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm" :class="warehouse === w.warehouse ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:bg-gray-50'">
            <input v-model="warehouse" type="radio" :value="w.warehouse" class="text-brand-600" />
            <span class="min-w-0 flex-1 truncate font-medium">{{ w.warehouse }}</span>
            <span class="text-xs" :class="w.actual_qty > 0 ? 'text-green-700' : 'text-red-600'">{{ fmt(w.actual_qty) }} {{ item.stock_uom }}</span>
          </label>
          <p v-if="!warehouses.length" class="text-sm text-red-600">This part is out of stock everywhere.</p>
        </div>
      </fieldset>
      <div>
        <label class="label" for="part-qty">Quantity</label>
        <div class="flex items-center gap-2">
          <button type="button" class="btn btn-secondary btn-icon" aria-label="Less" :disabled="qty <= 1" @click="qty = Math.max(1, qty - 1)"><FeatherIcon name="minus" class="h-4 w-4" /></button>
          <input id="part-qty" v-model.number="qty" type="number" min="0.001" step="any" inputmode="decimal" class="input w-24 text-center text-[16px] font-semibold" />
          <button type="button" class="btn btn-secondary btn-icon" aria-label="More" @click="qty += 1"><FeatherIcon name="plus" class="h-4 w-4" /></button>
          <span class="text-sm text-gray-500">{{ item.stock_uom }}</span>
        </div>
      </div>
    </form>
    <p v-if="error" role="alert" class="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <template #footer>
      <button type="button" class="btn btn-secondary" @click="emit('update:modelValue', false)">Cancel</button>
      <button v-if="item" form="part-form" class="btn btn-primary" :disabled="busy || !warehouse || !(qty > 0)"><FeatherIcon name="plus" class="h-4 w-4" />{{ busy ? 'Adding…' : 'Add part' }}</button>
    </template>
  </Modal>
</template>
<script setup>
import { ref, watch, nextTick } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import Modal from './Modal.vue'
import { api } from '@/data/ops'

const props = defineProps({ modelValue: Boolean, workOrder: String, defaultWarehouse: String })
const emit = defineEmits(['update:modelValue', 'added'])
const query = ref('')
const results = ref([])
const item = ref(null)
const warehouses = ref([])
const warehouse = ref('')
const qty = ref(1)
const busy = ref(false)
const error = ref('')
const searchBox = ref(null)
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    item.value = null
    query.value = ''
    qty.value = 1
    error.value = ''
    search()
    nextTick(() => searchBox.value?.focus())
  },
)

let timer = null
function search() {
  clearTimeout(timer)
  busy.value = true
  timer = setTimeout(async () => {
    try {
      results.value = await api('projectit.parts.search_parts', { txt: query.value, warehouse: props.defaultWarehouse })
    } catch (e) {
      error.value = e.message
    } finally {
      busy.value = false
    }
  }, 200)
}

async function pick(r) {
  item.value = r
  error.value = ''
  try {
    const w = await api('projectit.parts.part_warehouses', { item_code: r.name })
    warehouses.value = w.warehouses
    const stocked = w.warehouses.find((x) => x.warehouse === w.default && x.actual_qty > 0) || w.warehouses.find((x) => x.actual_qty > 0)
    warehouse.value = stocked?.warehouse || ''
  } catch (e) {
    error.value = e.message
  }
}

async function add() {
  busy.value = true
  error.value = ''
  try {
    const result = await api('projectit.parts.add_part', { work_order: props.workOrder, item_code: item.value.name, qty: qty.value, warehouse: warehouse.value })
    emit('added', result)
    emit('update:modelValue', false)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>
