<template>
  <div class="segmented shrink-0" role="group" aria-label="Layout">
    <button v-for="v in VIEWS" :key="v.value" :aria-pressed="modelValue === v.value" :title="v.label" @click="emit('update:modelValue', v.value)"><FeatherIcon :name="v.icon" class="h-4 w-4" /><span class="hidden sm:inline">{{ v.label }}</span><span class="sr-only sm:hidden">{{ v.label }}</span></button>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'

defineProps({ modelValue: { type: String, default: 'cards' } })
const emit = defineEmits(['update:modelValue'])
const VIEWS = [{ value: 'cards', label: 'Cards', icon: 'grid' }, { value: 'list', label: 'List', icon: 'list' }]
</script>
