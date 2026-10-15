<template>
  <span v-if="meta" class="inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-xs font-semibold ring-1 ring-inset" :class="meta.tone" :title="title">
    <FeatherIcon :name="meta.icon" class="h-3.5 w-3.5" />{{ short ? meta.short : meta.label }}<template v-if="until && !short"> · until {{ formatDate(until) }}</template>
  </span>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import { COVERAGE } from '@/data/equipment'
import { formatDate } from '@/data/ops'

const props = defineProps({ kind: String, until: String, short: Boolean })
const meta = computed(() => COVERAGE[props.kind])
const title = computed(() => (props.kind === 'Chargeable' ? 'Not under warranty or contract: bill the customer' : props.until ? `${meta.value?.label} until ${formatDate(props.until)}` : meta.value?.label))
</script>
