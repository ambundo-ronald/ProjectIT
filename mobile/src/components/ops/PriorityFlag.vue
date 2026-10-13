<template>
  <span class="inline-flex items-center gap-1 text-xs font-medium" :class="style">
    <FeatherIcon :name="priority === 'Low' ? 'chevrons-down' : 'flag'" class="h-3.5 w-3.5" />{{ priority }}
  </span>
</template>
<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
const props = defineProps({ priority: String })
const style = computed(() => ({ Low: 'text-gray-500', Medium: 'text-brand-600', High: 'text-orange-600', Urgent: 'text-red-600' })[props.priority] || 'text-gray-500')
</script>
