<template>
  <span class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium" :class="style.pill">
    <span class="h-1.5 w-1.5 rounded-full" :class="style.dot" aria-hidden="true" />{{ label }}
  </span>
</template>
<script setup>
import { computed } from 'vue'
import { STATUS_LABEL } from '@/data/ops'
const props = defineProps({ status: String, request: Boolean })
const STYLES = {
  Open: ['bg-blue-50 text-blue-700', 'bg-blue-500'],
  Overdue: ['bg-red-50 text-red-700', 'bg-red-500'],
  Working: ['bg-amber-50 text-amber-800', 'bg-amber-500'],
  'Pending Review': ['bg-violet-50 text-violet-700', 'bg-violet-500'],
  Completed: ['bg-green-50 text-green-700', 'bg-green-500'],
  Cancelled: ['bg-gray-100 text-gray-600', 'bg-gray-400'],
  Pending: ['bg-amber-50 text-amber-800', 'bg-amber-500'],
  Approved: ['bg-blue-50 text-blue-700', 'bg-blue-500'],
  Declined: ['bg-gray-100 text-gray-600', 'bg-gray-400'],
  Done: ['bg-green-50 text-green-700', 'bg-green-500'],
}
const label = computed(() => (props.request ? props.status : STATUS_LABEL[props.status] || props.status))
const style = computed(() => {
  const [pill, dot] = STYLES[props.status] || ['bg-gray-100 text-gray-700', 'bg-gray-400']
  return { pill, dot }
})
</script>
