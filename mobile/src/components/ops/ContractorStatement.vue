<template>
  <!-- A contractor's pay: what is waiting, approved, billed and paid, and every line (owners and managers). -->
  <div class="space-y-4">
    <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
      <div v-for="t in tiles" :key="t.key" class="card p-3.5">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-gray-500">{{ t.label }}</p>
        <p class="mt-1 text-[19px] font-semibold tabular-nums text-gray-900">{{ money(t.value, data.currency) }}</p>
        <p class="mt-0.5 text-xs text-gray-500">{{ t.hint }}</p>
      </div>
    </div>

    <div class="card overflow-hidden">
      <div class="card-header"><h2 class="card-title">Lines</h2><span class="text-xs text-gray-500">{{ data.lines.length }}</span></div>
      <ul v-if="data.lines.length" class="divide-y divide-gray-100">
        <li v-for="l in data.lines" :key="l.name" class="px-4 py-3">
          <div class="flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-gray-900">{{ l.description }}</p>
              <p class="mt-0.5 truncate text-xs text-gray-500">
                {{ PAY_TYPE_LABEL[l.pay_type] }}<template v-if="l.subject || l.project_name"> · {{ l.subject || l.project_name }}</template>
                <template v-if="['Hourly', 'Per unit'].includes(l.pay_type) && l.qty"> · {{ Number(l.qty) }} {{ l.unit }} × {{ money(l.rate, data.currency) }}</template>
              </p>
              <p v-if="l.queried" class="mt-1.5 whitespace-pre-wrap rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900">{{ l.query_note }}</p>
              <p v-else-if="l.query_note" class="mt-1.5 whitespace-pre-wrap rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-600">{{ l.query_note }}</p>
            </div>
            <div class="shrink-0 text-right">
              <p class="text-sm font-semibold tabular-nums" :class="l.pay_type === 'Deduction' ? 'text-red-700' : 'text-gray-900'">{{ l.pay_type === 'Deduction' ? '−' : '' }}{{ l.shown === 'Draft' && ['Hourly', 'Per unit'].includes(l.pay_type) && !Number(l.amount) ? 'On approval' : money(l.amount, data.currency) }}</p>
              <span class="mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium" :class="LINE_STYLE[l.shown]">{{ LINE_LABEL[l.shown] }}</span>
            </div>
          </div>
          <div v-if="canQuery || $slots.actions" class="mt-2 flex flex-wrap justify-end gap-1.5">
            <slot name="actions" :line="l" />
            <button v-if="canQuery && !l.queried && l.shown !== 'Paid'" class="btn btn-ghost btn-sm text-gray-600" @click="$emit('query', l)"><FeatherIcon name="help-circle" class="h-4 w-4" />Query</button>
          </div>
        </li>
      </ul>
      <p v-else class="px-4 py-5 text-sm text-gray-500">Nothing yet. Agreed pay shows here once a job is given to you.</p>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { money, PAY_TYPE_LABEL, LINE_STYLE, LINE_LABEL } from '@/data/contractor'

const props = defineProps({ data: Object, canQuery: Boolean })
defineEmits(['query'])
const tiles = computed(() => [
  { key: 'Draft', label: 'Waiting', value: props.data.totals.Draft, hint: 'Work not yet approved' },
  { key: 'Approved', label: 'To be paid', value: props.data.totals.Approved + props.data.totals['On hold'], hint: props.data.totals['On hold'] ? `${money(props.data.totals['On hold'], props.data.currency)} on hold` : 'In the next payout' },
  { key: 'Billed', label: 'Being paid', value: props.data.totals.Billed, hint: 'Billed, payment on the way' },
  { key: 'Paid', label: 'Paid', value: props.data.paid_in_period, hint: 'In the period' },
])
</script>
