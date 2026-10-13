<template>
  <div class="space-y-1.5 text-sm">
    <p v-if="terms.payment_warning" class="flex items-start gap-1.5 rounded-md bg-red-50 px-2 py-1.5 text-xs font-medium text-red-700"><FeatherIcon name="alert-circle" class="mt-px h-3.5 w-3.5 shrink-0" />Subscription {{ terms.subscription_status.toLowerCase() }}. Check payment before extra work.</p>
    <p v-if="terms.state !== 'Active'" class="text-xs font-semibold text-red-600">Contract {{ terms.state.toLowerCase() }}<template v-if="terms.state === 'Expired'"> on {{ formatDate(terms.end_date) }}</template></p>
    <p v-else-if="!compact" class="text-gray-700">{{ terms.title || terms.name }} · until {{ formatDate(terms.end_date) }} · {{ terms.visit_frequency }} visits</p>
    <ul class="space-y-1">
      <li v-for="line in lines" :key="line.text" class="flex items-start gap-1.5" :class="line.ok ? 'text-gray-700' : 'text-gray-500'">
        <FeatherIcon :name="line.ok ? 'check' : 'x'" class="mt-0.5 h-3.5 w-3.5 shrink-0" :class="line.ok ? 'text-green-600' : 'text-gray-400'" />
        <span>{{ line.text }}</span>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { formatDate } from '@/data/ops'

const props = defineProps({ terms: { type: Object, required: true }, compact: Boolean })
const lines = computed(() => [
  { ok: !!props.terms.labour_included, text: props.terms.labour_included ? 'Labour included on service visits' : 'Labour chargeable' },
  { ok: !!props.terms.callouts_included, text: props.terms.callouts_included ? 'Breakdown call-outs included' : 'Breakdown call-outs chargeable' },
  props.terms.items?.length
    ? { ok: true, text: `Parts included: ${props.terms.items.map((i) => i.item_name || i.item_code).join(', ')}` }
    : { ok: false, text: 'All parts chargeable' },
])
</script>
