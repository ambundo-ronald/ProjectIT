<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">Parts used</h2>
      <button v-if="parts.can_edit" class="btn btn-secondary btn-sm" :disabled="busy" @click="picking = true"><FeatherIcon name="plus" class="h-4 w-4" />Add part</button>
    </div>
    <ul v-if="parts.rows.length" class="divide-y divide-gray-100">
      <li v-for="r in parts.rows" :key="r.name" class="flex items-start gap-3 px-5 py-3">
        <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500"><FeatherIcon name="package" class="h-4 w-4" /></span>
        <div class="min-w-0 flex-1">
          <div class="flex items-start justify-between gap-3">
            <p class="min-w-0 text-[15px] font-medium leading-snug">{{ fmt(r.qty) }} × {{ r.item_name || r.item_code }}</p>
            <span v-if="r.billing === 'Chargeable'" class="shrink-0 text-sm font-semibold tabular-nums">{{ money(r.amount) }}</span>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
            <select v-if="parts.manager" :value="r.billing" class="input h-7 w-auto py-0 pl-2 pr-7 text-xs font-semibold" :class="BILLING[r.billing].tone" :aria-label="`Billing for ${r.item_name}`" :disabled="busy" @change="setBilling(r, $event.target.value)">
              <option v-for="(b, key) in BILLING" :key="key" :value="key">{{ b.label }}</option>
            </select>
            <span v-else class="rounded-md px-1.5 py-0.5 font-semibold" :class="BILLING[r.billing].tone">{{ BILLING[r.billing].label }}</span>
            <span class="truncate">{{ r.warehouse }}</span>
            <span v-if="r.status === 'Issued'" class="inline-flex items-center gap-1 text-green-700"><FeatherIcon name="check" class="h-3 w-3" />Taken from stock</span>
          </div>
        </div>
        <button v-if="parts.can_edit && r.status === 'Recorded'" class="btn btn-ghost btn-icon btn-sm -mr-2 shrink-0 text-gray-400 hover:text-red-600" :aria-label="`Remove ${r.item_name}`" :disabled="busy" @click="remove(r)"><FeatherIcon name="x" class="h-4 w-4" /></button>
      </li>
    </ul>
    <p v-else class="px-5 py-4 text-sm text-gray-500">{{ parts.can_edit ? 'Record each part you fit. Stock is taken out when the job is completed.' : 'No parts used.' }}</p>
    <div v-if="parts.rows.length" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 bg-gray-50/70 px-5 py-3 text-sm">
      <span class="text-gray-600">
        <template v-if="parts.chargeable_total">Chargeable to customer</template>
        <template v-else>Nothing to charge for parts</template>
        <span v-if="parts.manager" class="text-xs text-gray-400"> · cost {{ money(parts.cost_total) }}</span>
      </span>
      <span v-if="parts.chargeable_total" class="text-[15px] font-semibold tabular-nums">{{ money(parts.chargeable_total) }}</span>
    </div>
    <div v-if="pending && closed && parts.manager" class="flex flex-wrap items-center justify-between gap-2 border-t border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-800">
      <span>{{ pending }} part line{{ pending === 1 ? ' has' : 's have' }} not left stock yet.</span>
      <button class="btn btn-secondary btn-sm" :disabled="busy" @click="retry">Take out of stock</button>
    </div>
    <PartPicker v-model="picking" :work-order="workOrder" :default-warehouse="parts.default_warehouse" @added="(r) => emit('updated', r)" />
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import PartPicker from './PartPicker.vue'
import { api } from '@/data/ops'

const props = defineProps({ parts: { type: Object, required: true }, workOrder: String, closed: Boolean })
const emit = defineEmits(['updated', 'error'])
const picking = ref(false)
const busy = ref(false)
const pending = computed(() => props.parts.rows.filter((r) => r.status === 'Recorded').length)

const BILLING = {
  Chargeable: { label: 'Chargeable', tone: 'bg-amber-50 text-amber-800' },
  Contract: { label: 'Contract', tone: 'bg-brand-50 text-brand-700' },
  Warranty: { label: 'Warranty', tone: 'bg-green-50 text-green-700' },
  Internal: { label: 'Internal', tone: 'bg-gray-100 text-gray-600' },
  'No charge': { label: 'No charge', tone: 'bg-gray-100 text-gray-600' },
}
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
const money = (n) => {
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency: props.parts.currency || 'KES', maximumFractionDigits: 0 })
  } catch (e) {
    return `${props.parts.currency || ''} ${fmt(n)}`
  }
}

async function call(method, args) {
  busy.value = true
  try {
    emit('updated', await api(method, { work_order: props.workOrder, ...args }))
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
const remove = (r) => call('projectit.parts.remove_part', { name: r.name })
const setBilling = (r, billing) => call('projectit.parts.set_billing', { name: r.name, billing })
const retry = () => call('projectit.parts.retry_issue', {})
</script>
