<template>
  <div class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 bg-panel px-6 py-10 text-center">
    <span class="flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-brand-600">
      <FeatherIcon :name="icon" class="h-5 w-5" />
    </span>
    <p class="mt-3 font-semibold text-gray-900">{{ title }}</p>
    <p v-if="text" class="mt-1 max-w-sm text-sm text-gray-500">{{ text }}</p>
    <div v-if="$slots.default" class="mt-4"><slot /></div>
  </div>
</template>
<script setup>
import { FeatherIcon } from 'frappe-ui'
defineProps({ icon: { type: String, default: 'inbox' }, title: String, text: String })
</script>
