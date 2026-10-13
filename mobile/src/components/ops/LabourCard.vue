<template>
  <div class="card overflow-hidden">
    <div class="card-header">
      <h2 class="card-title">Labour &amp; invoice</h2>
      <select v-if="b.can_edit" :value="b.billing" class="input h-8 w-auto py-0 pl-2 pr-7 text-xs font-semibold" :class="TONE[b.billing]" aria-label="Labour billing" :disabled="busy" @change="save({ billing: $event.target.value })">
        <option v-for="o in ['Chargeable', 'Included', 'No charge']" :key="o" :value="o">{{ o === 'Included' ? 'Included (cover)' : o }}</option>
      </select>
      <span v-else class="rounded-md px-2 py-0.5 text-xs font-semibold" :class="TONE[b.billing]">{{ b.billing === 'Included' ? 'Included in cover' : b.billing }}</span>
    </div>
    <div class="space-y-4 p-5">
      <div v-if="b.can_edit" class="segmented" role="group" aria-label="Labour charged">
        <button v-for="m in ['Hourly', 'Flat fee']" :key="m" :aria-pressed="b.mode === m" :disabled="busy" @click="save({ mode: m })">{{ m }}</button>
      </div>
      <div v-if="b.mode === 'Hourly'" class="flex flex-wrap items-end gap-3">
        <div>
          <label class="label" for="lab-hours">Hours worked</label>
          <input id="lab-hours" type="number" min="0" step="0.25" inputmode="decimal" class="input w-28 text-[15px] font-semibold" :value="b.hours || ''" placeholder="0" :disabled="!b.can_edit_hours || busy" @change="save({ hours: $event.target.value || 0 })" />
        </div>
        <span class="pb-2.5 text-gray-400">×</span>
        <div>
          <label class="label" for="lab-rate">Rate per hour</label>
          <input v-if="b.can_edit" id="lab-rate" type="number" min="0" step="any" class="input w-32" :value="b.rate" :disabled="busy" @change="save({ rate: $event.target.value || 0 })" />
          <p v-else class="h-10 py-2.5 text-[15px] tabular-nums">{{ money(b.rate) }}</p>
        </div>
      </div>
      <div v-else>
        <label class="label" for="lab-fee">Flat fee</label>
        <input v-if="b.can_edit" id="lab-fee" type="number" min="0" step="any" class="input w-40" :value="b.flat_fee" :disabled="busy" @change="save({ flat_fee: $event.target.value || 0 })" />
        <p v-else class="text-[15px] tabular-nums">{{ money(b.flat_fee) }}</p>
      </div>
      <p v-if="b.billing === 'Chargeable' && b.mode === 'Hourly' && !b.hours" class="text-xs font-medium text-amber-700">Record the hours worked so the labour can be invoiced.</p>
      <p v-if="b.billing !== b.default_billing && b.can_edit" class="text-xs text-gray-500">Changed from the default ({{ b.default_billing }}) for this machine's cover.</p>

      <dl class="space-y-1.5 border-t border-gray-100 pt-3 text-sm">
        <div class="flex justify-between"><dt class="text-gray-600">Labour</dt><dd class="tabular-nums">{{ money(b.amount) }}</dd></div>
        <div class="flex justify-between"><dt class="text-gray-600">Approved parts</dt><dd class="tabular-nums">{{ money(b.parts_total) }}</dd></div>
        <div class="flex justify-between text-[15px] font-semibold"><dt>To charge</dt><dd class="tabular-nums">{{ money(b.total) }}</dd></div>
      </dl>

      <div v-if="b.invoice" class="flex items-center justify-between gap-3 rounded-lg bg-green-50 px-3 py-2.5 text-sm text-green-800">
        <span class="inline-flex items-center gap-2"><FeatherIcon name="file-text" class="h-4 w-4" />Invoice <a :href="`/desk/sales-invoice/${b.invoice.name}`" target="_blank" rel="noopener" class="font-semibold underline">{{ b.invoice.name }}</a></span>
        <span class="text-xs">{{ b.invoice.docstatus === 0 ? 'Draft' : b.invoice.status }} · {{ money(b.invoice.grand_total) }}</span>
      </div>
      <div v-else-if="b.can_invoice" class="flex flex-wrap items-center justify-between gap-2">
        <router-link :to="{ name: 'OpsBilling' }" class="text-xs font-medium text-brand-600 hover:underline">Invoice with other jobs for this customer</router-link>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="invoice"><FeatherIcon name="file-plus" class="h-4 w-4" />Create invoice</button>
      </div>
      <p v-else-if="b.total > 0 && !b.closed" class="text-xs text-gray-500">The invoice can be made once the job is completed.</p>
    </div>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { FeatherIcon, toast } from 'frappe-ui'
import { api } from '@/data/ops'

const props = defineProps({ billing: { type: Object, required: true }, workOrder: String })
const emit = defineEmits(['updated', 'error'])
const b = computed(() => props.billing)
const busy = ref(false)
const TONE = { Chargeable: 'bg-amber-50 text-amber-800', Included: 'bg-green-50 text-green-700', 'No charge': 'bg-gray-100 text-gray-600' }
const money = (n) => {
  try {
    return Number(n || 0).toLocaleString(undefined, { style: 'currency', currency: b.value.currency || 'KES', maximumFractionDigits: 0 })
  } catch (e) {
    return `${b.value.currency || ''} ${Number(n || 0).toLocaleString()}`
  }
}

async function save(values) {
  busy.value = true
  try {
    emit('updated', await api('projectit.billing.set_labour', { work_order: props.workOrder, ...values }))
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
async function invoice() {
  busy.value = true
  try {
    const r = await api('projectit.billing.create_invoice', { jobs: [props.workOrder] })
    toast({ title: `Draft invoice ${r.invoice} created`, icon: 'check-circle', iconClasses: 'text-green-600', position: 'top-center' })
    emit('updated', await api('projectit.work_orders.get_work_order', { name: props.workOrder }))
  } catch (e) {
    emit('error', e.message)
  } finally {
    busy.value = false
  }
}
</script>
